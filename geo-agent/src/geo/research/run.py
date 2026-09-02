# src/geo/research/run.py
from __future__ import annotations
import json, logging, shutil, time
from pathlib import Path
from geo.shared.config import REPO
from geo.shared.io_utils import atomic_write_text
from geo.shared.weeks import validate_production_week
from geo.research.corpus import build_corpus
from geo.research.sample import select_topn, fetch_topn
from geo.research.features import aggregate
from geo.research.kimi import synthesize, web_search_verify
from geo.research.render import render_playbook, render_profiles

log = logging.getLogger("research.run")
PLATFORMS_TO_VERIFY = ["Qwen","Doubao","Zhipu"]
BROADER = ["ChatGPT","Gemini","Perplexity","Claude"]

def _collect_feed(week: int, repo: Path) -> dict | None:
    """确定性反哺输入:上期 eval_report + 已发布清单 + 当前规则版本。零 Kimi。"""
    def _metrics(w):
        p = repo / "data" / "analysis" / f"w{w}" / "eval_report.json"
        if not p.exists():
            return None
        r = json.loads(p.read_text(encoding="utf-8"))
        m = (r.get("gap", {}) or {}).get("metrics", {}) or {}
        return {"week": w, "mention_rate": m.get("mention_rate"), "citation_rate": m.get("citation_rate"),
                "sov": m.get("sov"), "self_geo": (r.get("self_geo") or {}).get("total"),
                "self_seo": (r.get("self_seo") or {}).get("total")}
    published = []
    pub_dir = repo / "content" / "published"
    if pub_dir.exists():
        import yaml as _y
        for f in sorted(pub_dir.glob("*.md")):
            try:
                fm = _y.safe_load(f.read_text(encoding="utf-8").split("---")[1])
                published.append({"slug": fm.get("slug") or f.stem, "created": fm.get("created", "")})
            except Exception:
                continue
    latest, prev = _metrics(week - 1), _metrics(week - 2)
    if latest is None and not published:
        return None
    return {"published": published, "latest": latest, "prev": prev}

def run_research(week: int, kimi_enabled: bool = True, *, synth_fn=None, web_fn=None,
                 fetch_n: int = 40, repo: Path = REPO) -> dict:
    corpus = build_corpus(week, repo=repo)
    urls = select_topn(corpus, n=fetch_n, repo=repo, week=week)
    if urls:
        stats = fetch_topn(urls, week=week); log.info("fetched %s", stats.__dict__)
        corpus = build_corpus(week, repo=repo)   # reload to pick up new L3
    agg = aggregate(corpus)

    conclusions = []
    verified = {}
    feed = _collect_feed(week, repo)
    if kimi_enabled:
        try: conclusions = synthesize(agg, examples=[], chat_fn=synth_fn) if synth_fn else synthesize(agg, [])
        except Exception as e: log.warning("synthesize disabled/failed: %s", e)
        try:
            items = [{"platform":p,"fact":"crawler_and_inclusion"} for p in PLATFORMS_TO_VERIFY + BROADER]
            verified = web_search_verify(items, chat_fn=web_fn) if web_fn else web_search_verify(items)
        except Exception as e: log.warning("web_search failed: %s", e)
    # D5(2026-09-02)：预算耗尽的平台统一汇总（kimi_enabled=False 时 verified={} → 空表）。
    exhausted = sorted(p for p, v in (verified or {}).items() if v.get("budget_exhausted"))
    if exhausted:
        log.warning("平台查证预算耗尽（降级「外部未验证」）：%s", exhausted)

    (repo/"data"/"analysis"/f"w{week}").mkdir(parents=True, exist_ok=True)
    atomic_write_text(repo/"data"/"analysis"/f"w{week}"/"research_aggregates.json",
                      json.dumps(_agg_jsonable(agg), ensure_ascii=False, indent=2))
    (repo/"knowledge").mkdir(parents=True, exist_ok=True)
    pb_path = repo/"knowledge"/"playbook.md"; pf_path = repo/"knowledge"/"platform-profiles.md"
    pb_degraded = kimi_enabled and not conclusions
    pf_degraded = kimi_enabled and not any((v or {}).get("answer") for v in verified.values())
    ts = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    pb_banner = (f"> ⚠️ 本轮 Kimi 综合不可用（{ts}），结论为空——确定性聚合仍有效。"
                 "此为草稿，未晋升；正式 playbook 保持上一成功轮。") if pb_degraded else \
                ("> 确定性模式（--no-kimi）：本 playbook 未含 Kimi 综合结论。" if not kimi_enabled else "")
    pf_banner = (f"> ⚠️ 本轮联网查证不可用（{ts}）——画像为确定性数据+草稿，未晋升。"
                 ) if pf_degraded else ""
    _promote(pb_path, render_playbook(conclusions, agg, week, feed=feed, banner=pb_banner),
             week=week, draft=pb_degraded, repo=repo)
    _promote(pf_path, render_profiles(agg.platforms, verified, week, banner=pf_banner),
             week=week, draft=pf_degraded, repo=repo)
    drafts = [str(p) for p, d in ((pb_path, pb_degraded), (pf_path, pf_degraded)) if d
              for p in [p.parent / (p.name + ".draft")]]
    return {"playbook": str(pb_path), "profiles": str(pf_path),
            "conclusions": len(conclusions), "verified_platforms": len(verified),
            "degraded": pb_degraded or pf_degraded, "drafts": drafts,
            "budget_exhausted": exhausted}

def _promote(target: Path, text: str, *, week: int, draft: bool, repo: Path) -> Path:
    """draft=True → 写 <name>.draft 不动正式文件;否则晋升(旧文件备份 knowledge/.history/)。"""
    out = target.parent / (target.name + ".draft") if draft else target
    if not draft:
        if target.exists():
            hist = repo / "knowledge" / ".history"; hist.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            shutil.copy2(target, hist / f"{target.stem}-w{week}-{ts}{target.suffix}")
        stale = target.parent / (target.name + ".draft")
        if stale.exists(): stale.unlink()
    atomic_write_text(out, text)
    return out

def _agg_jsonable(a):
    return {"week":a.week,"coverage":a.coverage.__dict__,
            "formats":[b.__dict__ for b in a.formats],"sources":a.sources,
            "platforms":a.platforms,"problem_space":a.problem_space}

if __name__ == "__main__":
    import argparse, logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(); ap.add_argument("--week", type=int, default=1)
    ap.add_argument("--no-kimi", action="store_true")
    a = ap.parse_args()
    print(run_research(validate_production_week(a.week), kimi_enabled=not a.no_kimi))
