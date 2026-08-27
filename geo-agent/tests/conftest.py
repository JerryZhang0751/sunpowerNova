import pytest

def pytest_configure(config):
    """Register markers."""
    config.addinivalue_line("markers", "live: needs network + real API; skipped in CI")

def pytest_collection_modifyitems(config, items):
    """Automatically skip live tests unless -m live is used."""
    marker_expr = config.getoption("-m", default="")
    # Only skip live tests if the marker expression doesn't include "live"
    if "live" not in marker_expr:
        for item in items:
            if "live" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="live tests require -m live flag"))

@pytest.fixture
def iso_snapshots(tmp_path, monkeypatch):
    """把 snapshot_dir 重定向到 tmp,隔离生产 data/snapshots(周编号带子之外的第二道防线)。"""
    def fake_dir(week):
        p = tmp_path / f"w{week}"; p.mkdir(parents=True, exist_ok=True); return p
    import geo.fetch.gsc as _g, geo.fetch.site_signals as _s
    monkeypatch.setattr(_g, "snapshot_dir", fake_dir)
    monkeypatch.setattr(_s, "snapshot_dir", fake_dir)
    return tmp_path
