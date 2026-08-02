"""Tests for L3 fetcher - OFFLINE tests only (mock httpx, mock Kimi)."""
from geo.fetch.fetcher import extract_structural, sha1_url
from bs4 import BeautifulSoup

HTML = """<html><head><link rel="canonical" href="https://x.com/a"/>
<script type="application/ld+json">{"@type":"FAQPage"}</script></head>
<body><h1>T</h1><h2>A</h2><table><tr><td>1</td></tr></table></body></html>"""

def test_structural_p0():
    """Test P0 structural extraction from HTML."""
    s = extract_structural(BeautifulSoup(HTML, "lxml"))
    assert s["canonical"] == "https://x.com/a"
    assert "FAQPage" in s["schema_types"]
    assert s["h_counts"]["h1"] == 1 and s["table_count"] == 1

def test_sha1_dedup():
    """Test SHA1 URL deduplication consistency."""
    assert sha1_url("https://x.com/a") == sha1_url("https://x.com/a")
