# tests/test_sample.py
from geo.research.sample import select_topn
from geo.research.corpus import build_corpus
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "research"

def _corpus():
    return build_corpus(1, repo=FIX)

def test_select_topn_ranks_external_excludes_brand(tmp_path):
    # tmp_path has no sources dir → urls not yet fetched → returned
    # T9(2026-09-02 D1): select_topn 周感知——fixture 数据在 w1/ 下,week=1。
    urls = select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=tmp_path, week=1)
    # With 3 external sources (cnet, missing, jsonly), all should be returned when none are fetched
    # Order is by frequency: all have frequency 1, so order matches appearance order
    assert set(urls) == {"https://www.cnet.com/x", "https://example.com/missing", "https://example.com/jsonly"}

def test_select_topn_caps_at_n(tmp_path):
    assert len(select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=tmp_path, week=1)) <= 40

def test_select_topn_excludes_already_fetched():
    # FIX has cnet and jsonly source meta.json under w1/ → already fetched → excluded
    # But example.com/missing has no meta.json → not fetched → included
    urls = select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=FIX, week=1)
    assert urls == ["https://example.com/missing"]

def test_fetch_topn_counts_js_only(monkeypatch):
    from geo.research.sample import fetch_topn
    from unittest.mock import MagicMock
    # 三个 URL 依序返回: js_only / 正常 / 抛错(失败)
    results = [MagicMock(js_only=True), MagicMock(js_only=False), None]
    it = iter(results)
    def fake(u, week=None):
        v = next(it)
        if v is None: raise RuntimeError("x")
        return v
    monkeypatch.setattr("geo.fetch.fetcher.fetch_source", fake)
    st = fetch_topn(["a/js", "b/doc", "c/dead"], week=901)
    assert st.requested == 3 and st.fetched == 2 and st.failed == 1 and st.js_only == 1
