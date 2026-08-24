# src/geo/assess/registry.py
"""信号注册表:checker 纯函数,值域 0–100。
GEO 签名 (src: L3Source, brand: dict, static: dict) -> float
SEO 签名 (p: dict, gsc: dict, c: dict) -> float
公式自 geo_scorer/seo_scorer 逐字搬迁(v1 语义零漂移);None 一律安全降 0。"""
from __future__ import annotations
from geo.shared.models import L3Source


def _pct(ok) -> float:
    return 100.0 if ok else 0.0


def _ratio(n, lo, hi) -> float:      # n in [lo,hi] → 0..100
    if n is None:
        return 0.0
    if n <= lo:
        return 0.0
    if n >= hi:
        return 100.0
    return round(100 * (n - lo) / (hi - lo), 1)


GEO_SIGNALS = {
    # citability(旧公式均值 5 项)
    "has_definition_segment": lambda s, b, st: _pct((s.semantic or {}).get("has_definition_segment")),
    "faq_block_count":        lambda s, b, st: _ratio((s.semantic or {}).get("faq_block_count", 0), 0, 3),
    "table_count":            lambda s, b, st: _ratio((s.structural or {}).get("table_count", 0), 0, 2),
    "datapoint_count":        lambda s, b, st: _ratio((s.semantic or {}).get("datapoint_count", 0), 0, 5),
    "list_count":             lambda s, b, st: _ratio((s.structural or {}).get("h_counts", {}).get("ul_count", 0), 0, 3),
    # brand
    "mention_count":          lambda s, b, st: _ratio(b.get("mention", 0), 0, 3),
    "cited_count":            lambda s, b, st: _ratio(b.get("cited", 0), 0, 2),
    "sov_share":              lambda s, b, st: _ratio(b.get("sov", 0.0), 0, 0.2),  # sov=声量份额0–1(brand/(brand+comp));份额≥0.2 满分
    "entity_known":           lambda s, b, st: _pct(b.get("entity_known")),
    # eeat
    "has_author_byline":      lambda s, b, st: _pct((s.semantic or {}).get("has_author_byline")),
    "has_publish_date":       lambda s, b, st: _pct((s.semantic or {}).get("has_publish_date")),
    "cites_external_sources": lambda s, b, st: _pct((s.semantic or {}).get("cites_external_sources")),
    "org_or_person_schema":   lambda s, b, st: _pct("Organization" in (s.structural or {}).get("schema_types", [])
                                                    or "Person" in (s.structural or {}).get("schema_types", [])),
    # technical_geo
    "robots_gptbot":          lambda s, b, st: _pct((st.get("robots_ai") or {}).get("GPTBot")),
    "robots_claudebot":       lambda s, b, st: _pct((st.get("robots_ai") or {}).get("ClaudeBot")),
    "https":                  lambda s, b, st: _pct(st.get("https")),
    "canonical_present":      lambda s, b, st: _pct((s.structural or {}).get("canonical")),
    # schema
    "schema_type_count":      lambda s, b, st: _ratio(len((s.structural or {}).get("schema_types", [])), 0, 3),
    "has_faqpage":            lambda s, b, st: _pct("FAQPage" in (s.structural or {}).get("schema_types", [])),
    "has_product":            lambda s, b, st: _pct("Product" in (s.structural or {}).get("schema_types", [])),
    "has_organization":       lambda s, b, st: _pct("Organization" in (s.structural or {}).get("schema_types", [])),
    "has_article":            lambda s, b, st: _pct("Article" in (s.structural or {}).get("schema_types", [])),
    # platform(brand dict)
    "on_youtube":             lambda s, b, st: _pct(b.get("on_youtube")),
    "on_reddit":              lambda s, b, st: _pct(b.get("on_reddit")),
    "on_wikipedia":           lambda s, b, st: _pct(b.get("on_wikipedia")),
    "on_linkedin":            lambda s, b, st: _pct(b.get("on_linkedin")),
    # —— 候选池(v1 不进成员,draft 条目激活对象)——
    "about_page_present":     lambda s, b, st: _pct(any(p.get("path") == "/about" for p in (st.get("pages") or []))),
    "author_schema":          lambda s, b, st: _pct("Person" in (s.structural or {}).get("schema_types", [])),
    "has_breadcrumblist":     lambda s, b, st: _pct("BreadcrumbList" in (s.structural or {}).get("schema_types", [])),
}

SEO_SIGNALS = {
    # crawlability_index
    "http_200":               lambda p, g, c: _pct(p.get("http_status") == 200),
    "in_sitemap":             lambda p, g, c: _pct(p.get("in_sitemap")),
    "robots_not_blocked":     lambda p, g, c: _pct(p.get("robots_not_blocked")),
    "canonical_self":         lambda p, g, c: _pct(p.get("canonical_self")),
    "https":                  lambda p, g, c: _pct(p.get("https")),
    # technical_foundation
    "mobile_viewport":        lambda p, g, c: _pct(p.get("has_viewport")),
    "http2":                  lambda p, g, c: _pct(p.get("http2", True)),
    "renderable_static":      lambda p, g, c: _pct(p.get("renderable_static", True)),
    # on_page
    "unique_title":           lambda p, g, c: _pct(bool(p.get("title"))),
    "title_len_ok":           lambda p, g, c: _pct(40 <= len(p.get("title") or "") <= 60),
    "meta_desc_present":      lambda p, g, c: _pct(p.get("meta_desc")),
    "single_h1":              lambda p, g, c: _pct(p.get("h_counts", {}).get("h1", 0) == 1),
    "heading_hierarchy_ok":   lambda p, g, c: _pct(p.get("h_counts", {}).get("h2", 0) >= 1
                                                   and p.get("h_counts", {}).get("h3", 0) >= 0),
    # content_eeat(读 content 参数 c,与 GEO 同名不同源)
    "has_author_byline":      lambda p, g, c: _pct(c.get("has_author_byline")),
    "has_publish_date":       lambda p, g, c: _pct(c.get("has_publish_date")),
    "cites_external_sources": lambda p, g, c: _pct(c.get("cites_external_sources")),
    "word_count_band":        lambda p, g, c: _ratio(c.get("word_count", 0), 300, 1500),
    # authority
    "gsc_impressions":        lambda p, g, c: _ratio(g.get("impressions", 0), 0, 1000),
    "gsc_clicks":             lambda p, g, c: _ratio(g.get("clicks", 0), 0, 50),
    "gsc_ctr":                lambda p, g, c: _ratio(g.get("ctr") or 0, 0, 0.05),
    "backlinks_est":          lambda p, g, c: 0.0,   # P2+ unknown → 恒 0(p2plus_missing)
}
