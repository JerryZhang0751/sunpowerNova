# tests/test_corpus.py
from pathlib import Path
from geo.research.corpus import build_corpus
import json, hashlib

FIX = Path(__file__).parent / "fixtures" / "research"

def test_build_corpus_joins_and_counts():
    corpus = build_corpus(1, repo=FIX)
    assert corpus.week == 1
    assert len(corpus.items) == 1
    it = corpus.items[0]
    assert it.l1.prompt_id == "C01"
    assert it.prompt.category == "comparison"
    assert len(it.sources) == 1
    cited, l3 = it.sources[0]
    assert cited.url == "https://www.cnet.com/x"
    assert l3 is not None and l3.structural["table_count"] == 1   # L3 resolved
    assert corpus.coverage.total_l1 == 1
    assert corpus.coverage.total_cited_sources == 1
    assert corpus.coverage.l3_resolved == 1
    assert corpus.gsc_queries == ["hestia solar"]
