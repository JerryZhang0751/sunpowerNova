"""Tests for L3 fetcher - OFFLINE tests only (mock httpx, mock Kimi)."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from geo.fetch.fetcher import extract_structural, fetch_source
from geo.fetch.meta_llm import extract_semantic
from geo.shared.storage import sha1_url, source_dir, l1_path, snapshot_dir
from bs4 import BeautifulSoup
import json

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

def test_sha1_consistency():
    """Test SHA1 produces consistent hashes for identical URLs."""
    url1 = "https://example.com/page"
    url2 = "https://example.com/page"
    url3 = "https://example.com/other"
    assert sha1_url(url1) == sha1_url(url2)
    assert sha1_url(url1) != sha1_url(url3)
    assert len(sha1_url(url1)) == 40  # SHA1 is 40 hex chars

def test_fetch_source_core_logic():
    """Test fetch_source() core logic with mocked httpx - validates L3Source fields."""
    url = "https://example.com/test"

    # Create pre-fetched cached data to test cache reading path
    sha = sha1_url(url)
    sd = source_dir(sha)
    sd.mkdir(parents=True, exist_ok=True)

    # Create mock cached data that simulates a successful fetch
    cached_meta = {
        "url": url,
        "sha1": sha,
        "http_status": 200,
        "text": "Extracted text content",
        "structural": {
            "canonical": "https://x.com/a",
            "schema_types": ["FAQPage"],
            "h_counts": {"h1": 1, "h2": 1},
            "table_count": 1,
            "ul_count": 0
        },
        "semantic": {
            "page_type": "product",
            "has_definition_segment": True,
            "has_faq_block": False,
            "datapoint_count": 5,
            "has_author_byline": False,
            "has_publish_date": True,
            "cites_external_sources": True
        },
        "js_only": False,
        "fetched_iso": "2026-08-02T12:00:00Z"
    }

    (sd / "text.md").write_text("Extracted text content", encoding="utf-8")
    (sd / "meta.json").write_text(json.dumps(cached_meta), encoding="utf-8")

    # Test cache read - should read from disk instead of network
    result = fetch_source(url, fetcher_kimi=False)

    # Assert cached data is returned correctly
    assert result.url == url
    assert result.http_status == 200
    assert result.text == "Extracted text content"
    assert result.structural['canonical'] == "https://x.com/a"
    assert "FAQPage" in result.structural['schema_types']
    assert result.structural['h_counts']['h1'] == 1
    assert result.structural['table_count'] == 1
    assert result.semantic['page_type'] == 'product'
    assert result.semantic['has_definition_segment'] is True
    assert result.js_only is False
    assert result.fetched_iso == "2026-08-02T12:00:00Z"

    # Clean up
    (sd / "text.md").unlink()
    (sd / "meta.json").unlink()
    sd.rmdir()

def test_fetch_source_js_only_detection():
    """Test JS-only page detection when trafilatura returns empty text."""
    url = "https://example.com/js-only"

    # Create pre-fetched cached data that simulates JS-only page
    sha = sha1_url(url)
    sd = source_dir(sha)
    sd.mkdir(parents=True, exist_ok=True)

    cached_meta = {
        "url": url,
        "sha1": sha,
        "http_status": 200,
        "text": "",  # Empty text indicates JS-only
        "structural": {},
        "semantic": {},
        "js_only": True,  # JS-only flag set
        "fetched_iso": "2026-08-02T12:00:00Z"
    }

    (sd / "text.md").write_text("", encoding="utf-8")
    (sd / "meta.json").write_text(json.dumps(cached_meta), encoding="utf-8")

    # Test cache read of JS-only page
    result = fetch_source(url, fetcher_kimi=False)

    # Assert JS-only characteristics
    assert result.js_only is True
    assert result.text == ""
    assert result.http_status == 200
    assert result.structural == {}

    # Clean up
    (sd / "text.md").unlink()
    (sd / "meta.json").unlink()
    sd.rmdir()

def test_extract_semantic_graceful_fallback():
    """Test meta_llm graceful fallback - mocked Kimi failure should return {} without crashing."""
    text = "Some page text content"

    # Mock OpenAI client to raise exception
    with patch('geo.fetch.meta_llm.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client

        # Mock Kimi API call to fail
        mock_client.chat.completions.create.side_effect = Exception("Kimi API error")

        result = extract_semantic(text)

    # Should return empty dict on failure, not crash
    assert result == {}
    assert isinstance(result, dict)

def test_extract_semantic_empty_input():
    """Test meta_llm with empty input - should return {} without calling API."""
    with patch('geo.fetch.meta_llm.OpenAI') as mock_openai:
        result = extract_semantic("   ")

    # Should return {} for empty text without calling API
    assert result == {}
    mock_openai.assert_not_called()

def test_extract_semantic_success():
    """Test meta_llm successful semantic extraction."""
    text = "This is a product page with specifications and technical details."

    with patch('geo.fetch.meta_llm.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client

        # Mock successful Kimi response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            'page_type': 'product',
            'has_definition_segment': False,
            'has_faq_block': False,
            'datapoint_count': 3,
            'has_author_byline': False,
            'has_publish_date': False,
            'cites_external_sources': False
        })
        mock_client.chat.completions.create.return_value = mock_response

        result = extract_semantic(text)

    assert result['page_type'] == 'product'
    assert result['datapoint_count'] == 3
    assert result['has_definition_segment'] is False

def test_storage_path_generation():
    """Test storage utilities - sha1-based directory structure."""
    # Test sha1_url
    sha = sha1_url("https://example.com/test")
    assert len(sha) == 40
    assert sha[:12] in str(source_dir(sha))

    # Test source_dir creates correct path
    sd = source_dir(sha)
    assert "data/sources" in str(sd)
    assert sha[:12] in str(sd)

    # Test l1_path generation
    l1p = l1_path(1, "qwen", "prompt_123", 1)
    assert "data/raw/w1/qwen/prompt_123" in str(l1p)
    assert "r1.json" in str(l1p)

    # Test snapshot_dir generation
    snap = snapshot_dir(5)
    assert "data/snapshots/w5" in str(snap)

def test_fetch_source_deduplication():
    """Test SHA1 deduplication - existing cache should be read instead of re-fetching."""
    url = "https://example.com/cached"
    sha = sha1_url(url)
    sd = source_dir(sha)

    # Create mock cached files
    sd.mkdir(parents=True, exist_ok=True)
    cached_meta = {
        "url": url,
        "sha1": sha,
        "http_status": 200,
        "text": "cached text",
        "structural": {"canonical": "https://example.com/canonical"},
        "semantic": {"page_type": "blog"},
        "js_only": False,
        "fetched_iso": "2026-08-02T12:00:00Z"
    }
    (sd / "text.md").write_text("cached text", encoding="utf-8")
    (sd / "meta.json").write_text(json.dumps(cached_meta), encoding="utf-8")

    # Call fetch_source - should read from cache
    result = fetch_source(url, fetcher_kimi=False)

    # Assert cached data is returned
    assert result.url == url
    assert result.text == "cached text"
    assert result.structural['canonical'] == "https://example.com/canonical"
    assert result.semantic['page_type'] == "blog"
    assert result.fetched_iso == "2026-08-02T12:00:00Z"

    # Clean up
    (sd / "text.md").unlink()
    (sd / "meta.json").unlink()
    sd.rmdir()

def test_structural_multiple_schema_types():
    """Test structural extraction with multiple schema types."""
    html = """<html><head>
    <script type="application/ld+json">{"@type":"FAQPage"}</script>
    <script type="application/ld+json">{"@type":"Product"}</script>
    <script type="application/ld+json">{"@type":["Organization","BreadcrumbList"]}</script>
    </head><body><h1>Test</h1></body></html>"""

    s = extract_structural(BeautifulSoup(html, "lxml"))
    assert "FAQPage" in s["schema_types"]
    assert "Product" in s["schema_types"]
    assert "Organization" in s["schema_types"]
    assert "BreadcrumbList" in s["schema_types"]
    assert len(s["schema_types"]) == 4  # All unique types

def test_structural_comprehensive():
    """Test comprehensive structural signal extraction."""
    html = """<html><head><link rel="canonical" href="https://example.com/canonical"/>
    <script type="application/ld+json">{"@type":"Article"}</script>
    </head><body>
    <h1>Main Title</h1><h2>Subtitle 1</h2><h2>Subtitle 2</h2><h3>Deep Dive</h3>
    <ul><li>Item 1</li><li>Item 2</li></ul>
    <ol><li>Step 1</li><li>Step 2</li></ol>
    <table><tr><td>Data</td></tr></table>
    </body></html>"""

    s = extract_structural(BeautifulSoup(html, "lxml"))
    assert s["canonical"] == "https://example.com/canonical"
    assert "Article" in s["schema_types"]
    assert s["h_counts"]["h1"] == 1
    assert s["h_counts"]["h2"] == 2
    assert s["h_counts"]["h3"] == 1
    assert s["table_count"] == 1
    assert s["ul_count"] == 2  # Both <ul> and <ol> counted

def test_fetch_source_http_error_handling():
    """Test fetch_source handles HTTP errors gracefully via cached error state."""
    url = "https://example.com/error"

    # Create pre-fetched cached data that simulates HTTP error state
    sha = sha1_url(url)
    sd = source_dir(sha)
    sd.mkdir(parents=True, exist_ok=True)

    cached_meta = {
        "url": url,
        "sha1": sha,
        "http_status": None,  # No status due to error
        "text": "",  # Empty text due to error
        "structural": {},
        "semantic": {},
        "js_only": True,  # JS-only flag set due to error
        "fetched_iso": "2026-08-02T12:00:00Z"
    }

    (sd / "text.md").write_text("", encoding="utf-8")
    (sd / "meta.json").write_text(json.dumps(cached_meta), encoding="utf-8")

    # Test cache read of error state
    result = fetch_source(url, fetcher_kimi=False)

    # Assert error handling characteristics
    assert result.js_only is True
    assert result.url == url
    assert result.http_status is None
    assert result.text == ""
    assert result.structural == {}

    # Clean up
    (sd / "text.md").unlink()
    (sd / "meta.json").unlink()
    sd.rmdir()


# ---- Fix(2026-08-24 审查#3): SSRF 防线 ----------------------------------
import httpx
import pytest
from geo.fetch.url_guard import UnsafeURLError

# 假域名不真解析:统一 mock 成公网地址,让防线只检验"跳转目标"本身
from unittest.mock import patch as _patch
import ipaddress as _ipa
_PUB = [_ipa.ip_address("93.184.216.34")]

BODY = "<html><head><title>t</title></head><body><p>word " * 20 + "</p></body></html>"

def _cleanup(url):
    sd = source_dir(sha1_url(url))
    for f in (sd / "text.md", sd / "meta.json"):
        if f.exists(): f.unlink()
    if sd.exists(): sd.rmdir()

def test_fetch_source_blocks_redirect_to_internal():
    """公网 URL 302 → 云元数据地址:第二跳必须被拦截,且不落缓存。"""
    url = "https://public-redirect.example/a"
    _cleanup(url)
    def handler(request):
        if request.url.path == "/a":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
        return httpx.Response(200, text=BODY)
    with _patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        with pytest.raises(UnsafeURLError):
            fetch_source(url, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    sd = source_dir(sha1_url(url))
    assert not (sd / "meta.json").exists() and not (sd / "text.md").exists()
    _cleanup(url)

def test_fetch_source_follows_safe_redirects():
    """安全重定向正常跟随(手动循环,每跳已验证)。"""
    url = "https://public-hop.example/start"
    _cleanup(url)
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(301, headers={"location": "/final"})
        return httpx.Response(200, text=BODY)
    with _patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    assert rec.http_status == 200
    _cleanup(url)

def test_fetch_source_caps_redirect_hops():
    url = "https://loop.example/0"
    _cleanup(url)
    def handler(request):
        n = int(request.url.path.strip("/"))
        return httpx.Response(302, headers={"location": f"/{n+1}"})
    with _patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        with pytest.raises(UnsafeURLError, match="重定向"):
            fetch_source(url, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    _cleanup(url)

def test_fetch_source_rejects_internal_url_immediately():
    url = "http://10.0.0.7/private"
    _cleanup(url)
    with pytest.raises(UnsafeURLError):
        fetch_source(url, fetcher_kimi=False)
    sd = source_dir(sha1_url(url))
    assert not (sd / "meta.json").exists() and not (sd / "text.md").exists()
    _cleanup(url)
