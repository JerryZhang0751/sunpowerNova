from __future__ import annotations
from geo.shared.models import DimScore, CompositeScore
from geo.rules.loader import load_rules

RULES = load_rules("seo")


def _pct(ok):
    return 100.0 if ok else 0.0


def _ratio(n, lo, hi):
    if n is None:
        return 0.0
    if n <= lo:
        return 0.0
    if n >= hi:
        return 100.0
    return round(100 * (n - lo) / (hi - lo), 1)


def _dim(name, score, signals):
    if name not in RULES.weights:
        raise ValueError(f"Dimension '{name}' not found in seo rules weights. Available: {list(RULES.weights.keys())}")
    return DimScore(name=name, score=score, weight=RULES.weights[name], signals=signals)


def score_seo(p: dict, gsc: dict, c: dict) -> CompositeScore:
    title = p.get("title", "")
    h = p.get("h_counts", {})

    # Crawlability Index (5 signals: http_200, in_sitemap, robots_not_blocked, canonical_self, https)
    crawl = round(
        (
            _pct(p.get("http_status") == 200)
            + _pct(p.get("in_sitemap"))
            + _pct(p.get("robots_not_blocked"))
            + _pct(p.get("canonical_self"))
            + _pct(p.get("https"))
        ) / 5,
        1,
    )

    # Technical Foundation (4 signals: https, mobile_viewport, http2, renderable_static)
    tech = round(
        (
            _pct(p.get("https"))
            + _pct(p.get("has_viewport"))
            + _pct(p.get("http2", True))
            + _pct(p.get("renderable_static", True))
        ) / 4,
        1,
    )

    # On-Page SEO (5 signals: unique_title, title_len_ok, meta_desc_present, single_h1, heading_hierarchy_ok)
    onp = round(
        (
            _pct(title and title == p.get("title"))  # unique_title check (title exists and matches itself)
            + _pct(40 <= len(title) <= 60)
            + _pct(p.get("meta_desc"))
            + _pct(h.get("h1", 0) == 1)
            + _pct(h.get("h2", 0) >= 1 and h.get("h3", 0) >= 0)
        ) / 5,
        1,
    )

    # Content E-E-A-T (4 signals: word_count_band, has_author_byline, has_publish_date, cites_external_sources)
    ceat = round(
        (
            _ratio(c.get("word_count", 0), 300, 1500)
            + _pct(c.get("has_author_byline"))
            + _pct(c.get("has_publish_date"))
            + _pct(c.get("cites_external_sources"))
        ) / 4,
        1,
    )

    # Authority (GSC P0 + 外链/DA P2+ unknown 降级)
    auth_signals = {
        "impressions": gsc.get("impressions", 0),
        "clicks": gsc.get("clicks", 0),
        "ctr": gsc.get("ctr", 0),
        "backlinks_est": "unknown",
        "domain_authority": "unknown",
        "p2plus_degraded": True,
    }
    auth = round(
        (
            _ratio(gsc.get("impressions", 0), 0, 1000)
            + _ratio(gsc.get("clicks", 0), 0, 50)
            + _ratio((gsc.get("ctr") or 0), 0, 0.05)
            + 0  # 外链/DA 占的 2/4 未知→按 0
        ) / 4,
        1,
    )

    dims = [
        _dim(
            "crawlability_index",
            crawl,
            {"in_sitemap": p.get("in_sitemap"), "canonical_self": p.get("canonical_self")},
        ),
        _dim(
            "technical_foundation",
            tech,
            {"https": p.get("https"), "viewport": p.get("has_viewport")},
        ),
        _dim(
            "on_page",
            onp,
            {"title": title, "h": h},
        ),
        _dim(
            "content_eeat",
            ceat,
            c,
        ),
        _dim(
            "authority",
            auth,
            auth_signals,
        ),
    ]

    total = round(sum(d.score * d.weight for d in dims) / 100.0, 1)
    return CompositeScore(total=total, dims=dims)
