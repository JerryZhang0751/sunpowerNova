from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import os
from contextlib import contextmanager
from geo.shared.config import settings, REPO
from geo.collect.collector import run_collection, collection_health, COLLECTION_GATE
from geo.fetch.fetcher import fetch_source
from geo.fetch.gsc import snapshot_gsc
from geo.fetch.site_signals import snapshot_static_signals
from geo.assess.analyst import assemble
from geo.report.reporter import render
from geo.shared.weeks import validate_production_week
from geo.orchestrate.auto_week import is_complete, select_week

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
        try: fetch_source(u, week=w)   # D1(2026-09-02): L3 落本周目录
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

def _new_run_conn():
    """生产 checkpoint 连接工厂:WAL(崩溃不损 checkpoint)+ busy_timeout(并发写不炸)。(2026-09-02 §2)"""
    (REPO/"state").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REPO/"state"/"runs.sqlite", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def build_graph(conn: sqlite3.Connection | None = None):
    """conn=None 时自建生产连接;传入 conn 则所有权归调用方(测试传 tmp 库,不触碰生产库)。"""
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
    conn = conn or _new_run_conn()
    return g.compile(checkpointer=SqliteSaver(conn))

@contextmanager
def pipeline_lock(repo):
    """完整流水线入口互斥(spec 2026-09-19 §6): 选周前取得、退出释放。
    flock 随 fd 关闭释放;锁文件残留无害,不删除。重复启动立即报错,不排队。"""
    import fcntl
    lock_path = repo / "state" / "pipeline.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            raise RuntimeError(f"已有流水线进程在运行(锁: {lock_path}): {e}") from e
        yield
    finally:
        os.close(fd)


def run_pipeline(week: int | None = None, force_new_run: bool = False):
    """week=None 时自动选周(已完成最大生产周+1,spec 2026-09-19);显式周保留
    完成跳过/失败续跑语义。force_new_run 必须配显式 week(重跑目标明确)。"""
    if week is not None:
        validate_production_week(week)      # 先于锁: 拒绝时不碰 state/
    if force_new_run and week is None:
        raise ValueError("--force-new-run 须同时显式传入 --week(重跑目标明确)")
    from datetime import datetime

    with pipeline_lock(REPO):
        conn = _new_run_conn()
        try:
            app = build_graph(conn)

            if week is None:
                sel = select_week(app, conn, REPO)
                week = sel.week
                if sel.max_completed is None:
                    print(f"[week-select] 无完成生产周(空白项目) → 本次执行 w{week}({sel.note})")
                else:
                    print(f"[week-select] 最大完成生产周: {sel.max_completed} → "
                          f"本次执行 w{week}({sel.note})")

            if force_new_run:
                # Timestamped thread ID: w{week}-{YYYYMMDD-HHMMSS}
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                thread_id = f"w{week}-{timestamp}"
            else:
                thread_id = f"w{week}"
            config = {"configurable": {"thread_id": thread_id}}

            # Completion check via get_state: a graph at END has next == (). DO NOT test
            # channel_values.week alone — it is set from the very first checkpoint, so a
            # crashed run is indistinguishable from a completed one that way (w202 incident).
            partial = False
            if not force_new_run:
                snap = app.get_state(config)
                if is_complete(snap, week):
                    print(f"[pipeline] w{week} already completed (thread {thread_id}) — skip")
                    return
                partial = snap.values.get("week") == week
                if partial:
                    print(f"[pipeline] w{week} resuming from checkpoint, pending nodes: {list(snap.next)}")

            # invoke(None) resumes a partial thread from its checkpoint (only pending
            # nodes re-run); passing fresh input would restart the graph from START
            # and re-execute already-checkpointed (paid) work.
            app.invoke(None if partial else {"week": week}, config=config)
        finally:
            conn.close()

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="geo.orchestrate.graph")
    ap.add_argument("--week", type=int, default=None,
                    help="显式选择生产周;省略时自动 = 已完成的最大生产周 + 1")
    ap.add_argument("--force-new-run", action="store_true",
                    help="忽略既有 checkpoint 强制重跑(须同时显式传 --week)")
    a = ap.parse_args()
    if a.force_new_run and a.week is None:
        ap.error("--force-new-run 须同时显式传入 --week")
    run_pipeline(a.week, force_new_run=a.force_new_run)
