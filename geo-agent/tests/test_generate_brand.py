# tests/test_generate_brand.py
from pathlib import Path
import pytest
from geo.generate.brand import load_brand, BrandError, slugify, parse_claims, brand_claims, claims_match, validate_brand
import yaml

FIX = Path(__file__).parent / "fixtures" / "generate"
BRAND = FIX / "knowledge" / "brand.yaml"
SITE = FIX / "site" / "src" / "pages"

def test_load_brand_valid():
    brand = load_brand(BRAND)
    assert brand["version"] == 1
    assert brand["products"][0]["id"] == "home-battery"
    assert "no_pricing" in brand["banned"]

def test_load_brand_missing_file():
    with pytest.raises(BrandError, match="brand.yaml 不存在"):
        load_brand(FIX / "knowledge" / "nope.yaml")

def test_load_brand_missing_top_keys(tmp_path):
    p = tmp_path / "brand.yaml"
    p.write_text("version: 1\nentity: {brand: SunHestia}\n", encoding="utf-8")
    with pytest.raises(BrandError, match="缺少顶层键"):
        load_brand(p)

def test_load_brand_bad_version(tmp_path):
    p = tmp_path / "brand.yaml"
    p.write_text("version: 0\nentity: {}\nproducts: []\nfaqs: []\nglossary: []\nbanned: []\n", encoding="utf-8")
    with pytest.raises(BrandError, match="version"):
        load_brand(p)

def test_slugify():
    assert slugify("How to Size a Home Battery?") == "how-to-size-a-home-battery"
    assert slugify("  LiFePO4  vs  NMC ") == "lifepo4-vs-nmc"

def _sources_text():
    return "\n\n".join(p.read_text(encoding="utf-8") for p in SITE.rglob("*.astro"))

def test_parse_claims_prose():
    claims = parse_claims("modular from 5–15 kWh with a 10-year warranty, 400–450 W panels")
    assert (frozenset({"5", "15"}), "kwh") in claims
    assert (frozenset({"10"}), "year") in claims
    assert (frozenset({"400", "450"}), "w") in claims

def test_parse_claims_ignores_ordinals_and_years():
    claims = parse_claims("1. first step in 2026, item 3, and 40 pages")
    assert claims == []

def test_brand_claims_from_key_names():
    brand = yaml.safe_load(BRAND.read_text(encoding="utf-8"))
    inv = brand_claims(brand)
    assert (frozenset({"5", "15"}), "kwh") in inv
    assert (frozenset({"10"}), "year") in inv          # warranty_years: 10
    assert (frozenset({"25"}), "year") in inv          # performance_guarantee_years: 25
    assert (frozenset({"400", "450"}), "w") in inv

def test_claims_match_subset_semantics():
    inv = [(frozenset({"5", "15"}), "kwh")]
    assert claims_match((frozenset({"15"}), "kwh"), inv)      # 单值是范围的子集
    assert claims_match((frozenset({"5", "15"}), "kwh"), inv)
    assert not claims_match((frozenset({"20"}), "kwh"), inv)  # 编造的 20 kWh
    assert not claims_match((frozenset({"10"}), "kwh"), inv)  # 单位不符

def test_validate_brand_pass():
    brand = yaml.safe_load(BRAND.read_text(encoding="utf-8"))
    assert validate_brand(brand, _sources_text()) == []

def test_validate_brand_flags_invented_number_and_name():
    brand = yaml.safe_load(BRAND.read_text(encoding="utf-8"))
    brand["products"][0]["specs"]["capacity_kwh"] = "5–20"        # 源页没有 20
    brand["products"].append({"id": "ev-charger", "name": "SunHestia EV Charger",
                              "specs": {"power_kw": "22"}})        # 源页没有该产品
    violations = validate_brand(brand, _sources_text())
    assert any("20" in v and "kwh" in v for v in violations)
    assert any("EV Charger" in v for v in violations)

def test_validate_brand_captures_both_prose_and_keyval_claims_in_same_leaf():
    """Covering test for review finding R1: leaf with BOTH prose and keyval claims.
    When a leaf contains '10-year warranty' (prose) AND 'capacity_kwh: 5–15' (keyval),
    BOTH must be extracted and validated. The 'or' short-circuit bug misses keyval claims."""
    # Source text contains "10-year" but NOT "5–15 kWh"
    sources = "The system has a 10-year warranty on all components."
    # Brand contains BOTH prose claim ("10-year warranty") AND keyval claim ("capacity_kwh: 5–15")
    brand_dict = {
        "version": 1,
        "entity": {"brand": "TestBrand"},
        "products": [{
            "id": "battery",
            "name": "Test Battery",
            "specs": {
                "description": "The 10-year warranty covers modular expansion; see capacity_kwh: 5–15"
            }
        }],
        "faqs": [],
        "glossary": [],
        "banned": []
    }
    violations = validate_brand(brand_dict, sources)
    # Should flag BOTH the missing 5–15 kWh claim (keyval) AND potentially the 10-year if not found
    # At minimum, must catch the keyval claim '5–15 kWh' which is NOT in sources
    assert any("5" in v and "15" in v and "kwh" in v for v in violations), \
        "Should catch keyval claim '5–15 kWh' missing from sources"

def test_parse_claims_captures_percent_sign():
    """Final review finding F1: % sign must be detected after numbers.
    The regex \b after % never matches (both % and next char are non-word).
    This test ensures parse_clains('Round-trip efficiency is 96%') extracts the percent claim."""
    claims = parse_claims("Round-trip efficiency is 96%")
    assert (frozenset({"96"}), "%") in claims, \
        "Should extract '96%' claim - % is a valid unit that must be detected"

def test_parse_claims_guards_against_kwhz_false_positive():
    """Final review finding F1: negative test - 'kwhz' must NOT produce a kwh claim.
    After fixing the % bug with (?![a-z0-9]), verify it still blocks 'kwhz' false positives."""
    claims = parse_claims("3 kwhz units")
    assert (frozenset({"3"}), "kwh") not in claims, \
        "Should NOT extract 'kwh' from 'kwhz' - lookahead must block alphanumeric after unit"
