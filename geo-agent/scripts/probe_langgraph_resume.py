"""Probe langgraph 1.2.10 semantics needed to fix run_pipeline resume logic.

Questions to answer empirically (2026-08-24, before fixing graph.py):
Q1: What does app.get_state(thread) return when NO checkpoint exists for the thread?
Q2: What does get_state().next look like after a COMPLETED run?
Q3: What does get_state().next look like after a MID-GRAPH crash (node raised)?
Q4: Does app.invoke(None, config) resume from checkpoint (run only remaining nodes)?
Q4b: What does invoke(None) do on a COMPLETED thread?
Q5: Does app.invoke({"week": w}, config) on an existing PARTIAL thread re-run from START?
"""
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

class S(TypedDict):
    week: int

log = []
# Mutable failure flags so a probe can "fix" a node before resuming
fail_flags = {"a": False, "b": False, "c": False, "d": False}

def mk(name):
    def f(state):
        log.append(name)
        if fail_flags[name]:
            raise RuntimeError(f"boom at {name}")
        return state
    return f

def build(db_path):
    g = StateGraph(S)
    for name in ["a", "b", "c", "d"]:
        g.add_node(name, mk(name))
    g.add_edge(START, "a"); g.add_edge("a", "b"); g.add_edge("b", "c")
    g.add_edge("c", "d"); g.add_edge("d", END)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))

tmp = Path(tempfile.mkdtemp())

# --- Q1: get_state on thread with no checkpoint ---
app = build(tmp / "q1.sqlite")
cfg = {"configurable": {"thread_id": "t-empty"}}
try:
    snap = app.get_state(cfg)
    print(f"Q1: no exception; values={snap.values!r} next={snap.next!r} metadata={snap.metadata!r}")
except Exception as e:
    print(f"Q1: raised {type(e).__name__}: {e}")

# --- Q2: get_state after completed run ---
app = build(tmp / "q2.sqlite")
cfg = {"configurable": {"thread_id": "t-done"}}
log.clear()
app.invoke({"week": 7}, config=cfg)
snap = app.get_state(cfg)
print(f"Q2: completed run log={log} values={snap.values!r} next={snap.next!r}")
print(f"Q2 metadata: {json.dumps(snap.metadata, default=str)[:300]}")

# --- Q3: get_state after mid-graph crash ---
app = build(tmp / "q3.sqlite", fail_node="b")
cfg = {"configurable": {"thread_id": "t-partial"}}
log.clear()
try:
    app.invoke({"week": 7}, config=cfg)
    print("Q3: no exception ?!")
except RuntimeError as e:
    print(f"Q3: crashed as expected ({e}); log so far={log}")
snap = app.get_state(cfg)
print(f"Q3: values={snap.values!r} next={snap.next!r}")

# --- Q4: invoke(None) resumes remaining nodes only ---
log.clear()
app.invoke(None, config=cfg)
print(f"Q4: after resume log={log} (expect c,d only)")
snap = app.get_state(cfg)
print(f"Q4: final values={snap.values!r} next={snap.next!r}")

# --- Q4b: invoke(None) on a COMPLETED thread ---
log.clear()
app.invoke(None, config=cfg)
print(f"Q4b: invoke(None) on completed thread log={log} (expect nothing)")

# --- Q5: invoke(input) on existing PARTIAL thread ---
app = build(tmp / "q5.sqlite", fail_node="b")
cfg = {"configurable": {"thread_id": "t-reinput"}}
try:
    app.invoke({"week": 7}, config=cfg)
except RuntimeError:
    pass
log.clear()
app.invoke({"week": 7}, config=cfg)  # same input again on partial thread
print(f"Q5: re-invoke with INPUT on partial thread log={log} (a,b,c,d = full restart)")
