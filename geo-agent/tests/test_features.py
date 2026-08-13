# tests/test_features.py
from geo.research.corpus import build_corpus
from geo.research.features import aggregate, LOW_CONF_THRESHOLD
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "research"

def _corpus():
    return build_corpus(1, repo=FIX)

def test_aggregate_formats_bucket_counts():
    agg = aggregate(_corpus())
    keys = {b.key for b in agg.formats}
    assert {"comparison_table","qa","list","definition","spec_card"} <= keys
    tbl = next(b for b in agg.formats if b.key == "comparison_table")
    assert tbl.cited_n == 1 and tbl.sample_n == 1          # fixture: 1 cited source w/ table
    assert tbl.low_confidence is True                       # sample_n=1 < threshold(5)

def test_aggregate_platforms_metrics():
    agg = aggregate(_corpus())
    assert "qwen" in agg.platforms
    assert agg.platforms["qwen"]["n"] == 1

def test_aggregate_problem_space_has_intents():
    agg = aggregate(_corpus())
    assert any(c["intent"] == "comparison" for c in agg.problem_space["intent_clusters"])
