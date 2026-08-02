"""Zhipu collection client for BigModel Anthropic-compatible endpoint."""

from __future__ import annotations

import re
import time
import httpx
from geo.shared.config import settings
from geo.collect.doubao_client import _harvest   # reuse URL extraction

_NOISE = re.compile(r"<(GUIDContent|autonomous-content|custom-tool)[^>]*>.*?</\1>", re.DOTALL)
_URL = re.compile(r"https?://[^\s\"'<>)\]]+")


def strip_noise(text: str) -> str:
    """Strip internal noise tags from answer text."""
    return _NOISE.sub("", text or "")


def parse_zhipu_response(raw: dict) -> dict:
    """Parse Zhipu response into standard format.

    CRITICAL: tool_result.content is a STRING (not list) - URLs must be extracted from it.
    Strips noise tags (<GUIDContent>, <autonomous-content>, etc.) from answer text.

    Args:
        raw: Raw Zhipu response with content[] array

    Returns:
        dict with answer, search_results
    """
    answer = ""
    for c in raw.get("content", []):
        if isinstance(c, dict) and c.get("type") == "text":
            answer += c.get("text", "") or ""

    # Extract URLs from tool_result blocks (content is a string representation)
    urls = _harvest(raw.get("content", []))

    return {
        "answer": strip_noise(answer),
        "search_results": [{"url": u, "title": ""} for u in urls]
    }


def collect_zhipu(prompt: str, model: str = "glm-5.2") -> dict:
    """Collect Zhipu response using BigModel Anthropic-compatible endpoint.

    Parameters taken verbatim from m0_smoke.probe_zhipu_anthropic.
    Model is glm-5.2 (NOT glm-5.2[1m] - that suffix is display-only and 400s).

    Args:
        prompt: User prompt
        model: Zhipu model name (default: glm-5.2)

    Returns:
        dict with answer, raw, search_results, elapsed_s
    """
    url = settings.bigmodel_base_url + "/v1/messages"
    body = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
    }
    headers = {
        "x-api-key": settings.bigmodel_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    t0 = time.time()
    with httpx.Client(timeout=300.0, proxy=settings.proxy) as c:
        r = c.post(url, headers=headers, json=body)
        r.raise_for_status()
        raw = r.json()

    out = parse_zhipu_response(raw)
    return {
        "answer": out["answer"],
        "raw": raw,
        "search_results": out["search_results"],
        "elapsed_s": round(time.time() - t0, 1),
    }
