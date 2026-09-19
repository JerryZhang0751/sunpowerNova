"""周次自动选择单元测试(spec 2026-09-19 §3): 全部 tmp 库,不触生产 state/runs.sqlite。

用两节点迷你图(a→b)构造 完成/崩溃 两种线程形态——auto_week 不关心图形状,
不 patch geo.orchestration.graph 的 8 个节点。
"""
import sqlite3
import pytest
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from geo.orchestrate.auto_week import (
    WeekSelectionError, parse_production_thread, list_root_threads,
    is_complete, classify_threads,
)


class S(TypedDict):
    week: int


def _mini_conn(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _mini_app(conn, fail_flags=None):
    """两节点迷你图;fail_flags={"b": True} 时 b 崩溃,造未完成线程。"""
    fail_flags = fail_flags if fail_flags is not None else {}

    def mk(name):
        def f(state):
            if fail_flags.get(name):
                raise RuntimeError(f"boom at {name}")
            return state
        return f

    g = StateGraph(S)
    g.add_node("a", mk("a"))
    g.add_node("b", mk("b"))
    g.add_edge(START, "a"); g.add_edge("a", "b"); g.add_edge("b", END)
    return g.compile(checkpointer=SqliteSaver(conn))


def _run_thread(app, thread_id, week):
    app.invoke({"week": week}, config={"configurable": {"thread_id": thread_id}})


def _crash_thread(app, thread_id, week, fail_flags):
    fail_flags["b"] = True
    try:
        with pytest.raises(RuntimeError, match="boom at b"):
            app.invoke({"week": week}, config={"configurable": {"thread_id": thread_id}})
    finally:
        fail_flags["b"] = False


# ---- parse_production_thread: 线程名解析与排除规则 ----
def test_parse_production_thread():
    assert parse_production_thread("w7") == (7, False)
    assert parse_production_thread("w8-20260919-130000") == (8, True)
    assert parse_production_thread("test_w99") is None           # 测试线程前缀
    assert parse_production_thread("w901") is None               # 测试保留带
    assert parse_production_thread("w0") is None                 # 非正数
    assert parse_production_thread("w7-20260919-1300") is None   # 时间戳格式不符
    assert parse_production_thread("w20260919") is None
    assert parse_production_thread("") is None


# ---- list_root_threads: 根命名空间枚举 + 损坏库报错 ----
def test_list_root_threads_root_namespace_only(tmp_path):
    conn = _mini_conn(tmp_path / "t.sqlite")
    app = _mini_app(conn)
    _run_thread(app, "w3", 3)
    # 仅有子命名空间行的线程不得出现在根枚举里
    conn.execute("INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id) "
                 "VALUES ('w9', 'sub', 'x')")
    conn.commit()
    assert list_root_threads(conn) == ["w3"]
    conn.close()


def test_list_root_threads_corrupt_db_errors(tmp_path):
    db = tmp_path / "bad.sqlite"
    db.write_bytes(b"not a sqlite database at all" * 10)
    conn = sqlite3.connect(db)
    with pytest.raises(WeekSelectionError, match="读取失败"):
        list_root_threads(conn)
    conn.close()


# ---- is_complete: 完成判定(与 run_pipeline 完成跳过同语义,抽取复用) ----
def test_is_complete_semantics(tmp_path):
    conn = _mini_conn(tmp_path / "t.sqlite")
    ff = {}
    app = _mini_app(conn, ff)
    _run_thread(app, "w5", 5)
    assert is_complete(app.get_state({"configurable": {"thread_id": "w5"}}), 5) is True
    _crash_thread(app, "w6", 6, ff)
    snap6 = app.get_state({"configurable": {"thread_id": "w6"}})
    assert is_complete(snap6, 6) is False    # next 指向失败节点 → 未完成
    assert is_complete(snap6, 5) is False    # week 不匹配 → 未完成
    empty = app.get_state({"configurable": {"thread_id": "nope"}})
    assert is_complete(empty, 1) is False    # 空 values → 未完成
    conn.close()


# ---- classify_threads: 分桶 + 排除 + 状态不一致报错 ----
def test_classify_threads_buckets_and_exclusions(tmp_path):
    conn = _mini_conn(tmp_path / "t.sqlite")
    ff = {}
    app = _mini_app(conn, ff)
    _run_thread(app, "w7", 7)                            # 普通完成
    _run_thread(app, "w8-20260919-120000", 8)            # 强制完成 → 计入
    _crash_thread(app, "w9", 9, ff)                      # 普通未完成
    _crash_thread(app, "w10-20260919-120001", 10, ff)    # 强制未完成
    _run_thread(app, "test_w99", 99)                     # 测试线程 → 排除
    _run_thread(app, "w901", 901)                        # 测试保留带 → 排除
    c = classify_threads(app, conn)
    assert sorted(c.completed) == [7, 8]
    assert c.completed[8] == ["w8-20260919-120000"]
    assert c.incomplete_normal == {9: "w9"}
    assert c.incomplete_force == {10: ["w10-20260919-120001"]}
    conn.close()


def test_classify_threads_rejects_state_week_mismatch(tmp_path):
    conn = _mini_conn(tmp_path / "t.sqlite")
    app = _mini_app(conn)
    # 线程名 w5 但状态 week=6 → 有效生产记录无法解析 → 明确报错(不降级)
    app.invoke({"week": 6}, config={"configurable": {"thread_id": "w5"}})
    with pytest.raises(WeekSelectionError, match="w5"):
        classify_threads(app, conn)
    conn.close()


from geo.orchestrate.auto_week import select_week, weekly_artifacts_exist


# ---- select_week: 场景表(spec §4) ----
def test_select_week_blank_project_starts_w1(tmp_path):
    conn = _mini_conn(tmp_path / "t.sqlite"); app = _mini_app(conn)
    sel = select_week(app, conn, tmp_path)
    assert (sel.week, sel.mode, sel.max_completed) == (1, "new", None)
    conn.close()


def test_select_week_after_w7_picks_w8(tmp_path):
    conn = _mini_conn(tmp_path / "t.sqlite"); app = _mini_app(conn)
    _run_thread(app, "w7", 7)
    sel = select_week(app, conn, tmp_path)
    assert (sel.week, sel.max_completed, sel.mode) == (8, 7, "new")
    conn.close()


def test_select_week_resumes_incomplete_w8(tmp_path):
    conn = _mini_conn(tmp_path / "t.sqlite"); ff = {}; app = _mini_app(conn, ff)
    _run_thread(app, "w7", 7); _crash_thread(app, "w8", 8, ff)
    sel = select_week(app, conn, tmp_path)
    assert (sel.week, sel.mode, sel.resume_thread) == (8, "resume", "w8")
    conn.close()


def test_select_week_numeric_max_w9_w10_picks_w11(tmp_path):
    """按整数取最大(防 "w10" < "w9" 字符串序)。"""
    conn = _mini_conn(tmp_path / "t.sqlite"); app = _mini_app(conn)
    _run_thread(app, "w9", 9); _run_thread(app, "w10", 10)
    assert select_week(app, conn, tmp_path).week == 11
    conn.close()


def test_select_week_test_threads_do_not_affect_result(tmp_path):
    conn = _mini_conn(tmp_path / "t.sqlite"); app = _mini_app(conn)
    _run_thread(app, "w7", 7)
    _run_thread(app, "test_w99", 99)
    _run_thread(app, "w901", 901)
    assert select_week(app, conn, tmp_path).week == 8
    conn.close()


def test_select_week_force_completed_counts_force_only_incomplete_guards(tmp_path):
    # 完成的强制线程计入: w7 普通 + w8-xxx 强制完成 → 选 w9
    conn = _mini_conn(tmp_path / "t.sqlite"); app = _mini_app(conn)
    _run_thread(app, "w7", 7); _run_thread(app, "w8-20260919-110000", 8)
    assert select_week(app, conn, tmp_path).week == 9
    conn.close()
    # 选中周只有未完成强制线程 → 报出线程并停止,不悄悄另开普通线程
    conn2 = _mini_conn(tmp_path / "t2.sqlite"); ff2 = {}; app2 = _mini_app(conn2, ff2)
    _run_thread(app2, "w7", 7); _crash_thread(app2, "w8-20260919-110001", 8, ff2)
    with pytest.raises(WeekSelectionError, match="w8-20260919-110001"):
        select_week(app2, conn2, tmp_path)
    conn2.close()


def test_select_week_no_records_but_artifacts_stops(tmp_path):
    """库在但无有效生产记录,盘上却有按周产物 → 停止,不凭文件夹猜完成。"""
    (tmp_path / "data" / "analysis" / "w3").mkdir(parents=True)
    (tmp_path / "data" / "analysis" / "w3" / "eval_report.json").write_text("{}", encoding="utf-8")
    conn = _mini_conn(tmp_path / "t.sqlite"); app = _mini_app(conn)
    with pytest.raises(WeekSelectionError, match="按周产物"):
        select_week(app, conn, tmp_path)
    conn.close()


def test_select_week_into_test_band_errors(tmp_path):
    """自动结果落入测试保留带 → validate_production_week 报错,不擅自跳号。"""
    conn = _mini_conn(tmp_path / "t.sqlite"); app = _mini_app(conn)
    _run_thread(app, "w899", 899)
    with pytest.raises(ValueError, match="测试保留带"):
        select_week(app, conn, tmp_path)
    conn.close()


def test_weekly_artifacts_exist(tmp_path):
    assert weekly_artifacts_exist(tmp_path) is False
    (tmp_path / "reports" / "w2").mkdir(parents=True)
    assert weekly_artifacts_exist(tmp_path) is True
