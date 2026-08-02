"""Analyst: deterministic evaluation report assembly from L2 records, GEO/SEO scores, and competitive benchmarks."""

from __future__ import annotations
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from geo.shared.config import REPO, settings
from geo.shared.models import L1Record, L2Record


@dataclass
class MentionMetrics:
    """Metrics for brand mentions and citations per model."""
    model: str
    planned: int
    valid: int
    mention: int
    cited: int
    position_sum: float | None
    sov: float

    @property
    def mention_rate(self) -> float:
        """Calculate mention rate (mentions / valid responses)."""
        return round(self.mention / self.valid, 3) if self.valid else 0.0

    @property
    def citation_rate(self) -> float:
        """Calculate citation rate (citations with link / valid responses)."""
        return round(self.cited / self.valid, 3) if self.valid else 0.0

    @property
    def avg_position(self) -> float | None:
        """Calculate average citation position (only for citations)."""
        if self.position_sum is not None:
            return round(self.position_sum, 1)
        return None


def _iter_l1(week: int):
    """Iterate over L1 records for a given week from raw data."""
    root = REPO / "data" / "raw" / f"w{week}"
    for jp in root.rglob("r*.json"):
        yield L1Record(**json.loads(jp.read_text(encoding="utf-8")))


def assemble(week: int) -> dict:
    """
    Assemble deterministic evaluation report from L2 records, GEO/SEO scores, and competitive benchmarks.

    This function is deterministic - same inputs + rule_version → identical report.
    No LLM involvement, pure aggregation of versioned snapshots.

    Args:
        week: Week number to analyze

    Returns:
        dict: Evaluation report with metrics, scores, and competitive differentials
    """
    rule_version = settings.run.rule_version
    l1s = list(_iter_l1(week))

    # Group L1 records by model
    by_model = {}
    for l in l1s:
        by_model.setdefault(l.model, []).append(l)

    # Calculate metrics per model
    metrics = {}
    for model, items in by_model.items():
        valid = len(items)
        mention = sum(1 for i in items if i.l2.mentioned)
        cited = sum(1 for i in items if i.l2.cited_with_link)

        # Calculate average position (only for citations)
        positions = [i.l2.citation_position for i in items if i.l2.citation_position is not None]
        position_sum = sum(positions) / len(positions) if positions else None

        # Calculate SOV (Share of Voice - avg competitors mentioned per response)
        sov = round(
            sum(len(i.l2.competitors_mentioned) for i in items) / max(1, valid), 3
        )

        metrics[model] = MentionMetrics(
            model=model,
            planned=valid,
            valid=valid,
            mention=mention,
            cited=cited,
            position_sum=position_sum,
            sov=sov
        )

    # Get prompt set version from first L1 record (if available)
    prompt_set_version = l1s[0].prompt_set_version if l1s else ""

    # Build report structure
    report = {
        "week": week,
        "rule_version": rule_version,
        "prompt_set_version": prompt_set_version,
        "metrics": {
            model: {
                "planned": m.planned,
                "valid": m.valid,
                "mention_rate": m.mention_rate,
                "citation_rate": m.citation_rate,
                "avg_position": m.avg_position,
                "sov": m.sov
            }
            for model, m in metrics.items()
        },
        "self_geo": None,  # Placeholder for self-audit GEO score
        "self_seo": None,  # Placeholder for self-audit SEO score
        "gap": None,  # Placeholder for competitive differential
        "authority_gap_note": "权威分基于 P0 代理；外部权威(backlinks/DA)未计入"
    }

    # Create output directory
    out = REPO / "data" / "analysis" / f"w{week}"
    out.mkdir(parents=True, exist_ok=True)

    # Write eval_report.json
    (out / "eval_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    # Write source_scores.csv
    with (out / "source_scores.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "prompt_id", "mentioned", "cited", "position", "competitors"])
        for l in l1s:
            w.writerow([
                l.model,
                l.prompt_id,
                int(l.l2.mentioned),
                int(l.l2.cited_with_link),
                l.l2.citation_position if l.l2.citation_position else "",
                ";".join(l.l2.competitors_mentioned)
            ])

    return report