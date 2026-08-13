# tests/test_sample.py
from geo.research.sample import select_topn
from geo.research.corpus import build_corpus
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "research"

def _corpus():
    return build_corpus(1, repo=FIX)

def test_select_topn_ranks_external_excludes_brand(tmp_path):
    # tmp_path has no sources dir → url not yet fetched → returned
    urls = select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=tmp_path)
    assert urls == ["https://www.cnet.com/x"]

def test_select_topn_caps_at_n(tmp_path):
    assert len(select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=tmp_path)) <= 40

def test_select_topn_excludes_already_fetched():
    # FIX has the source meta.json → already fetched → excluded
    assert select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=FIX) == []
