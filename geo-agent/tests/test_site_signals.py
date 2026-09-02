from unittest.mock import patch, MagicMock, PropertyMock
from geo.fetch.site_signals import snapshot_static_signals, _robots_allows_ai
from geo.shared.weeks import TEST_WEEK
import pytest

def test_signals_per_page(iso_snapshots):
    """Test happy path: all signals extracted correctly."""
    fake = MagicMock(status_code=200, text="<html><head><meta name='viewport' content='w'>"
                          "<link rel='canonical' href='https://sunhestia.com/x'>"
                          "<script type='application/ld+json'>{\"@type\":\"Organization\"}</script></head></html>")
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    pg = out["pages"][0]
    assert pg["https"] is True and pg["has_viewport"] is True and "Organization" in pg["schema_types"]

def test_graceful_per_page_failure(iso_snapshots):
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

        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

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

# ---- D3 robots 解析修正:通配组 + 精确路径匹配(旧实现 fail-open:忽略 * 组、子串误伤) ----

def test_robots_wildcard_group_respected():
    """User-agent: * 组的 Disallow: / 必须约束所有 bot(旧实现只查 bot 专属组→全放行)。"""
    txt = "User-agent: *\nDisallow: /\n"
    assert _robots_allows_ai(txt) == {"GPTBot": False, "ClaudeBot": False,
                                      "PerplexityBot": False, "Googlebot": False}

def test_robots_specific_group_overrides_wildcard():
    """bot 专属组优先于 * 组(REP 惯例):GPTBot 专属 Allow 覆盖 * 的全站 Disallow。"""
    txt = "User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nAllow: /\n"
    r = _robots_allows_ai(txt)
    assert r["GPTBot"] is True and r["ClaudeBot"] is False

def test_robots_substring_not_overreach():
    # Disallow: /private 不等于全站封禁(旧子串匹配误伤:"Disallow: /" in "Disallow: /private")
    txt = "User-agent: GPTBot\nDisallow: /private\n"
    assert _robots_allows_ai(txt)["GPTBot"] is True

def test_robots_agent_lookup_case_insensitive():
    """REP:user-agent 名大小写不敏感——小写 'gptbot' 组也须命中 GPTBot 专属组。"""
    txt = "User-agent: gptbot\nDisallow: /\n"
    r = _robots_allows_ai(txt)
    assert r["GPTBot"] is False
    assert r["ClaudeBot"] is True        # 其他 bot 不受该专属组影响

def test_sitemap_presence_and_parsing(iso_snapshots):
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

        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

    assert out["sitemap_present"] is True
    # Check that some pages are correctly identified as in sitemap
    in_sitemap = [p for p in out["pages"] if p.get("in_sitemap") is True]
    assert len(in_sitemap) >= 1

def test_sitemap_absence(iso_snapshots):
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

        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

    assert out["sitemap_present"] is False
    # All pages should show in_sitemap as False when sitemap is missing
    assert all(p.get("in_sitemap") is False for p in out["pages"])

def test_thirteen_page_iteration(iso_snapshots):
    """Test that all 13 pages are processed."""
    pages_processed = []

    def mock_get(url):
        pages_processed.append(url)
        return MagicMock(status_code=200, text="<html><head></head></html>")

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        mock_client = MagicMock()
        mock_client.get.side_effect = mock_get
        C.return_value.__enter__.return_value = mock_client

        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

    # Should have processed all pages from targets.yaml
    assert len(out["pages"]) >= 13
    assert len(pages_processed) >= 13

def test_signal_extraction_correctness(iso_snapshots):
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
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

    pg = out["pages"][0]

    # Check individual signals
    assert pg["has_viewport"] is True
    assert pg["https"] is True
    assert pg["http_status"] == 200
    assert "Organization" in pg["schema_types"]
    assert "WebSite" in pg["schema_types"]
    # Check that structural data was extracted
    assert "h_counts" in pg or "table_count" in pg or "ul_count" in pg

def test_http_status_codes(iso_snapshots):
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

        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

    # Should have various status codes
    status_codes = [p.get("http_status") for p in out["pages"]]
    assert len(set(status_codes)) > 1  # Multiple different status codes

def test_missing_signals(iso_snapshots):
    """Test pages with missing canonical, schema, viewport."""
    minimal_html = "<html><head><title>Minimal Page</title></head><body><h1>Title</h1></body></html>"

    fake_response = MagicMock(status_code=200, text=minimal_html)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake_response
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

    pg = out["pages"][0]

    # Should handle missing signals gracefully
    assert pg["has_viewport"] is False
    assert pg["schema_types"] == []  # No schema types found
    assert pg.get("canonical") is None or pg.get("canonical") == ""

def test_empty_html(iso_snapshots):
    """Test with empty/invalid HTML."""
    empty_html = ""

    fake_response = MagicMock(status_code=200, text=empty_html)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake_response
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

    # Should still create a record without crashing
    assert len(out["pages"]) >= 1
    pg = out["pages"][0]
    assert pg["http_status"] == 200

def test_https_detection(iso_snapshots):
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
            out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")

    pg = out["pages"][0]
    assert pg["https"] is True
    assert pg["url"].startswith("https://")

def test_snapshot_structure(iso_snapshots):
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


# ---- D2 快照 degraded 守卫:干净(含旧格式无 degraded 键)→ 冻结;degraded → 重取 ----

def test_static_signals_old_format_snapshot_still_frozen(iso_snapshots):
    """旧格式快照(无 degraded 键,如已冻结的 w1):prev.get('degraded')=None=falsy → 冻结。
    黄金锁兼容:w1 重算必须仍读旧格式冻结快照,不得触发重取。"""
    import json as _json
    from geo.fetch.site_signals import snapshot_dir   # iso_snapshots 已 patch → tmp
    p = snapshot_dir(TEST_WEEK) / "static_signals.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "t", "site": "s",
                              "pages": [{"url": "FROZEN"}]}), encoding="utf-8")
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    C.assert_not_called()                                  # 不发任何请求
    assert out["pages"] == [{"url": "FROZEN"}]

def test_snapshot_clean_snapshot_still_frozen(iso_snapshots):
    """显式 degraded:False 的干净快照 → 冻结零网络(既有冻结语义保留)。"""
    import json as _json
    from geo.fetch.site_signals import snapshot_dir
    p = snapshot_dir(TEST_WEEK) / "static_signals.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "t", "site": "s",
                              "degraded": False,
                              "pages": [{"url": "CLEAN", "http_status": 200}]}), encoding="utf-8")
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    C.assert_not_called()
    assert out["pages"] == [{"url": "CLEAN", "http_status": 200}]

def test_snapshot_error_page_marks_degraded_and_refetchable(iso_snapshots):
    """error 页(http_status=None)→ degraded=true;修复后二次调用重取 → degraded 消解并冻结。"""
    from geo.fetch.site_signals import snapshot_dir
    ok_html = "<html><head></head></html>"

    def one_page_down(url):
        if "about" in url:
            raise Exception("Network error")
        return MagicMock(status_code=200, text=ok_html)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        m = MagicMock()
        m.get.side_effect = one_page_down
        C.return_value.__enter__.return_value = m
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is True
    assert any(p.get("http_status") is None and p.get("error") for p in out["pages"])
    assert isinstance(out["robots_ai"], dict)              # robots 正常 → 仍是 dict

    # 二次调用:全部 200 → degraded 快照允许重取 → 转干净
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        m2 = MagicMock()
        m2.get.return_value = MagicMock(status_code=200, text=ok_html)
        C.return_value.__enter__.return_value = m2
        out2 = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    assert out2["degraded"] is False
    assert all(p.get("http_status") == 200 for p in out2["pages"])

    # 三次调用:已干净 → 冻结零网络
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        m3 = MagicMock()
        C.return_value.__enter__.return_value = m3
        out3 = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    m3.get.assert_not_called()
    assert out3["degraded"] is False
    assert out3["pages"] == out2["pages"]

def test_snapshot_robots_fetch_fail_marks_degraded(iso_snapshots):
    """robots 拉取异常 → robots_ai=None(D3 未知≠允许)+ degraded=true;修复后重取恢复 dict。"""
    ok_html = "<html><head></head></html>"

    def robots_down(url):
        if url.endswith("robots.txt"):
            raise Exception("robots unreachable")
        return MagicMock(status_code=200, text=ok_html)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        m = MagicMock()
        m.get.side_effect = robots_down
        C.return_value.__enter__.return_value = m
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    assert out["robots_ai"] is None
    assert out["degraded"] is True

    # 修复后重取 → robots_ai 恢复 dict,快照转干净
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        m2 = MagicMock()
        m2.get.return_value = MagicMock(status_code=200, text=ok_html)
        C.return_value.__enter__.return_value = m2
        out2 = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    assert isinstance(out2["robots_ai"], dict)
    assert out2["degraded"] is False

def test_snapshot_robots_5xx_marks_degraded(iso_snapshots):
    """robots.txt 返回 5xx(错误 HTML 页,httpx 不 raise)→ 同样视为拉取失败:
    robots_ai=None + degraded=true;修复后(200)重取恢复 dict。"""
    ok_html = "<html><head></head></html>"

    def robots_500(url):
        if url.endswith("robots.txt"):
            return MagicMock(status_code=500, text="<html>Server Error</html>")
        return MagicMock(status_code=200, text=ok_html)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        m = MagicMock()
        m.get.side_effect = robots_500
        C.return_value.__enter__.return_value = m
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    assert out["robots_ai"] is None
    assert out["degraded"] is True

    # 修复后(200)重取 → robots_ai 恢复 dict,degraded 消解
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        m2 = MagicMock()
        m2.get.return_value = MagicMock(status_code=200, text="User-agent: *\nDisallow: /\n")
        C.return_value.__enter__.return_value = m2
        out2 = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    assert out2["robots_ai"]["GPTBot"] is False
    assert out2["degraded"] is False

def test_snapshot_robots_404_means_unrestricted(iso_snapshots):
    """404 robots.txt = REP 合法"无限制"→ 全允许且快照干净(区别于 5xx 拉取失败)。"""
    ok_html = "<html><head></head></html>"

    def robots_404(url):
        if url.endswith("robots.txt"):
            return MagicMock(status_code=404, text="<html>Not Found</html>")
        return MagicMock(status_code=200, text=ok_html)

    with patch("geo.fetch.site_signals.httpx.Client") as C:
        m = MagicMock()
        m.get.side_effect = robots_404
        C.return_value.__enter__.return_value = m
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    assert out["robots_ai"] == {"GPTBot": True, "ClaudeBot": True,
                                "PerplexityBot": True, "Googlebot": True}
    assert out["degraded"] is False
