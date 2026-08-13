# src/geo/research/corpus.py
from __future__ import annotations
import json
from pathlib import Path
from geo.shared.config import REPO
from geo.shared.models import L1Record, L2Record, CitedSource, L3Source, PromptRow
from geo.shared.storage import sha1_url
from geo.research.models import ResearchItem, ResearchCorpus, Coverage

def _iter_l1(week: int, repo: Path) -> list[L1Record]:
    base = repo / "data" / "raw" / f"w{week}"
    out = []
    if not base.exists(): return out
    for p in sorted(base.rglob("r*.json")):
        out.append(L1Record(**json.loads(p.read_text(encoding="utf-8"))))
    return out

def _load_prompts(repo: Path) -> dict[str, PromptRow]:
    import csv
    rows = {}
    with (repo / "input" / "prompts.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["id"]] = PromptRow(id=r["id"], category=r["category"], prompt=r["prompt"],
                                      market=r["market"], intent=r["intent"], core=r["core"]=="1" or r["core"].lower()=="true")
    return rows

def _load_l3(url: str, repo: Path) -> L3Source | None:
    d = repo / "data" / "sources" / sha1_url(url)[:12]
    mp = d / "meta.json"
    if not mp.exists(): return None
    l3 = L3Source(**json.loads(mp.read_text(encoding="utf-8")))
    return None if l3.js_only else l3

def _load_gsc_queries(week: int, repo: Path) -> list[str]:
    gp = repo / "data" / "snapshots" / f"w{week}" / "gsc.json"
    if not gp.exists(): return []
    data = json.loads(gp.read_text(encoding="utf-8"))
    return [k for row in data.get("rows", []) for k in row.get("keys", [])]

def build_corpus(week: int, repo: Path = REPO) -> ResearchCorpus:
    prompts = _load_prompts(repo)
    l1s = _iter_l1(week, repo)
    items, resolved, missing, js, total_cited = [], 0, 0, 0, 0
    for l1 in l1s:
        src_pairs = []
        for cited in l1.l2.cited_sources:
            total_cited += 1
            l3 = _load_l3(cited.url, repo)
            if l3 is None:
                missing += 1
            elif l3.js_only:
                js += 1
            else:
                resolved += 1
            src_pairs.append((cited, l3))
        p = prompts.get(l1.prompt_id, PromptRow(id=l1.prompt_id, category="?", prompt="", market="", intent="?", core=False))
        items.append(ResearchItem(l1=l1, prompt=p, sources=src_pairs))
    cov = Coverage(total_l1=len(l1s), total_cited_sources=total_cited,
                   l3_resolved=resolved, l3_missing=missing, l3_js_only=js)
    return ResearchCorpus(week=week, items=items, gsc_queries=_load_gsc_queries(week, repo), coverage=cov)
