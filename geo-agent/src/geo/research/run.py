# src/geo/research/run.py
from __future__ import annotations
import json, logging
from pathlib import Path
from geo.shared.config import REPO
from geo.research.corpus import build_corpus
from geo.research.sample import select_topn, fetch_topn
from geo.research.features import aggregate
from geo.research.kimi import synthesize, web_search_verify
from geo.research.render import render_playbook, render_profiles

log = logging.getLogger("research.run")
PLATFORMS_TO_VERIFY = ["Qwen","Doubao","Zhipu"]
BROADER = ["ChatGPT","Gemini","Perplexity","Claude"]

def run_research(week: int, kimi_enabled: bool = True, *, synth_fn=None, web_fn=None,
                 fetch_n: int = 40, repo: Path = REPO) -> dict:
    corpus = build_corpus(week, repo=repo)
    urls = select_topn(corpus, n=fetch_n, repo=repo)
    if urls:
        stats = fetch_topn(urls); log.info("fetched %s", stats.__dict__)
        corpus = build_corpus(week, repo=repo)   # reload to pick up new L3
    agg = aggregate(corpus)

    conclusions = []
    verified = {}
    if kimi_enabled:
        try: conclusions = synthesize(agg, examples=[], chat_fn=synth_fn) if synth_fn else synthesize(agg, [])
        except Exception as e: log.warning("synthesize disabled/failed: %s", e)
        try:
            items = [{"platform":p,"fact":"crawler_and_inclusion"} for p in PLATFORMS_TO_VERIFY + BROADER]
            verified = web_search_verify(items, chat_fn=web_fn) if web_fn else web_search_verify(items)
        except Exception as e: log.warning("web_search failed: %s", e)

    (repo/"data"/"analysis"/f"w{week}").mkdir(parents=True, exist_ok=True)
    (repo/"data"/"analysis"/f"w{week}"/"research_aggregates.json").write_text(
        json.dumps(_agg_jsonable(agg), ensure_ascii=False, indent=2), encoding="utf-8")
    (repo/"knowledge").mkdir(parents=True, exist_ok=True)
    (repo/"knowledge"/"playbook.md").write_text(render_playbook(conclusions, agg, week), encoding="utf-8")
    (repo/"knowledge"/"platform-profiles.md").write_text(
        render_profiles(agg.platforms, verified, week), encoding="utf-8")
    return {"playbook": str(repo/"knowledge"/"playbook.md"),
            "profiles": str(repo/"knowledge"/"platform-profiles.md"),
            "conclusions": len(conclusions), "verified_platforms": len(verified)}

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
    print(run_research(a.week, kimi_enabled=not a.no_kimi))
