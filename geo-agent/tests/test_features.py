# tests/test_features.py
from geo.research.corpus import build_corpus, ResearchCorpus, Coverage
from geo.research.features import aggregate, LOW_CONF_THRESHOLD
from geo.research.models import ResearchItem, CitedSource, L3Source, L1Record, PromptRow
from geo.shared.models import L2Record
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "research"

def _corpus():
    return build_corpus(1, repo=FIX)

def test_aggregate_formats_bucket_counts():
    agg = aggregate(_corpus())
    keys = {b.key for b in agg.formats}
    assert {"comparison_table","qa","list","definition","spec_card"} <= keys
    tbl = next(b for b in agg.formats if b.key == "comparison_table")
    assert tbl.cited_n == 1 and tbl.sample_n == 1          # fixture: 3 cited sources but only 1 resolved (cnet has table, missing/js_only have no l3)
    assert tbl.low_confidence is True                       # sample_n=1 < threshold(5)

def test_aggregate_platforms_metrics():
    agg = aggregate(_corpus())
    assert "qwen" in agg.platforms
    assert agg.platforms["qwen"]["n"] == 1

def test_aggregate_problem_space_has_intents():
    agg = aggregate(_corpus())
    assert any(c["intent"] == "comparison" for c in agg.problem_space["intent_clusters"])

def test_aggregate_sources_counts_ugc():
    # Test UGC counting with in-memory corpus (no shared fixture modification)

    # Create UGC L3 source with forum structure
    ugc_l3 = L3Source(
        url="https://www.reddit.com/r/solar",
        sha1="abcd12345678",
        structural={"canonical": "https://www.reddit.com/r/solar", "title": "Reddit discussion", "table_count": 0},
        semantic={"page_type": "forum", "has_definition_segment": False, "has_faq_block": False, "datapoint_count": 0},
        js_only=False,
        fetched_iso="2026-08-13T00:00:00Z"
    )

    # Create cited source
    ugc_cited = CitedSource(position=1, url="https://www.reddit.com/r/solar", title="Reddit discussion", extract_method="structured")

    # Create L1 record
    ugc_l1 = L1Record(
        week=1,
        model="test",
        prompt_id="UGC01",
        run=1,
        answer="Test answer",
        l2=L2Record(cited_sources=[ugc_cited], mentioned=False, cited_with_link=False, citation_position=None, sentiment="neu", competitors_mentioned=[], low_confidence=False),
        usage={},
        elapsed_s=1.0,
        search_triggered=True,
        ts_iso="2026-08-13T00:00:00Z",
        prompt_set_version="test"
    )

    # Create prompt row
    ugc_prompt = PromptRow(id="UGC01", category="test", prompt="Test", market="US", intent="informational", core=False)

    # Create research item with UGC source
    ugc_item = ResearchItem(l1=ugc_l1, prompt=ugc_prompt, sources=[(ugc_cited, ugc_l3)])

    # Create minimal corpus with UGC item
    ugc_corpus = ResearchCorpus(
        week=1,
        items=[ugc_item],
        gsc_queries=["test"],
        coverage=Coverage(total_l1=1, total_cited_sources=1, l3_resolved=1, l3_missing=0, l3_js_only=0)
    )

    agg = aggregate(ugc_corpus)
    assert agg.sources["ugc"] >= 1, "UGC sources (Reddit/forum) should be counted in sources['ugc']"
