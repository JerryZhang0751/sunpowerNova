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
    assert len(it.sources) == 3  # extended to 3 sources for coverage testing

    # First source: resolved L3 (js_only: false)
    cited, l3 = it.sources[0]
    assert cited.url == "https://www.cnet.com/x"
    assert l3 is not None and l3.structural["table_count"] == 1   # L3 resolved

    # Second source: missing L3 (no meta.json)
    cited, l3 = it.sources[1]
    assert cited.url == "https://example.com/missing"
    assert l3 is None  # No meta.json exists

    # Third source: js_only L3 (meta.json exists but js_only: true)
    cited, l3 = it.sources[2]
    assert cited.url == "https://example.com/jsonly"
    assert l3 is None  # js_only sources are paired as None for Task 4

    # Coverage counts should be correct
    assert corpus.coverage.total_l1 == 1
    assert corpus.coverage.total_cited_sources == 3
    assert corpus.coverage.l3_resolved == 1  # only cnet.com
    assert corpus.coverage.l3_missing == 1  # only example.com/missing
    assert corpus.coverage.l3_js_only == 1  # only example.com/jsonly
    assert corpus.gsc_queries == ["hestia solar"]
