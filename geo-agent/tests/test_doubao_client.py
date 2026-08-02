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
