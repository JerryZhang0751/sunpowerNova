# tests/test_research_models.py
from geo.research.models import (ResearchItem, Coverage, ResearchCorpus, FeatureBucket,
    FeatureAggregates, PlaybookConclusion, FetchStats)
from geo.shared.models import L1Record, L2Record, CitedSource, PromptRow

def test_researchcorpus_roundtrip():
    l1 = L1Record(week=1, model="qwen", prompt_id="C01", run=1, answer="x",
                  l2=L2Record(cited_sources=[CitedSource(position=1, url="https://a.com")]),
                  ts_iso="2026-08-13T00:00:00Z", prompt_set_version="abc")
    prompt = PromptRow(id="C01", category="comparison", prompt="q", market="EU", intent="comparison", core=True)
    item = ResearchItem(l1=l1, prompt=prompt, sources=[(l1.l2.cited_sources[0], None)])
    cov = Coverage(total_l1=1, total_cited_sources=1, l3_resolved=0, l3_missing=1, l3_js_only=0)
    corpus = ResearchCorpus(week=1, items=[item], gsc_queries=["hestia solar"], coverage=cov)
    assert corpus.coverage.total_cited_sources == 1

def test_featurebucket_low_confidence_flag():
    b = FeatureBucket(key="comparison_table", cited_n=2, sample_n=3, platforms=["qwen"], low_confidence=True)
    assert b.low_confidence is True

def test_playbookconclusion_fields():
    c = PlaybookConclusion(id="F01", category="format", conclusion="对比表常见", sample_n=45,
                           cited_n=12, platforms=["qwen","zhipu"], confidence="high",
                           action="多用对比表", examples=["https://a.com"])
    assert c.category == "format" and c.confidence == "high"

def test_fetchstats():
    f = FetchStats(requested=40, fetched=35, failed=3, js_only=2)
    assert f.fetched == 35
