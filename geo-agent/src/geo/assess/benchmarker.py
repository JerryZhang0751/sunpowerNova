"""Benchmarker: competitive differential analysis using same-rubric P0 proxy caliber."""

from __future__ import annotations
from geo.shared.models import CompositeScore


def gap(self_geo: CompositeScore, comp_geos: list[CompositeScore], metrics: dict) -> dict:
    """
    Calculate competitive differential (brand vs competitors) using same P0 proxy caliber.

    Args:
        self_geo: Brand's composite score (self-audit L3+static)
        comp_geos: List of competitor composite scores (L3 of cited_sources)
        metrics: Additional SOV/mention/citation/position metrics to pass through

    Returns:
        dict with:
        - self_total: Brand's total score
        - comp_avg_total: Average total score across competitors
        - dim_diff: Dict of dimension_name -> (self_score - competitor_avg_score)
        - metrics: Passthrough of input metrics (SOV, mention, citation, position, etc.)
    """
    def avg(score: CompositeScore, dim_name: str) -> float:
        """Extract average score for a specific dimension from a CompositeScore."""
        values = [d.score for d in score.dims if d.name == dim_name]
        return sum(values) / len(values) if values else 0.0

    # Get all dimension names from self_geo (only dimensions brand has)
    dim_names = [d.name for d in self_geo.dims]

    # Calculate differential for each dimension
    dim_diff = {}
    for dim_name in dim_names:
        # Calculate competitor average for this dimension
        # Only include competitors that actually have this dimension (avg > 0)
        comp_scores = [avg(comp, dim_name) for comp in comp_geos if avg(comp, dim_name) > 0]
        comp_avg = sum(comp_scores) / max(1, len(comp_scores))

        # Calculate differential (self - competitor_avg), rounded to 1 decimal
        self_score = avg(self_geo, dim_name)
        dim_diff[dim_name] = round(self_score - comp_avg, 1)

    # Calculate total score averages
    comp_avg_total = round(
        sum(comp.total for comp in comp_geos) / max(1, len(comp_geos)), 1
    )

    return {
        "self_total": self_geo.total,
        "comp_avg_total": comp_avg_total,
        "dim_diff": dim_diff,
        "metrics": metrics
    }
