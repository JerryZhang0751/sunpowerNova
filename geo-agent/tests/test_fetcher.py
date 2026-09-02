"""Tests for L3 fetcher - OFFLINE tests only (mock httpx, mock Kimi)."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from geo.fetch.fetcher import extract_structural, fetch_source, FetchError
import httpx as _httpx  # 2026-08-27 P1② 失败不落缓存测试用
from geo.fetch.meta_llm import extract_semantic
from geo.shared.storage import sha1_url, source_dir, l1_path, snapshot_dir
from bs4 import BeautifulSoup
import json

# T9(2026-09-02 D1): fetch_source/source_dir 周目录化——本文件全部用 901 测试周。
TEST_WEEK = 901

@pytest.fixture(autouse=True)
def _iso_storage_repo(tmp_path, monkeypatch):
    """Task4 评审移交:本文件多测直调 source_dir/snapshot_dir/l1_path(自带 mkdir
    副作用),全量跑会在生产 data/ 下反复建出 data/snapshots/w5 等空目录、破坏冻结
    不变量。patch storage.REPO 到 tmp(同 test_integration_assemble_render 先例)——
    不 patch snapshot_dir 本身:test_storage_path_generation 断言的恰是路径串,
    patch REPO 只挪根,断言对象与路径结构不变。"""
    import geo.shared.storage as _storage
    monkeypatch.setattr(_storage, "REPO", tmp_path)

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
    """T5(2026-09-02): 原断言同字面量调两次恒真;改为确定性+判别性真断言。"""
    u = "https://x.com/a"
    assert sha1_url(u) == sha1_url(u)                  # 确定性: 同 URL 两次独立调用同键
    assert sha1_url(u) != sha1_url("https://x.com/b")  # 不同 URL 不同键

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
    sd = source_dir(TEST_WEEK, sha)
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
    result = fetch_source(url, TEST_WEEK, fetcher_kimi=False)

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
    sd = source_dir(TEST_WEEK, sha)
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
    result = fetch_source(url, TEST_WEEK, fetcher_kimi=False)

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
    """Mocked Kimi failure → ({}, True):degraded=True 标志可见(T13 元组契约)。"""
    text = "Some page text content"

    # T4(2026-09-02): meta_llm 的 client 构造已合一至 shared.make_kimi_client,
    # mock 缝隙从 OpenAI 类换成 meta_llm 命名空间里的 make_kimi_client 工厂。
    with patch('geo.fetch.meta_llm.make_kimi_client') as mock_factory:
        mock_client = Mock()
        mock_factory.return_value = mock_client

        # Mock Kimi API call to fail
        mock_client.chat.completions.create.side_effect = Exception("Kimi API error")

        result, degraded = extract_semantic(text)

    # Should return empty dict + degraded flag on failure, not crash
    assert result == {}
    assert isinstance(result, dict)
    assert degraded is True

def test_extract_semantic_empty_input():
    """Test meta_llm with empty input - should return {} without calling API."""
    with patch('geo.fetch.meta_llm.make_kimi_client') as mock_factory:
        result, degraded = extract_semantic("   ")

    # Should return {} for empty text without calling API
    assert result == {}
    assert degraded is False     # 空文本=无从提取,非降级(T13)
    mock_factory.assert_not_called()

def test_extract_semantic_success():
    """Test meta_llm successful semantic extraction."""
    text = "This is a product page with specifications and technical details."

    with patch('geo.fetch.meta_llm.make_kimi_client') as mock_factory:
        mock_client = Mock()
        mock_factory.return_value = mock_client

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

        result, degraded = extract_semantic(text)

    assert result['page_type'] == 'product'
    assert result['datapoint_count'] == 3
    assert result['has_definition_segment'] is False
    assert degraded is False

def test_storage_path_generation():
    """Test storage utilities - week-scoped sha1 directory structure (D1)."""
    # Test sha1_url
    sha = sha1_url("https://example.com/test")
    assert len(sha) == 40
    assert sha[:12] in str(source_dir(TEST_WEEK, sha))

    # Test source_dir creates correct week-scoped path
    sd = source_dir(TEST_WEEK, sha)
    assert "data/sources" in str(sd)
    assert f"w{TEST_WEEK}" in str(sd)
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
    sd = source_dir(TEST_WEEK, sha)

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
    result = fetch_source(url, TEST_WEEK, fetcher_kimi=False)

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
    """Fix(2026-08-27 P1②): 旧语义"错误态缓存为 js_only 常驻"已废弃——存量毒化
    条目(js_only+http_status None)视为 miss 重抓;重抓仍失败则上抛 FetchError,
    且失败路径不落盘,毒化 meta 原样保留留给下次运行再试。"""
    url = "https://example.com/error"

    # Create pre-fetched cached data that simulates the legacy poisoned error state
    sha = sha1_url(url)
    sd = source_dir(TEST_WEEK, sha)
    sd.mkdir(parents=True, exist_ok=True)

    poisoned_meta = {
        "url": url,
        "sha1": sha,
        "http_status": None,  # legacy异常路径从不带 status
        "text": "",
        "structural": {},
        "semantic": {},
        "js_only": True,
        "fetched_iso": "2026-08-02T12:00:00Z"
    }

    (sd / "text.md").write_text("", encoding="utf-8")
    (sd / "meta.json").write_text(json.dumps(poisoned_meta), encoding="utf-8")

    # 毒化条目触发重抓,重抓又遇 HTTP 403 → 上抛 FetchError
    r = MagicMock(status_code=403, text="<html>forbidden</html>")
    with patch("geo.fetch.fetcher._safe_get", return_value=r):
        with pytest.raises(FetchError, match="403"):
            fetch_source(url, TEST_WEEK, fetcher_kimi=False)

    # 失败路径不覆写磁盘:毒化 meta 原样保留,下次运行自然再试自愈
    on_disk = json.loads((sd / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["http_status"] is None and on_disk["js_only"] is True

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
    sd = source_dir(TEST_WEEK, sha1_url(url))
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
            fetch_source(url, TEST_WEEK, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    sd = source_dir(TEST_WEEK, sha1_url(url))
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
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False, transport=httpx.MockTransport(handler))
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
            fetch_source(url, TEST_WEEK, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    _cleanup(url)

def test_fetch_source_rejects_internal_url_immediately():
    url = "http://10.0.0.7/private"
    _cleanup(url)
    with pytest.raises(UnsafeURLError):
        fetch_source(url, TEST_WEEK, fetcher_kimi=False)
    sd = source_dir(TEST_WEEK, sha1_url(url))
    assert not (sd / "meta.json").exists() and not (sd / "text.md").exists()
    _cleanup(url)


# ---- Fix(2026-08-25 二次审查#3): IP pin —— 校验解析 ≠ 连接解析的 rebinding 窗口
# 防线解析出的公网 IP 直接作为连接目标(URL 主机改写为 IP),Host 头/SNI 保留
# 原主机;每一跳都 pin。MockTransport 下 pin 的可观测面 = 请求 URL host 与 Host 头。

def test_fetch_pins_connection_to_validated_ip():
    """直连(代理关闭): 请求必须打到已验证 IP,Host 头保留原域名。"""
    from types import SimpleNamespace
    url = "https://pin-target.example/a"
    _cleanup(url)
    seen = {}
    def handler(request):
        seen["host"] = request.url.host
        seen["Host"] = request.headers.get("host")
        return httpx.Response(200, text=BODY)
    with _patch("geo.fetch.fetcher.settings", SimpleNamespace(proxy=None)), \
         _patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    assert rec.http_status == 200
    assert seen["host"] == "93.184.216.34", "连接目标必须是防线验过的 IP"
    assert seen["Host"] == "pin-target.example", "Host 头必须保留原主机"
    _cleanup(url)

def test_fetch_pins_each_redirect_hop_with_port_in_host_header():
    """直连: 重定向第二跳同样 pin;非默认端口的 Host 头需带端口。"""
    from types import SimpleNamespace
    url = "https://pin-hop.example:8443/start"
    _cleanup(url)
    seen = []
    def handler(request):
        seen.append((request.url.host, request.headers.get("host")))
        if request.url.path == "/start":
            return httpx.Response(301, headers={"location": "https://pin-hop.example:8443/final"})
        return httpx.Response(200, text=BODY)
    with _patch("geo.fetch.fetcher.settings", SimpleNamespace(proxy=None)), \
         _patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    assert rec.http_status == 200
    assert seen[0][0] == "93.184.216.34" and seen[1][0] == "93.184.216.34"
    assert seen[0][1] == "pin-hop.example:8443", "非默认端口 Host 头须带端口"
    _cleanup(url)


# ---- Fix(2026-08-28 w2 实跑): 代理模式发域名;直连 pin 优先 IPv4 -------------
# w2 是 r2 IP-pin(08-26)后首个真实 research 跑: top-40 抓取 40/40 全灭、
# research sample_n 崩至 4。根因双重: (a)域名分流代理(xray/Clash)收到裸 IP
# CONNECT 会绕过域名路由规则,外站被直连拒收;(b)getaddrinfo IPv6 优先 + 网络
# IPv6 出口不通,双栈域名全灭。语义改为: 代理=每跳仍过防线校验,但发原始域名
# 交代理路由(残余 rebinding 窗口=受信本地代理二次解析,已接受并注明);
# 直连(含 transport 注入)=保留 pin,优先 IPv4,无 A 记录才用 IPv6。

_V6 = _ipa.ip_address("2620:127:f00f:5::")
_V4D = _ipa.ip_address("23.227.38.65")

def test_proxy_mode_sends_domain_not_pinned_ip():
    """代理模式: 请求 URL 必须是原域名(交代理按域名路由),不做 Host/SNI 改写。"""
    from types import SimpleNamespace
    url = "https://proxy-target.example/a"
    _cleanup(url)
    seen = {}
    def handler(request):
        seen["host"] = request.url.host
        seen["Host"] = request.headers.get("host")
        return httpx.Response(200, text=BODY)
    fake_settings = SimpleNamespace(proxy="http://127.0.0.1:7890")
    with _patch("geo.fetch.fetcher.settings", fake_settings), \
         _patch("geo.fetch.url_guard._resolve_ips", return_value=[_V6, _V4D]):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    assert rec.http_status == 200
    assert seen["host"] == "proxy-target.example", "代理模式必须发域名,不得 pin IP"
    assert seen["Host"] == "proxy-target.example", "代理模式不得改写 Host"
    _cleanup(url)

def test_proxy_mode_still_validates_each_hop():
    """代理模式安全门不撤: 解析出内网地址照旧拒绝、不落缓存。"""
    from types import SimpleNamespace
    url = "https://proxy-unsafe.example/a"
    _cleanup(url)
    fake_settings = SimpleNamespace(proxy="http://127.0.0.1:7890")
    with _patch("geo.fetch.fetcher.settings", fake_settings), \
         _patch("geo.fetch.url_guard._resolve_ips",
                return_value=[_ipa.ip_address("10.0.0.7")]):
        with pytest.raises(UnsafeURLError):
            fetch_source(url, TEST_WEEK, fetcher_kimi=False,
                         transport=httpx.MockTransport(lambda r: httpx.Response(200, text=BODY)))
    sd = source_dir(TEST_WEEK, sha1_url(url))
    assert not (sd / "meta.json").exists() and not (sd / "text.md").exists()
    _cleanup(url)

def test_direct_pin_prefers_ipv4_over_ipv6():
    """直连 pin: 同批地址里有 v4 就用 v4(v6 优先序 + v6 出口不通曾致全灭)。"""
    from types import SimpleNamespace
    url = "https://dualstack.example/a"
    _cleanup(url)
    seen = {}
    def handler(request):
        seen["host"] = request.url.host
        return httpx.Response(200, text=BODY)
    with _patch("geo.fetch.fetcher.settings", SimpleNamespace(proxy=None)), \
         _patch("geo.fetch.url_guard._resolve_ips", return_value=[_V6, _V4D]):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    assert rec.http_status == 200
    assert seen["host"] == "23.227.38.65", "必须优先 pin IPv4"
    _cleanup(url)

def test_direct_pin_ipv6_when_no_v4():
    """v6-only 域名: 无 A 记录时仍 pin v6(不因修 v4 偏好而退化)。"""
    from types import SimpleNamespace
    url = "https://v6only.example/a"
    _cleanup(url)
    seen = {}
    def handler(request):
        seen["host"] = request.url.host
        return httpx.Response(200, text=BODY)
    with _patch("geo.fetch.fetcher.settings", SimpleNamespace(proxy=None)), \
         _patch("geo.fetch.url_guard._resolve_ips", return_value=[_V6]):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False, transport=httpx.MockTransport(handler))
    assert rec.http_status == 200
    assert seen["host"] == "2620:127:f00f:5::"
    _cleanup(url)


# ---- Fix(2026-08-27 P1②): 失败不落缓存 + 存量毒化自愈 --------------------

def _clean(url):
    import shutil
    sd = source_dir(TEST_WEEK, sha1_url(url))
    shutil.rmtree(sd, ignore_errors=True)
    return sd

def test_transport_error_raises_no_cache():
    url = "https://transient.example/x"
    sd = _clean(url)
    with patch("geo.fetch.fetcher._safe_get", side_effect=_httpx.ConnectError("net down")):
        with pytest.raises(FetchError):
            fetch_source(url, TEST_WEEK, fetcher_kimi=False)
    assert not (sd/"text.md").exists() and not (sd/"meta.json").exists()

def test_http_error_raises_no_cache():
    url = "https://blocked.example/y"
    sd = _clean(url)
    r = MagicMock(status_code=403, text="<html>forbidden</html>")
    with patch("geo.fetch.fetcher._safe_get", return_value=r):
        with pytest.raises(FetchError, match="403"):
            fetch_source(url, TEST_WEEK, fetcher_kimi=False)
    assert not (sd/"meta.json").exists()

def test_200_empty_body_caches_js_only():
    url = "https://jsshell.example/z"
    sd = _clean(url)
    r = MagicMock(status_code=200, text="<html><body><div id='app'></div></body></html>")
    with patch("geo.fetch.fetcher._safe_get", return_value=r):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False)
    assert rec.js_only is True and rec.http_status == 200
    assert (sd/"meta.json").exists()          # 真 JS-only 照常缓存

def test_poisoned_cache_entry_is_refetched():
    """存量毒化条目(js_only+http_status None)命中时视为 miss 重抓。"""
    url = "https://poisoned.example/p"
    sd = _clean(url)
    sd.mkdir(parents=True, exist_ok=True)
    (sd/"text.md").write_text("", encoding="utf-8")
    (sd/"meta.json").write_text(json.dumps(
        {"url": url, "sha1": sha1_url(url), "http_status": None, "text": "",
         "structural": {}, "semantic": {}, "js_only": True, "fetched_iso": "2026-08-01T00:00:00Z"}),
        encoding="utf-8")
    r = MagicMock(status_code=200, text="<html><body><p>Real article text paragraph.</p></body></html>")
    with patch("geo.fetch.fetcher._safe_get", return_value=r):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False)
    assert rec.http_status == 200 and rec.js_only is False   # 已被新结果覆写
    _clean(url)
