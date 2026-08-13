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
