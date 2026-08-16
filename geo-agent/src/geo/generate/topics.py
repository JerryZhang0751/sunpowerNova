# src/geo/generate/topics.py
from __future__ import annotations
import json
from pathlib import Path

GAP_TEMPLATES = {
    "citability":       ("Guide with concrete sizing/how-to numbers drawn from brand facts", "guide"),
    "eeat":             ("About-the-team page: who designs and installs, credentials, process", "guide"),
    "schema":           ("FAQ page adding FAQPage JSON-LD", "faq"),
    "platform":         ("Side-by-side comparison page suited for AI platform pickup", "comparison"),
    "technical_geo":    ("Spec sheet page with structured product data", "spec"),
    "on_page":          ("Spec sheet page with structured headings and product data", "spec"),
    "content_eeat":     ("Deep-dive article with dates, sources and concrete data points", "guide"),
    "authority":        ("Glossary/definition hub page for core terminology", "guide"),
}
_DEFAULT_TEMPLATE = ("Content targeting this weak dimension (generic)", "guide")

def suggest_topics(week: int, *, repo: Path) -> tuple[list[dict], list[str]]:
    repo = Path(repo)
    out: list[dict] = []
    missing: list[str] = []
    er = repo / "data" / "analysis" / f"w{week}" / "eval_report.json"
    if er.exists():
        rep = json.loads(er.read_text(encoding="utf-8"))
        dims = [d for sec in ("self_geo", "self_seo") for d in rep.get(sec, {}).get("dims", [])
                if d.get("score", 100) < 50]
        for d in sorted(dims, key=lambda x: x["score"]):
            topic, ptype = GAP_TEMPLATES.get(d["name"], _DEFAULT_TEMPLATE)
            out.append({"source": "eval_gap", "detail": f"{d['name']}={d['score']}", "topic": topic, "page_type": ptype})
    else:
        missing.append(str(er))
    gsc = repo / "data" / "snapshots" / f"w{week}" / "gsc.json"
    if gsc.exists():
        snap = json.loads(gsc.read_text(encoding="utf-8"))
        for row in sorted(snap.get("rows", []), key=lambda r: -r.get("impressions", 0))[:8]:
            q = " ".join(row.get("keys", [])).strip()
            if q:
                out.append({"source": "gsc", "detail": f"impressions={row.get('impressions', 0)}",
                            "topic": q, "page_type": "guide"})
    else:
        missing.append(str(gsc))
    return out, missing
