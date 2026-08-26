import pytest
import yaml
from geo.rules.loader import load_rules, assert_normalized, RULES_DIR


def test_geo_normalized():
    r = load_rules("geo")
    assert_normalized(r)
    assert sum(r.weights.values()) == 100


def test_seo_normalized():
    r = load_rules("seo")
    assert sum(r.weights.values()) == 100


def test_reject_unnormalized(tmp_path, monkeypatch):
    import geo.rules.loader as L

    bad = tmp_path / "x.yaml"
    bad.write_text("version: t\ncomposite: geo\nweights: {a: 50}\nsignals: {}\n")
    monkeypatch.setattr(L, "RULES_DIR", tmp_path)
    with pytest.raises(ValueError):
        assert_normalized(L._load(bad))


def test_load_with_version_reads_history(tmp_path):
    hist = tmp_path / "history" / "geo-seo-v1"
    hist.mkdir(parents=True)
    (hist / "geo-rules.yaml").write_text(yaml.safe_dump({
        "version": "geo-seo-v1", "composite": "geo",
        "weights": {"citability": 25}, "signals": {"citability": ["has_definition_segment"]},
        "entries": [{"id": "add-x", "type": "signal_add", "target": "schema",
                     "signal": "has_breadcrumblist", "status": "draft",
                     "statement": "s", "evidence": {"share": 0.19}, "since_version": None}]}))
    orig = RULES_DIR   # monkeypatch 注入 tmp
    import geo.rules.loader as L
    L.RULES_DIR = tmp_path
    try:
        r = load_rules("geo", version="geo-seo-v1")
        assert r.version == "geo-seo-v1" and r.entries[0]["signal"] == "has_breadcrumblist"
        with pytest.raises(FileNotFoundError):
            load_rules("geo", version="geo-seo-v99")
    finally:
        L.RULES_DIR = orig


def test_entries_default_empty():
    r = load_rules("geo")
    assert r.entries == []            # v1 文件尚无 entries → 默认空


# ---- Fix(2026-08-25 二次审查#6): 报告版本标签必须与实际加载的规则一致 -----------

def test_current_rule_files_match_run_yaml_version():
    """run.yaml 的 rule_version(报告将贴的标签)必须与 rules/*.yaml 的 version
    (评分器实际加载的规则)一致——否则产出"v2 标签、v1 规则"的审计错位,
    且 rules/run.py 的 do_recalc(version=) 会因 history/ 缺失而 FileNotFoundError。"""
    from geo.shared.config import settings
    rg = load_rules("geo")
    rs = load_rules("seo")
    assert rg.version == rs.version, (
        f"geo({rg.version})/seo({rs.version}) 规则文件版本不同步")
    assert rg.version == settings.run.rule_version, (
        f"rules/*.yaml={rg.version} != run.yaml rule_version={settings.run.rule_version}")
    # 请求现行版本 → 解析到现行文件,不要求 history/ 里已有同名归档
    assert load_rules("geo", version=settings.run.rule_version).version == rg.version
    # 历史版本走归档: v1 归档已补齐(2026-08-25),do_recalc --to geo-seo-v1 可用
    assert load_rules("geo", version="geo-seo-v1").version == "geo-seo-v1"
