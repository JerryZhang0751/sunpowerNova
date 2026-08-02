from unittest.mock import patch, MagicMock
from geo.fetch.site_signals import snapshot_static_signals

def test_signals_per_page(tmp_path):
    fake = MagicMock(status_code=200, text="<html><head><meta name='viewport' content='w'>"
                          "<link rel='canonical' href='https://sunhestia.com/x'>"
                          "<script type='application/ld+json'>{\"@type\":\"Organization\"}</script></head></html>")
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake
        out = snapshot_static_signals(week=99, rule_version="t")
    pg = out["pages"][0]
    assert pg["https"] is True and pg["has_viewport"] is True and "Organization" in pg["schema_types"]
