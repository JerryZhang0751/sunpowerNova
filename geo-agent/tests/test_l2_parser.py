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
                assert all(s.extract_method in ("structured","inferred") for s in l2.cited_sources)
            assert l2.mentioned == exp["mentioned"]
            assert l2.cited_with_link == exp["cited_with_link"]
            assert l2.sentiment == exp["sentiment"]
            # precision: 抽出的 url 里真出现在答案/来源文本里的比例 ≥ 0.9
            if l2.cited_sources:
                text = (raw["response"].get("answer","") or json.dumps(raw["response"]))
                hit = sum(1 for s in l2.cited_sources if s.url in text or any(s.url.startswith(u) for u in text.split()))
                assert (hit / max(1,len(l2.cited_sources))) >= 0.9 or exp.get("cited_urls_subset")
