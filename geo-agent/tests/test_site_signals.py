from unittest.mock import patch, MagicMock, PropertyMock
from geo.fetch.site_signals import snapshot_static_signals, _robots_allows_ai
import pytest

def test_signals_per_page(tmp_path):
    """Test happy path: all signals extracted correctly."""
    fake = MagicMock(status_code=200, text="<html><head><meta name='viewport' content='w'>"
                          "<link rel='canonical' href='https://sunhestia.com/x'>"
                          "<script type='application/ld+json'>{\"@type\":\"Organization\"}</script></head></html>")
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake
        out = snapshot_static_signals(week=99, rule_version="t")
    pg = out["pages"][0]
    assert pg["https"] is True and pg["has_viewport"] is True and "Organization" in pg["schema_types"]

def test_graceful_per_page_failure():
    """Test that individual page failures don't crash the batch."""
    fake_response = MagicMock(status_code=200, text="<html><head></head></html>")

    def raise_error(url):
        if "about" in url:
            raise Exception("Network error")
        return fake_response

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        mock_client = MagicMock()
        mock_client.get.side_effect = raise_error
        C.return_value.__enter__.return_value = mock_client

        out = snapshot_static_signals(week=99, rule_version="t")

    # Should have both success and failure records
    assert len(out["pages"]) >= 1
    # At least one page should have succeeded
    success_pages = [p for p in out["pages"] if p.get("http_status") == 200]
    assert len(success_pages) >= 1
    # At least one page should have failed
    failed_pages = [p for p in out["pages"] if p.get("http_status") is None]
    assert len(failed_pages) >= 1

def test_robots_txt_allows_ai_parsing():
    """Test robots.txt AI crawler permission parsing."""
    # Test with all bots allowed
    robots_all = """
    User-agent: *
    Allow: /
    """
    result = _robots_allows_ai(robots_all)
    assert result["GPTBot"] is True
    assert result["ClaudeBot"] is True
    assert result["PerplexityBot"] is True
    assert result["Googlebot"] is True

def test_robots_txt_specific_bot_blocked():
    """Test robots.txt with specific bot blocked."""
    robots_blocked_gpt = """
    User-agent: GPTBot
    Disallow: /

    User-agent: *
    Allow: /
    """
    result = _robots_allows_ai(robots_blocked_gpt)
    assert result["GPTBot"] is False
    assert result["ClaudeBot"] is True
    assert result["PerplexityBot"] is True
    assert result["Googlebot"] is True

def test_robots_txt_multiple_bots_blocked():
    """Test robots.txt with multiple AI bots blocked."""
    robots_multi_blocked = """
    User-agent: GPTBot
    Disallow: /

    User-agent: ClaudeBot
    Disallow: /

    User-agent: Googlebot
    Allow: /
    """
    result = _robots_allows_ai(robots_multi_blocked)
    assert result["GPTBot"] is False
    assert result["ClaudeBot"] is False
    assert result["Googlebot"] is True
    assert result["PerplexityBot"] is True

def test_robots_txt_empty():
    """Test with empty robots.txt."""
    result = _robots_allows_ai("")
    assert all(result[bot] is True for bot in result)

def test_sitemap_presence_and_parsing():
    """Test sitemap.xml presence and URL parsing."""
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://sunhestia.com/</loc></url>
        <url><loc>https://sunhestia.com/about</loc></url>
        <url><loc>https://sunhestia.com/products</loc></url>
    </urlset>
    """

    fake_response = MagicMock(status_code=200, text="<html><head></head></html>")

    call_count = {"count": 0}
    def mock_get(url):
        call_count["count"] += 1
        if "sitemap.xml" in url:
            return MagicMock(status_code=200, text=sitemap_xml)
        return fake_response

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        mock_client = MagicMock()
        mock_client.get.side_effect = mock_get
        C.return_value.__enter__.return_value = mock_client

        out = snapshot_static_signals(week=99, rule_version="t")

    assert out["sitemap_present"] is True
    # Check that some pages are correctly identified as in sitemap
    in_sitemap = [p for p in out["pages"] if p.get("in_sitemap") is True]
    assert len(in_sitemap) >= 1

def test_sitemap_absence():
    """Test with sitemap.xml missing."""
    fake_response = MagicMock(status_code=200, text="<html><head></head></html>")

    call_count = {"count": 0}
    def mock_get(url):
        call_count["count"] += 1
        if "sitemap.xml" in url:
            raise Exception("Sitemap not found")
        return fake_response

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        mock_client = MagicMock()
        mock_client.get.side_effect = mock_get
        C.return_value.__enter__.return_value = mock_client

        out = snapshot_static_signals(week=99, rule_version="t")

    assert out["sitemap_present"] is False
    # All pages should show in_sitemap as False when sitemap is missing
    assert all(p.get("in_sitemap") is False for p in out["pages"])

def test_thirteen_page_iteration():
    """Test that all 13 pages are processed."""
    pages_processed = []

    def mock_get(url):
        pages_processed.append(url)
        return MagicMock(status_code=200, text="<html><head></head></html>")

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        mock_client = MagicMock()
        mock_client.get.side_effect = mock_get
        C.return_value.__enter__.return_value = mock_client

        out = snapshot_static_signals(week=99, rule_version="t")

    # Should have processed all pages from targets.yaml
    assert len(out["pages"]) >= 13
    assert len(pages_processed) >= 13

def test_signal_extraction_correctness():
    """Test comprehensive signal extraction from realistic HTML."""
    html_with_signals = """
    <html>
    <head>
        <meta name='viewport' content='width=device-width'>
        <link rel='canonical' href='https://sunhestia.com/canonical-page'>
        <script type='application/ld+json'>
            {"@type":"Organization","name":"SunHestia"}
        </script>
        <script type='application/ld+json'>
            {"@type":"WebSite","name":"SunHestia Site"}
        </script>
    </head>
    <body>
        <h1>Main Title</h1>
        <h2>Subtitle</h2>
        <table><tr><td>Table content</td></tr></table>
        <ul><li>List item</li></ul>
    </body>
    </html>
    """

    fake_response = MagicMock(status_code=200, text=html_with_signals)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake_response
        out = snapshot_static_signals(week=99, rule_version="t")

    pg = out["pages"][0]

    # Check individual signals
    assert pg["has_viewport"] is True
    assert pg["https"] is True
    assert pg["http_status"] == 200
    assert "Organization" in pg["schema_types"]
    assert "WebSite" in pg["schema_types"]
    # Check that structural data was extracted
    assert "h_counts" in pg or "table_count" in pg or "ul_count" in pg

def test_http_status_codes():
    """Test different HTTP status codes."""
    status_responses = [404, 500, 200, 403, 301]

    call_count = {"count": 0}
    def mock_get(url):
        call_count["count"] += 1
        status = status_responses[call_count["count"] % len(status_responses)]
        return MagicMock(status_code=status, text="<html><head></head></html>")

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        mock_client = MagicMock()
        mock_client.get.side_effect = mock_get
        C.return_value.__enter__.return_value = mock_client

        out = snapshot_static_signals(week=99, rule_version="t")

    # Should have various status codes
    status_codes = [p.get("http_status") for p in out["pages"]]
    assert len(set(status_codes)) > 1  # Multiple different status codes

def test_missing_signals():
    """Test pages with missing canonical, schema, viewport."""
    minimal_html = "<html><head><title>Minimal Page</title></head><body><h1>Title</h1></body></html>"

    fake_response = MagicMock(status_code=200, text=minimal_html)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake_response
        out = snapshot_static_signals(week=99, rule_version="t")

    pg = out["pages"][0]

    # Should handle missing signals gracefully
    assert pg["has_viewport"] is False
    assert pg["schema_types"] == []  # No schema types found
    assert pg.get("canonical") is None or pg.get("canonical") == ""

def test_empty_html():
    """Test with empty/invalid HTML."""
    empty_html = ""

    fake_response = MagicMock(status_code=200, text=empty_html)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake_response
        out = snapshot_static_signals(week=99, rule_version="t")

    # Should still create a record without crashing
    assert len(out["pages"]) >= 1
    pg = out["pages"][0]
    assert pg["http_status"] == 200

def test_https_detection():
    """Test HTTPS vs HTTP detection."""
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        with patch("geo.fetch.site_signals.settings") as S:
            # Mock both settings and httpx client
            type(S).targets = PropertyMock(return_value={
                "site": {"url": "https://sunhestia.com", "pages": ["/"]}
            })
            C.return_value.__enter__.return_value.get.return_value = MagicMock(
                status_code=200, text="<html><head></head></html>"
            )
            out = snapshot_static_signals(week=99, rule_version="t")

    pg = out["pages"][0]
    assert pg["https"] is True
    assert pg["url"].startswith("https://")

def test_snapshot_structure():
    """Test overall snapshot structure and metadata."""
    fake_response = MagicMock(status_code=200, text="<html><head></head></html>")

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake_response
        out = snapshot_static_signals(week=42, rule_version="v1.2")

    # Check top-level structure
    assert "week" in out
    assert "rule_version" in out
    assert "site" in out
    assert "pages" in out
    assert out["week"] == 42
    assert out["rule_version"] == "v1.2"
    assert "robots_ai" in out
    assert "sitemap_present" in out

    # Check page structure
    assert len(out["pages"]) >= 1
    pg = out["pages"][0]
    assert "url" in pg
    assert "path" in pg
    assert "https" in pg
    assert "http_status" in pg
