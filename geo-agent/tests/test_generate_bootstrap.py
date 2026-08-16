# tests/test_generate_bootstrap.py
import json
from pathlib import Path
import pytest
import yaml
from geo.generate.brand import (
    read_site_pages, bootstrap_draft, competitors_from_raw, assemble_brand, run_bootstrap, BrandError)

FIX = Path(__file__).parent / "fixtures" / "generate"

def _mock_chat(payload: dict):
    def chat_fn(messages, tools=None, timeout=120) -> str:
        return json.dumps(payload, ensure_ascii=False)
    return chat_fn

_GOOD = {
    "entity": {"brand": "SunHestia", "domain": "sunhestia.com",
               "positioning": "Residential solar and storage for European homes"},
    "products": [{"id": "home-battery", "name": "SunHestia Home Battery",
                  "specs": {"chemistry": "LiFePO4", "capacity_kwh": "5–15", "warranty_years": 10}},
                 {"id": "pv-module", "name": "SunHestia Solar PV Modules",
                  "specs": {"cell_type": "monocrystalline", "power_w": "400–450",
                            "performance_guarantee_years": 25}}],
    "faqs": [{"q": "What does a residential solar and storage system include?",
              "a": "Typically rooftop solar panels, a hybrid inverter, and a home battery."}],
    "glossary": [{"term": "self-consumption",
                  "definition": "The share of your electricity use covered by solar produced on your own property."},
                 {"term": "LiFePO4", "definition": "Lithium iron phosphate battery chemistry."}],
}

def test_read_site_pages():
    pages = read_site_pages(FIX / "site" / "src" / "pages")
    assert set(pages) == {"products.astro", "faq.astro"}
    assert "LiFePO4" in pages["products.astro"]

def test_bootstrap_draft_ok():
    draft = bootstrap_draft({"products.astro": "LiFePO4 5–15 kWh 10-year warranty"},
                            chat_fn=_mock_chat(_GOOD))
    assert draft["products"][0]["id"] == "home-battery"

def test_bootstrap_draft_bad_json():
    def bad(messages, tools=None, timeout=120):
        return "not json"
    with pytest.raises(BrandError, match="Kimi 抽取失败"):
        bootstrap_draft({"p": "x"}, chat_fn=bad)

def test_competitors_from_raw():
    comps = competitors_from_raw(FIX / "data" / "raw")
    assert comps[0] == "Tesla"
    assert "Enphase" in comps

def test_assemble_brand():
    brand = assemble_brand(_GOOD, ["Tesla"])
    assert brand["version"] == 1 and brand["banned"] == ["no_pricing", "no_savings_percentages"]
    assert brand["competitors"] == ["Tesla"] and brand["i18n"] == {}

def test_run_bootstrap_clean_writes_brand(tmp_path):
    import shutil
    for d in ["site", "data", "knowledge"]:
        src = FIX / d
        if src.exists():
            shutil.copytree(src, tmp_path / d)
    
    res = run_bootstrap(repo=tmp_path, chat_fn=_mock_chat(_GOOD))
    assert res["violations"] == []
    out = tmp_path / "knowledge" / "brand.yaml"
    assert out.exists()
    content = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert content["version"] == 1

def test_run_bootstrap_violations_write_draft_only(tmp_path):
    import shutil
    for d in ["site", "data", "knowledge"]:
        src = FIX / d
        if src.exists():
            shutil.copytree(src, tmp_path / d)
    
    bad_payload = json.loads(json.dumps(_GOOD))
    bad_payload["products"][0]["specs"]["capacity_kwh"] = "5–20"
    res = run_bootstrap(repo=tmp_path, chat_fn=_mock_chat(bad_payload))
    assert res["violations"] and "20" in res["violations"][0]
    assert res["wrote"] == str(tmp_path / "knowledge" / "brand.yaml.draft")
