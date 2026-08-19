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
