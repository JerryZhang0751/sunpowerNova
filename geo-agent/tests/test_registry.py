# tests/test_registry.py
from geo.assess.registry import GEO_SIGNALS, SEO_SIGNALS
from geo.shared.models import L3Source

SRC = L3Source(url="https://sunhestia.com", sha1="x", text="t",
    structural={"schema_types": ["FAQPage", "Organization", "Product", "Article", "BreadcrumbList"],
                "h_counts": {"h1": 1, "h2": 3, "ul_count": 2}, "table_count": 2,
                "canonical": "https://sunhestia.com"},
    semantic={"has_definition_segment": True, "faq_block_count": 2, "datapoint_count": 5,
              "has_author_byline": True, "has_publish_date": True,
              "cites_external_sources": True})
BRAND = {"mention": 1, "cited": 0, "sov": 0.0, "entity_known": False,
         "on_youtube": False, "on_reddit": False, "on_wikipedia": False, "on_linkedin": False}
STATIC = {"robots_ai": {"GPTBot": True, "ClaudeBot": True}, "https": True,
          "pages": [{"path": "/about"}, {"path": "/faq"}]}

def test_geo_checker_values():  # 逐 checker 与旧硬编码公式对数
    g = lambda sid: GEO_SIGNALS[sid](SRC, BRAND, STATIC)
    assert g("has_definition_segment") == 100.0
    assert g("faq_block_count") == 66.7          # _ratio(2,0,3)
    assert g("table_count") == 100.0             # _ratio(2,0,2)
    assert g("datapoint_count") == 100.0         # _ratio(5,0,5)
    assert g("list_count") == 66.7               # _ratio(ul_count=2,0,3)
    assert g("mention_count") == 33.3            # _ratio(1,0,3)
    assert g("entity_known") == 0.0
    assert g("org_or_person_schema") == 100.0
    assert g("robots_gptbot") == 100.0 and g("robots_claudebot") == 100.0
    assert g("canonical_present") == 100.0       # truthy canonical
    assert g("schema_type_count") == 100.0       # _ratio(5,0,3)
    assert g("has_faqpage") == 100.0 and g("has_organization") == 100.0
    assert g("has_breadcrumblist") == 100.0      # 候选池
    assert g("about_page_present") == 100.0      # 候选池(pages 含 /about)
    assert g("author_schema") == 0.0             # 候选池(无 Person)

def test_geo_none_safe():
    empty = L3Source(url="u", sha1="s")
    for sid in GEO_SIGNALS:
        v = GEO_SIGNALS[sid](empty, {}, {})      # 空 src/brand/static 不崩,返回 float
        assert isinstance(v, float) and 0.0 <= v <= 100.0

def test_seo_checker_values():
    p = {"http_status": 200, "in_sitemap": True, "robots_not_blocked": True,
         "canonical_self": True, "https": True, "has_viewport": True,
         "title": "SunHestia Solar Battery Storage Systems For Homes", "h_counts": {"h1": 1, "h2": 2},
         "meta_desc": "Guides"}
    gsc = {"impressions": 500, "clicks": 25, "ctr": 0.05}
    c = {"word_count": 800, "has_author_byline": True, "has_publish_date": True,
         "cites_external_sources": True}
    s = lambda sid: SEO_SIGNALS[sid](p, gsc, c)
    assert s("http_200") == 100.0 and s("in_sitemap") == 100.0
    assert s("title_len_ok") == 100.0            # len 40..60
    assert s("single_h1") == 100.0 and s("heading_hierarchy_ok") == 100.0
    assert s("word_count_band") == 41.7         # _ratio(800,300,1500)
    assert s("gsc_impressions") == 50.0          # _ratio(500,0,1000)
    assert s("gsc_ctr") == 100.0                 # _ratio(0.05,0,0.05)
    assert s("backlinks_est") == 0.0             # P2+ unknown 恒 0
