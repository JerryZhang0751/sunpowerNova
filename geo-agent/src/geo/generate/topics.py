# src/geo/generate/topics.py
from __future__ import annotations
import json
from pathlib import Path
import yaml

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

def _published_keys(repo: Path) -> set[tuple[str, str]]:
    """已发布+草稿的 (page_type, topic) 键集;坏/缺 frontmatter 文件跳过不炸。"""
    keys: set[tuple[str, str]] = set()
    for sub in ("published", "drafts"):
        d = repo / "content" / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                parts = f.read_text(encoding="utf-8").split("---")
                fm = yaml.safe_load(parts[1]) if len(parts) >= 3 else None
                if isinstance(fm, dict) and fm.get("topic") and fm.get("page_type"):
                    keys.add((fm["page_type"], fm["topic"]))
            except Exception:
                continue          # 只读诊断命令:单文件损坏不整体失败
    return keys

def suggest_topics(week: int, *, repo: Path) -> tuple[list[dict], list[str], list[dict]]:
    repo = Path(repo)
    candidates: list[dict] = []
    missing: list[str] = []
    er = repo / "data" / "analysis" / f"w{week}" / "eval_report.json"
    if er.exists():
        rep = json.loads(er.read_text(encoding="utf-8"))
        dims = [d for sec in ("self_geo", "self_seo") for d in rep.get(sec, {}).get("dims", [])
                if d.get("score", 100) < 50]
        for d in sorted(dims, key=lambda x: x["score"]):
            topic, ptype = GAP_TEMPLATES.get(d["name"], _DEFAULT_TEMPLATE)
            candidates.append({"source": "eval_gap", "detail": f"{d['name']}={d['score']}",
                               "topic": topic, "page_type": ptype})
    else:
        missing.append(str(er))
    gsc = repo / "data" / "snapshots" / f"w{week}" / "gsc.json"
    if gsc.exists():
        snap = json.loads(gsc.read_text(encoding="utf-8"))
        for row in sorted(snap.get("rows", []), key=lambda r: -r.get("impressions", 0))[:8]:
            q = " ".join(row.get("keys", [])).strip()
            if q:
                candidates.append({"source": "gsc", "detail": f"impressions={row.get('impressions', 0)}",
                                   "topic": q, "page_type": "guide"})
    else:
        missing.append(str(gsc))
    pub = _published_keys(repo)                     # 已发布/草稿精确去重(spec §3)
    out = [s for s in candidates if (s["page_type"], s["topic"]) not in pub]
    suppressed = [s for s in candidates if (s["page_type"], s["topic"]) in pub]
    return out, missing, suppressed
