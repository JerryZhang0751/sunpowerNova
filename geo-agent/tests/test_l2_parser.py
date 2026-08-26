import json
from pathlib import Path
from geo.shared.models import PromptRow
from geo.collect.l2_parser import parse_l2, _client_out_from_fixture

RAW = Path(__file__).parent/"fixtures/raw"; EXP = Path(__file__).parent/"fixtures/expected"
ROW = PromptRow(id="C01", category="category", prompt="x", market="EU", intent="c", core=True)
BRAND = ["SunHestia", "sunhestia.com"]
COMP = ["Tesla","Enphase","SolarEdge","Canadian Solar","BYD","sonnen","LG","Panasonic","Generac","Franklin","Bluetti"]

def _case(pid, provider):
    raw = json.loads((RAW/f"{provider}_{pid}.json").read_text(encoding="utf-8"))
    exp_path = EXP/f"{provider}_{pid}.json"
    if not exp_path.exists(): return None
    return provider, raw, json.loads(exp_path.read_text(encoding="utf-8"))

def test_l2_all_fixtures():
    for provider in ("qwen","doubao","zhipu"):
        for pid in ("C01","D01","B02"):
            c = _case(pid, provider)
            if c is None: continue
            provider, raw, exp = c
            l2 = parse_l2(provider, _client_out_from_fixture(provider, raw), ROW, BRAND, COMP)
            # 特殊情况: D01·Qwen 真无搜索, cited_sources 允许为空 (brief 验证"不崩、cited 空、derived 正确")
            if l2.cited_sources:
                assert all(s.extract_method in ("structured","inferred","attested") for s in l2.cited_sources)
            assert l2.mentioned == exp["mentioned"]
            assert l2.cited_with_link == exp["cited_with_link"]
            assert l2.sentiment == exp["sentiment"]
            # 竞品只认答案文本(URL/标题里的不算)——期望文件按新语义核算
            for c in exp.get("competitors_mentioned_contains", []):
                assert c in l2.competitors_mentioned
            # Fix(2026-08-24 审查#1): cited 必须有答案内证据——每条 cited url 都出现在
            # 最终答案文本里(doubao attested 除外,provider 明证)
            if l2.cited_sources:
                text = (raw["response"].get("answer","") or json.dumps(raw["response"]))
                hit = sum(1 for s in l2.cited_sources
                          if s.extract_method == "attested"
                          or s.url in text or any(s.url.startswith(u) for u in text.split()))
                assert (hit / max(1,len(l2.cited_sources))) >= 0.9 or exp.get("cited_urls_subset")


# ---- Fix(2026-08-24 审查#1): 检索≠引用 ----------------------------------
# 模型 search_results 只是"检索过";只有 URL 真出现在最终答案文本(或 provider
# 明证的 annotation)才算"引用了"。提及/竞品同理只看答案文本。

def test_retrieved_results_are_not_citations():
    """检索到品牌 URL(搜索排名第 1)但答案没引用 → cited_with_link=False。"""
    out = {"answer": "SunHestia is a residential solar company.",
           "search_results": [{"url": "https://sunhestia.com/", "title": "SunHestia"},
                              {"url": "https://www.tesla.com/solar", "title": "Tesla"}]}
    l2 = parse_l2("qwen", out, ROW, BRAND, COMP)
    assert len(l2.retrieved_sources) == 2                 # 检索列表保留,单独存放
    assert all(s.extract_method == "retrieved" for s in l2.retrieved_sources)
    assert l2.cited_sources == []                         # 检索≠引用
    assert l2.cited_with_link is False
    assert l2.citation_position is None                   # 搜索排名不得充当引用位置
    assert l2.mentioned is True                           # 品牌名在答案文本中

def test_urls_in_answer_are_citations_in_answer_order():
    """答案文本里的 URL 才是引用;position=答案内出现顺序,非搜索结果排名。"""
    out = {"answer": "See https://a.com/x first, then https://sunhestia.com/ and https://b.com.",
           "search_results": [{"url": "https://sunhestia.com/", "title": "SunHestia"},
                              {"url": "https://zzz.com", "title": ""}]}
    l2 = parse_l2("qwen", out, ROW, BRAND, COMP)
    assert [s.url for s in l2.cited_sources] == ["https://a.com/x", "https://sunhestia.com/", "https://b.com"]
    assert [s.extract_method for s in l2.cited_sources] == ["inferred", "structured", "inferred"]
    assert l2.cited_with_link is True
    assert l2.citation_position == 2                      # 答案内第 2 个引用,不是搜索第 1

def test_bare_brand_domain_in_answer_counts_as_link():
    """答案写裸域名 "SunHestia (sunhestia.com)" → 算引用(网址证据在答案文本内)。"""
    out = {"answer": "SunHestia (sunhestia.com) designs residential solar.", "search_results": []}
    l2 = parse_l2("qwen", out, ROW, BRAND, COMP)
    assert l2.cited_with_link is True
    assert l2.citation_position is None                   # 无具名 URL 引用列表 → 位置未知

def test_mention_and_competitors_from_answer_text_only():
    """检索结果 URL/标题里的品牌与竞品名不算提及;只认答案文本。"""
    out = {"answer": "Tesla makes cars. No brand opinion here.",
           "search_results": [{"url": "https://sunhestia.com/", "title": "SunHestia official"},
                              {"url": "https://enphase.com/", "title": "Enphase"},
                              {"url": "https://byd.com", "title": "BYD"}]}
    l2 = parse_l2("qwen", out, ROW, BRAND, COMP)
    assert l2.mentioned is False                          # 品牌只在检索 URL 里,答案没提
    assert l2.competitors_mentioned == ["Tesla"]          # enphase/byd 只在检索 URL 里

def test_provider_attested_citations_count():
    """doubao url_citation annotations 是 provider 明证的引用,即使答案无 URL。"""
    out = {"answer": "Some answer without any URL.",
           "search_results": [{"url": "https://x.com/"}],
           "citations": [{"url": "https://sunhestia.com/", "title": "SunHestia"}]}
    l2 = parse_l2("doubao", out, ROW, BRAND, COMP)
    assert [s.url for s in l2.cited_sources] == ["https://sunhestia.com/"]
    assert l2.cited_sources[0].extract_method == "attested"
    assert l2.cited_with_link is True
    assert l2.citation_position == 1


# ---- Fix(2026-08-25 二次审查#1): URL 身份与品牌引用判定 ----------------------
# 品牌引用只认 URL 主机(=品牌域或其子域);路径/参数里含品牌词的第三方 URL
# 不是品牌引用。query 是 URL 身份的一部分,不得剥离合并。

def test_brand_word_in_url_path_is_not_brand_citation():
    """codex 复现: evil.example/sunhestia-review 含品牌词 → 旧子串匹配误报
    cited_with_link=True 且 position=1。host 不匹配必须判 False/None。"""
    out = {"answer": "See https://evil.example/sunhestia-review for details.",
           "search_results": []}
    l2 = parse_l2("qwen", out, ROW, BRAND, COMP)
    assert len(l2.cited_sources) == 1                    # URL 本身仍是答案内引用
    assert l2.cited_with_link is False
    assert l2.citation_position is None

def test_brand_domain_host_and_subdomain_are_brand_citations():
    out = {"answer": "Docs at https://www.sunhestia.com/docs and https://sunhestia.com.",
           "search_results": []}
    l2 = parse_l2("qwen", out, ROW, BRAND, COMP)
    assert l2.cited_with_link is True
    assert l2.citation_position == 1                     # www 子域也算,按答案内顺序

def test_query_urls_keep_identity():
    """codex 复现: ?id=one 与 ?id=two 剥 query 后合并成同一条;且文本 URL 带
    query 时旧逻辑对不上带 query 的检索键,误判 inferred。"""
    out = {"answer": "See https://example.com/page?id=one and https://example.com/page?id=two.",
           "search_results": [{"url": "https://example.com/page?id=one", "title": "One"}]}
    l2 = parse_l2("qwen", out, ROW, BRAND, COMP)
    assert [s.url for s in l2.cited_sources] == ["https://example.com/page?id=one",
                                                 "https://example.com/page?id=two"]
    assert l2.cited_sources[0].extract_method == "structured"
    assert l2.cited_sources[1].extract_method == "inferred"

def test_bare_domain_lookalike_in_answer_is_not_brand_link():
    """答案写 "sunhestia.com.evil.io"(伪装域名)不算品牌裸域名出现。"""
    out = {"answer": "Watch out for sunhestia.com.evil.io lookalikes.", "search_results": []}
    l2 = parse_l2("qwen", out, ROW, BRAND, COMP)
    assert l2.cited_with_link is False
