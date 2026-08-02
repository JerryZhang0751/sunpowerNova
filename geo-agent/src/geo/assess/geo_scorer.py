from __future__ import annotations
from geo.shared.models import L3Source, DimScore, CompositeScore
from geo.rules.loader import load_rules

RULES = load_rules("geo")


def _pct(ok):
    return 100.0 if ok else 0.0


def _ratio(n, lo, hi):  # n in [lo,hi] → 0..100
    if n <= lo:
        return 0.0
    if n >= hi:
        return 100.0
    return round(100 * (n - lo) / (hi - lo), 1)


def _dim(name, score, signals):
    if name not in RULES.weights:
        raise ValueError(f"Dimension '{name}' not found in geo rules weights. Available: {list(RULES.weights.keys())}")
    return DimScore(name=name, score=score, weight=RULES.weights[name], signals=signals)


def score_geo(src: L3Source, brand: dict, static: dict) -> CompositeScore:
    sem = src.semantic or {}
    st = src.structural or {}
    schemas = st.get("schema_types", [])
    h = st.get("h_counts", {})
    dims = [
        _dim(
            "citability",
            round(
                (
                    _pct(sem.get("has_definition_segment"))
                    + _ratio(sem.get("faq_block_count", 0), 0, 3)
                    + _ratio(st.get("table_count", 0), 0, 2)
                    + _ratio(sem.get("datapoint_count", 0), 0, 5)
                    + _ratio(h.get("ul_count", 0), 0, 3)
                )
                / 5,
                1,
            ),
            {k: sem.get(k) for k in ("has_definition_segment", "faq_block_count", "datapoint_count")},
        ),
        _dim(
            "brand",
            round(
                (
                    _ratio(brand.get("mention", 0), 0, 3)
                    + _ratio(brand.get("cited", 0), 0, 2)
                    + _ratio(brand.get("sov", 0.0), 0, 0.2)
                    + _pct(brand.get("entity_known"))
                )
                / 4,
                1,
            ),
            brand,
        ),
        _dim(
            "eeat",
            round(
                (
                    _pct(sem.get("has_author_byline"))
                    + _pct(sem.get("has_publish_date"))
                    + _pct(sem.get("cites_external_sources"))
                    + _pct("Organization" in schemas or "Person" in schemas)
                )
                / 4,
                1,
            ),
            {k: sem.get(k) for k in ("has_author_byline", "has_publish_date", "cites_external_sources")},
        ),
        _dim(
            "technical_geo",
            round(
                (
                    _pct((static.get("robots_ai") or {}).get("GPTBot"))
                    + _pct((static.get("robots_ai") or {}).get("ClaudeBot"))
                    + _pct(static.get("https"))
                    + _pct(src.structural.get("canonical"))
                )
                / 4,
                1,
            ),
            static,
        ),
        _dim(
            "schema",
            round(
                (
                    _ratio(len(schemas), 0, 3)
                    + _pct("FAQPage" in schemas)
                    + _pct("Product" in schemas)
                    + _pct("Organization" in schemas)
                    + _pct("Article" in schemas)
                )
                / 5,
                1,
            ),
            {"schema_types": schemas},
        ),
        _dim(
            "platform",
            round(
                (
                    _pct(brand.get("on_youtube"))
                    + _pct(brand.get("on_reddit"))
                    + _pct(brand.get("on_wikipedia"))
                    + _pct(brand.get("on_linkedin"))
                )
                / 4,
                1,
            ),
            {k: brand.get(k) for k in ("on_youtube", "on_reddit", "on_wikipedia", "on_linkedin")},
        ),
    ]
    total = round(sum(d.score * d.weight for d in dims) / 100.0, 1)
    return CompositeScore(total=total, dims=dims)
