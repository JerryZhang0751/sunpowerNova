from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from geo.shared.config import settings, REPO
from geo.collect.collector import run_collection, collection_health, COLLECTION_GATE
from geo.fetch.fetcher import fetch_source
from geo.fetch.gsc import snapshot_gsc
from geo.fetch.site_signals import snapshot_static_signals
from geo.assess.analyst import assemble
from geo.report.reporter import render
from geo.shared.weeks import validate_production_week

class S(TypedDict): week: int

def collect_node(state):
    run_collection(week=state["week"], models=settings.run.providers, prompt_ids=None,
                   runs=settings.run.runs, rule_version=settings.run.rule_version)
    # 数据质量门(2026-08-24 审查#5): 采集成功率 <95% 就此阻断,拒绝让"planned=valid"
    # 的虚假健康流入 fetch/assess/rules;重跑 collect 补齐失败项后续跑即可恢复。
    h = collection_health(state["week"])
    if h["manifest"] and h["min_success_rate"] is not None \
            and h["min_success_rate"] < COLLECTION_GATE:
        raise RuntimeError(
            f"采集成功率 {h['min_success_rate']:.1%} < {COLLECTION_GATE:.0%} 门槛,阻断流水线: {h['per_model']}")
    return state

def fetch_node(state):
    # 只抓 analyst 真正读取 L3 的 URL：品牌站 + 站点页 + Top 竞品域名。
    # 全量 cited_sources 抓取对 P0 报告无用（analyst 只读这 ~20 个 URL）且会触发
    # 上千次 Kimi 调用；P1 研究 agent 需要时再恢复全量抓取。
    from geo.assess.analyst import competitor_domains_by_count
    w = state["week"]
    site = settings.targets["site"]["url"]
    urls = [site] + [site.rstrip("/") + p for p in settings.targets["site"]["pages"]]
    urls += [f"https://{d}" for d in competitor_domains_by_count(w, 10)]
    for u in urls:
        try: fetch_source(u)
        except Exception: pass        # 失败跳过、不入分母
    return state

def snapshot_node(state):
    snapshot_gsc(state["week"], settings.run.rule_version)
    snapshot_static_signals(state["week"], settings.run.rule_version)
    return state

def assess_node(state):
    assemble(state["week"]); return state

def report_node(state):
    import json
    w = state["week"]
    rep = json.loads((REPO/"data"/"analysis"/f"w{w}"/"eval_report.json").read_text(encoding="utf-8"))
    # Merge rules_iteration if present
    ri = REPO / "data" / "analysis" / f"w{w}" / "rules_iteration.json"
    if ri.exists():
        rep["rules_iteration"] = json.loads(ri.read_text(encoding="utf-8"))
    out = REPO/"reports"/f"w{w}"/"report.html"; out.parent.mkdir(parents=True, exist_ok=True)
    render(rep, out); return state

def research_node(state):
    from geo.research.run import run_research
    run_research(state["week"])
    return state

def generate_node(state):
    # Only produces drafts, never publishes (publishing is manual outside DAG)
    # Queue discipline: skip if unreviewed drafts exist (only backlog one at a time)
    from geo.generate.run import run_suggest, run_generate
    w = state["week"]
    drafts_dir = REPO / "content" / "drafts"
    pending = list(drafts_dir.glob("*.md")) if drafts_dir.exists() else []
    if pending:
        print(f"[generate] Skipped: unreviewed drafts exist {[p.stem for p in pending]} (resume after manual --review)")
        return state
    sugg = run_suggest(w).get("suggestions") or []
    if not sugg:
        print("[generate] Skipped: no candidates (check gsc/playbook data sources)")
        return state
    top = sugg[0]
    run_generate(top["topic"], top.get("page_type", "guide"), w)
    return state

def rules_node(state):
    from geo.rules.keeper import iterate
    iterate(state["week"])
    return state

def build_graph():
    g = StateGraph(S)
    g.add_node("collect", collect_node)
    g.add_node("fetch", fetch_node)
    g.add_node("snapshot", snapshot_node)
    g.add_node("assess", assess_node)
    g.add_node("research", research_node)
    g.add_node("generate", generate_node)
    g.add_node("rules", rules_node)
    g.add_node("report", report_node)
    g.add_edge(START, "collect")
    g.add_edge("collect", "fetch")
    g.add_edge("fetch", "snapshot")
    g.add_edge("snapshot", "assess")  # v1.1: assess before generate (generate needs this week's eval_report)
    g.add_edge("assess", "research")
    g.add_edge("research", "generate")
    g.add_edge("generate", "rules")
    g.add_edge("rules", "report")
    g.add_edge("report", END)
    (REPO/"state").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REPO/"state"/"runs.sqlite", check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))

def run_pipeline(week: int, next_week: bool = False, force_new_run: bool = False):
    validate_production_week(week)
    from datetime import datetime

    if force_new_run:
        # Timestamped thread ID: w{week}-{YYYYMMDD-HHMMSS}
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        thread_id = f"w{week}-{timestamp}"
    else:
        thread_id = f"w{week}"

    app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # Completion check via get_state: a graph at END has next == (). DO NOT test
    # channel_values.week alone — it is set from the very first checkpoint, so a
    # crashed run is indistinguishable from a completed one that way (w202 incident).
    partial = False
    if not force_new_run:
        snap = app.get_state(config)
        if snap.values.get("week") == week and not snap.next:
            print(f"[pipeline] w{week} already completed (thread {thread_id}) — skip")
            return
        partial = snap.values.get("week") == week
        if partial:
            print(f"[pipeline] w{week} resuming from checkpoint, pending nodes: {list(snap.next)}")

    # invoke(None) resumes a partial thread from its checkpoint (only pending
    # nodes re-run); passing fresh input would restart the graph from START
    # and re-execute already-checkpointed (paid) work.
    app.invoke(None if partial else {"week": week}, config=config)

    if next_week:
        import yaml as _y
        run_raw = _y.safe_load((REPO / "run.yaml").read_text(encoding="utf-8"))
        run_raw["week"] = week + 1
        (REPO / "run.yaml").write_text(
            _y.safe_dump(run_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"run.yaml week → {week + 1}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="geo.orchestrate.graph")
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--next-week", action="store_true", help="Increment run.yaml week after run")
    ap.add_argument("--force-new-run", action="store_true",
                    help="Ignore existing checkpoint, use timestamped thread for fresh run")
    a = ap.parse_args()
    run_pipeline(a.week or settings.run.week, next_week=a.next_week, force_new_run=a.force_new_run)
