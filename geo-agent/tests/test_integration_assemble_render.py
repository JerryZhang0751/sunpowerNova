"""Integration test for the analyst → fetcher → reporter seam.

This is the regression test for the whole-branch Critical-1 finding:
``analyst._load_l3_source`` previously searched for
``data/sources/{any}/{url_hash}.json`` while the fetcher writes
``data/sources/{sha1[:12]}/meta.json`` — so the loader returned None
unconditionally, GEO scoring + benchmarker never ran, and the reporter
crashed on ``None.total`` at render time.

The test exercises the REAL ``fetch_source`` → REAL ``assemble`` → REAL
``render`` path. Only the network (``httpx``) and the external Kimi LLM
(``meta_llm.OpenAI``) are mocked — those are not the seam under test. It does
NOT patch ``_load_l3_source`` and does NOT mock the analyst or reporter nodes.
"""

import json
from unittest.mock import patch, MagicMock

from bs4 import BeautifulSoup

from geo.shared.models import L1Record, L2Record, CitedSource
from geo.shared.storage import sha1_url, source_dir
from geo.fetch.fetcher import fetch_source, extract_structural
from geo.assess.analyst import assemble
from geo.report.reporter import render

BRAND_URL = "https://sunhestia.com"
COMP_URL = "https://competitor.example"

# Enough body text (>300 words) so word_count yields a real, non-zero ratio.
HTML = """<html><head>
<title>SunHestia Solar Home Battery Storage Solutions</title>
<meta name="description" content="SunHestia manufactures residential solar battery storage for European homes.">
<link rel="canonical" href="https://sunhestia.com">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script type="application/ld+json">{"@type":"Organization"}</script>
<script type="application/ld+json">{"@type":"Product"}</script>
</head><body>
<h1>SunHestia Home Battery</h1>
<h2>Why SunHestia</h2>
<p>""" + ("SunHestia stores rooftop solar energy in a modular lithium battery. " * 80) + """</p>
<table><tr><td>Capacity</td><td>5 kWh</td></tr></table>
<ul><li>Modular</li><li>Smart inverter</li></ul>
</body></html>"""


def _mock_httpx():
    """httpx.Client mock that serves HTML for any URL (no real network)."""
    client = MagicMock()
    # is_redirect=False 显式声明(2026-08-24 起走手动重定向循环,MagicMock 真值会误入跳转分支)
    # **kw: 2026-08-25 IP pin 起 get 携带请求级 headers/extensions(Host/SNI 保留原主机)
    client.get.side_effect = lambda url, **kw: MagicMock(status_code=200, text=HTML, is_redirect=False)
    client.__enter__.return_value = client
    return client


def _kimi_response(*_a, **_kw):
    """Mock Kimi (meta_llm) response carrying real E-E-A-T signals."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = json.dumps({
        "page_type": "product",
        "has_definition_segment": True,
        "has_faq_block": True,
        "faq_block_count": 2,
        "datapoint_count": 4,
        "has_author_byline": True,
        "has_publish_date": True,
        "cites_external_sources": True,
    })
    return resp


def test_assemble_render_seam_real_l3(tmp_path):
    """REAL fetcher writes L3 → REAL analyst loads it → REAL reporter renders.

    Previously this path returned self_geo=None and crashed render() on
    None.total. It must now score GEO/SEO, compute the competitive gap, and
    render without raising.
    """
    # Point storage + analyst at an isolated tmp repo (same root for both so the
    # fetcher's write path and the analyst's read path coincide).
    with patch("geo.shared.storage.REPO", tmp_path), \
         patch("geo.assess.analyst.REPO", tmp_path):

        # 1. Fetch brand + competitor L3 via the REAL fetcher (offline).
        #    (SSRF 防线在 httpx 之前做 DNS 校验——离线假域名须一并 mock,见 test_url_guard)
        import ipaddress as _ipa
        with patch("geo.fetch.url_guard._resolve_ips",
                   return_value=[_ipa.ip_address("93.184.216.34")]), \
             patch("httpx.Client", return_value=_mock_httpx()), \
             patch("geo.fetch.meta_llm.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.side_effect = _kimi_response
            brand_l3 = fetch_source(BRAND_URL, fetcher_kimi=True)
            fetch_source(COMP_URL, fetcher_kimi=True)

        # The fetcher really wrote meta.json at the storage path, and that path
        # is exactly the path the (fixed) analyst loader reads.
        brand_meta = source_dir(sha1_url(BRAND_URL)) / "meta.json"
        analyst_meta = tmp_path / "data" / "sources" / sha1_url(BRAND_URL)[:12] / "meta.json"
        assert brand_meta.exists(), "fetcher must write L3 meta.json to disk"
        assert brand_meta == analyst_meta, "analyst read path must equal fetcher write path"
        assert brand_l3.structural.get("title"), "title captured by extract_structural"
        assert brand_l3.structural.get("meta_desc"), "meta_desc captured by extract_structural"

        # 2. Write static_signals + gsc snapshots with REAL extracted page signals.
        st = extract_structural(BeautifulSoup(HTML, "lxml"))
        static_signals = {
            "site": BRAND_URL,
            "pages": [{
                "url": BRAND_URL, "https": True, "http_status": 200,
                "in_sitemap": True, "has_viewport": True, **st,
            }],
            "robots_ai": {"GPTBot": True, "ClaudeBot": True,
                          "PerplexityBot": True, "Googlebot": True},
            "sitemap_present": True,
        }
        snap = tmp_path / "data" / "snapshots" / "w7"
        snap.mkdir(parents=True, exist_ok=True)
        (snap / "static_signals.json").write_text(json.dumps(static_signals), encoding="utf-8")
        (snap / "gsc.json").write_text(
            json.dumps({"impressions": 600, "clicks": 30, "ctr": 0.05}), encoding="utf-8")

        # 3. Write an L1 record that mentions the brand and cites the competitor
        #    so the benchmarker (gap) path is exercised end-to-end too.
        l1 = L1Record(
            week=7, model="qwen", prompt_id="B02", run=1,
            answer="SunHestia is great. See https://competitor.example too.",
            l2=L2Record(
                cited_sources=[CitedSource(position=1, url=COMP_URL,
                                           title="Comp", snippet="")],
                mentioned=True, cited_with_link=True, citation_position=1,
                sentiment="pos", competitors_mentioned=["competitor.example"],
            ),
            ts_iso="2026-08-02T12:00:00Z", prompt_set_version="psv-int",
        )
        raw = tmp_path / "data" / "raw" / "w7" / "qwen" / "B02"
        raw.mkdir(parents=True, exist_ok=True)
        (raw / "r1.json").write_text(l1.model_dump_json(), encoding="utf-8")

        # 4. REAL assemble — must load the L3 the fetcher wrote and score it.
        report = assemble(week=7)

        # --- Critical-1 regression assertions ---
        assert report["self_geo"] is not None, \
            "self_geo must be scored (L3 read path must match fetcher write path)"
        assert report["self_geo"]["total"] > 0
        assert report["gap"] is not None, \
            "gap must be computed when brand + competitor L3 are both present"
        assert "dim_diff" in report["gap"]
        assert report["self_seo"] is not None, "self_seo must be scored"

        # --- Important-1 assertions: SEO on_page/content_eeat fed REAL signals ---
        seo_dims = {d["name"]: d for d in report["self_seo"]["dims"]}
        # New payload shape uses registered signal IDs (e.g., unique_title, title_len_ok)
        assert "unique_title" in seo_dims["on_page"]["signals"], \
            "SEO on_page must contain unique_title signal (registered ID)"
        assert "title_len_ok" in seo_dims["on_page"]["signals"], \
            "SEO on_page must contain title_len_ok signal (registered ID)"
        # Check that title_len_ok computed from real extracted title
        real_title = brand_l3.structural.get("title", "")
        expected_len_ok = 40 <= len(real_title) <= 60
        assert seo_dims["on_page"]["signals"]["title_len_ok"] == (100.0 if expected_len_ok else 0.0), \
            "SEO title_len_ok must be computed from the real extracted <title>"
        # content_eeat uses registered signal IDs (word_count_band, not word_count)
        ceat = seo_dims["content_eeat"]["signals"]
        assert "word_count_band" in ceat, "SEO content_eeat must use word_count_band signal (registered ID)"
        assert "has_author_byline" in ceat, "SEO content_eeat must use has_author_byline signal (registered ID)"
        assert ceat["has_author_byline"] == 100.0, \
            "SEO E-E-A-T must come from the real L3 semantic (Kimi), not hardcoded (100.0 = True)"

        # 5. REAL reporter render — must not raise on the real assembled report.
        out = tmp_path / "report.html"
        render(report, out)
        assert out.exists()
        html = out.read_text(encoding="utf-8")
        assert "周度评测" in html
        assert "GEO 综合得分" in html


def test_reporter_degrades_none_scores_without_crashing(tmp_path):
    """Defense-in-depth: a report with null self_geo/self_seo/gap (the state the
    bug produced) must render to a dash / placeholder, NOT raise UndefinedError.
    """
    report = {
        "week": 1, "rule_version": "geo-seo-v1", "prompt_set_version": "abc",
        "metrics": {}, "self_geo": None, "self_seo": None, "gap": None,
        "authority_gap_note": "权威分基于 P0 代理；外部权威未计入",
    }
    out = tmp_path / "degraded.html"
    render(report, out)  # must not raise
    html = out.read_text(encoding="utf-8")
    assert "-" in html  # totals render as dash instead of crashing
    assert "无竞品 L3 数据" in html  # gap section degraded placeholder
