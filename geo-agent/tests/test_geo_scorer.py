from geo.assess.geo_scorer import score_geo
from geo.shared.models import L3Source

SRC = L3Source(
    url="https://sunhestia.com",
    sha1="x",
    text="t",
    structural={
        "schema_types": ["FAQPage", "Organization", "Product", "Article"],
        "h_counts": {"h1": 1, "h2": 3},
        "table_count": 2,
        "canonical": "https://sunhestia.com"
    },
    semantic={
        "has_definition_segment": True,
        "faq_block_count": 2,
        "datapoint_count": 5,
        "has_author_byline": True,
        "has_publish_date": True,
        "cites_external_sources": True
    }
)


def test_deterministic_and_bands():
    brand = {"mention": 1, "cited": 0, "sov": 0.0, "entity_known": False}
    static = {"robots_ai": {"GPTBot": True, "ClaudeBot": True}, "https": True}
    c1 = score_geo(SRC, brand, static)
    c2 = score_geo(SRC, brand, static)
    assert c1.total == c2.total
    assert 0 <= c1.total <= 100
    d = {x.name: x for x in c1.dims}
    assert d["schema"].score == 100 and d["technical_geo"].score == 100  # 全满足
    assert d["platform"].score < 100  # 平台信号未提供→降级
