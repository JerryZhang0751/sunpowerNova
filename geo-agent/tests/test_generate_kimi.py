# tests/test_generate_kimi.py
from pathlib import Path
import json
import httpx
import openai
import yaml
import pytest
from geo.generate.kimi import playbook_digest, generate_draft, skeleton_draft, GenerateError

FIX = Path(__file__).parent / "fixtures" / "generate"

def test_playbook_digest_parses_week_and_formats():
    d = playbook_digest((FIX / "knowledge" / "playbook.md").read_text(encoding="utf-8"))
    assert d["week"] == 1
    by_key = {f["key"]: f for f in d["formats"]}
    assert by_key["comparison_table"] == {"key": "comparison_table", "cited_n": 4, "sample_n": 6, "confidence": "ok"}
    assert by_key["definition"]["confidence"] == "low"

def test_playbook_digest_empty_text():
    d = playbook_digest("")
    assert d["week"] is None and d["formats"] == []

def test_playbook_digest_unrelated_text():
    d = playbook_digest("# 别的文档\nnothing here")
    assert d["week"] is None and d["formats"] == []

_BRAND = yaml.safe_load((FIX / "knowledge" / "brand.yaml").read_text(encoding="utf-8"))
_DIGEST = {"week": 1, "formats": [{"key": "comparison_table", "cited_n": 4, "sample_n": 6, "confidence": "ok"}],
           "templates_note": "对比表优先"}

_GOOD_KIMI = {
    "frontmatter": {"topic": "How to size a home battery", "page_type": "guide", "slug": "how-to-size-a-home-battery"},
    "title": "How to size a home battery",
    "body_md": "# How to size a home battery\n\nA common starting point is 5–15 kWh; the battery carries a 10-year warranty.",
    "json_ld": [{"@context": "https://schema.org", "@type": "Article", "headline": "How to size a home battery"}],
    "fact_anchors": [{"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
                     {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}],
}

def _ok_chat(payload):
    def chat_fn(messages, tools=None, timeout=120):
        assert "BRAND FACTS" in messages[1]["content"]
        return json.dumps(payload, ensure_ascii=False)
    return chat_fn

def test_generate_draft_ok():
    d = generate_draft("How to size a home battery", "guide", _BRAND, _DIGEST,
                       chat_fn=_ok_chat(_GOOD_KIMI))
    assert d["frontmatter"]["slug"] == "how-to-size-a-home-battery"
    assert d["fact_anchors"][0]["path"] == "products[home-battery].specs.capacity_kwh"

def test_generate_draft_retries_once_then_raises():
    calls = {"n": 0}
    def flaky(messages, tools=None, timeout=120):
        calls["n"] += 1
        return "not json"
    with pytest.raises(GenerateError, match="两次失败"):
        generate_draft("t", "guide", _BRAND, _DIGEST, chat_fn=flaky)
    assert calls["n"] == 2

def test_skeleton_draft_deterministic():
    d1 = skeleton_draft("t", "spec", _BRAND)
    d2 = skeleton_draft("t", "spec", _BRAND)
    assert d1 == d2
    assert "LiFePO4" in d1["body_md"]
    assert d1["frontmatter"]["page_type"] == "spec"


def test_kimi_chat_timeout_covers_documented_tail():
    """generate 草稿是长补全,Kimi 实测响应 50–215s(模型记录);180s 默认超时在
    w3 实跑(2026-09-01)连续两次掐死正常生成。默认超时须 ≥300s 覆盖已记录长尾。

    codex w3 修改二(2026-09-02): 同时断言 max_retries == 0——SDK 层默认
    max_retries=2 会与业务层 generate_draft 的 2 次重试叠加成最多 6 个 HTTP
    请求、超长阻塞;重试责任只留业务层一层。"""
    from unittest.mock import patch, MagicMock
    from geo.generate.kimi import _kimi_chat
    with patch("openai.OpenAI") as oi:
        resp = MagicMock()
        resp.choices[0].message.content = "ok"
        oi.return_value.chat.completions.create.return_value = resp
        out = _kimi_chat([{"role": "user", "content": "hi"}])
    assert out == "ok"
    assert oi.call_args.kwargs.get("timeout") >= 300, \
        f"timeout={oi.call_args.kwargs.get('timeout')} 低于实测长尾 215s"
    assert oi.call_args.kwargs.get("max_retries") == 0, \
        f"max_retries={oi.call_args.kwargs.get('max_retries')} 须为 0(重试只在业务层)"


def test_generate_draft_makes_at_most_two_http_attempts():
    """codex w3 修改二: 单次 generate_draft 最多触发 2 个底层 HTTP 请求——
    走真 _kimi_chat + mock openai.OpenAI(禁联网),create 恒失败时恰好 2 次。"""
    from unittest.mock import patch
    import geo.generate.kimi as gk
    with patch("openai.OpenAI") as oi:
        oi.return_value.chat.completions.create.side_effect = RuntimeError("Request timed out.")
        with pytest.raises(GenerateError, match="两次失败"):
            gk.generate_draft("t", "guide", _BRAND, _DIGEST)      # 不注 chat_fn=真 _kimi_chat
        assert oi.return_value.chat.completions.create.call_count == 2


def test_generate_draft_does_not_start_attempt_after_total_budget(monkeypatch):
    """codex w3 修改二: 总预算耗尽后不得启动新一轮尝试(可控 monotonic 时钟,
    不真实等待)——首尝试失败 + 时钟跳过 deadline → chat 只被调 1 次。"""
    import geo.generate.kimi as gk
    seq = iter([0.0, 0.0, 10000.0])            # t0 / 首尝试 remaining / 次尝试 remaining

    class _FakeTime:
        @staticmethod
        def monotonic():
            return next(seq, 10000.0)

    monkeypatch.setattr(gk, "time", _FakeTime)
    calls = {"n": 0}

    def fail_fast(messages, tools=None, timeout=120):
        calls["n"] += 1
        raise RuntimeError("boom")

    with pytest.raises(GenerateError):
        gk.generate_draft("t", "guide", _BRAND, _DIGEST, chat_fn=fail_fast)
    assert calls["n"] == 1, "预算耗尽后不得启动第二次尝试"


# ---- Bug#5(w4): 连接类错误放宽(不耗 token),其它维持 2 次 ----------------------

def _conn_err():
    return openai.APIConnectionError(
        request=httpx.Request("POST", "https://api.moonshot.cn/v1/chat/completions"))

def test_conn_error_gets_third_attempt(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}
    def chat(messages, tools=None, timeout=120):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _conn_err()
        return json.dumps(_GOOD_KIMI, ensure_ascii=False)
    d = generate_draft("How to size a home battery", "guide", _BRAND, _DIGEST, chat_fn=chat)
    assert d["title"] == "How to size a home battery" and calls["n"] == 3

def test_conn_error_exhausts_at_three(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}
    def chat(messages, tools=None, timeout=120):
        calls["n"] += 1
        raise _conn_err()
    with pytest.raises(GenerateError, match="连接类"):
        generate_draft("t", "guide", _BRAND, _DIGEST, chat_fn=chat)
    assert calls["n"] == 3

def test_mixed_conn_then_value_error_stops_at_two(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}
    def chat(messages, tools=None, timeout=120):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _conn_err()
        return json.dumps({"title": "t"})          # 缺键 → ValueError(非连接类)
    with pytest.raises(GenerateError, match="两次失败"):
        generate_draft("t", "guide", _BRAND, _DIGEST, chat_fn=chat)
    assert calls["n"] == 2
