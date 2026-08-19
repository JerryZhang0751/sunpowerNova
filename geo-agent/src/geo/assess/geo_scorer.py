# src/geo/assess/geo_scorer.py
from __future__ import annotations
from geo.shared.models import L3Source, DimScore, CompositeScore
from geo.rules.loader import load_rules
from geo.assess.registry import GEO_SIGNALS


def score_geo(src: L3Source, brand: dict, static: dict, rules=None) -> CompositeScore:
    """Membership-driven GEO scoring:维度分 = 成员 checker 均值,权重读 rules。"""
    r = rules or load_rules("geo")
    unknown = [s for ids in r.signals.values() for s in ids if s not in GEO_SIGNALS]
    if unknown:
        raise ValueError(f"unknown geo signals: {unknown}; available: {sorted(GEO_SIGNALS)}")
    if set(r.signals) != set(r.weights):
        raise ValueError(f"signals dims {sorted(r.signals)} != weights dims {sorted(r.weights)}")
    dims = []
    for dim, sig_ids in r.signals.items():          # YAML 顺序 = 维度顺序(与旧硬编码一致)
        vals = {sid: GEO_SIGNALS[sid](src, brand, static) for sid in sig_ids}
        score = round(sum(vals.values()) / len(vals), 1)
        dims.append(DimScore(name=dim, score=score, weight=r.weights[dim], signals=vals))
    total = round(sum(d.score * d.weight for d in dims) / 100.0, 1)
    return CompositeScore(total=total, dims=dims)