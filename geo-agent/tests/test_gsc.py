import logging
from unittest.mock import patch, MagicMock
from geo.fetch.gsc import snapshot_gsc, _build_service
from geo.shared.config import settings
from geo.shared.weeks import TEST_WEEK

def test_gsc_degrades_on_auth_error(iso_snapshots):
    with patch("geo.fetch.gsc._build_service", side_effect=Exception("403 forbidden")):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is True and out["rows"] == []

def test_gsc_http_sets_timeout():
    """httplib2 has NO default timeout — every Http() in the GSC path must set one,
    or a stalled Google endpoint (through the Clash proxy) hangs snapshot_node forever.
    Must hold on BOTH branches: direct and proxied."""
    for proxy in (None, "http://127.0.0.1:7890"):
        with patch("geo.fetch.gsc.settings") as mock_settings:
            mock_settings.proxy = proxy
            mock_settings.gsc_key_file = "/tmp/fake-key.json"
            with patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file"):
                with patch("geo.fetch.gsc.httplib2.Http") as mock_http:
                    with patch("geo.fetch.gsc.build"):
                        _build_service()
        for call in mock_http.call_args_list:
            assert call.kwargs.get("timeout") == 60, \
                f"Http() missing timeout=60 (proxy={proxy}): {call}"

def test_gsc_happy(iso_snapshots):
    svc = MagicMock()
    svc.searchanalytics().query().execute.return_value = {"rows":[{"keys":["solar battery"],"clicks":3,"impressions":50,"ctr":0.06,"position":4.2}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["rows"][0]["keys"]==["solar battery"] and out["degraded"] is False

def test_gsc_proxy_applied_when_set():
    """Verify proxy configuration is threaded into GSC HTTP transport when settings.proxy is set."""
    # Test with proxy set - verify proxy_info_from_url is called
    with patch("geo.fetch.gsc.settings") as mock_settings:
        mock_settings.proxy = "http://127.0.0.1:7890"
        mock_settings.gsc_key_file = "/tmp/fake-key.json"

        with patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file") as mock_creds:
            mock_creds.return_value.authorize = MagicMock()
            with patch("geo.fetch.gsc.httplib2.proxy_info_from_url") as mock_proxy_info:
                mock_proxy_info.return_value = MagicMock()
                with patch("geo.fetch.gsc.build") as mock_build:
                    mock_build.return_value = MagicMock()
                    _build_service()

                    # Verify proxy_info_from_url was called with the proxy URL
                    mock_proxy_info.assert_called_once_with("http://127.0.0.1:7890")

    # Test without proxy - verify proxy_info_from_url is NOT called
    with patch("geo.fetch.gsc.settings") as mock_settings:
        mock_settings.proxy = None
        mock_settings.gsc_key_file = "/tmp/fake-key.json"

        with patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file") as mock_creds:
            mock_creds.return_value.authorize = MagicMock()
            with patch("geo.fetch.gsc.httplib2.proxy_info_from_url") as mock_proxy_info:
                with patch("geo.fetch.gsc.build") as mock_build:
                    mock_build.return_value = MagicMock()
                    _build_service()

                    # Verify proxy_info_from_url was NOT called (no proxy)
                    mock_proxy_info.assert_not_called()


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
    svc.searchanalytics().query().execute.return_value = {"rows": [{"keys": ["NEW!"]}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="geo-seo-v2")
    assert out["rows"] == [{"keys": ["frozen"]}]          # 返回现有,未重取
    svc.searchanalytics().query().execute.assert_not_called()

def test_gsc_degraded_snapshot_can_be_refrozen(iso_snapshots):
    """08-13 的 SSLEOFError 合法重跑 = degraded 例外口径:degraded 快照必须允许重取。"""
    import json as _json
    from geo.fetch.gsc import snapshot_dir
    p = snapshot_dir(TEST_WEEK) / "gsc.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "t", "site": "s",
                              "rows": [], "degraded": True, "error": "SSLEOFError"}),
                 encoding="utf-8")
    svc = MagicMock()
    svc.searchanalytics().query().execute.return_value = {"rows": [{"keys": ["ok"]}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is False and out["rows"] == [{"keys": ["ok"]}]

def test_gsc_corrupted_snapshot_treated_as_miss(iso_snapshots):
    """损坏快照(截断/非法 JSON)不得让守卫抛 JSONDecodeError 硬停管线——视为缺失重取并覆写。"""
    import json as _json
    from geo.fetch.gsc import snapshot_dir
    p = snapshot_dir(TEST_WEEK) / "gsc.json"
    p.write_text('{"trunc', encoding="utf-8")   # 截断的非法 JSON
    svc = MagicMock()
    svc.searchanalytics().query().execute.return_value = {"rows": [{"keys": ["ok"]}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
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
    svc.searchanalytics().query().execute.return_value = {"rows": [{"keys": ["NEW!"]}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        with caplog.at_level(logging.WARNING, logger="fetch.gsc"):
            out = snapshot_gsc(week=TEST_WEEK, rule_version="geo-seo-v3")
    assert out["rows"] == [{"keys": ["frozen"]}]          # 返回冻结内容,未重取
    assert out["rule_version"] == "geo-seo-v2"            # 历史基线版本不被改写
    svc.searchanalytics().query().execute.assert_not_called()
    assert any(r.levelno == logging.WARNING and "规则版本" in r.getMessage()
               for r in caplog.records)
