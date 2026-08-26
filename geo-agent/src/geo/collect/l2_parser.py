from __future__ import annotations
import re
from urllib.parse import urlparse
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

def _retrieved_sources(client_out: dict) -> list[CitedSource]:
    """search_results = 模型检索过的列表(≠引用),原样保留在 retrieved_sources。"""
    srcs = []
    for i, s in enumerate(client_out.get("search_results", []) or []):
        url = s.get("url") if isinstance(s, dict) else None
        if not url: continue
        srcs.append(CitedSource(position=i+1, url=url, title=(s.get("title") or ""),
                                snippet=(s.get("snippet") or ""), extract_method="retrieved"))
    return srcs

def _answer_urls(answer: str) -> list[str]:
    """答案文本中的 URL,按首次出现顺序去重(仅去尾部标点)。

    query 是 URL 身份的一部分,不得剥离——?id=one 与 ?id=two 是两个来源,
    合并会丢失引用身份;且带 query 的文本 URL 对不上检索列表里的完整键,
    会被误判 inferred(2026-08-25 二次审查)。
    """
    seen, out = set(), []
    for m in _URL.findall(answer):
        u = m.rstrip(".,);]\"'!?#")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out

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

def _brand_hosts(brand_terms: list[str]) -> set[str]:
    """品牌裸域集合: ["SunHestia","sunhestia.com"] → {"sunhestia.com"}。
    只有带点号的词条能构成 host 匹配基准;路径/参数含品牌词不算(二次审查#1)。"""
    return {t.lower().strip("./") for t in brand_terms if "." in t}

def _is_brand_url(url: str, brand_hosts: set[str]) -> bool:
    """URL 主机等于品牌域或其子域才算品牌引用。

    旧实现对整条 URL 做品牌词子串匹配: evil.example/sunhestia-review 会被
    误判为品牌引用(cited_with_link=True + position=1)——第三方页面上提及
    品牌不等于品牌被引用(2026-08-25 二次审查#1)。
    """
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return bool(host) and any(host == h or host.endswith("." + h) for h in brand_hosts)

def parse_l2(provider: str, client_out: dict, row: PromptRow,
             brand_terms: list[str], competitor_set: list[str]) -> L2Record:
    """L2 解析:cited 只认答案内证据。

    证据分层(2026-08-24 审查#1 修复:检索结果≠最终引用):
    - structured / inferred: URL 真出现在最终答案文本里(前者可在检索列表找到
      元数据,后者找不到)——这是"模型引用了"的确定性证据;
    - attested: provider 明证的引用(doubao message 内容上的 url_citation
      annotations),即使答案文本不重复 URL 也采信;
    - retrieved: 仅出现在 search_results(模型"检索过"),存 retrieved_sources,
      不进 cited、不计提及/引用率/引用位置/竞品。
    mentioned/competitors 只看答案文本;citation_position = 答案内引用顺序,
    不是搜索结果排名。品牌引用只认 URL 主机=品牌域或其子域(_is_brand_url);
    答案 URL 保留 query(query 是 URL 身份的一部分)。
    """
    answer = client_out.get("answer", "") or ""
    retrieved = _retrieved_sources(client_out)
    # 检索索引只按完整 URL 精确匹配: query 是 URL 身份的一部分,答案写
    # ?id=two 时不得借 ?id=one 的 stripped 键冒充 structured(二次审查#8)。
    retrieved_by_url = {s.url: s for s in retrieved}

    cited: list[CitedSource] = []
    inferred_any = False
    for u in _answer_urls(answer):
        meta = retrieved_by_url.get(u)
        if meta:
            cited.append(CitedSource(position=len(cited)+1, url=u, title=meta.title,
                                     snippet=meta.snippet, extract_method="structured"))
        else:
            cited.append(CitedSource(position=len(cited)+1, url=u, title="", snippet="",
                                     extract_method="inferred"))
            inferred_any = True

    cited_urls = {s.url for s in cited}
    for c in client_out.get("citations", []) or []:
        u = c.get("url") if isinstance(c, dict) else None
        if not u or u in cited_urls: continue
        cited.append(CitedSource(position=len(cited)+1, url=u, title=(c.get("title") or ""),
                                 snippet=(c.get("snippet") or ""), extract_method="attested"))
        cited_urls.add(u)

    low = "SunHestia" in row.prompt.upper() or row.category == "brand"
    mentioned = any(t.lower() in answer.lower() for t in brand_terms)

    brand_hosts = _brand_hosts(brand_terms)
    # 裸域名提及边界: "sunhestia.com" 成立,但 "evil.sunhestia.com"(他人子域)
    # 与 "sunhestia.com.evil.io"(伪装域)不算——前后不得再接域名字符
    domain_pats = [re.compile(rf"(?<![\w.-]){re.escape(h)}(?![\w-]|\.[a-z0-9])")
                   for h in sorted(brand_hosts)]
    # 答案内 URL 引用指向品牌域(host 匹配),或答案文本写出了品牌裸域名
    # (如 "SunHestia (sunhestia.com)")
    cited_with_link = (any(_is_brand_url(s.url, brand_hosts) for s in cited)
                       or any(p.search(answer.lower()) for p in domain_pats))
    position = next((s.position for s in cited if _is_brand_url(s.url, brand_hosts)), None)

    comp = sorted({c for c in competitor_set if c.lower() in answer.lower()})

    # Only compute sentiment if brand is mentioned in the answer (spec: "未提及时空")
    sentiment = _compute_sentiment(answer) if mentioned else "neu"

    return L2Record(cited_sources=cited, retrieved_sources=retrieved, mentioned=mentioned,
                    cited_with_link=cited_with_link, citation_position=position,
                    sentiment=sentiment, competitors_mentioned=comp,
                    low_confidence=inferred_any and low)
