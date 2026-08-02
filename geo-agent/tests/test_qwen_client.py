"""Qwen collection client tests (offline, fixture-based)."""

import json
from pathlib import Path

import pytest

# Import functions we'll implement
from geo.collect.qwen_client import parse_qwen_response, _mm_text

FX = Path(__file__).parent / "fixtures/raw"


def load(pid: str) -> dict:
    """Load fixture by prompt ID."""
    path = FX / f"qwen_{pid}.json"
    if not path.exists():
        pytest.skip(f"Fixture qwen_{pid}.json pending")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_qwen_c01():
    """Test parsing Qwen C01 response (~55 search results)."""
    fx = load("C01")
    out = parse_qwen_response(fx["response"])

    # Should have answer text
    assert out["answer"].strip()

    # Search results should match fixture exactly
    srs = fx["response"]["search_info"]["search_results"]
    assert out["search_results"] == srs

    # Validate structure and count
    assert len(out["search_results"]) == 58  # Fixture has 58 results
    assert all(isinstance(s, dict) and "url" in s for s in out["search_results"])

    # All URLs should be unique
    urls = [s["url"] for s in out["search_results"]]
    assert len(urls) == len(set(urls)), "All URLs should be unique"


def test_parse_qwen_b02():
    """Test parsing Qwen B02 response (~57 search results)."""
    fx = load("B02")
    out = parse_qwen_response(fx["response"])

    # Should have answer text
    assert out["answer"].strip()

    # Search results should match fixture exactly
    srs = fx["response"]["search_info"]["search_results"]
    assert out["search_results"] == srs

    # Validate structure and count
    assert len(out["search_results"]) == 57
    assert all(isinstance(s, dict) and "url" in s for s in out["search_results"])

    # All URLs should be unique
    urls = [s["url"] for s in out["search_results"]]
    assert len(urls) == len(set(urls)), "All URLs should be unique"


def test_parse_qwen_d01():
    """Test parsing Qwen D01 response (no search results)."""
    fx = load("D01")
    out = parse_qwen_response(fx["response"])

    # Should have answer text
    assert out["answer"].strip()

    # Should have no search results
    assert out["search_results"] == []
    assert len(out["search_results"]) == 0


def test_mm_text():
    """Test multimodal text extraction helper."""
    # Simple string
    assert _mm_text("hello") == "hello"

    # Flat list with strings and dicts
    content = ["hello ", {"text": "world"}, " foo"]
    assert _mm_text(content) == "hello world foo"

    # Nested list
    content = ["a", ["b", {"text": "c"}], "d"]
    assert _mm_text(content) == "abcd"

    # Empty/None cases
    assert _mm_text("") == ""
    assert _mm_text([]) == ""
    assert _mm_text(None) == ""
