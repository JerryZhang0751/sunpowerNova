# tests/test_generate_kimi.py
from pathlib import Path
from geo.generate.kimi import playbook_digest

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
