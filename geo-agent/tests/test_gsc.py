from unittest.mock import patch, MagicMock
from geo.fetch.gsc import snapshot_gsc

def test_gsc_degrades_on_auth_error(tmp_path, monkeypatch):
    with patch("geo.fetch.gsc._build_service", side_effect=Exception("403 forbidden")):
        out = snapshot_gsc(week=99, rule_version="t")
    assert out["degraded"] is True and out["rows"] == []

def test_gsc_happy(tmp_path, monkeypatch):
    svc = MagicMock()
    svc.searchanalytics().query().execute.return_value = {"rows":[{"keys":["solar battery"],"clicks":3,"impressions":50,"ctr":0.06,"position":4.2}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        out = snapshot_gsc(week=99, rule_version="t")
    assert out["rows"][0]["keys"]==["solar battery"] and out["degraded"] is False
