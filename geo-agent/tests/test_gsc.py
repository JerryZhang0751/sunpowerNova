import logging
import requests
from unittest.mock import patch, MagicMock
import pytest
from pathlib import Path
from geo.fetch.gsc import snapshot_gsc, _gsc_session, _resolve_gsc_key, GSC_TIMEOUT_S
from geo.shared.config import settings
from geo.shared.weeks import TEST_WEEK

def _resp(json_data=None, status=200):
    m = MagicMock()
    m.status_code = status
    if status >= 400:
        m.raise_for_status.side_effect = requests.HTTPError(f"{status}")
    m.json.return_value = json_data or {}
    return m

def test_gsc_degrades_on_auth_error(iso_snapshots, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    with patch("geo.fetch.gsc._gsc_session", return_value=MagicMock(
            post=MagicMock(return_value=_resp(status=403)))):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is True and out["rows"] == []

def test_gsc_http_sets_timeout(iso_snapshots, monkeypatch):
    """每个 GSC 请求必须带显式超时——否则经代理的挂起会卡死 snapshot_node
    (原 httplib2 教训,transport 无关地保下来)。"""
    monkeypatch.setattr("time.sleep", lambda s: None)
    sess = MagicMock()
    sess.post.return_value = _resp({"rows": []})
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert sess.post.call_args.kwargs.get("timeout") == GSC_TIMEOUT_S

def test_gsc_happy(iso_snapshots):
    sess = MagicMock()
    sess.post.return_value = _resp({"rows": [{"keys": ["solar battery"], "clicks": 3,
                                              "impressions": 50, "ctr": 0.06, "position": 4.2}]})
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["rows"][0]["keys"] == ["solar battery"] and out["degraded"] is False

def test_gsc_proxy_applied_when_set():
    """settings.proxy 非空 → 主 session 与 token 刷新 session 两处 proxies 都设置;
    为空 → 两处都不设。(原 httplib2 proxy_info 断言的 transport 无关化)"""
    with patch("geo.fetch.gsc.settings") as mock_settings, \
         patch("geo.fetch.gsc._resolve_gsc_key", return_value=Path("/tmp/fake-key.json")), \
         patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file"):
        mock_settings.proxy = "http://127.0.0.1:10808"
        mock_settings.gsc_key_file = "/tmp/fake-key.json"
        sess = _gsc_session()
    want = {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}
    assert dict(sess.proxies) == want
    assert dict(sess._auth_request.session.proxies) == want   # token 刷新走代理
    with patch("geo.fetch.gsc.settings") as mock_settings, \
         patch("geo.fetch.gsc._resolve_gsc_key", return_value=Path("/tmp/fake-key.json")), \
         patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file"):
        mock_settings.proxy = None
        mock_settings.gsc_key_file = "/tmp/fake-key.json"
        sess = _gsc_session()
    assert not sess.proxies and not sess._auth_request.session.proxies

# ---- 2026-08-27 P1④ 快照冻结守卫:干净快照不可重冻结 --------------------

def test_gsc_clean_snapshot_is_frozen(iso_snapshots):
    """干净快照不可重冻结——GSC 28 天窗口会移动,重冻结=毁历史基线。"""
    import json as _json
    from geo.fetch.gsc import snapshot_dir   # iso_snapshots 已 patch → tmp
    p = snapshot_dir(TEST_WEEK) / "gsc.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "geo-seo-v2",
                              "site": "sc-domain:x", "rows": [{"keys": ["frozen"]}], "degraded": False}),
                 encoding="utf-8")
    svc = MagicMock()
    svc.post.return_value = _resp({"rows": [{"keys": ["NEW!"]}]})
    with patch("geo.fetch.gsc._gsc_session", return_value=svc) as mock_sess:
        out = snapshot_gsc(week=TEST_WEEK, rule_version="geo-seo-v2")
    assert out["rows"] == [{"keys": ["frozen"]}]          # 返回现有,未重取
    mock_sess.assert_not_called()                          # 守卫提前 return,拉取不发生

def test_gsc_degraded_snapshot_can_be_refrozen(iso_snapshots, monkeypatch):
    """08-13 的 SSLEOFError 合法重跑 = degraded 例外口径:degraded 快照必须允许重取。"""
    monkeypatch.setattr("time.sleep", lambda s: None)
    import json as _json
    from geo.fetch.gsc import snapshot_dir
    p = snapshot_dir(TEST_WEEK) / "gsc.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "t", "site": "s",
                              "rows": [], "degraded": True, "error": "SSLEOFError"}),
                 encoding="utf-8")
    sess = MagicMock()
    sess.post.return_value = _resp({"rows": [{"keys": ["ok"]}]})
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is False and out["rows"] == [{"keys": ["ok"]}]

def test_gsc_corrupted_snapshot_treated_as_miss(iso_snapshots, monkeypatch):
    """损坏快照(截断/非法 JSON)不得让守卫抛 JSONDecodeError 硬停管线——视为缺失重取并覆写。"""
    monkeypatch.setattr("time.sleep", lambda s: None)
    import json as _json
    from geo.fetch.gsc import snapshot_dir
    p = snapshot_dir(TEST_WEEK) / "gsc.json"
    p.write_text('{"trunc', encoding="utf-8")   # 截断的非法 JSON
    sess = MagicMock()
    sess.post.return_value = _resp({"rows": [{"keys": ["ok"]}]})
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is False and out["rows"] == [{"keys": ["ok"]}]   # 重取到新数据
    assert _json.loads(p.read_text(encoding="utf-8"))["rows"] == [{"keys": ["ok"]}]   # 文件被合法 JSON 覆写

def test_gsc_freeze_warns_on_rule_version_mismatch(iso_snapshots, caplog):
    """2026-08-27 快照冻结守卫的 mismatch 告警分支(此前零覆盖):
    盘上快照 rule_version ≠ 请求版本 → 仍按冻结语义返回旧内容(不重取、
    不覆写历史基线),同时 log.warning 提示版本不一致。"""
    import json as _json
    from geo.fetch.gsc import snapshot_dir
    p = snapshot_dir(TEST_WEEK) / "gsc.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "geo-seo-v2",
                              "site": "sc-domain:x", "rows": [{"keys": ["frozen"]}],
                              "degraded": False}),
                 encoding="utf-8")
    svc = MagicMock()
    svc.post.return_value = _resp({"rows": [{"keys": ["NEW!"]}]})
    with patch("geo.fetch.gsc._gsc_session", return_value=svc) as mock_sess:
        with caplog.at_level(logging.WARNING, logger="fetch.gsc"):
            out = snapshot_gsc(week=TEST_WEEK, rule_version="geo-seo-v3")
    assert out["rows"] == [{"keys": ["frozen"]}]          # 返回冻结内容,未重取
    assert out["rule_version"] == "geo-seo-v2"            # 历史基线版本不被改写
    mock_sess.assert_not_called()                          # 守卫提前 return,拉取不发生
    assert any(r.levelno == logging.WARNING and "规则版本" in r.getMessage()
               for r in caplog.records)


# ---- Bug#2(w4): GSC key 相对路径回退链 --------------------------------------

def test_gsc_key_empty_raises():
    with pytest.raises(ValueError, match="GSC_KEY_FILE"):
        _resolve_gsc_key("")

def test_gsc_key_absolute_passthrough(tmp_path):
    key = tmp_path / "k.json"; key.write_text("{}", encoding="utf-8")
    assert _resolve_gsc_key(str(key)) == key

def test_gsc_key_repo_root_relative_fallback(tmp_path, monkeypatch):
    """w4 复现场景: .env 写 'geo-agent/gsc-x.json'(仓库根相对), CWD 不在仓库根。"""
    root = tmp_path / "proj"; geo_dir = root / "geo-agent"; geo_dir.mkdir(parents=True)
    key = geo_dir / "gsc-x.json"; key.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("geo.fetch.gsc.REPO", geo_dir)
    assert _resolve_gsc_key("geo-agent/gsc-x.json") == key

def test_gsc_key_cwd_relative(tmp_path, monkeypatch):
    key = tmp_path / "k2.json"; key.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _resolve_gsc_key("k2.json") == key

def test_gsc_key_repo_relative(tmp_path, monkeypatch):
    geo_dir = tmp_path / "geo-agent"; geo_dir.mkdir()
    key = geo_dir / "k3.json"; key.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("geo.fetch.gsc.REPO", geo_dir)
    assert _resolve_gsc_key("k3.json") == key

def test_gsc_key_all_miss_lists_candidates(tmp_path, monkeypatch):
    geo_dir = tmp_path / "geo-agent"; geo_dir.mkdir()
    monkeypatch.setattr("geo.fetch.gsc.REPO", geo_dir)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError) as ei:
        _resolve_gsc_key("nope.json")
    msg = str(ei.value)
    assert "nope.json" in msg and str(geo_dir.parent / "nope.json") in msg and str(geo_dir / "nope.json") in msg

def test_gsc_session_resolves_relative_key(tmp_path):
    root = tmp_path / "proj"; geo_dir = root / "geo-agent"; geo_dir.mkdir(parents=True)
    (geo_dir / "gsc-rel.json").write_text("{}", encoding="utf-8")
    from unittest.mock import patch as _patch
    with _patch("geo.fetch.gsc.REPO", geo_dir):
        with _patch("geo.fetch.gsc.settings") as mock_settings:
            mock_settings.proxy = None
            mock_settings.gsc_key_file = "geo-agent/gsc-rel.json"
            with _patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file") as mc:
                _gsc_session()
    mc.assert_called_once()
    assert Path(mc.call_args.args[0]) == geo_dir / "gsc-rel.json"


# ---- 传输层持久修复(2026-09-06): token 刷新显式走代理,零环境变量依赖 ----------

def test_gsc_session_token_refresh_proxied():
    """AuthorizedSession 默认给 token 刷新另建裸 session(只吃 HTTP(S)_PROXY 环境变量,
    不继承主 session.proxies)——w4 事故根因之一。本锁断言注入路径使两处都显式走代理。"""
    from google.auth.transport.requests import AuthorizedSession
    for proxy in ("http://127.0.0.1:10808", None):
        with patch("geo.fetch.gsc.settings") as mock_settings, \
             patch("geo.fetch.gsc._resolve_gsc_key", return_value=Path("/tmp/fake-key.json")), \
             patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file"):
            mock_settings.proxy = proxy
            mock_settings.gsc_key_file = "/tmp/fake-key.json"
            sess = _gsc_session()
        assert isinstance(sess, AuthorizedSession)
        if proxy:
            want = {"http": proxy, "https": proxy}
            assert dict(sess.proxies) == want
            assert dict(sess._auth_request.session.proxies) == want
        else:
            assert not sess.proxies and not sess._auth_request.session.proxies


# ---- Bug#3(w4): snapshot 拉取段管线内重试 ------------------------------------

def test_gsc_retry_succeeds_third_attempt(iso_snapshots, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    sess = MagicMock()
    sess.post.side_effect = [TimeoutError("timed out"), TimeoutError("timed out"),
                             _resp({"rows": [{"keys": ["solar battery"], "clicks": 3,
                                              "impressions": 50, "ctr": 0.06, "position": 4.2}]})]
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is False and len(out["rows"]) == 1

def test_gsc_retry_exhausted_degrades(iso_snapshots, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    sess = MagicMock()
    sess.post.side_effect = TimeoutError("timed out")
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is True and "TimeoutError" in out["error"]
    assert sess.post.call_count == 3
