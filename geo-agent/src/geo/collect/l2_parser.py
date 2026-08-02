from __future__ import annotations
import re
from geo.shared.models import L2Record, CitedSource, PromptRow

_URL = re.compile(r"https?://[^\s\"'<>)\]]+")

# Sentiment keywords for deterministic sentiment analysis
_NEGATIVE_KEYWORDS = [
    "scam", "fraud", "fraudulent", "fly-by-night", "white-label", "white label",
    "dropshipping", "dropship", "caution", "cautious", "avoid", "risky", "risk",
    "problematic", "concern", "dubious", "suspect", "suspicious",
    "recommend against", "not recommend", "beware", "warning", "questionable",
    "unverified", "unproven", "no track record", "lack of reputation",
    "unknown entity", "better alternative", "consider instead", "steer clear",
    # Chinese negative keywords
    "谨慎", " cautious", "避免", "劣质", "风险", "隐患", "怀疑", "可疑", "不推荐",
    "问题", "担忧", " dubious", "警惕", "不靠谱", "差评", "虚假", "欺骗"
]

_POSITIVE_KEYWORDS = [
    "recommend", "recommended", "reliable", "trusted", "trustworthy",
    "excellent", "best", "top", "quality", "reputable", "proven",
    "dependable", "leader",
    # Chinese positive keywords
    "推荐", "可靠", "信任", "优秀", "最佳", "顶级", "质量", "声誉", " proven",
    "领先", "值得信赖"
]

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

def _compute_sentiment(answer: str) -> str:
    """Compute sentiment deterministically using keyword-based approach."""
    if not answer:
        return "neu"

    answer_lower = answer.lower()

    # Check for negative keywords (negative dominates)
    for keyword in _NEGATIVE_KEYWORDS:
        if keyword in answer_lower:
            # For ASCII keywords, use word boundary matching
            # For non-ASCII keywords (Chinese, etc), just check substring presence
            if keyword.isascii():
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, answer_lower):
                    return "neg"
            else:
                # Chinese characters don't have word boundaries, just check presence
                if keyword in answer_lower:
                    return "neg"

    # Check for positive keywords (only if no negative match)
    for keyword in _POSITIVE_KEYWORDS:
        if keyword in answer_lower:
            if keyword.isascii():
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, answer_lower):
                    return "pos"
            else:
                # Chinese characters don't have word boundaries
                if keyword in answer_lower:
                    return "pos"

    # Default to neutral
    return "neu"

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

    # Extract brand key from brand_terms (e.g., from "sunhestia.com" -> "sunhestia")
    brand_keys = []
    for term in brand_terms:
        # Remove TLD if present and extract base brand name
        base = term.lower()
        if "." in base:
            # Extract domain without TLD
            base = base.split(".")[0]
        brand_keys.append(base)

    # Use brand_keys for URL checking
    cited_with_link = any(any(b in s.url.lower() for b in brand_keys) for s in cited)
    position = next((s.position for s in structured if any(b in s.url.lower() for b in brand_keys)), None)

    comp = sorted({c for c in competitor_set if c.lower() in blob.lower()})

    # Only compute sentiment if brand is mentioned in the answer (spec: "未提及时空")
    sentiment = _compute_sentiment(answer) if mentioned else "neu"

    return L2Record(cited_sources=cited, mentioned=mentioned, cited_with_link=cited_with_link,
                    citation_position=position, sentiment=sentiment, competitors_mentioned=comp,
                    low_confidence=bool(inferred) and low)
