from __future__ import annotations
import re
from geo.shared.models import L2Record, CitedSource, PromptRow

_URL = re.compile(r"https?://[^\s\"'<>)\]]+")

def _client_out_from_fixture(provider: str, raw_fixture: dict) -> dict:
    resp = raw_fixture["response"]
    if provider == "qwen":
        from geo.collect.qwen_client import parse_qwen_response
        return parse_qwen_response(resp)
    if provider == "doubao":
        from geo.collect.doubao_client import parse_doubao_response
        return parse_doubao_response(resp)
    from geo.collect.zhipu_client import parse_zhipu_response
    return parse_zhipu_response(resp)

def _structured_sources(provider: str, client_out: dict) -> list[CitedSource]:
    srcs = []
    for i, s in enumerate(client_out.get("search_results", [])):
        url = s.get("url") if isinstance(s, dict) else None
        if not url: continue
        srcs.append(CitedSource(position=i+1, url=url, title=(s.get("title") or ""),
                                snippet=(s.get("snippet") or ""), extract_method="structured"))
    return srcs

def _fallback_sources(answer: str, structured: list[CitedSource]) -> list[CitedSource]:
    have = {s.url for s in structured}
    extra = []
    for m in _URL.findall(answer):
        u = m.split("?")[0].rstrip(".,)")
        if u not in have: extra.append(CitedSource(position=None, url=u, extract_method="inferred"))
    return extra

def parse_l2(provider: str, client_out: dict, row: PromptRow,
             brand_terms: list[str], competitor_set: list[str]) -> L2Record:
    answer = client_out.get("answer", "") or ""
    structured = _structured_sources(provider, client_out)
    inferred = _fallback_sources(answer, structured)
    cited = structured + inferred
    blob = answer + " " + " ".join(s.url for s in cited)
    low = "SunHestia" in row.prompt.upper() or row.category == "brand"
    mentioned = any(t.lower() in blob.lower() for t in brand_terms)
    cited_with_link = any(any(b in s.url.lower() for b in ("sunhestia",)) for s in cited)
    position = next((s.position for s in structured if "sunhestia" in s.url.lower()), None)
    comp = sorted({c for c in competitor_set if c.lower() in blob.lower()})
    return L2Record(cited_sources=cited, mentioned=mentioned, cited_with_link=cited_with_link,
                    citation_position=position, sentiment=None, competitors_mentioned=comp,
                    low_confidence=bool(inferred) and low)
