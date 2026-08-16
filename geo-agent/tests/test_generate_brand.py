# tests/test_generate_brand.py
from pathlib import Path
import pytest
from geo.generate.brand import load_brand, BrandError, slugify

FIX = Path(__file__).parent / "fixtures" / "generate"
BRAND = FIX / "knowledge" / "brand.yaml"

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
