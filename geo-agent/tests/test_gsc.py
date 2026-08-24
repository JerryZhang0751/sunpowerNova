from unittest.mock import patch, MagicMock
from geo.fetch.gsc import snapshot_gsc, _build_service
from geo.shared.config import settings

def test_gsc_degrades_on_auth_error(tmp_path, monkeypatch):
    with patch("geo.fetch.gsc._build_service", side_effect=Exception("403 forbidden")):
        out = snapshot_gsc(week=99, rule_version="t")
    assert out["degraded"] is True and out["rows"] == []

def test_gsc_http_sets_timeout(tmp_path, monkeypatch):
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

def test_gsc_happy(tmp_path, monkeypatch):
    svc = MagicMock()
    svc.searchanalytics().query().execute.return_value = {"rows":[{"keys":["solar battery"],"clicks":3,"impressions":50,"ctr":0.06,"position":4.2}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        out = snapshot_gsc(week=99, rule_version="t")
    assert out["rows"][0]["keys"]==["solar battery"] and out["degraded"] is False

def test_gsc_proxy_applied_when_set(tmp_path, monkeypatch):
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
