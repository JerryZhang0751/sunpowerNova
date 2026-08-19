# src/geo/rules/evidence.py
"""确定性证据提取:候选(声明式映射) + 维度证据强度。零 LLM。
证据口径 = 唯一 URL(页-周)计数(v1.1):with_n/unique_n/share/platforms 全部去重口径;
出现次数仅留在 aggregates 供 P1 展示,不进门槛。"""
from __future__ import annotations

# 声明式映射:checker id -> research_aggregates 桶。不在表内 = 无证据源,不会被提名。
ADD_CANDIDATES: dict[str, str] = {
    "has_breadcrumblist": "schema.BreadcrumbList",      # sources.schema_unique 桶
}
REMOVE_CANDIDATES: dict[str, str] = {
    "faq_block_count": "qa",                            # formats 桶 key
}


def _format_bucket(agg: dict, key: str) -> dict | None:
    for b in agg.get("formats", []):
        if b.get("key") == key:
            return b
    return None


def _schema_bucket(agg: dict, type_: str) -> dict | None:
    src = agg.get("sources", {}) or {}
    with_n = src.get("schema_unique", {}).get(type_)
    unique_n = src.get("unique_n", 0)
    if with_n is None or not unique_n:
        return None
    return {"with_n": with_n, "unique_n": unique_n,
            "platforms": list(src.get("schema_unique_platforms", {}).get(type_, []))}


def _evidence(signal: str, kind: str, bucket_label: str, b: dict) -> dict:
    share = round(b["with_n"] / b["unique_n"], 4) if b["unique_n"] else 0.0
    return {"signal": signal, "kind": kind, "bucket": bucket_label,
            "with_n": b["with_n"], "unique_n": b["unique_n"],
            "platforms": list(b.get("platforms", [])), "share": share}


def collect_evidence(agg: dict) -> list[dict]:
    out = []
    for sig, spec in ADD_CANDIDATES.items():
        b = _schema_bucket(agg, spec.split(".", 1)[1])
        if b:
            out.append(_evidence(sig, "signal_add", spec, b))
    for sig, fmt_key in REMOVE_CANDIDATES.items():
        b = _format_bucket(agg, fmt_key)
        if b and b.get("unique_n"):
            out.append(_evidence(sig, "signal_remove", f"formats.{fmt_key}",
                                 {"with_n": b.get("unique_cited_n", 0), "unique_n": b["unique_n"],
                                  "platforms": b.get("unique_platforms", [])}))
    return out


def dimension_strengths(agg: dict, evalrep: dict) -> dict[str, float | None]:
    """GEO 维度证据强度(唯一 URL 口径);无证据流的维度为 None(不参与权重调整)。SEO 全维度暂无流。"""
    fmts = [b.get("unique_cited_n", 0) / b["unique_n"]
            for b in agg.get("formats", []) if b.get("unique_n")]
    src = agg.get("sources", {}) or {}
    unique_n = src.get("unique_n", 0)
    schema_shares = [c / unique_n for t, c in src.get("schema_unique", {}).items() if t and unique_n]
    m = ((evalrep.get("gap", {}) or {}).get("metrics", {}) or {})
    mention, citation = m.get("mention_rate"), m.get("citation_rate")
    return {
        "citability": max(fmts) if fmts else None,
        "schema": max(schema_shares) if schema_shares else None,
        "brand": (mention + citation) / 2 if (mention is not None and citation is not None) else None,
        "eeat": None, "technical_geo": None, "platform": None,
    }