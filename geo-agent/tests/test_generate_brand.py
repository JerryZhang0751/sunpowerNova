# tests/test_generate_brand.py
from pathlib import Path
import pytest
from geo.generate.brand import (load_brand, BrandError, slugify, parse_claims, brand_claims,
                                claims_match, validate_brand, tokenize_nums)
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

def test_brand_claims_from_free_text_numbers():
    """live 校准（2026-08-18）：FAQ/modularity 自由文本"数字在前单位在后"的 claim
       也须进库存，否则 w1 真草稿的 "5–10 kWh"（brand FAQ 原文）被误判"编造"。"""
    brand = {"entity": {}, "products": [], "glossary": [],
             "faqs": [{"q": "size?", "a": "A common starting point is 5–10 kWh, stackable to around 15 kWh."}]}
    inv = brand_claims(brand)
    assert (frozenset({"5", "10"}), "kwh") in inv
    assert (frozenset({"15"}), "kwh") in inv

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


# ---- Fix(2026-08-24 审查#4): 小数与千分位不得绕过数字门禁 --------------------
def test_parse_claims_decimals():
    claims = parse_claims("A 5.5 kW inverter with a 10.9 kWh battery")
    assert (frozenset({"5.5"}), "kw") in claims
    assert (frozenset({"10.9"}), "kwh") in claims
    assert (frozenset({"5"}), "kw") not in claims      # 不得截成 5
    assert (frozenset({"9"}), "kwh") not in claims     # 不得截成 9

def test_parse_claims_thousands_separator():
    claims = parse_claims("Peak output of 1,500 W")
    assert (frozenset({"1500"}), "w") in claims
    assert (frozenset({"500"}), "w") not in claims     # 不得截成 500

def test_claims_match_rejects_decimal_against_int_inventory():
    """审查复现: brand 只有 5 kW,正文称 5.5 kW —— 旧解析两边都成 {5},误判通过。"""
    inv = [(frozenset({"5"}), "kw")]
    assert not claims_match((frozenset({"5.5"}), "kw"), inv)

def test_claims_match_decimal_inventory_roundtrip():
    inv = [(frozenset({"5.5"}), "kw")]
    assert claims_match((frozenset({"5.5"}), "kw"), inv)
    assert not claims_match((frozenset({"5"}), "kw"), inv)

def test_validate_brand_rejects_thousands_mismatch():
    brand_dict = {"version": 1, "entity": {}, "glossary": [], "faqs": [],
                  "products": [{"id": "inv", "name": "Inv", "specs": {"power_w": "1,500"}}],
                  "banned": []}
    violations = validate_brand(brand_dict, "The inverter peaks at 2,500 W.")
    assert any("2500" in v or "1500" in v for v in violations), \
        "2,500 W 不得经 500 W 匹配到 1,500 W 库存"


# ---- Fix(2026-08-25 二次审查#4): 符号与组合格式不得绕过数字门禁 --------------
# codex 复现三连: +10°C vs -10°C 通过(方向错); 500.5 W vs 1,500.5 W 通过
# (数量级错); 5,5 kW 被解析成 5 kW(欧式小数逗号截断)。

def test_parse_claims_signed_temperatures():
    claims = parse_claims("Operates from -10°C to +45°C.")
    assert (frozenset({"-10"}), "°c") in claims
    assert (frozenset({"45"}), "°c") in claims          # +45 与 45 同值

def test_sign_mismatch_rejected():
    inv = [(frozenset({"10"}), "°c")]                   # 事实 +10°C
    assert claims_match((frozenset({"10"}), "°c"), inv)      # +10 == 10
    assert not claims_match((frozenset({"-10"}), "°c"), inv) # -10 ≠ +10(方向)
    inv_neg = [(frozenset({"-10"}), "°c")]              # 事实 -10°C
    assert not claims_match((frozenset({"10"}), "°c"), inv_neg)

def test_thousands_with_decimal_not_truncated():
    claims = parse_claims("Peak output of 1,500.5 W.")
    assert (frozenset({"1500.5"}), "w") in claims
    assert (frozenset({"500.5"}), "w") not in claims    # 不得回退截出 500.5
    assert (frozenset({"1500"}), "w") not in claims     # 不得丢小数

def test_thousands_decimal_mismatch_rejected():
    inv = [(frozenset({"500.5"}), "w")]
    assert not claims_match((frozenset({"1500.5"}), "w"), inv)  # 数量级错不得过

def test_decimal_comma_european_not_collapsed():
    claims = parse_claims("Rated at 5,5 kW.")
    assert (frozenset({"5.5"}), "kw") in claims
    assert (frozenset({"5"}), "kw") not in claims       # "5,5" 不得当成 "5"

def test_validate_brand_rejects_sign_flip():
    brand_dict = {"version": 1, "entity": {}, "glossary": [], "faqs": [],
                  "products": [{"id": "b", "name": "B",
                                "specs": {"description": "Operates down to +10°C."}}],
                  "banned": []}
    violations = validate_brand(brand_dict, "The battery operates down to -10°C.")
    assert any("10" in v and "°c" in v for v in violations), \
        "+10°C 事实不得被 -10°C 正文通过"

def test_tokenize_nums_signed_and_ranges():
    """tokenizer 与 parse_claims 同口径: 负值带符号、range 两端拆开、+ 视为无符号。"""
    assert tokenize_nums("-10°C and 5–15 kWh") == ["-10", "5", "15"]
    assert tokenize_nums("+10") == ["10"]
