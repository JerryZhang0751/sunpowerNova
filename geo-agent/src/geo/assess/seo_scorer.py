# src/geo/assess/seo_scorer.py
from __future__ import annotations
from geo.shared.models import DimScore, CompositeScore
from geo.rules.loader import load_rules
from geo.assess.registry import SEO_SIGNALS


def score_seo(p: dict, gsc: dict, c: dict, rules=None) -> CompositeScore:
    """Membership-driven SEO scoring:维度分 = 成员 checker 均值,权重读 rules。"""
    r = rules or load_rules("seo")
    unknown = [s for ids in r.signals.values() for s in ids if s not in SEO_SIGNALS]
    if unknown:
        raise ValueError(f"unknown seo signals: {unknown}; available: {sorted(SEO_SIGNALS)}")
    if set(r.signals) != set(r.weights):
        raise ValueError(f"signals dims {sorted(r.signals)} != weights dims {sorted(r.weights)}")
    dims = []
    for dim, sig_ids in r.signals.items():
        vals = {sid: SEO_SIGNALS[sid](p, gsc, c) for sid in sig_ids}
        score = round(sum(vals.values()) / len(vals), 1)
        dims.append(DimScore(name=dim, score=score, weight=r.weights[dim], signals=vals))
    total = round(sum(d.score * d.weight for d in dims) / 100.0, 1)
    return CompositeScore(total=total, dims=dims)