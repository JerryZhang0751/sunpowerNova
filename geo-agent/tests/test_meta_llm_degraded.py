"""T13(2026-09-02): 静默降级可见化 —— Kimi 语义提取的 degraded 标志契约。

- extract_semantic 返回 (semantic, degraded):失败不再与"无语义字段"不可区分
  (旧行为 Kimi 失败返回 {} → E-E-A-T 静默清零);
- 空文本 = 无从提取,非降级 → ({}, False);
- fetcher 解包后落 L3Source.semantic_degraded(meta.json 持久可见)。
评分零变化由黄金锁(test_v1_semantics)另证;本文件全部离线(mock 网络+Kimi)。
"""
import ipaddress
import json
from unittest.mock import MagicMock, patch

from geo.fetch import meta_llm
from geo.fetch.fetcher import fetch_source
from geo.shared.models import L3Source
from geo.shared.storage import sha1_url

# 足量正文,保证 trafilatura 抽出非空文本(fetcher 只在 text.strip() 时走语义)
HTML = ("<html><body><p>"
        + "SunHestia stores rooftop solar energy in a modular lithium battery. " * 80
        + "</p></body></html>")


def _kimi_boom(*a, **kw):
    raise RuntimeError("kimi down")


def _client_returning(content: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    client = MagicMock()
    client.chat.completions.create.return_value = resp
    return client


def test_extract_semantic_failure_returns_degraded_flag(monkeypatch, caplog):
    """Kimi 失败 → ({}, True) + warning;空文本 → ({}, False) 不算降级。"""
    monkeypatch.setattr(meta_llm, "make_kimi_client", _kimi_boom)   # T4 注入点
    with caplog.at_level("WARNING"):
        sem, degraded = meta_llm.extract_semantic("some page text")
    assert sem == {} and degraded is True
    assert caplog.records, "Kimi 失败必须 warning(静默降级可见化)"
    sem2, degraded2 = meta_llm.extract_semantic("")   # 空文本=未降级(无从提取)
    assert sem2 == {} and degraded2 is False


def test_extract_semantic_success_returns_not_degraded(monkeypatch):
    """成功且 JSON 为对象 → (dict, False)。"""
    monkeypatch.setattr(meta_llm, "make_kimi_client",
                        lambda *a, **kw: _client_returning(json.dumps({"page_type": "product"})))
    sem, degraded = meta_llm.extract_semantic("text")
    assert sem == {"page_type": "product"} and degraded is False


def test_extract_semantic_non_dict_json_not_degraded(monkeypatch):
    """JSON 合法但非对象(如 list)→ ({}, False):请求成功、仅无字段,非降级。"""
    monkeypatch.setattr(meta_llm, "make_kimi_client",
                        lambda *a, **kw: _client_returning('["not", "an", "object"]'))
    sem, degraded = meta_llm.extract_semantic("text")
    assert sem == {} and degraded is False


def test_extract_semantic_unparseable_json_is_degraded(monkeypatch, caplog):
    """HTTP 成功但 content 非 JSON → 解析失败与 Kimi 失败同径,计降级。"""
    monkeypatch.setattr(meta_llm, "make_kimi_client",
                        lambda *a, **kw: _client_returning("{not json"))
    with caplog.at_level("WARNING"):
        sem, degraded = meta_llm.extract_semantic("text")
    assert sem == {} and degraded is True
    assert caplog.records


# ---- fetcher 解包:degraded 落 L3Source(meta.json 持久可见) ----

def _httpx_mock():
    client = MagicMock()
    client.get.side_effect = lambda url, **kw: MagicMock(
        status_code=200, text=HTML, is_redirect=False)
    client.__enter__.return_value = client
    return client


def _fetch_with_sem(week, sem_return, tmp_path, url="https://example.com/page"):
    import geo.shared.storage as _storage
    import geo.fetch.fetcher as _fetcher
    with patch.object(_storage, "REPO", tmp_path), \
         patch("geo.fetch.url_guard._resolve_ips",
               return_value=[ipaddress.ip_address("93.184.216.34")]), \
         patch("httpx.Client", return_value=_httpx_mock()), \
         patch.object(_fetcher, "extract_semantic", return_value=sem_return):
        rec = fetch_source(url, week=week, fetcher_kimi=True)
    return rec, url


def test_fetcher_persists_semantic_degraded_true(tmp_path):
    rec, url = _fetch_with_sem(902, ({}, True), tmp_path)
    assert rec.semantic == {} and rec.semantic_degraded is True
    meta = json.loads((tmp_path / "data" / "sources" / "w902" /
                       sha1_url(url)[:12] / "meta.json").read_text(encoding="utf-8"))
    assert meta["semantic_degraded"] is True, "降级标志必须落盘可见"


def test_fetcher_semantic_healthy_flag_false(tmp_path):
    rec, _ = _fetch_with_sem(903, ({"page_type": "faq"}, False), tmp_path)
    assert rec.semantic == {"page_type": "faq"} and rec.semantic_degraded is False


def test_fetcher_kimi_off_defaults_not_degraded(tmp_path):
    """fetcher_kimi=False(不走语义)→ 语义空且非降级(既有行为,显式锁定)。"""
    import geo.shared.storage as _storage
    with patch.object(_storage, "REPO", tmp_path), \
         patch("geo.fetch.url_guard._resolve_ips",
               return_value=[ipaddress.ip_address("93.184.216.34")]), \
         patch("httpx.Client", return_value=_httpx_mock()):
        rec = fetch_source("https://example.com/off", week=904, fetcher_kimi=False)
    assert rec.semantic == {} and rec.semantic_degraded is False


def test_l3source_default_backward_compatible():
    """存量 meta.json 无该字段 → pydantic 默认 False(w1-w3 归档零漂移)。"""
    assert L3Source(url="u", sha1="s").semantic_degraded is False
