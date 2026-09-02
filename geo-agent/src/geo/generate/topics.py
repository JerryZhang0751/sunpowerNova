# src/geo/generate/topics.py
from __future__ import annotations
import json
from pathlib import Path
import yaml

from geo.generate.brand import slugify

# 近重复门(codex w3 修改五,2026-09-02):slug 按连字符拆词去重后的词集
# Jaccard 相似度 ≥ 该阈值 → 视为与已发布内容近重复。只阻断提示不删草稿,
# 人工经 review/override 裁决;无 embedding/外部模型/网络依赖。
NEAR_DUP_JACCARD = 0.8

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

def _read_fm(path: Path) -> dict | None:
    """读单文件 frontmatter;坏/缺 frontmatter 返回 None 不炸(只读诊断命令)。"""
    try:
        parts = path.read_text(encoding="utf-8").split("---")
        fm = yaml.safe_load(parts[1]) if len(parts) >= 3 else None
        return fm if isinstance(fm, dict) else None
    except Exception:
        return None


def _published_index(repo: Path) -> list[dict]:
    """已发布内容确定性索引(无模型调用,codex w3 修改五):topic/slug/published_url。
    供 suggest 精确去重与 generate 近重复门共用。"""
    idx: list[dict] = []
    d = Path(repo) / "content" / "published"
    if not d.is_dir():
        return idx
    for f in sorted(d.glob("*.md")):
        fm = _read_fm(f)
        if fm and fm.get("topic") and fm.get("page_type"):
            idx.append({"topic": fm["topic"], "page_type": fm["page_type"],
                        "slug": fm.get("slug") or f.stem,
                        "published_url": fm.get("published_url") or ""})
    return idx


def _dup_key_map(repo: Path) -> dict[tuple[str, str], str]:
    """重复键 → 已发布 slug(或 draft 标识)映射。键为规范化形态:
    (page_type, slugify(topic)) 与 (page_type, slug)——大小写/标点变体算同题。"""
    m: dict[tuple[str, str], str] = {}
    for e in _published_index(repo):
        for norm in (slugify(e["topic"]), e["slug"]):
            m.setdefault((e["page_type"], norm), e["slug"])
    dd = Path(repo) / "content" / "drafts"
    if dd.is_dir():
        for f in sorted(dd.glob("*.md")):
            fm = _read_fm(f)
            if fm and fm.get("topic") and fm.get("page_type"):
                m.setdefault((fm["page_type"], slugify(fm["topic"])), f"draft:{f.stem}")
    return m


def _published_keys(repo: Path) -> set[tuple[str, str]]:
    """已发布+草稿的规范化 (page_type, 键) 集合;坏/缺 frontmatter 文件跳过不炸。"""
    return set(_dup_key_map(repo))


def near_duplicate_issues(slug: str, published_index: list[dict]) -> list[str]:
    """slug 与已发布 slug 的词集 Jaccard ≥ NEAR_DUP_JACCARD → 返回近重复 issue
    (格式 near_duplicate:<已发布slug>),供 generate 阶段把草稿标 validation=flagged。
    确定性纯函数:连字符拆词、小写、词集去重。"""
    words = {w for w in (slug or "").lower().split("-") if w}
    issues: list[str] = []
    for p in published_index:
        other = p.get("slug") or ""
        ow = {w for w in other.lower().split("-") if w}
        if not words or not ow:
            continue
        j = len(words & ow) / len(words | ow)
        if j >= NEAR_DUP_JACCARD:
            issues.append(f"near_duplicate:{other}(Jaccard {j:.2f}≥{NEAR_DUP_JACCARD},"
                          f"与已发布内容近同题)")
    return issues

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
    pub = _dup_key_map(repo)                        # 已发布/草稿规范化去重(spec §3 + codex 修改五)
    out, suppressed = [], []
    for s in candidates:
        hit = pub.get((s["page_type"], slugify(s["topic"])))
        if hit:
            s["suppressed_reason"] = f"duplicate:{hit}"
            suppressed.append(s)
        else:
            out.append(s)
    return out, missing, suppressed
