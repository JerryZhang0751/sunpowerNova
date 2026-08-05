from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from geo.shared.config import settings, REPO
from geo.collect.collector import run_collection
from geo.fetch.fetcher import fetch_source
from geo.fetch.gsc import snapshot_gsc
from geo.fetch.site_signals import snapshot_static_signals
from geo.assess.analyst import assemble
from geo.report.reporter import render

class S(TypedDict): week: int

def collect_node(state):
    run_collection(week=state["week"], models=settings.run.providers, prompt_ids=None,
                   runs=settings.run.runs, rule_version=settings.run.rule_version)
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
    out = REPO/"reports"/f"w{w}"/"report.html"; out.parent.mkdir(parents=True, exist_ok=True)
    render(rep, out); return state

def build_graph():
    g = StateGraph(S)
    g.add_node("collect", collect_node)
    g.add_node("fetch", fetch_node)
    g.add_node("snapshot", snapshot_node)
    g.add_node("assess", assess_node)
    g.add_node("report", report_node)
    g.add_edge(START, "collect")
    g.add_edge("collect", "fetch")
    g.add_edge("fetch", "snapshot")
    g.add_edge("snapshot", "assess")
    g.add_edge("assess", "report")
    g.add_edge("report", END)
    (REPO/"state").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REPO/"state"/"runs.sqlite", check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))

def run_pipeline(week: int):
    from langgraph.checkpoint.sqlite import SqliteSaver

    thread_id = f"w{week}"
    db_path = REPO/"state"/"runs.sqlite"

    # Check if checkpoint already exists for this week (resume from previous run)
    if db_path.exists():
        conn = sqlite3.connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        checkpoint = checkpointer.get({"configurable": {"thread_id": thread_id}})

        # If checkpoint exists with complete state, skip re-execution
        if checkpoint is not None and "channel_values" in checkpoint:
            if checkpoint["channel_values"].get("week") == week:
                # Graph already completed for this week, skip re-run
                return

    app = build_graph()
    # thread_id=w{week} → SqliteSaver checkpoint 续跑：已完成节点重跑时跳过
    app.invoke({"week": week}, config={"configurable": {"thread_id": thread_id}})

if __name__ == "__main__":
    run_pipeline(settings.run.week)
