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

def test_resolve_path_numeric_index_fallback():
    """live 校准：Kimi 偶用数字下标路径（faqs[1].a）；id 匹配优先，失配且为纯数字时按下标回退。"""
    from geo.generate.validate import resolve_path
    brand = BRAND
    by_id = resolve_path(brand, f"faqs[{brand['faqs'][0].get('id', 'faq-system-includes')}].a")
    assert by_id is not None and isinstance(by_id, str)
    by_idx = resolve_path(brand, "faqs[0].a")
    assert by_idx == by_id
    from geo.generate.validate import _MISSING
    assert resolve_path(brand, "faqs[99].a") is _MISSING        # 越界安全
    assert resolve_path(brand, "faqs[no-such-id].a") is _MISSING

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

def test_validate_allows_breadcrumblist():
    """live 校准：BreadcrumbList 是 w1 被引源 schema 第一名（26/134），白名单纳入；
       缺 itemListElement 仍须拒。"""
    ok = _draft(json_ld=[{"@type": "Article", "headline": "h"},
                         {"@type": "BreadcrumbList",
                          "itemListElement": [{"@type": "ListItem", "position": 1, "name": "n"}]}])
    r = validate_draft(ok, BRAND)
    assert not any("BreadcrumbList" in i for i in r.issues), r.issues
    bad = _draft(json_ld=[{"@type": "Article", "headline": "h"}, {"@type": "BreadcrumbList"}])
    r2 = validate_draft(bad, BRAND)
    assert not r2.ok and any("BreadcrumbList" in i for i in r2.issues)

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
    """Anchor 数字不足以覆盖 claim 时必须拒（{5} 锚 ≠ claim {5,15}）。
       语义（2026-08-18 live 校准）：anchor 集合须 ⊇ claim；不足=拒，超出=可（见 covering 测试）。"""
    d = _draft(
        body_md="# How to size a home battery\n\nStart at 5–15 kWh; the battery carries a 10-year warranty.",
        fact_anchors=[
            # Partial claim "5 kWh" does NOT cover body claim {5,15} - must be rejected
            {"claim": "5 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5"},
            # Valid anchor for 10-year warranty
            {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}]
    )
    r = validate_draft(d, BRAND)
    assert not r.ok, f"Expected validation failure but got ok. Issues: {r.issues}"

def test_validate_covering_range_anchor_satisfies_endpoint_claim():
    """Range 锚（5–15 kWh）覆盖正文中独立的端点 claim（5 kWh）——live 校准：
       原 exact-equality 把被 range 覆盖的真 claim 误报"缺 anchor"（w1 首篇真草稿 6 处假阳性中的 4 处）。"""
    d = _draft(
        body_md="# Stackable\n\nModular from 5 kWh, the battery carries a 10-year warranty.",
        fact_anchors=[
            {"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
            {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}]
    )
    r = validate_draft(d, BRAND)
    assert r.ok, f"Expected ok but got issues: {r.issues}"
    assert "| 5 kWh | products[home-battery].specs.capacity_kwh | ✅ |" in r.appendix_md

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
