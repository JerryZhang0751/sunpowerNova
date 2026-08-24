"""Qwen collection client for DashScope MultiModalConversation with native search."""

from __future__ import annotations

import logging
import time
from typing import Any

import dashscope
from dashscope import MultiModalConversation

from geo.shared.config import settings

log = logging.getLogger("qwen")

# DashScope request_timeout: for STREAMING calls this is the idle timeout between
# chunks (sock_read), per sdk api_entities/http_request.py. The SDK default is 300s,
# but we pass it explicitly like doubao/zhipu do (visible, configurable defense).
REQUEST_TIMEOUT_S = 300.0
# Idle timeout alone cannot bound a slow-drip stream (one chunk every <300s runs
# forever) — this hard wall-clock cap bounds one collect_qwen call end to end.
TOTAL_BUDGET_S = 600.0


def _mm_text(content) -> str:
    """Extract text from multimodal content (strings/dicts/lists)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for it in content:
            if isinstance(it, str):
                parts.append(it)
            elif isinstance(it, dict) and isinstance(it.get("text"), str):
                parts.append(it["text"])
            elif isinstance(it, list):
                parts.append(_mm_text(it))
        return "".join(parts)
    return ""


def parse_qwen_response(resp: dict[str, Any]) -> dict[str, Any]:
    """Parse Qwen response into standard format.

    Args:
        resp: Raw Qwen response with search_info, answer, usage

    Returns:
        dict with answer, search_results, usage
    """
    srs = ((resp.get("search_info") or {}).get("search_results") or [])
    return {
        "answer": resp.get("answer", ""),
        "search_results": srs,
        "usage": resp.get("usage", {}),
    }


def collect_qwen(prompt: str, model: str = "qwen3.7-plus") -> dict[str, Any]:
    """Collect Qwen response with native search aggregation.

    CRITICAL: Search results arrive across MULTIPLE stream chunks.
    We MUST aggregate and deduplicate by URL to avoid losing citations.
    The prior bug took only the first non-empty search_info, which lost results.

    Args:
        prompt: User prompt
        model: Qwen model name (default: qwen3.7-plus)

    Returns:
        dict with answer, search_results, usage, elapsed_s
    """
    dashscope.base_http_api_url = settings.dashscope_base_url

    t0 = time.time()
    stream = MultiModalConversation.call(
        api_key=settings.dashscope_api_key,
        model=model,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        enable_search=True,
        search_options={"search_strategy": "agent", "enable_source": True},
        stream=True,
        incremental_output=True,
        request_timeout=REQUEST_TIMEOUT_S,
    )

    search_results, answer_parts, usage = [], [], {}
    timed_out = False

    # Track seen URLs for deduplication across stream chunks
    seen_urls = set()

    for r in stream:
        if time.time() - t0 >= TOTAL_BUDGET_S:
            log.warning("qwen total budget %.0fs exceeded — returning partial answer",
                        TOTAL_BUDGET_S)
            timed_out = True
            break
        out = getattr(r, "output", None)
        o = out if isinstance(out, dict) else {}

        # Aggregate search results across ALL chunks (critical bug fix)
        sr = (o.get("search_info") or {}).get("search_results") or []
        for s in sr:
            if isinstance(s, dict) and s.get("url"):
                url = s["url"]
                # Only add if we haven't seen this URL before
                if url not in seen_urls:
                    search_results.append(s)
                    seen_urls.add(url)

        # Extract answer text from this chunk
        ch = (o.get("choices") or [{}])[0]
        msg = ch.get("message", {}) if isinstance(ch, dict) else {}
        answer_parts.append(_mm_text(msg.get("content")))

        # Capture usage (should be in last chunks)
        u = getattr(r, "usage", None)
        if isinstance(u, dict) and u:
            usage = u

    answer = "".join(answer_parts)

    return {
        "answer": answer,
        "search_results": search_results,
        "usage": usage,
        "elapsed_s": round(time.time() - t0, 1),
        "timeout": timed_out,
    }
