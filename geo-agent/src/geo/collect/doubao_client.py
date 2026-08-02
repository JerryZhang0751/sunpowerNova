"""Doubao collection client for Ark Responses API with web_search tool."""

from __future__ import annotations

import re
import time
import httpx
from geo.shared.config import settings

_URL = re.compile(r"https?://[^\s\"'<>)\]]+")


def parse_doubao_response(raw: dict) -> dict:
    """Parse Doubao response into standard format.

    CRITICAL: Citations live in output[type=message].content[].annotations[]
    (type="url_citation"), NOT in web_search_call.

    Args:
        raw: Raw Doubao response with output[]

    Returns:
        dict with answer, search_results
    """
    answer = ""
    for o in raw.get("output", []):
        if not isinstance(o, dict):
            continue
        if o.get("type") == "message":
            for c in (o.get("content") or []):
                if isinstance(c, dict):
                    answer += c.get("text") or c.get("output_text") or ""

    # Doubao citations in output[type=message].content[].annotations[]
    # ({type:url_citation,title,url}), NOT in web_search_call
    seen, srcs = set(), []
    for o in raw.get("output", []):
        if isinstance(o, dict) and o.get("type") == "message":
            for c in (o.get("content") or []):
                for a in ((c.get("annotations") if isinstance(c, dict) else None) or []):
                    u = (a or {}).get("url")
                    if u and u not in seen:
                        seen.add(u)
                        srcs.append({"url": u, "title": (a or {}).get("title", "")})

    # Fallback: if annotations missing, recursively harvest URLs
    if not srcs:
        srcs = [{"url": u, "title": ""} for u in _harvest(raw.get("output", []))]

    return {"answer": answer, "search_results": srcs}


def _harvest(obj, found=None) -> list[str]:
    """Recursively harvest URLs from nested structure."""
    found = [] if found is None else found
    if isinstance(obj, str):
        for m in _URL.findall(obj):
            u = m.split("?")[0].rstrip(".,)")
            if u not in found:
                found.append(u)
    elif isinstance(obj, dict):
        for v in obj.values():
            _harvest(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _harvest(v, found)
    return found


def collect_doubao(prompt: str, model: str = "doubao-seed-2-1-pro-260628") -> dict:
    """Collect Doubao response using Ark Responses API.

    Parameters taken verbatim from m0_smoke.probe_ark_responses
    (tested working, timeout=300).

    Args:
        prompt: User prompt
        model: Doubao model name (default: doubao-seed-2-1-pro-260628)

    Returns:
        dict with answer, raw, search_results, elapsed_s
    """
    url = settings.ark_base_url + "/responses"
    body = {
        "model": model,
        "input": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search"}],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.ark_api_key}",
        "Content-Type": "application/json",
    }

    t0 = time.time()
    with httpx.Client(timeout=300.0, proxy=settings.proxy) as c:
        r = c.post(url, headers=headers, json=body)
        r.raise_for_status()
        raw = r.json()

    out = parse_doubao_response(raw)
    return {
        "answer": out["answer"],
        "raw": raw,
        "search_results": out["search_results"],
        "elapsed_s": round(time.time() - t0, 1),
    }
