"""Golden test: v1 semantics unchanged on real w1 data."""
import json
import pytest
from pathlib import Path
import sys

# Add src to path so we can import geo modules
src_path = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(src_path))

from geo.shared.config import REPO
from geo.assess.analyst import assemble


@pytest.mark.skipif(
    not (REPO / "data" / "raw" / "w1").exists(),
    reason="需本地真实 w1 数据(data/ gitignored)"
)
def test_v1_semantics_unchanged_on_real_w1():
    """证明 v1 语义在真实 w1 数据上零漂移：重新计算的 report 与归档的 eval_report.json 完全一致。

    这是黄金测试——若 FAIL，说明 Task 1/3 有转录漂移，需回修，不可调整本测试或归档数据。

    注意：
    - assemble(1) 会覆写 eval_report.json，故必须先读归档版本再调用 assemble
    - 新引擎 DimScore.signals 携带 {signal_id: value}(4 keys for eeat incl. org_or_person_schema)
      而归档仅 3 keys——本测试仅比对 name/score/weight，不比对 signals payload
    """
    # Step 1: Read archived report BEFORE assemble overwrites it
    archived_path = REPO / "data" / "analysis" / "w1" / "eval_report.json"
    archived = json.loads(archived_path.read_text(encoding="utf-8"))

    # Step 2: Recompute with new engine (幂等覆写)
    rep = assemble(1)

    # Step 3: Assert golden totals
    assert rep["self_geo"]["total"] == archived["self_geo"]["total"] == 47.6
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
