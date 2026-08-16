# tests/test_generate_validate.py
import yaml
from pathlib import Path
from geo.generate.validate import validate_draft, resolve_path, _MISSING

FIX = Path(__file__).parent / "fixtures" / "generate"
BRAND = yaml.safe_load((FIX / "knowledge" / "brand.yaml").read_text(encoding="utf-8"))

def _draft(**over):
    d = {
        "frontmatter": {"topic": "How to size a home battery", "page_type": "guide",
                        "slug": "how-to-size-a-home-battery", "created": "2026-08-16",
                        "brand_version": 1},
        "title": "How to size a home battery",
        "body_md": "# How to size a home battery\n\nStart at 5–15 kWh; the battery carries a 10-year warranty.",
        "json_ld": [{"@context": "https://schema.org", "@type": "Article",
                     "headline": "How to size a home battery"}],
        "fact_anchors": [
            {"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
            {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}],
    }
    d.update(over)
    return d

def test_resolve_path():
    assert resolve_path(BRAND, "products[home-battery].specs.warranty_years") == 10
    assert resolve_path(BRAND, "products[nope].specs.x") is _MISSING

def test_validate_ok():
    r = validate_draft(_draft(), BRAND)
    assert r.ok, r.issues
    assert "| 5–15 kWh | products[home-battery].specs.capacity_kwh | ✅ |" in r.appendix_md

def test_validate_flags_invented_number():
    d = _draft(body_md="# t\n\nA 20 kWh battery is big.")
    r = validate_draft(d, BRAND)
    assert not r.ok and any("20" in i for i in r.issues)

def test_validate_flags_missing_anchor():
    d = _draft(fact_anchors=[{"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"}])
    r = validate_draft(d, BRAND)     # 10-year 无 anchor
    assert not r.ok and any("anchor" in i for i in r.issues)

def test_validate_flags_bad_anchor_path():
    d = _draft(fact_anchors=[
        {"claim": "5–15 kWh", "path": "products[home-battery].specs.nonexistent", "value": "5–15"},
        {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}])
    r = validate_draft(d, BRAND)
    assert not r.ok and any("nonexistent" in i for i in r.issues)

def test_validate_flags_bad_jsonld():
    d = _draft(json_ld=[{"@type": "FAQPage"}])          # 缺 mainEntity
    r = validate_draft(d, BRAND)
    assert not r.ok and any("FAQPage" in i for i in r.issues)

def test_validate_flags_pricing():
    d = _draft(body_md="# t\n\nThe system costs $9999.")
    r = validate_draft(d, BRAND)
    assert not r.ok and any("no_pricing" in i for i in r.issues)

def test_validate_flags_savings_percent():
    d = _draft(body_md="# t\n\nSave 40% on your bills.")
    r = validate_draft(d, BRAND)
    assert not r.ok and any("no_savings_percentages" in i for i in r.issues)

def test_validate_flags_frontmatter():
    d = _draft()
    d["frontmatter"] = {"topic": "x"}                    # 缺 page_type/slug/created/brand_version
    r = validate_draft(d, BRAND)
    assert not r.ok and any("frontmatter" in i for i in r.issues)

def test_validate_flags_wrong_anchor_value():
    """Tests that resolved brand values are verified against claim numbers.
       Branch: after resolve_path succeeds, check resolved value covers claim."""
    d = _draft(fact_anchors=[
        {"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
        {"claim": "10-year warranty", "path": "products[pv-module].specs.performance_guarantee_years", "value": "25"}])
    r = validate_draft(d, BRAND)
    assert not r.ok, f"Expected validation failure but got ok. Issues: {r.issues}"
    assert any("值不吻合" in i for i in r.issues), f"Expected '值不吻合' issue but got: {r.issues}"

def test_validate_partial_anchor_not_matched():
    """Tests that partial anchor claims are NOT accepted (exact match only required).
       Branch: anchor selection uses exact match (claim OR value, both must be == nums)."""
    d = _draft(
        body_md="# How to size a home battery\n\nStart at 5–15 kWh; the battery carries a 10-year warranty.",
        fact_anchors=[
            # Partial claim "5 kWh" should NOT match body claim {5,15} - neither claim nor value exact matches
            {"claim": "5 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5"},
            # Valid anchor for 10-year warranty
            {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}]
    )
    r = validate_draft(d, BRAND)
    assert not r.ok, f"Expected validation failure but got ok. Issues: {r.issues}"
    assert any("缺 anchor" in i for i in r.issues), f"Expected '缺 anchor' issue but got: {r.issues}"

def test_validate_flags_unattributed_percent_claims():
    """Final review finding F1 end-to-end: percent claims in draft body must be validated.
    When brand has no % facts but draft claims '96% efficient', validation should flag it."""
    d = _draft(
        body_md="# How to size a home battery\n\nRound-trip efficiency is 96% and modular from 5–15 kWh.",
        fact_anchors=[
            # Valid anchor for kWh range
            {"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
        ]
        # NO anchor for "96%" - this should be flagged as unattributed claim
    )
    r = validate_draft(d, BRAND)
    assert not r.ok, f"Expected validation failure for unattributed % claim but got ok. Issues: {r.issues}"
    assert any("96" in i and ("%" in i or "percent" in i.lower()) for i in r.issues), \
        f"Expected issue about unattributed '96%' claim but got: {r.issues}"
