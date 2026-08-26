"""Doubao collection client tests (offline, fixture-based)."""

import json
from pathlib import Path

import pytest

# Import functions we'll implement
from geo.collect.doubao_client import parse_doubao_response, _harvest

FX = Path(__file__).parent / "fixtures/raw"


def load(pid: str) -> dict:
    """Load fixture by prompt ID."""
    path = FX / f"doubao_{pid}.json"
    if not path.exists():
        pytest.skip(f"Fixture doubao_{pid}.json pending")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_doubao_c01():
    """Test parsing Doubao C01 response (~3 search results)."""
    fx = load("C01")
    out = parse_doubao_response(fx["response"])

    # Should have answer text
    assert out["answer"].strip()

    # Search results should be extracted from annotations
    assert out["search_results"]
    assert all("url" in s for s in out["search_results"])

    # Should have 3 unique URLs (from fixture inspection)
    assert len(out["search_results"]) == 3

    # All URLs should be unique
    urls = [s["url"] for s in out["search_results"]]
    assert len(urls) == len(set(urls)), "All URLs should be unique"


def test_parse_doubao_b02():
    """Test parsing Doubao B02 response (~12 search results)."""
    fx = load("B02")
    out = parse_doubao_response(fx["response"])

    # Should have answer text
    assert out["answer"].strip()

    # Search results should be extracted from annotations
    assert out["search_results"]
    assert all("url" in s for s in out["search_results"])

    # Should have 12 unique URLs (from fixture inspection)
    assert len(out["search_results"]) == 12

    # All URLs should be unique
    urls = [s["url"] for s in out["search_results"]]
    assert len(urls) == len(set(urls)), "All URLs should be unique"


def test_parse_doubao_d01():
    """Test parsing Doubao D01 response (~7 search results)."""
    fx = load("D01")
    out = parse_doubao_response(fx["response"])

    # Should have answer text
    assert out["answer"].strip()

    # Search results should be extracted from annotations
    assert out["search_results"]
    assert all("url" in s for s in out["search_results"])

    # Should have 7 unique URLs (from fixture inspection)
    assert len(out["search_results"]) == 7

    # All URLs should be unique
    urls = [s["url"] for s in out["search_results"]]
    assert len(urls) == len(set(urls)), "All URLs should be unique"


def test_harvest():
    """Test recursive URL harvesting helper."""
    # Simple string
    assert _harvest("Check https://example.com and https://test.com") == [
        "https://example.com",
        "https://test.com",
    ]

    # Nested structure
    data = {
        "text": "Visit https://example.com",
        "items": [{"url": "https://test.com"}, ["https://another.com"]],
    }
    urls = _harvest(data)
    assert "https://example.com" in urls
    assert "https://test.com" in urls
    assert "https://another.com" in urls

    # URL cleanup (removes query params and trailing punctuation)
    assert _harvest("Go to https://example.com?foo=bar and then https://test.com.") == [
        "https://example.com",
        "https://test.com",
    ]

    # Empty/None cases
    assert _harvest("") == []
    assert _harvest([]) == []
    assert _harvest(None) == []


# Fix(2026-08-24 审查#1): annotations 是 provider 明证的"引用"(url_citation
# 附着在 message 内容上),须与"检索"区分暴露,供 parse_l2 单独采信。
def test_parse_doubao_exposes_attested_citations():
    """annotations 同时出现在 search_results(检索视图)与 citations(明证引用视图)。"""
    fx = load("C01")
    out = parse_doubao_response(fx["response"])
    assert out["citations"], "url_citation annotations 必须进入 citations 键"
    ann_urls = [s["url"] for s in out["citations"]]
    assert len(ann_urls) == len(set(ann_urls))
    # C01 有 3 条 annotation 引用
    assert len(ann_urls) == 3
    # 检索视图(向后兼容)与明证视图同源
    assert ann_urls == [s["url"] for s in out["search_results"]]


def test_collect_doubao_passes_citations_through(monkeypatch):
    """二次审查(2026-08-25)#1: parse 出的 citations 必须随客户端返回值交给 L2。

    线上断链复现: parse_doubao_response 已产出 citations,但 collect_doubao
    返回 dict 丢弃了该键 → L2 的 attested 路径永远拿不到豆包明证引用,
    答案只有 annotation、无裸 URL 时真实引用被漏报为"未引用"。
    """
    import geo.collect.doubao_client as dc
    fx = load("C01")

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return fx["response"]

    class _Client:
        def __init__(self, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): return _Resp()

    monkeypatch.setattr(dc.httpx, "Client", _Client)
    out = dc.collect_doubao("prompt")
    expected = parse_doubao_response(fx["response"])["citations"]
    assert out.get("citations") == expected, "collect_doubao 必须透传 citations 给 L2"


def test_parse_doubao_citations_empty_on_harvest_fallback(monkeypatch):
    """无 annotations 走 _harvest 兜底时,citations 必须为空——harvest 出的是检索,不是引用。"""
    raw = {"output": [{"type": "message",
                       "content": [{"type": "output_text", "text": "answer",
                                    "annotations": None}]}]}
    # 强制 annotations 路径不产出 → 落到 harvest 兜底
    raw = {"output": [{"type": "message",
                       "content": [{"type": "output_text", "text": "see https://a.com/x"}]}]}
    out = parse_doubao_response(raw)
    assert out["search_results"] == [{"url": "https://a.com/x", "title": ""}]
    assert out["citations"] == []
