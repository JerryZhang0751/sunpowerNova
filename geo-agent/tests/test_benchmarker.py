"""Comprehensive tests for benchmarker module - competitive differential analysis."""

from geo.assess.benchmarker import gap
from geo.shared.models import CompositeScore, DimScore


def mk_comp(t, dim_name="schema"):
    """Helper to create CompositeScore for testing."""
    return CompositeScore(
        total=t,
        dims=[DimScore(name=dim_name, score=t, weight=10, signals={})]
    )


def mk_multi_comp(total, dim_configs):
    """Helper to create CompositeScore with multiple dimensions."""
    dims = [DimScore(name=name, score=score, weight=10, signals={})
            for name, score in dim_configs.items()]
    return CompositeScore(total=total, dims=dims)


def test_gap_basic_single_dim():
    """Test basic gap calculation with single dimension."""
    self_geo = mk_comp(80)
    comp_geos = [mk_comp(60), mk_comp(70)]
    metrics = {"mention": 0.1, "citation": 0.0, "sov": 0.05, "position": None}

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics=metrics)

    # Competitor average = (60 + 70) / 2 = 65
    # Self - Comp_avg = 80 - 65 = 15
    assert result["dim_diff"]["schema"] == 15.0
    assert result["self_total"] == 80.0
    assert result["comp_avg_total"] == 65.0
    assert result["metrics"]["mention"] == 0.1
    assert result["metrics"]["sov"] == 0.05
    assert result["metrics"]["citation"] == 0.0
    assert result["metrics"]["position"] is None


def test_gap_signed_differential():
    """Test that differential can be negative (competitor stronger)."""
    # Self weaker than competitors
    self_geo = mk_comp(50)
    comp_geos = [mk_comp(70), mk_comp(80)]

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    # Competitor avg = 75, Self - Comp = 50 - 75 = -25
    assert result["dim_diff"]["schema"] == -25.0
    assert result["self_total"] == 50.0
    assert result["comp_avg_total"] == 75.0


def test_gap_multi_dimension():
    """Test gap calculation across multiple dimensions."""
    self_geo = mk_multi_comp(75, {"schema": 80, "content": 70, "technical": 75})
    comp_geos = [
        mk_multi_comp(60, {"schema": 60, "content": 55, "technical": 65}),
        mk_multi_comp(70, {"schema": 70, "content": 65, "technical": 75})
    ]

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    # Schema: (80) - ((60+70)/2) = 80 - 65 = 15
    assert result["dim_diff"]["schema"] == 15.0
    # Content: (70) - ((55+65)/2) = 70 - 60 = 10
    assert result["dim_diff"]["content"] == 10.0
    # Technical: (75) - ((65+75)/2) = 75 - 70 = 5
    assert result["dim_diff"]["technical"] == 5.0
    assert result["self_total"] == 75.0
    assert result["comp_avg_total"] == 65.0


def test_gap_single_competitor():
    """Test with single competitor."""
    self_geo = mk_comp(80)
    comp_geos = [mk_comp(60)]

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    # Single competitor, no averaging needed
    assert result["dim_diff"]["schema"] == 20.0
    assert result["comp_avg_total"] == 60.0


def test_gap_empty_competitors():
    """Test with no competitors - should not crash."""
    self_geo = mk_comp(80)
    comp_geos = []

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    # With no competitors, comp_avg should be 0 (via max(1, len) protection)
    assert result["dim_diff"]["schema"] == 80.0
    assert result["comp_avg_total"] == 0.0


def test_gap_rounding():
    """Test that scores are properly rounded to 1 decimal place."""
    self_geo = mk_comp(80.666)
    comp_geos = [mk_comp(60.333), mk_comp(70.888)]

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    # (60.333 + 70.888) / 2 = 65.6105, 80.666 - 65.6105 = 15.0555 -> 15.1
    assert result["dim_diff"]["schema"] == 15.1
    assert result["self_total"] == 80.666  # No rounding on input
    # (60.333 + 70.888) / 2 = 65.6105 -> 65.6
    assert result["comp_avg_total"] == 65.6


def test_gap_mismatched_dimensions():
    """Test when self and competitors have different dimension sets."""
    self_geo = mk_multi_comp(75, {"schema": 80, "content": 70})
    comp_geos = [
        mk_multi_comp(60, {"schema": 60, "technical": 50}),  # Missing 'content'
        mk_multi_comp(70, {"schema": 70, "content": 65, "technical": 75})  # Has 'technical'
    ]

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    # Schema: both competitors have it -> (60 + 70) / 2 = 65, 80 - 65 = 15
    assert result["dim_diff"]["schema"] == 15.0

    # Content: only second competitor has it -> 65 / 1 = 65, 70 - 65 = 5
    # But since only 1 comp has it, should be 70 - 65 = 5
    assert result["dim_diff"]["content"] == 5.0

    # Technical: self doesn't have it, so shouldn't be in diff
    assert "technical" not in result["dim_diff"]


def test_metrics_passthrough():
    """Test that metrics are passed through correctly."""
    self_geo = mk_comp(80)
    comp_geos = [mk_comp(60)]

    metrics = {
        "mention": 0.15,
        "citation": 0.08,
        "sov": 0.12,
        "position": 3,
        "visibility": 0.85
    }

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics=metrics)

    assert result["metrics"]["mention"] == 0.15
    assert result["metrics"]["citation"] == 0.08
    assert result["metrics"]["sov"] == 0.12
    assert result["metrics"]["position"] == 3
    assert result["metrics"]["visibility"] == 0.85


def test_gap_deterministic():
    """Test that results are deterministic - no randomness."""
    self_geo = mk_comp(75)
    comp_geos = [mk_comp(60), mk_comp(70)]
    metrics = {"sov": 0.05}

    result1 = gap(self_geo=self_geo, comp_geos=comp_geos, metrics=metrics)
    result2 = gap(self_geo=self_geo, comp_geos=comp_geos, metrics=metrics)

    assert result1["dim_diff"]["schema"] == result2["dim_diff"]["schema"]
    assert result1["self_total"] == result2["self_total"]
    assert result1["comp_avg_total"] == result2["comp_avg_total"]
    assert result1["metrics"] == result2["metrics"]


def test_gap_zero_scores():
    """Test with zero scores."""
    self_geo = mk_comp(0)
    comp_geos = [mk_comp(0), mk_comp(0)]

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    assert result["dim_diff"]["schema"] == 0.0
    assert result["self_total"] == 0.0
    assert result["comp_avg_total"] == 0.0


def test_gap_perfect_scores():
    """Test with perfect (100) scores."""
    self_geo = mk_comp(100)
    comp_geos = [mk_comp(100), mk_comp(100)]

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    assert result["dim_diff"]["schema"] == 0.0
    assert result["self_total"] == 100.0
    assert result["comp_avg_total"] == 100.0


def test_gap_complex_realistic_scenario():
    """Test a realistic competitive scenario with mixed dimensions."""
    # Brand has strong schema but weak content
    self_geo = mk_multi_comp(72, {
        "schema": 85,      # Strong
        "content": 60,     # Weak
        "technical": 70,   # Mid
        "authority": 75    # Good
    })

    # Competitors: better content, weaker schema
    comp_geos = [
        mk_multi_comp(68, {"schema": 65, "content": 75, "technical": 70, "authority": 65}),
        mk_multi_comp(74, {"schema": 70, "content": 80, "technical": 75, "authority": 72}),
        mk_multi_comp(65, {"schema": 60, "content": 70, "technical": 62, "authority": 68})
    ]

    result = gap(self_geo=self_geo, comp_geos=comp_geos, metrics={})

    # Schema: 85 - ((65+70+60)/3) = 85 - 65 = 20 (advantage)
    assert result["dim_diff"]["schema"] == 20.0

    # Content: 60 - ((75+80+70)/3) = 60 - 75 = -15 (disadvantage)
    assert result["dim_diff"]["content"] == -15.0

    # Technical: 70 - ((70+75+62)/3) = 70 - 69 = 1 (slight advantage)
    assert result["dim_diff"]["technical"] == 1.0

    # Authority: 75 - ((65+72+68)/3) = 75 - 68.3 = 6.7
    assert result["dim_diff"]["authority"] == 6.7

    # Total averages
    assert result["self_total"] == 72.0
    assert round(result["comp_avg_total"], 1) == 69.0
