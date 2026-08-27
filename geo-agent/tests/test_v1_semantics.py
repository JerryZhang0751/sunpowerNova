"""Golden test: 当前规则语义在真实 w1 数据上零漂移。
历史: v1 锁 47.6/49.8(2026-08-02); 2026-08-24 审查#2 SOV 方向修正(平均竞品数→
声量份额)后重算为 43.4/49.8,旧归档保留于 data/analysis/w1/eval_report.geo-seo-v1-archived.json,
语义变更记录见 rules/changelog.md geo-seo-v2 条目。本次更新是对该已评审语义变更的
重新锁值——非转录漂移;此后再 FAIL 即为漂移,需回修,不可再调本测试或归档数据。
"""
import json
import pytest
from pathlib import Path
import sys

# Add src to path so we can import geo modules
src_path = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(src_path))

from geo.shared.config import REPO
from geo.assess.analyst import assemble
from geo.rules.loader import _load


_REQUIRED_LOCAL = [
    REPO / "data" / "raw" / "w1",
    REPO / "data" / "analysis" / "w1" / "eval_report.json",   # 与断言实际读取同源(假信心修复)
]

@pytest.mark.skipif(
    not all(p.exists() for p in _REQUIRED_LOCAL),
    reason="需本地真实 w1 数据(gitignored): data/raw/w1 与 data/analysis/w1/eval_report.json",
)
def test_v1_semantics_unchanged_on_real_w1():
    """证明当前语义在真实 w1 数据上零漂移：重新计算的 report 与归档的 eval_report.json 完全一致。

    注意：
    - assemble(1) 会覆写 eval_report.json，故必须先读归档版本再调用 assemble
    - 新引擎 DimScore.signals 携带 {signal_id: value}(4 keys for eeat incl. org_or_person_schema)
      而归档仅 3 keys——本测试仅比对 name/score/weight，不比对 signals payload
    - 测试加载提交的 v2 fixture 规则（tests/fixtures/rules/），而非当前规则，防止版本漂移
    """
    # Step 1: Read archived report BEFORE assemble overwrites it
    archived_path = REPO / "data" / "analysis" / "w1" / "eval_report.json"
    archived = json.loads(archived_path.read_text(encoding="utf-8"))

    # Step 2: Load committed v2 fixture rules (version-proof against runtime advancement)
    fix_path = Path(__file__).parent / "fixtures" / "rules"
    rg = _load(fix_path / "geo_rules_v2.yaml")
    rs = _load(fix_path / "seo_rules_v2.yaml")

    # Step 3: Recompute with v2 rules injected (幂等覆写)
    rep = assemble(1, rules_geo=rg, rules_seo=rs, rule_version="geo-seo-v2")

    # Step 3: Assert golden totals (geo-seo-v2: SOV 份额修正后 43.4;SEO 不受影响 49.8)
    assert rep["self_geo"]["total"] == archived["self_geo"]["total"] == 43.4
    assert rep["self_seo"]["total"] == archived["self_seo"]["total"] == 49.8

    # Step 4: Assert per-dimension equality (name, score, weight only — NOT signals payload)
    for a, b in zip(rep["self_geo"]["dims"], archived["self_geo"]["dims"]):
        assert a["name"] == b["name"], f"GEO dim name mismatch: {a['name']} vs {b['name']}"
        assert a["score"] == b["score"], f"GEO dim score mismatch for {a['name']}: {a['score']} vs {b['score']}"
        assert a["weight"] == b["weight"], f"GEO dim weight mismatch for {a['name']}: {a['weight']} vs {b['weight']}"

    for a, b in zip(rep["self_seo"]["dims"], archived["self_seo"]["dims"]):
        assert a["name"] == b["name"], f"SEO dim name mismatch: {a['name']} vs {b['name']}"
        assert a["score"] == b["score"], f"SEO dim score mismatch for {a['name']}: {a['score']} vs {b['score']}"
        assert a["weight"] == b["weight"], f"SEO dim weight mismatch for {a['name']}: {a['weight']} vs {b['weight']}"

    # Step 5: SOV 方向反回归——份额口径 0–1,不得再出现 >1 的"平均竞品数"
    for m in rep["metrics"].values():
        assert 0.0 <= m["sov"] <= 1.0
