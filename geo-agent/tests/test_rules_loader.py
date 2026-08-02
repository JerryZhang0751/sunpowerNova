import pytest
from geo.rules.loader import load_rules, assert_normalized


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
