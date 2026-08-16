# tests/test_generate_kimi.py
from pathlib import Path
import json
import yaml
import pytest
from geo.generate.kimi import playbook_digest, generate_draft, skeleton_draft, GenerateError

FIX = Path(__file__).parent / "fixtures" / "generate"

def test_playbook_digest_parses_week_and_formats():
    d = playbook_digest((FIX / "knowledge" / "playbook.md").read_text(encoding="utf-8"))
    assert d["week"] == 1
    by_key = {f["key"]: f for f in d["formats"]}
    assert by_key["comparison_table"] == {"key": "comparison_table", "cited_n": 4, "sample_n": 6, "confidence": "ok"}
    assert by_key["definition"]["confidence"] == "low"

def test_playbook_digest_empty_text():
    d = playbook_digest("")
    assert d["week"] is None and d["formats"] == []

def test_playbook_digest_unrelated_text():
    d = playbook_digest("# 别的文档\nnothing here")
    assert d["week"] is None and d["formats"] == []

_BRAND = yaml.safe_load((FIX / "knowledge" / "brand.yaml").read_text(encoding="utf-8"))
_DIGEST = {"week": 1, "formats": [{"key": "comparison_table", "cited_n": 4, "sample_n": 6, "confidence": "ok"}],
           "templates_note": "对比表优先"}

_GOOD_KIMI = {
    "frontmatter": {"topic": "How to size a home battery", "page_type": "guide", "slug": "how-to-size-a-home-battery"},
    "title": "How to size a home battery",
    "body_md": "# How to size a home battery\n\nA common starting point is 5–15 kWh; the battery carries a 10-year warranty.",
    "json_ld": [{"@context": "https://schema.org", "@type": "Article", "headline": "How to size a home battery"}],
    "fact_anchors": [{"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
                     {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}],
}

def _ok_chat(payload):
    def chat_fn(messages, tools=None, timeout=120):
        assert "BRAND FACTS" in messages[1]["content"]
        return json.dumps(payload, ensure_ascii=False)
    return chat_fn

def test_generate_draft_ok():
    d = generate_draft("How to size a home battery", "guide", _BRAND, _DIGEST,
                       chat_fn=_ok_chat(_GOOD_KIMI))
    assert d["frontmatter"]["slug"] == "how-to-size-a-home-battery"
    assert d["fact_anchors"][0]["path"] == "products[home-battery].specs.capacity_kwh"

def test_generate_draft_retries_once_then_raises():
    calls = {"n": 0}
    def flaky(messages, tools=None, timeout=120):
        calls["n"] += 1
        return "not json"
    with pytest.raises(GenerateError, match="两次失败"):
        generate_draft("t", "guide", _BRAND, _DIGEST, chat_fn=flaky)
    assert calls["n"] == 2

def test_skeleton_draft_deterministic():
    d1 = skeleton_draft("t", "spec", _BRAND)
    d2 = skeleton_draft("t", "spec", _BRAND)
    assert d1 == d2
    assert "LiFePO4" in d1["body_md"]
    assert d1["frontmatter"]["page_type"] == "spec"
