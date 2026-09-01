"""Qwen collection client tests (offline, fixture-based)."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import functions we'll implement
from geo.collect.qwen_client import parse_qwen_response, _mm_text, collect_qwen, QwenAPIError

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


class _Chunk:
    """Minimal stand-in for a DashScope stream chunk (plain attrs, dict output)."""

    def __init__(self, text, usage=None):
        self.output = {"choices": [{"message": {"content": [{"text": text}]}}]}
        self.usage = usage or {}


def test_collect_qwen_passes_request_timeout():
    """collect_qwen must pass an explicit request_timeout to DashScope.

    DashScope semantics (sdk http_request.py): for streaming calls, request_timeout
    is the idle timeout between chunks (sock_read). Relying on the invisible SDK
    default (300s) leaves the hang defense undocumented and unconfigurable — the
    doubao/zhipu clients already pass timeout=300.0 explicitly.
    """
    mm = MagicMock()
    mm.call.return_value = iter([_Chunk("ok", usage={"total_tokens": 1})])
    with patch("geo.collect.qwen_client.MultiModalConversation", mm):
        out = collect_qwen("hello")
    assert mm.call.call_args.kwargs.get("request_timeout") == 300
    assert out["answer"] == "ok"


def test_collect_qwen_raises_api_error_chunk():
    """流首错误块(如额度耗尽)必须抛 QwenAPIError 透传真实错误码,不得聚合成空答案。

    2026-09-01 w3 实跑:DashScope 免费额度中途耗尽,每题 0.2s 返回 code=Unknown +
    message 含 AllocationQuota.FreeTierOnly 的错误块;旧代码把它当普通块聚合成
    空答案,collector 只报"qwen 返回空答案",真实原因(账号额度)被吞。
    """
    class _ErrChunk:
        code = "Unknown"
        message = ('{"request_id":"x","code":"AllocationQuota.FreeTierOnly",'
                   '"message":"Free quota exhausted."}')
        output = {}

    mm = MagicMock()
    mm.call.return_value = iter([_ErrChunk()])
    with patch("geo.collect.qwen_client.MultiModalConversation", mm):
        with pytest.raises(QwenAPIError, match="AllocationQuota.FreeTierOnly"):
            collect_qwen("hello")


def test_collect_qwen_error_chunk_after_content_still_raises():
    """错误块出现在内容块之后(流中途失败)同样要抛,不得返回残缺答案当成功。"""
    class _ErrChunk:
        code = "InvalidParameter"
        message = "bad thing"
        output = {}

    mm = MagicMock()
    mm.call.return_value = iter([_Chunk("partial answer"), _ErrChunk()])
    with patch("geo.collect.qwen_client.MultiModalConversation", mm):
        with pytest.raises(QwenAPIError, match="InvalidParameter"):
            collect_qwen("hello")


def test_collect_qwen_enforces_total_budget(monkeypatch):
    """The stream loop must enforce a TOTAL wall-clock budget, not just the SDK's
    idle-between-chunks timeout: a slow-drip stream (one chunk every <300s) could
    otherwise run unboundedly long and stall the collector's executor."""
    from geo.collect import qwen_client

    drip = [_Chunk(f"c{i}") for i in range(500)]  # finite so RED fails, not hangs
    monkeypatch.setattr(qwen_client, "TOTAL_BUDGET_S", 0.0, raising=False)
    mm = MagicMock()
    mm.call.return_value = iter(drip)
    with patch("geo.collect.qwen_client.MultiModalConversation", mm):
        out = collect_qwen("hello")

    assert out["answer"] == "", "budget must stop aggregation before consuming chunks"
    assert out.get("timeout") is True, "partial result must be marked as timed out"
