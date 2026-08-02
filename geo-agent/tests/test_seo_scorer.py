from geo.assess.seo_scorer import score_seo

# Test fixtures from the brief
PAGE = {
    "http_status": 200,
    "https": True,
    "in_sitemap": True,
    "robots_not_blocked": True,
    "canonical_self": True,
    "has_viewport": True,
    "schema_types": ["Organization"],
    "title": "Best solar battery 2026 - SunHestia Guide",
    "meta_desc": "Discover the best solar battery for 2026 with expert reviews and comparisons.",
    "h_counts": {"h1": 1, "h2": 2, "h3": 0}
}

GSC = {
    "impressions": 500,
    "clicks": 20,
    "ctr": 0.04
}

CONTENT = {
    "word_count": 1200,
    "has_author_byline": True,
    "has_publish_date": True,
    "cites_external_sources": True
}


def test_seo_deterministic():
    """Test that SEO scoring is deterministic."""
    c1 = score_seo(PAGE, GSC, CONTENT)
    c2 = score_seo(PAGE, GSC, CONTENT)
    assert c1.total == c2.total
    assert 0 <= c1.total <= 100


def test_crawlability_dimension_max():
    """Test crawlability_index dimension at maximum."""
    d = {x.name: x for x in score_seo(PAGE, GSC, CONTENT).dims}
    assert d["crawlability_index"].score == 100.0


def test_crawlability_dimension_min():
    """Test crawlability_index dimension at minimum."""
    min_page = {
        "http_status": 404,
        "https": False,
        "in_sitemap": False,
        "robots_not_blocked": False,
        "canonical_self": False
    }
    result = score_seo(min_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["crawlability_index"].score == 0.0


def test_crawlability_dimension_partial():
    """Test crawlability_index dimension with partial signals."""
    partial_page = {
        "http_status": 200,
        "https": True,
        "in_sitemap": True,
        "robots_not_blocked": False,  # Only this fails
        "canonical_self": True
    }
    result = score_seo(partial_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["crawlability_index"].score == 80.0  # 4/5 = 80%


def test_technical_foundation_dimension_max():
    """Test technical_foundation dimension at maximum."""
    d = {x.name: x for x in score_seo(PAGE, GSC, CONTENT).dims}
    assert d["technical_foundation"].score == 100.0


def test_technical_foundation_dimension_min():
    """Test technical_foundation dimension at minimum."""
    min_page = {
        "https": False,
        "has_viewport": False,
        "http2": False,
        "renderable_static": False
    }
    result = score_seo(min_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["technical_foundation"].score == 0.0


def test_technical_foundation_dimension_partial():
    """Test technical_foundation dimension with partial signals."""
    partial_page = {
        "https": True,
        "has_viewport": False,  # Only this fails
        "http2": True,
        "renderable_static": True
    }
    result = score_seo(partial_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["technical_foundation"].score == 75.0  # 3/4 = 75%


def test_on_page_dimension_max():
    """Test on_page dimension at maximum."""
    max_page = {
        "title": "Best solar battery 2026 - Complete SunHestia Guide",  # 48 chars, in range
        "meta_desc": "Discover the best solar battery with expert reviews.",
        "h_counts": {"h1": 1, "h2": 2, "h3": 1}
    }
    result = score_seo(max_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score == 100.0


def test_on_page_dimension_min():
    """Test on_page dimension at minimum."""
    min_page = {
        "title": "",  # Empty
        "meta_desc": "",  # Empty
        "h_counts": {"h1": 0, "h2": 0, "h3": 0}
    }
    result = score_seo(min_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score == 0.0


def test_on_page_dimension_title_too_short():
    """Test on_page dimension with title too short."""
    short_title_page = {
        "title": "Solar",  # Only 5 chars, too short
        "meta_desc": "Good description here",
        "h_counts": {"h1": 1, "h2": 1, "h3": 0}
    }
    result = score_seo(short_title_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score < 100.0


def test_on_page_dimension_title_too_long():
    """Test on_page dimension with title too long."""
    long_title_page = {
        "title": "This is an extremely long title that exceeds the recommended length of 60 characters for SEO",
        "meta_desc": "Good description here",
        "h_counts": {"h1": 1, "h2": 1, "h3": 0}
    }
    result = score_seo(long_title_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score < 100.0


def test_on_page_dimension_heading_hierarchy():
    """Test on_page dimension with heading hierarchy issues."""
    bad_hierarchy_page = {
        "title": "Good title length here",
        "meta_desc": "Good description",
        "h_counts": {"h1": 2, "h2": 0, "h3": 0}  # Multiple H1, no H2
    }
    result = score_seo(bad_hierarchy_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score < 100.0


def test_content_eeat_dimension_max():
    """Test content_eeat dimension at maximum."""
    max_content = {
        "word_count": 1500,  # Max word count for 100.0 score
        "has_author_byline": True,
        "has_publish_date": True,
        "cites_external_sources": True
    }
    d = {x.name: x for x in score_seo(PAGE, GSC, max_content).dims}
    assert d["content_eeat"].score == 100.0


def test_content_eeat_dimension_min():
    """Test content_eeat dimension at minimum."""
    min_content = {
        "word_count": 0,
        "has_author_byline": False,
        "has_publish_date": False,
        "cites_external_sources": False
    }
    result = score_seo(PAGE, GSC, min_content)
    d = {x.name: x for x in result.dims}
    assert d["content_eeat"].score == 0.0


def test_content_eeat_dimension_word_count_ratio():
    """Test content_eeat dimension with varying word counts."""
    # Test at lower bound (300 words)
    low_content = {
        "word_count": 300,
        "has_author_byline": True,
        "has_publish_date": True,
        "cites_external_sources": True
    }
    result = score_seo(PAGE, GSC, low_content)
    d = {x.name: x for x in result.dims}
    assert d["content_eeat"].score >= 75.0  # 3/4 signals max, word count at min

    # Test at upper bound (1500 words)
    high_content = {
        "word_count": 1500,
        "has_author_byline": True,
        "has_publish_date": True,
        "cites_external_sources": True
    }
    result = score_seo(PAGE, GSC, high_content)
    d = {x.name: x for x in result.dims}
    assert d["content_eeat"].score == 100.0

    # Test mid-range (900 words)
    mid_content = {
        "word_count": 900,
        "has_author_byline": True,
        "has_publish_date": True,
        "cites_external_sources": True
    }
    result = score_seo(PAGE, GSC, mid_content)
    d = {x.name: x for x in result.dims}
    assert 75.0 < d["content_eeat"].score < 100.0


def test_authority_dimension_max():
    """Test authority dimension at maximum."""
    max_gsc = {
        "impressions": 1000,
        "clicks": 50,
        "ctr": 0.05
    }
    result = score_seo(PAGE, max_gsc, CONTENT)
    d = {x.name: x for x in result.dims}
    # Authority max should be lower due to P2+ missing signals
    assert d["authority"].score > 0.0
    assert d["authority"].signals.get("p2plus_degraded") is True


def test_authority_dimension_min():
    """Test authority dimension at minimum."""
    min_gsc = {
        "impressions": 0,
        "clicks": 0,
        "ctr": 0.0
    }
    result = score_seo(PAGE, min_gsc, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["authority"].score == 0.0


def test_authority_dimension_p2plus_degraded_flag():
    """Test that authority dimension sets p2plus_degraded flag."""
    result = score_seo(PAGE, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["authority"].signals.get("p2plus_degraded") is True
    assert d["authority"].signals.get("backlinks_est") == "unknown"
    assert d["authority"].signals.get("domain_authority") == "unknown"


def test_authority_dimension_gsc_ratio():
    """Test authority dimension with varying GSC metrics."""
    # Test mid-range GSC
    mid_gsc = {
        "impressions": 500,
        "clicks": 25,
        "ctr": 0.025
    }
    result = score_seo(PAGE, mid_gsc, CONTENT)
    d = {x.name: x for x in result.dims}
    assert 0 < d["authority"].score < 100


def test_weight_application():
    """Test that weights from seo-rules.yaml are correctly applied."""
    result = score_seo(PAGE, GSC, CONTENT)

    # Check that all 5 dimensions are present
    assert len(result.dims) == 5
    dim_names = {d.name for d in result.dims}
    expected_names = {"crawlability_index", "technical_foundation", "on_page", "content_eeat", "authority"}
    assert dim_names == expected_names

    # Check that each dimension has the correct weight
    d = {x.name: x for x in result.dims}
    assert d["crawlability_index"].weight == 20
    assert d["technical_foundation"].weight == 10
    assert d["on_page"].weight == 25
    assert d["content_eeat"].weight == 25
    assert d["authority"].weight == 20

    # Check that weights sum to 100
    total_weight = sum(d.weight for d in result.dims)
    assert total_weight == 100.0


def test_edge_cases_all_zeros():
    """Test edge case where all signals are zero/None/False."""
    zero_page = {
        "http_status": 0,
        "https": False,
        "in_sitemap": False,
        "robots_not_blocked": False,
        "canonical_self": False,
        "has_viewport": False,
        "http2": False,  # Explicitly set to False to override default
        "renderable_static": False,  # Explicitly set to False to override default
        "title": "",
        "meta_desc": "",
        "h_counts": {"h1": 0, "h2": 0, "h3": 0}
    }
    zero_gsc = {
        "impressions": 0,
        "clicks": 0,
        "ctr": 0.0
    }
    zero_content = {
        "word_count": 0,
        "has_author_byline": False,
        "has_publish_date": False,
        "cites_external_sources": False
    }

    result = score_seo(zero_page, zero_gsc, zero_content)
    assert result.total == 0.0
    for d in result.dims:
        assert d.score == 0.0


def test_edge_cases_all_max():
    """Test edge case where all signals are at maximum values."""
    max_page = {
        "http_status": 200,
        "https": True,
        "in_sitemap": True,
        "robots_not_blocked": True,
        "canonical_self": True,
        "has_viewport": True,
        "http2": True,
        "renderable_static": True,
        "title": "Perfect title length here for SEO",
        "meta_desc": "Great meta description for testing purposes",
        "h_counts": {"h1": 1, "h2": 2, "h3": 1}
    }
    max_gsc = {
        "impressions": 1000,
        "clicks": 50,
        "ctr": 0.05
    }
    max_content = {
        "word_count": 1500,
        "has_author_byline": True,
        "has_publish_date": True,
        "cites_external_sources": True
    }

    result = score_seo(max_page, max_gsc, max_content)
    # Total should be high (note: authority still degraded)
    assert result.total > 80.0  # High but not 100 due to P2+ degradation


def test_edge_cases_none_values():
    """Test edge case where some expected fields are None/missing."""
    minimal_page = {
        "http_status": 200,
        "https": True,
        # Other fields missing
    }
    minimal_gsc = {}
    minimal_content = {}

    result = score_seo(minimal_page, minimal_gsc, minimal_content)
    assert 0 <= result.total <= 100
    assert result is not None
    assert len(result.dims) == 5  # All dimensions should be present


def test_boundary_conditions_word_count():
    """Test boundary conditions for word_count ratio."""
    # At lower bound (300 words)
    low_page = PAGE.copy()
    low_content = {"word_count": 300, "has_author_byline": True, "has_publish_date": True, "cites_external_sources": True}
    result = score_seo(low_page, GSC, low_content)
    d = {x.name: x for x in result.dims}
    assert d["content_eeat"].score >= 75.0  # 3/4 signals + word_count at min

    # At upper bound (1500 words)
    high_page = PAGE.copy()
    high_content = {"word_count": 1500, "has_author_byline": True, "has_publish_date": True, "cites_external_sources": True}
    result = score_seo(high_page, GSC, high_content)
    d = {x.name: x for x in result.dims}
    assert d["content_eeat"].score == 100.0

    # Mid-range (900 words - should give ~50% of word_count score)
    mid_page = PAGE.copy()
    mid_content = {"word_count": 900, "has_author_byline": True, "has_publish_date": True, "cites_external_sources": True}
    result = score_seo(mid_page, GSC, mid_content)
    d = {x.name: x for x in result.dims}
    assert 75.0 < d["content_eeat"].score < 100.0


def test_boundary_conditions_title_length():
    """Test boundary conditions for title length."""
    # At lower bound (40 chars)
    min_title_page = PAGE.copy()
    min_title_page["title"] = "Perfect title length here for SEO guides"  # 40 chars
    min_title_page["meta_desc"] = "Good meta desc"
    min_title_page["h_counts"] = {"h1": 1, "h2": 1, "h3": 0}
    result = score_seo(min_title_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score == 100.0  # All signals pass

    # At upper bound (60 chars)
    max_title_page = PAGE.copy()
    max_title_page["title"] = "Perfect title length here for SEO optimization and best"  # 60 chars
    max_title_page["meta_desc"] = "Good meta desc"
    max_title_page["h_counts"] = {"h1": 1, "h2": 1, "h3": 0}
    result = score_seo(max_title_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score == 100.0  # All signals pass

    # Below lower bound (30 chars)
    short_page = PAGE.copy()
    short_page["title"] = "Too short title"  # 14 chars
    short_page["meta_desc"] = "Good meta desc"
    short_page["h_counts"] = {"h1": 1, "h2": 1, "h3": 0}
    result = score_seo(short_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score < 100.0

    # Above upper bound (70 chars)
    long_page = PAGE.copy()
    long_page["title"] = "This is an extremely long title that exceeds the recommended length"  # 72 chars
    long_page["meta_desc"] = "Good meta desc"
    long_page["h_counts"] = {"h1": 1, "h2": 1, "h3": 0}
    result = score_seo(long_page, GSC, CONTENT)
    d = {x.name: x for x in result.dims}
    assert d["on_page"].score < 100.0


def test_total_score_range():
    """Test that total score is always in range [0, 100]."""
    # Test various input combinations
    test_cases = [
        (PAGE, GSC, CONTENT),  # Good case
        ({"http_status": 200, "https": True}, {"impressions": 100}, {}),  # Minimal case
        ({"http_status": 404, "https": False}, {"impressions": 0}, {"word_count": 0}),  # Bad case
        ({"http_status": 200, "https": True, "in_sitemap": True}, {"impressions": 500, "clicks": 10},
         {"word_count": 800, "has_author_byline": True}),  # Mixed case
    ]

    for page, gsc, content in test_cases:
        result = score_seo(page, gsc, content)
        assert 0 <= result.total <= 100, f"Total {result.total} out of range for inputs: page={page}, gsc={gsc}, content={content}"


def test_signals_in_dimensions():
    """Test that dimensions contain the expected signal information."""
    result = score_seo(PAGE, GSC, CONTENT)
    d = {x.name: x for x in result.dims}

    # Check crawlability signals
    assert "in_sitemap" in d["crawlability_index"].signals
    assert "canonical_self" in d["crawlability_index"].signals

    # Check technical_foundation signals
    assert "https" in d["technical_foundation"].signals
    assert "viewport" in d["technical_foundation"].signals

    # Check on_page signals
    assert "title" in d["on_page"].signals
    assert "h" in d["on_page"].signals

    # Check content_eeat signals
    assert d["content_eeat"].signals == CONTENT

    # Check authority signals
    assert "impressions" in d["authority"].signals
    assert "p2plus_degraded" in d["authority"].signals


def test_invalid_dimension_name():
    """Test that invalid dimension names raise ValueError."""
    from geo.assess.seo_scorer import _dim
    import pytest

    with pytest.raises(ValueError, match="Dimension 'invalid_dim' not found"):
        _dim("invalid_dim", 50.0, {})


def test_seo_independent_from_geo():
    """Test that SEO scoring is independent from GEO system."""
    # SEO scorer should not use GEO-specific signals
    result = score_seo(PAGE, GSC, CONTENT)

    # Should have exactly 5 SEO dimensions, not 6 GEO dimensions
    assert len(result.dims) == 5

    # Should not contain GEO-specific dimensions
    dim_names = {d.name for d in result.dims}
    geo_dimensions = {"citability", "brand", "platform", "technical_geo", "schema", "eeat"}
    assert not dim_names.intersection(geo_dimensions), "SEO dimensions should not include GEO dimensions"

    # Should contain SEO-specific dimensions
    seo_dimensions = {"crawlability_index", "technical_foundation", "on_page", "content_eeat", "authority"}
    assert dim_names == seo_dimensions
