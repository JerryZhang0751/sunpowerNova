# tests/test_rules_run.py
import json, yaml
from pathlib import Path
import pytest
from geo.rules.run import do_recalc, do_rollback

@pytest.fixture
def repo(tmp_path):
    """v1 归档 + v2 当前(模拟 Task 8 迭代后状态)。"""
    r = tmp_path / "repo"
    fix = Path(__file__).parent / "fixtures" / "rules"
    for sub in ("rules", "rules/history/geo-seo-v1", "data/analysis/w1", "data/raw/w1/r0"):
        (r / sub).mkdir(parents=True, exist_ok=True)
    (r / "rules" / "geo-rules.yaml").write_text((fix / "geo_rules_v1.yaml").read_text())
    (r / "rules" / "seo-rules.yaml").write_text((fix / "seo_rules_v1.yaml").read_text())
    v1 = yaml.safe_load((fix / "geo_rules_v1.yaml").read_text())
    v2 = dict(v1); v2["version"] = "geo-seo-v2"
    v2["weights"] = {**v1["weights"], "citability": 26, "brand": 19}
    (r / "rules" / "geo-rules.yaml").write_text(yaml.safe_dump(v2, sort_keys=False))
    (r / "rules" / "history" / "geo-seo-v1" / "geo-rules.yaml").write_text(
        (fix / "geo_rules_v1.yaml").read_text())
    (r / "rules" / "history" / "geo-seo-v1" / "seo-rules.yaml").write_text(
        (fix / "seo_rules_v1.yaml").read_text())
    (r / "rules" / "changelog.md").write_text("# Rules changelog\n")
    (r / "run.yaml").write_text(yaml.safe_dump(
        {"week": 1, "mode": "audit", "scope": "core", "runs": 1,
         "rule_version": "geo-seo-v2", "providers": ["qwen"]}, sort_keys=False))
    return r

def test_rollback_creates_new_monotonic_version(repo):
    do_rollback(repo, "geo-seo-v1")
    g = yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text())
    assert g["version"] == "geo-seo-v3"                    # v1.1:不倒退到 v1,产新单调版本
    assert g["restores"] == "geo-seo-v1"                   # 内容 = v1 快照
    assert g["weights"]["citability"] == 25                # (v2 的 26 不残留)
    assert yaml.safe_load((repo / "run.yaml").read_text())["rule_version"] == "geo-seo-v3"
    assert (repo / "rules" / "history" / "geo-seo-v2" / "geo-rules.yaml").exists()  # 现行 v2 先归档
    assert "rollback" in (repo / "rules" / "changelog.md").read_text()

def test_recalc_writes_separate_file_never_overwrites(repo, monkeypatch):
    ana = repo / "data" / "analysis" / "w1"
    (ana / "eval_report.json").write_text('{"self_geo": {"total": 50.0}}')
    called = {}
    def fake_assemble(week, **kw):
        called.update(kw); result = {"self_geo": {"total": 47.6}, "rule_version": kw.get("rule_version")}
        # Actually write the file so test can check it exists
        out_path = ana / kw.get("out_name", "eval_report.json")
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return result
    import geo.rules.run as R
    monkeypatch.setattr(R, "assemble", fake_assemble)
    # Patch RULES_DIR to tmp repo's rules/ dir (fixture creates rules/history/geo-seo-v1/ there)
    import geo.rules.loader
    monkeypatch.setattr(geo.rules.loader, "RULES_DIR", repo / "rules")
    out = do_recalc(repo, week=1, rule_version="geo-seo-v1", render=False)
    assert called["rule_version"] == "geo-seo-v1" and called["out_name"] == "eval_report.recalc-geo-seo-v1.json"
    assert out["rule_version"] == "geo-seo-v1"
    assert (ana / "eval_report.recalc-geo-seo-v1.json").exists()
    assert json.loads((ana / "eval_report.json").read_text())["self_geo"]["total"] == 50.0  # 原件未动
