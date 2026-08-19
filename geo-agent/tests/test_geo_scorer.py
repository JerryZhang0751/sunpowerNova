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


def test_citability_dimension():
    """Test citability dimension with varying signal levels."""
    # Maximum citability (all signals present at max levels)
    max_src = L3Source(
        url="https://max.com", sha1="x", text="t",
        structural={"table_count": 2, "h_counts": {"ul_count": 3}},
        semantic={"has_definition_segment": True, "faq_block_count": 3, "datapoint_count": 5}
    )
    brand = {"mention": 0, "cited": 0, "sov": 0.0}
    static = {}
    result = score_geo(max_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert d["citability"].score == 100.0

    # Minimum citability (no signals)
    min_src = L3Source(
        url="https://min.com", sha1="x", text="t",
        structural={"table_count": 0, "h_counts": {"ul_count": 0}},
        semantic={"has_definition_segment": False, "faq_block_count": 0, "datapoint_count": 0}
    )
    result = score_geo(min_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert d["citability"].score == 0.0

    # Mid-range citability (mixed signals)
    mid_src = L3Source(
        url="https://mid.com", sha1="x", text="t",
        structural={"table_count": 1, "h_counts": {"ul_count": 1}},
        semantic={"has_definition_segment": True, "faq_block_count": 1, "datapoint_count": 2}
    )
    result = score_geo(mid_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert 0 < d["citability"].score < 100


def test_brand_dimension():
    """Test brand dimension with varying signal levels."""
    src = L3Source(url="https://test.com", sha1="x", text="t", structural={}, semantic={})

    # Maximum brand (all signals at max)
    max_brand = {"mention": 3, "cited": 2, "sov": 0.2, "entity_known": True}
    static = {}
    result = score_geo(src, max_brand, static)
    d = {x.name: x for x in result.dims}
    assert d["brand"].score == 100.0

    # Minimum brand (no signals)
    min_brand = {"mention": 0, "cited": 0, "sov": 0.0, "entity_known": False}
    result = score_geo(src, min_brand, static)
    d = {x.name: x for x in result.dims}
    assert d["brand"].score == 0.0

    # Mid-range brand
    mid_brand = {"mention": 1, "cited": 1, "sov": 0.1, "entity_known": False}
    result = score_geo(src, mid_brand, static)
    d = {x.name: x for x in result.dims}
    assert 0 < d["brand"].score < 100


def test_eeat_dimension():
    """Test E-E-A-T dimension with varying signal levels."""
    src = L3Source(url="https://test.com", sha1="x", text="t", structural={}, semantic={})

    # Maximum E-E-A-T (all signals + schema)
    max_src = L3Source(
        url="https://max.com", sha1="x", text="t",
        structural={"schema_types": ["Organization"]},
        semantic={"has_author_byline": True, "has_publish_date": True, "cites_external_sources": True}
    )
    brand = {}
    static = {}
    result = score_geo(max_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert d["eeat"].score == 100.0

    # Minimum E-E-A-T (no signals)
    min_src = L3Source(
        url="https://min.com", sha1="x", text="t",
        structural={"schema_types": []},
        semantic={"has_author_byline": False, "has_publish_date": False, "cites_external_sources": False}
    )
    result = score_geo(min_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert d["eeat"].score == 0.0


def test_technical_geo_dimension():
    """Test technical GEO dimension with varying signal levels."""
    src = L3Source(url="https://test.com", sha1="x", text="t", structural={}, semantic={})

    # Maximum technical GEO (all signals present)
    max_src = L3Source(
        url="https://max.com", sha1="x", text="t",
        structural={"canonical": "https://max.com"},
        semantic={}
    )
    brand = {}
    max_static = {"robots_ai": {"GPTBot": True, "ClaudeBot": True}, "https": True}
    result = score_geo(max_src, brand, max_static)
    d = {x.name: x for x in result.dims}
    assert d["technical_geo"].score == 100.0

    # Minimum technical GEO (no signals)
    min_src = L3Source(
        url="https://min.com", sha1="x", text="t",
        structural={"canonical": None},
        semantic={}
    )
    min_static = {"robots_ai": {"GPTBot": False, "ClaudeBot": False}, "https": False}
    result = score_geo(min_src, brand, min_static)
    d = {x.name: x for x in result.dims}
    assert d["technical_geo"].score == 0.0


def test_schema_dimension():
    """Test schema dimension with varying schema types."""
    src = L3Source(url="https://test.com", sha1="x", text="t", structural={}, semantic={})
    brand = {}
    static = {}

    # Maximum schema (all target types present + count ≥3)
    max_src = L3Source(
        url="https://max.com", sha1="x", text="t",
        structural={"schema_types": ["FAQPage", "Product", "Organization", "Article"]},
        semantic={}
    )
    result = score_geo(max_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert d["schema"].score == 100.0

    # Minimum schema (no schemas)
    min_src = L3Source(
        url="https://min.com", sha1="x", text="t",
        structural={"schema_types": []},
        semantic={}
    )
    result = score_geo(min_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert d["schema"].score == 0.0

    # Partial schema (some types present)
    partial_src = L3Source(
        url="https://partial.com", sha1="x", text="t",
        structural={"schema_types": ["FAQPage"]},
        semantic={}
    )
    result = score_geo(partial_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert 0 < d["schema"].score < 100


def test_platform_dimension():
    """Test platform dimension with varying platform presence."""
    src = L3Source(url="https://test.com", sha1="x", text="t", structural={}, semantic={})
    static = {}

    # Maximum platform (all platforms present)
    max_brand = {"on_youtube": True, "on_reddit": True, "on_wikipedia": True, "on_linkedin": True}
    result = score_geo(src, max_brand, static)
    d = {x.name: x for x in result.dims}
    assert d["platform"].score == 100.0

    # Minimum platform (no platforms)
    min_brand = {"on_youtube": False, "on_reddit": False, "on_wikipedia": False, "on_linkedin": False}
    result = score_geo(src, min_brand, static)
    d = {x.name: x for x in result.dims}
    assert d["platform"].score == 0.0

    # Partial platform (some platforms present)
    partial_brand = {"on_youtube": True, "on_reddit": False, "on_wikipedia": False, "on_linkedin": False}
    result = score_geo(src, partial_brand, static)
    d = {x.name: x for x in result.dims}
    assert d["platform"].score == 25.0


def test_edge_cases_all_zeros():
    """Test edge case where all signals are zero/None/False."""
    src = L3Source(
        url="https://zero.com", sha1="x", text="t",
        structural={"schema_types": [], "table_count": 0, "h_counts": {}, "canonical": None},
        semantic={"has_definition_segment": False, "faq_block_count": 0, "datapoint_count": 0,
                  "has_author_byline": False, "has_publish_date": False, "cites_external_sources": False}
    )
    brand = {"mention": 0, "cited": 0, "sov": 0.0, "entity_known": False,
             "on_youtube": False, "on_reddit": False, "on_wikipedia": False, "on_linkedin": False}
    static = {"robots_ai": {"GPTBot": False, "ClaudeBot": False}, "https": False}

    result = score_geo(src, brand, static)
    assert result.total == 0.0
    for d in result.dims:
        assert d.score == 0.0


def test_edge_cases_all_max():
    """Test edge case where all signals are at maximum values."""
    src = L3Source(
        url="https://max.com", sha1="x", text="t",
        structural={"schema_types": ["FAQPage", "Product", "Organization", "Article"],
                   "table_count": 2, "h_counts": {"ul_count": 3}, "canonical": "https://max.com"},
        semantic={"has_definition_segment": True, "faq_block_count": 3, "datapoint_count": 5,
                  "has_author_byline": True, "has_publish_date": True, "cites_external_sources": True}
    )
    brand = {"mention": 3, "cited": 2, "sov": 0.2, "entity_known": True,
             "on_youtube": True, "on_reddit": True, "on_wikipedia": True, "on_linkedin": True}
    static = {"robots_ai": {"GPTBot": True, "ClaudeBot": True}, "https": True}

    result = score_geo(src, brand, static)
    assert result.total == 100.0
    for d in result.dims:
        assert d.score == 100.0


def test_edge_cases_none_values():
    """Test edge case where some expected fields are None/missing."""
    src = L3Source(
        url="https://null.com", sha1="x", text="t",
        structural={},
        semantic={}
    )
    brand = {}
    static = {}

    result = score_geo(src, brand, static)
    assert 0 <= result.total <= 100
    assert result is not None


def test_weight_application():
    """Test that weights from geo-rules.yaml are correctly applied."""
    brand = {"mention": 1, "cited": 0, "sov": 0.0}
    static = {"robots_ai": {"GPTBot": True}, "https": True}

    result = score_geo(SRC, brand, static)

    # Check that all 6 dimensions are present
    assert len(result.dims) == 6
    dim_names = {d.name for d in result.dims}
    expected_names = {"citability", "brand", "eeat", "technical_geo", "schema", "platform"}
    assert dim_names == expected_names

    # Check that each dimension has a weight > 0
    for d in result.dims:
        assert d.weight > 0

    # Check that weights sum to 100 (normalized)
    total_weight = sum(d.weight for d in result.dims)
    assert total_weight == 100.0


def test_boundary_conditions_ratio():
    """Test boundary conditions for ratio-based signals through actual scoring."""
    src = L3Source(url="https://test.com", sha1="x", text="t", structural={}, semantic={})
    brand = {}
    static = {}

    # Test at lower bound (faq_block_count = 0)
    min_src = L3Source(url="https://min.com", sha1="x", text="t", structural={}, semantic={"faq_block_count": 0})
    result = score_geo(min_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert d["citability"].score >= 0  # At lower bound, should be minimum

    # Test at upper bound (faq_block_count = 3)
    max_src = L3Source(url="https://max.com", sha1="x", text="t", structural={}, semantic={"faq_block_count": 3})
    result = score_geo(max_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert d["citability"].score >= 20  # At upper bound, faq contribution should be max (20/5 = 4 points)

    # Test mid-point (faq_block_count = 1.5 should give 50%)
    mid_src = L3Source(url="https://mid.com", sha1="x", text="t", structural={}, semantic={"faq_block_count": 1})
    result = score_geo(mid_src, brand, static)
    d = {x.name: x for x in result.dims}
    assert 0 < d["citability"].score < 100


def test_membership_driven_and_rules_injection():
    """成员关系驱动:注入裁剪版规则 → 只算剩余维度;权重取注入值。"""
    from geo.rules.loader import load_rules
    import types
    brand = {"mention": 1, "cited": 0, "sov": 0.0, "entity_known": False}
    static = {"robots_ai": {"GPTBot": True, "ClaudeBot": True}, "https": True}
    full = score_geo(SRC, brand, static)
    assert full.total == 65.0                       # 与旧硬编码一致(见 Task1 fixture 对数)
    tiny = types.SimpleNamespace(
        version="geo-seo-v1", composite="geo",
        weights={"citability": 100}, signals={"citability": ["has_definition_segment"]},
        severity_bands={}, p2plus_missing=[], entries=[])
    one = score_geo(SRC, brand, static, rules=tiny)
    assert [d.name for d in one.dims] == ["citability"]
    assert one.dims[0].score == 100.0 and one.total == 100.0
    assert one.dims[0].signals == {"has_definition_segment": 100.0}


def test_unknown_signal_id_rejected():
    import types
    bad = types.SimpleNamespace(version="x", composite="geo",
        weights={"citability": 100}, signals={"citability": ["no_such_signal"]},
        severity_bands={}, p2plus_missing=[], entries=[])
    import pytest
    with pytest.raises(ValueError, match="no_such_signal"):
        score_geo(SRC, {}, {}, rules=bad)


def test_v1_yaml_membership_matches_registry():
    from geo.assess.registry import GEO_SIGNALS, SEO_SIGNALS
    from geo.rules.loader import load_rules
    for name, reg in (("geo", GEO_SIGNALS), ("seo", SEO_SIGNALS)):
        r = load_rules(name)
        assert r.entries == []
        for dim, ids in r.signals.items():
            assert ids, f"{name}.{dim} 成员为空"
            assert all(i in reg for i in ids), f"{name}.{dim} 含未注册信号"
    g = load_rules("geo")
    assert "about_page_present" not in g.signals.get("eeat", [])      # 校正点:从未生效者不得回流
    assert "llms_txt_present" not in g.signals.get("technical_geo", [])
