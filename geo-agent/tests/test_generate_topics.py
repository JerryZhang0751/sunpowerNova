# tests/test_generate_topics.py
import json, shutil
from pathlib import Path
from geo.generate.topics import suggest_topics

FIX = Path(__file__).parent / "fixtures" / "generate"

def test_suggest_topics_eval_gaps_first():
    out, missing = suggest_topics(1, repo=FIX)
    assert missing == []
    gaps = [s for s in out if s["source"] == "eval_gap"]
    # score<50 的三个维度：content_eeat(1.4) < eeat(25) < citability(32)，升序
    assert [g["detail"] for g in gaps] == ["content_eeat=1.4", "eeat=25.0", "citability=32.0"]
    assert gaps[0]["page_type"] in ("faq", "spec", "comparison", "guide")
    assert all(g["topic"] for g in gaps)

def test_suggest_topics_gsc_by_impressions():
    out, _ = suggest_topics(1, repo=FIX)
    gsc = [s for s in out if s["source"] == "gsc"]
    assert [s["topic"] for s in gsc] == ["lifepo4 battery", "photovoltaic self consumption", "hestia solar"]
    assert gsc[0]["detail"] == "impressions=9"

def test_suggest_topics_missing_sources_reported(tmp_path):
    out, missing = suggest_topics(2, repo=tmp_path)   # 空 repo
    assert out == []
    assert len(missing) == 2 and any("eval_report" in m for m in missing)
