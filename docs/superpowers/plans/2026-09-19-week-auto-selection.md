# 执行周次自动化（week auto-selection）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完整流水线入口无参数运行时自动执行 `本次周次 = 已完成的最大生产周次 + 1`，废除 run.yaml 手工维护 week 与 `--next-week` 写回机制。

**Architecture:** 新模块 `geo/orchestrate/auto_week.py`（线程枚举/完成分类/选周算法，错误一律明确报错不降级 w1）；`run_pipeline` 重排为「显式周校验 → flock 进程锁 → 自动选周(可选) → 复用既有完成跳过/续跑语义」；`RunSpec.week` 与两份 run YAML 的 week 字段删除；collector/reporter 独立入口改 `main(argv)` 显式 `--week`。

**Tech Stack:** Python 3.12 + langgraph 1.2.11（SqliteSaver checkpoint，无 `list_threads` API → 根命名空间枚举走 `SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns=''`，纯 TEXT 列不解码 BLOB）+ fcntl 文件锁。

**Spec:** `docs/superpowers/specs/2026-09-19-week-auto-selection-design.md`（已批准）

## Global Constraints

- 测试命令：`cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`（沙箱封锁 `.venv`；系统 `python3`=3.9 缺依赖必须用 `python3.12`；pylibs 在 `~/pylibs312`）。summary 行偶被吞——以 EXIT code + 点阵/junitxml 计数为准。
- 全程不触碰生产 `state/runs.sqlite`（Task 7 只读副本）；不调用真实模型/GSC/网络；单测一律 tmp sqlite + mock 节点。
- 禁 `git add -A`；只显式 add 本任务文件。main 分支线性提交，每任务一 commit。**工作树既有余量（演讲文稿 M / docs/ppt-* / gsc_page_impressions_probe.py / HTML 概览）零触碰。**
- 周次约束：`validate_production_week` 拒绝非正数与 [900,999] 测试保留带；测试造状态用 1–899 或 900+ 均可（graph 层入口才校验，库函数不校验）。
- 不改评分、规则迭代算法、内容生成逻辑、站点代码；保留 keeper.iterate / do_rollback 对 `run.yaml.rule_version` 的运行期写回。
- 每个任务结束时全量测试套件必须绿（任务间不留红窗）。

---

### Task 1: auto_week 模块 — 线程枚举 + 解析 + 完成判定 + 分类

**Files:**
- Create: `geo-agent/src/geo/orchestrate/auto_week.py`
- Test: `geo-agent/tests/test_auto_week.py`

**Interfaces:**
- Consumes: `geo.shared.weeks.validate_production_week`（既有）
- Produces（后续任务依赖的精确签名）:
  - `parse_production_thread(thread_id: str) -> tuple[int, bool] | None`（`(week, is_force)`；非生产线程/测试保留带/非正数 → None）
  - `list_root_threads(conn: sqlite3.Connection) -> list[str]`（库损坏抛 `WeekSelectionError`）
  - `is_complete(snap, week: int) -> bool`
  - `classify_threads(app, conn) -> Classification`（`Classification.completed: dict[int, list[str]]` / `incomplete_normal: dict[int, str]` / `incomplete_force: dict[int, list[str]]`）
  - `class WeekSelectionError(RuntimeError)`

- [ ] **Step 1: 写失败测试**

创建 `geo-agent/tests/test_auto_week.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_auto_week.py -v -p no:cacheprovider --timeout=120`
Expected: FAIL — `ModuleNotFoundError: No module named 'geo.orchestrate.auto_week'`

- [ ] **Step 3: 写实现**

创建 `geo-agent/src/geo/orchestrate/auto_week.py`：

```python
"""执行周次自动选择(spec 2026-09-19 §2-§4): 本次周次 = 已完成的最大生产周次 + 1。

完成判定只信 LangGraph checkpoint(复用 run_pipeline 的"state.week 匹配且无
pending 节点"语义),不信盘上产物——data/raw|analysis|reports 可能源于部分执行、
失败或手工操作。所有异常一律明确报错,绝不降级为 w1。
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from geo.shared.weeks import validate_production_week

# graph.run_pipeline 生成的线程名: 普通线程 wN / 强制重跑线程 wN-YYYYMMDD-HHMMSS
_THREAD_NORMAL = re.compile(r"^w(\d+)$")
_THREAD_FORCE = re.compile(r"^w(\d+)-\d{8}-\d{6}$")


class WeekSelectionError(RuntimeError):
    """自动选周失败: 状态异常/产物与记录矛盾/守卫触发。"""


@dataclass(frozen=True)
class WeekSelection:
    week: int
    max_completed: int | None
    mode: str                     # "new" | "resume"
    resume_thread: str | None     # mode=resume 时的普通线程名
    note: str = ""                # 启动日志明细


@dataclass
class Classification:
    completed: dict[int, list[str]] = field(default_factory=dict)
    incomplete_normal: dict[int, str] = field(default_factory=dict)
    incomplete_force: dict[int, list[str]] = field(default_factory=dict)


def parse_production_thread(thread_id: str) -> tuple[int, bool] | None:
    """生产线程名 → (week, is_force);非生产线程(test_wN 等)→ None。
    测试保留带 [900,999] 与非正数在解析层即排除,不参与完成统计。"""
    m = _THREAD_NORMAL.match(thread_id)
    force = False
    if not m:
        m = _THREAD_FORCE.match(thread_id)
        force = True
        if not m:
            return None
    week = int(m.group(1))
    if week < 1 or 900 <= week <= 999:
        return None
    return week, force


def list_root_threads(conn: sqlite3.Connection) -> list[str]:
    """枚举根命名空间(checkpoint_ns='')的线程名。只读 TEXT 列,不解码
    checkpoint/metadata BLOB;每线程状态读取由调用方经 app.get_state() 进行。
    库损坏/读取失败 → WeekSelectionError(不降级 w1)。"""
    try:
        rows = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns = ''"
        ).fetchall()
    except sqlite3.DatabaseError as e:
        raise WeekSelectionError(f"执行数据库读取失败,无法自动选周(不降级 w1): {e}") from e
    return sorted(r[0] for r in rows)


def is_complete(snap, week: int) -> bool:
    """完成判定(spec §3,自 run_pipeline 抽取复用):
    有效状态 week 匹配 + 无待执行节点 + 无错误/中断任务。"""
    if snap.values.get("week") != week or snap.next:
        return False
    return not any(t.error or t.interrupts for t in snap.tasks)


def classify_threads(app, conn: sqlite3.Connection) -> Classification:
    """根命名空间生产线程分桶。强制重跑线程完成也计入 completed;
    状态 week 与线程名 N 不一致、或状态读取抛错 → 明确报错列线程名。"""
    c = Classification()
    for tid in list_root_threads(conn):
        parsed = parse_production_thread(tid)
        if parsed is None:
            continue
        week, force = parsed
        try:
            snap = app.get_state({"configurable": {"thread_id": tid}})
        except Exception as e:
            raise WeekSelectionError(
                f"生产线程 {tid} 状态读取失败,无法自动选周(不降级 w1): {e}") from e
        if snap.values.get("week") != week:
            raise WeekSelectionError(
                f"生产线程 {tid} 的状态 week={snap.values.get('week')!r} 与线程名不一致,"
                f"无法自动选周(不降级 w1);请人工核查该线程或显式传 --week")
        if is_complete(snap, week):
            c.completed.setdefault(week, []).append(tid)
        elif force:
            c.incomplete_force.setdefault(week, []).append(tid)
        else:
            c.incomplete_normal[week] = tid
    return c
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_auto_week.py -v -p no:cacheprovider --timeout=120`
Expected: 7 passed

- [ ] **Step 5: 全量回归**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: EXIT=0（589+7 全绿）

- [ ] **Step 6: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/src/geo/orchestrate/auto_week.py geo-agent/tests/test_auto_week.py
git commit -m "feat(orchestrate): auto_week 线程枚举/解析/完成判定/分类 —— checkpoint 完成语义抽取复用

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: auto_week 模块 — 选周算法与错误语义

**Files:**
- Modify: `geo-agent/src/geo/orchestrate/auto_week.py`（追加）
- Test: `geo-agent/tests/test_auto_week.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `classify_threads` / `WeekSelectionError`
- Produces:
  - `weekly_artifacts_exist(repo: Path) -> bool`
  - `select_week(app, conn, repo) -> WeekSelection`

- [ ] **Step 1: 写失败测试**

在 `tests/test_auto_week.py` 追加（import 行补 `select_week, weekly_artifacts_exist`）：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_auto_week.py -v -p no:cacheprovider --timeout=120`
Expected: 新增用例 FAIL — `ImportError: cannot import name 'select_week'`

- [ ] **Step 3: 写实现**

在 `auto_week.py` 追加：

```python
def weekly_artifacts_exist(repo) -> bool:
    """按周产物目录存在性: data/analysis/w*/ | data/raw/w*/ | reports/w*/ 任一即 True。
    只用于"无有效生产记录"时的矛盾检测(有产物却无记录 → 停止),
    不用于完成判定(产物可能源于部分执行、失败或手工操作)。"""
    for sub in ("data/analysis", "data/raw", "reports"):
        base = repo / sub
        if base.is_dir() and any(base.glob("w[0-9]*")):
            return True
    return False


def select_week(app, conn: sqlite3.Connection, repo) -> WeekSelection:
    """自动选周(spec §4): 最大完成生产周 + 1;空白项目 w1;异常一律报错不降级。"""
    c = classify_threads(app, conn)
    if not c.completed:
        if weekly_artifacts_exist(repo):
            raise WeekSelectionError(
                "无有效生产执行记录但存在按周产物(data/analysis|data/raw|reports);"
                "请恢复执行数据库(state/runs.sqlite)或显式传 --week,不凭文件夹猜测完成状态")
        return WeekSelection(week=1, max_completed=None, mode="new",
                             resume_thread=None, note="空白项目,新建线程")
    max_completed = max(c.completed)               # 整数最大值,防字符串序
    week = validate_production_week(max_completed + 1)
    incomplete_force = sorted(c.incomplete_force.get(week, []))
    if incomplete_force and week not in c.incomplete_normal:
        raise WeekSelectionError(
            f"自动选中 w{week} 只有未完成的强制重跑线程 {incomplete_force},"
            f"拒绝悄悄另开普通线程重复执行;请处理该线程或显式传 --week {week}")
    if week in c.incomplete_normal:
        tid = c.incomplete_normal[week]
        note = f"续跑未完成线程 {tid}"
        if incomplete_force:
            note += f";另有未完成强制线程 {incomplete_force}"
        return WeekSelection(week=week, max_completed=max_completed, mode="resume",
                             resume_thread=tid, note=note)
    return WeekSelection(week=week, max_completed=max_completed, mode="new",
                         resume_thread=None, note="新建线程")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_auto_week.py -v -p no:cacheprovider --timeout=120`
Expected: 16 passed

- [ ] **Step 5: 全量回归 + Commit**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: EXIT=0

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/src/geo/orchestrate/auto_week.py geo-agent/tests/test_auto_week.py
git commit -m "feat(orchestrate): select_week 自动选周算法 —— 最大完成生产周+1 与全部守卫/报错语义

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: graph.py — 进程锁 + run_pipeline 重排 + CLI 更新

**Files:**
- Modify: `geo-agent/src/geo/orchestrate/graph.py`（全文重写 run_pipeline 段，删 `_bump_run_yaml_week`）
- Modify: `geo-agent/tests/test_graph.py`（增补 + 修既有 1 处）
- Modify: `geo-agent/tests/test_io_utils.py`（删 `test_graph_next_week_writes_run_yaml_atomically`，与功能同任务删除防红窗）

**Interfaces:**
- Consumes: Task 1 `is_complete`、Task 2 `select_week`
- Produces:
  - `pipeline_lock(repo)`（contextmanager；`@contextmanager` 装饰；锁=`repo/state/pipeline.lock`，`fcntl.flock(LOCK_EX|LOCK_NB)`，占用抛 `RuntimeError("已有流水线进程在运行...")`）
  - `run_pipeline(week: int | None = None, force_new_run: bool = False)`（**删除 `next_week` 参数**；`force_new_run` 且 `week is None` → `ValueError`）

- [ ] **Step 1: 写失败测试**

在 `tests/test_graph.py` 末尾追加：

```python
# ---- 2026-09-19 周次自动化: 自动选周/进程锁/无参运行 ----
def test_run_pipeline_auto_selects_resumes_and_advances(tmp_path, monkeypatch, capsys):
    """spec §4 场景 2/3: w7 完成,w8 中途崩 → 无参运行仍选 w8 从 checkpoint 续跑
    (collect 不重复执行);w8 完成后再无参运行 → 自动 w9。"""
    import geo.orchestrate.graph as G
    calls = []
    fail_flags = {}

    def mk(name):
        def f(state):
            calls.append(name)
            if fail_flags.get(name):
                raise RuntimeError(f"boom at {name}")
            return state
        return f

    monkeypatch.setattr(G, "REPO", tmp_path)
    for n in ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]:
        monkeypatch.setattr(G, f"{n}_node", mk(n))

    G.run_pipeline(week=7)                        # w7 完成
    fail_flags["fetch"] = True
    with pytest.raises(RuntimeError, match="boom at fetch"):
        G.run_pipeline(week=8)                    # w8 崩在 fetch
    fail_flags["fetch"] = False
    calls.clear()
    G.run_pipeline()                              # 无参 → 自动选 w8 续跑
    assert calls == ["fetch", "snapshot", "assess", "research", "generate", "rules", "report"]
    out = capsys.readouterr().out
    assert "[week-select]" in out and "w8" in out and "续跑" in out
    calls.clear()
    G.run_pipeline()                              # w8 已完成 → 自动 w9
    assert calls == ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]
    assert "w9" in capsys.readouterr().out


def test_run_pipeline_auto_blank_project_runs_w1(tmp_path, monkeypatch, capsys):
    import geo.orchestration  # noqa: F401  (确保包可导入)
    import geo.orchestrate.graph as G
    calls = []
    monkeypatch.setattr(G, "REPO", tmp_path)
    for n in ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]:
        monkeypatch.setattr(G, f"{n}_node", lambda s, _n=n: (calls.append(_n), s)[1])
    G.run_pipeline()                              # 空白项目 → w1
    assert calls == ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]
    out = capsys.readouterr().out
    assert "[week-select]" in out and "w1" in out


def test_run_pipeline_auto_does_not_write_run_yaml(tmp_path, monkeypatch):
    """spec §7-12: 自动选周与完成处理不得写 run.yaml(周次推进零写回)。"""
    import geo.orchestrate.graph as G
    monkeypatch.setattr(G, "REPO", tmp_path)
    run_yaml = tmp_path / "run.yaml"
    run_yaml.write_text("mode: audit\nscope: core\nruns: 1\n", encoding="utf-8")
    before = run_yaml.read_bytes()
    for n in ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]:
        monkeypatch.setattr(G, f"{n}_node", lambda s: s)
    G.run_pipeline()
    G.run_pipeline(week=1)                        # 完成跳过路径
    assert run_yaml.read_bytes() == before


def test_force_new_run_requires_explicit_week(tmp_path, monkeypatch):
    import geo.orchestrate.graph as G
    monkeypatch.setattr(G, "REPO", tmp_path)
    with pytest.raises(ValueError, match="--force-new-run"):
        G.run_pipeline(force_new_run=True)


def test_explicit_test_band_rejected_before_lock(tmp_path, monkeypatch):
    """显式周校验先于锁:拒绝时不创建 state/ 目录。"""
    import geo.orchestrate.graph as G
    monkeypatch.setattr(G, "REPO", tmp_path)
    with pytest.raises(ValueError, match="测试保留带"):
        G.run_pipeline(week=901)
    assert not (tmp_path / "state").exists()


def test_pipeline_lock_blocks_concurrent_run(tmp_path, monkeypatch):
    """spec §6/§7-13: 锁被占 → 立即报错;释放后可运行。"""
    import fcntl
    import os
    import geo.orchestrate.graph as G
    monkeypatch.setattr(G, "REPO", tmp_path)
    lock = tmp_path / "state" / "pipeline.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)      # 模拟已在运行的流水线进程
    try:
        with pytest.raises(RuntimeError, match="已有流水线"):
            G.run_pipeline(week=9)
    finally:
        os.close(fd)                                     # 释放
    for n in ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]:
        monkeypatch.setattr(G, f"{n}_node", lambda s: s)
    G.run_pipeline(week=9)                               # 锁已放 → 正常进入


def test_pipeline_lock_released_after_run(tmp_path, monkeypatch):
    import fcntl
    import os
    import geo.orchestrate.graph as G
    monkeypatch.setattr(G, "REPO", tmp_path)
    for n in ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]:
        monkeypatch.setattr(G, f"{n}_node", lambda s: s)
    G.run_pipeline(week=9)
    fd = os.open(tmp_path / "state" / "pipeline.lock", os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)       # 不抛 = run_pipeline 已释放
    os.close(fd)
```

同时修改既有测试 `test_run_pipeline_closes_own_conn`（加锁后避免在真实 `state/` 建 lock 文件）——在该测试的 `monkeypatch.setattr(G, "_new_run_conn", fake_new_conn)` 之前插入一行：

```python
    monkeypatch.setattr(G, "REPO", tmp_path)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_graph.py -v -p no:cacheprovider --timeout=120`
Expected: 新增用例 FAIL（`run_pipeline() missing 1 required positional argument: 'week'` 或 TypeError）

- [ ] **Step 3: 写实现**

改 `geo-agent/src/geo/orchestrate/graph.py`：

3a. 顶部 import 区补两行（`import sqlite3` 之后）：

```python
import os
from contextlib import contextmanager
```

并在 `from geo.shared.weeks import validate_production_week` 之后补：

```python
from geo.orchestrate.auto_week import is_complete, select_week
```

3b. **整体删除** `_bump_run_yaml_week`（原 121-129 行）与 `run_pipeline`（原 131-168 行），替换为：

```python
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
```

3c. `if __name__ == "__main__":` 块整体替换为：

```python
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
```

3d. 删除 `geo-agent/tests/test_io_utils.py` 的 `test_graph_next_week_writes_run_yaml_atomically` 整个函数（43-56 行，含 docstring）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_graph.py tests/test_io_utils.py -v -p no:cacheprovider --timeout=120`
Expected: 全 PASS

- [ ] **Step 5: CLI 手工验证（一次性，不入测试）**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
PYTHONPATH="$HOME/pylibs312:src" python3.12 -m geo.orchestrate.graph --force-new-run 2>&1 | tail -2
```
Expected: usage error，exit 2（`--force-new-run 须同时显式传入 --week`）。
**注意：不要裸跑无参形态——会在生产库真实启动 w8。**

- [ ] **Step 6: 全量回归**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: EXIT=0

- [ ] **Step 7: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/src/geo/orchestrate/graph.py geo-agent/tests/test_graph.py geo-agent/tests/test_io_utils.py
git commit -m "feat(orchestrate): run_pipeline 无参自动选周 + pipeline 进程锁;移除 --next-week 写回机制

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: collector / reporter 独立入口显式 --week

**Files:**
- Modify: `geo-agent/src/geo/collect/collector.py`（`__main__` 段改 `main(argv)`）
- Modify: `geo-agent/src/geo/report/reporter.py`（同上）
- Test: `geo-agent/tests/test_collector.py`（追加）
- Test: `geo-agent/tests/test_reporter.py`（追加）

**Interfaces:**
- Consumes: `validate_production_week`（既有；collector 已 import，reporter 需在 main 内 import）
- Produces: `collector.main(argv: list[str] | None = None)` / `reporter.main(argv: list[str] | None = None)`——缺 `--week` → argparse `SystemExit(2)`；测试带周 → ValueError

- [ ] **Step 1: 写失败测试**

`tests/test_collector.py` 末尾追加：

```python
# ---- 2026-09-19 周次自动化: 独立入口必须显式 --week ----
def test_collector_main_requires_explicit_week():
    import geo.collect.collector as C
    with pytest.raises(SystemExit):            # argparse required 缺参 → exit 2
        C.main([])


def test_collector_main_passes_explicit_week(monkeypatch):
    import geo.collect.collector as C
    seen = {}
    monkeypatch.setattr(C, "run_collection",
                        lambda week, models, prompt_ids, runs, rule_version:
                        seen.update(week=week, models=models))
    C.main(["--week", "3"])
    assert seen["week"] == 3


def test_collector_main_rejects_test_band_week(monkeypatch):
    import geo.collect.collector as C
    monkeypatch.setattr(C, "run_collection", lambda *a, **k: None)
    with pytest.raises(ValueError, match="测试保留带"):
        C.main(["--week", "901"])
```

`tests/test_reporter.py` 末尾追加：

```python
# ---- 2026-09-19 周次自动化: 独立入口必须显式 --week ----
def test_reporter_main_requires_explicit_week():
    import geo.report.reporter as R
    with pytest.raises(SystemExit):
        R.main([])


def test_reporter_main_passes_explicit_week(monkeypatch, tmp_path):
    import geo.report.reporter as R
    monkeypatch.setattr(R, "REPO", tmp_path)
    ana = tmp_path / "data" / "analysis" / "w3"
    ana.mkdir(parents=True)
    (ana / "eval_report.json").write_text('{"week": 3}', encoding="utf-8")
    seen = {}
    monkeypatch.setattr(R, "render", lambda rep, out: seen.update(week=rep["week"], out=out))
    R.main(["--week", "3"])
    assert seen["week"] == 3
    assert str(seen["out"]).endswith("reports/w3/report.html")
```

（两文件顶部若无 `import pytest` 则补。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_collector.py::test_collector_main_requires_explicit_week tests/test_reporter.py::test_reporter_main_requires_explicit_week -v -p no:cacheprovider --timeout=120`
Expected: FAIL — `AttributeError: module 'geo.collect.collector' has no attribute 'main'`

- [ ] **Step 3: 写实现**

3a. `collector.py` 的 `if __name__ == "__main__":` 块（192-193 行）替换为：

```python
def main(argv: list[str] | None = None) -> None:
    """独立采集入口: 必须显式 --week(自动选周只属于完整流水线入口,
    独立采集不开启也不完成一轮流水线)。其余参数仍取 settings。"""
    import argparse
    ap = argparse.ArgumentParser(prog="geo.collect.collector")
    ap.add_argument("--week", type=int, required=True,
                    help="生产周次(独立采集须显式指定)")
    a = ap.parse_args(argv)
    run_collection(validate_production_week(a.week), settings.run.providers, None,
                   settings.run.runs, settings.run.rule_version)


if __name__ == "__main__":
    main()
```

3b. `reporter.py` 的 `if __name__ == "__main__":` 块（69-87 行）替换为：

```python
def main(argv: list[str] | None = None) -> None:
    """报告重渲染入口: 必须显式 --week(重渲染不属于流水线完成语义)。"""
    import argparse
    import json
    from geo.shared.config import settings
    from geo.shared.weeks import validate_production_week

    ap = argparse.ArgumentParser(prog="geo.report.reporter")
    ap.add_argument("--week", type=int, required=True,
                    help="生产周次(重渲染须显式指定)")
    a = ap.parse_args(argv)
    week = validate_production_week(a.week)

    rep = json.loads(
        (REPO / "data" / "analysis" / f"w{week}" / "eval_report.json").read_text(encoding="utf-8")
    )
    ri_path = REPO / "data" / "analysis" / f"w{week}" / "rules_iteration.json"
    if ri_path.exists():
        rep["rules_iteration"] = json.loads(ri_path.read_text(encoding="utf-8"))

    out = REPO / "reports" / f"w{week}" / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    render(rep, out)
    print(out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_collector.py tests/test_reporter.py -v -p no:cacheprovider --timeout=120`
Expected: 全 PASS

- [ ] **Step 5: 全量回归 + Commit**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: EXIT=0

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/src/geo/collect/collector.py geo-agent/src/geo/report/reporter.py geo-agent/tests/test_collector.py geo-agent/tests/test_reporter.py
git commit -m "feat(cli): collector/reporter 独立入口显式 --week(main(argv) 可测形态)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 删除 RunSpec.week 与 run YAML week 字段

**前置：Task 3/4 已消除全部 `settings.run.week` 读者（graph.py:178 / collector.py:193 / reporter.py:73）。**

**Files:**
- Modify: `geo-agent/src/geo/shared/config.py:19`（删字段）与 `:41-44`（注释改述）
- Modify: `geo-agent/run.yaml`（删第 1 行）
- Modify: `geo-agent/run.yaml.example`（删第 1 行 + 加说明注释）
- Modify: `geo-agent/tests/test_config.py`（1 处用例）
- Modify: `geo-agent/tests/test_config_models.py`（3 处缓存测试改 `runs` 字段）
- Modify: `geo-agent/tests/test_rules_keeper.py:17`（fixture dict 去 week 键）
- Modify: `geo-agent/tests/test_rules_run.py:26-27`（同上）

**Interfaces:**
- Consumes: 无
- Produces: `RunSpec` 不再有 `week` 字段；`run.yaml`/`run.yaml.example` 不再有 `week` 键（键集锁测试 `test_run_yaml_keys_match_run_spec_fields` 双侧同步后自动保持绿）

- [ ] **Step 1: 改测试（先红）**

1a. `tests/test_config.py` `test_settings_loads_env_and_yaml`：
- 第 11 行 `run.write_text("week: 1\nmode: audit\nscope: core\n")` → `run.write_text("mode: audit\nscope: core\nruns: 2\n")`
- 第 15 行 `assert s.run.week == 1 and s.run.scope == "core"` → `assert s.run.runs == 2 and s.run.scope == "core"`

1b. `tests/test_config_models.py` 三处 `week: 3`/`week: 4` 全部换成 `runs` 字段：
- `test_settings_run_cached_until_mtime_changes`：`"week: 3\n"` → `"runs: 1\n"`；`"week: 4\n"` → `"runs: 2\n"`；断言 `s.run.week == 4` → `s.run.runs == 2`
- `test_settings_targets_cached_until_mtime_changes`：run.yaml 内容 `"week: 3\n"` → `"runs: 1\n"`（该文件内容不参与断言，仅去 week）
- `test_run_cache_invalidates_on_same_mtime_tick_rewrite`：`"week: 3\nmode: audit\nscope: core\n"` → `"runs: 1\nmode: audit\nscope: core\n"`；`"week: 4\nmode: audit\nscope: core\n"` → `"runs: 2\nmode: audit\nscope: core\n"`；两处断言 `s.run.week == 3`/`== 4` → `s.run.runs == 1`/`== 2`；注释里"week 3→4"改"runs 1→2"

1c. `tests/test_rules_keeper.py` 第 17 行 fixture dict：`{"week": 1, "mode": "audit", ...}` → `{"mode": "audit", ...}`（只删 `"week": 1, `）。
`tests/test_rules_run.py` 第 26-27 行同型删除。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_config.py tests/test_config_models.py -v -p no:cacheprovider --timeout=120`
Expected: `test_settings_loads_env_and_yaml` FAIL（`'RunSpec' object has no attribute 'week'` 之类）——此刻实现未改，测试先红

- [ ] **Step 3: 改实现**

3a. `src/geo/shared/config.py`：删除 RunSpec 内一行 `week: int = 1`；第 41-44 行注释中 `# (运行时写入方存在: keeper.iterate / do_rollback / graph --next-week)。` 改为 `# (运行时写入方存在: keeper.iterate / do_rollback——只写 rule_version 键)。`

3b. `geo-agent/run.yaml`：删除第 1 行 `week: 7`（其余 6 行原样保留）。

3c. `geo-agent/run.yaml.example`：删除第 1 行 `week: 1`，在文件顶部加注释行：

```yaml
# 周次由流水线自动选择(已完成最大生产周 + 1),不再手工维护 —— 详见 README
```

（其余含行内注释的行原样保留。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/test_config.py tests/test_config_models.py tests/test_rules_keeper.py tests/test_rules_run.py tests/test_run_yaml_example.py -v -p no:cacheprovider --timeout=120`
Expected: 全 PASS（键集锁双侧同步后自动绿）

- [ ] **Step 5: 全库残留检查 + 全量回归**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
grep -rn "run\.week\|next_week\|next-week\|_bump_run_yaml" src/ tests/ | grep -v __pycache__
```
Expected: 零命中（唯一允许的残留=无）。

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: EXIT=0

- [ ] **Step 6: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/src/geo/shared/config.py geo-agent/run.yaml geo-agent/run.yaml.example geo-agent/tests/test_config.py geo-agent/tests/test_config_models.py geo-agent/tests/test_rules_keeper.py geo-agent/tests/test_rules_run.py
git commit -m "refactor(config): 删除 RunSpec.week 与 run.yaml week 字段 —— 周次单一来源为 checkpoint

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: README 周次自动化说明

**Files:**
- Modify: `README.md`（仓库根，205-226 行区域）

**Interfaces:** 无代码接口；纯文档。

- [ ] **Step 1: 更新 README**

1a. 第 209 行关键配置表 run.yaml 行：
`| [`geo-agent/run.yaml`](geo-agent/run.yaml) | 周号、运行模式、范围、次数、规则版本与 provider |`
→ `| [`geo-agent/run.yaml`](geo-agent/run.yaml) | 运行模式、范围、次数、规则版本与 provider |`

1b. 第 214-226 行区域整体替换为：

```markdown
确认配置后，在 `geo-agent/` 中运行：

```bash
python -m geo.orchestrate.graph
```

不带参数时自动选周：**本次周次 = 已完成的最大生产周次 + 1**（完成状态只认执行数据库里的 LangGraph checkpoint；没有历史记录的新项目从 w1 开始）。同一周已完整运行会跳过，中途失败会从 checkpoint 续跑，已付费节点不重复执行。

| 参数 | 行为 |
| --- | --- |
| `--week N` | 显式选择生产周；省略时自动选周。测试保留 `900–999`，生产入口会拒绝该区间 |
| `--force-new-run` | 忽略同周 checkpoint、开时间戳线程从头运行并再次调用付费接口；**须同时显式传 `--week`** |

显式续跑某一未完成周（不自动跳到下一周）：

```bash
python -m geo.orchestrate.graph --week 8
```

强制重跑历史周：

```bash
python -m geo.orchestrate.graph --week 7 --force-new-run
```

其他说明：

- 完整流水线入口有进程锁（`state/pipeline.lock`）：已有流水线在运行时重复启动会立即报错退出。
- 执行数据库缺失或无有效生产记录、但盘上存在按周产物（`data/analysis` / `data/raw` / `reports`）时，自动选周会明确报错——请恢复执行数据库或显式传 `--week`，不凭文件夹猜测完成状态。
- 独立采集与报告重渲染入口不参与周次推进，须显式指定：`python -m geo.collect.collector --week N`、`python -m geo.report.reporter --week N`。
- 周次推进不再读写 `run.yaml` 的 week 字段（该字段已删除）；流水线运行期仍会更新 `run.yaml` 的 `rule_version`（规则升版，属既有功能）。
```

- [ ] **Step 2: 核对无残留**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && grep -n "next-week\|周号" README.md
```
Expected: 零命中。

- [ ] **Step 3: 全量回归（防误伤）+ Commit**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: EXIT=0

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add README.md
git commit -m "docs(readme): 周次自动化说明 —— 默认无参运行/显式续跑/强制重跑/并发锁

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: 收口验收 — 全量回归 + 生产库副本选周验证

**Files:** 无代码改动（纯验证；不 commit）。

- [ ] **Step 1: 全量离线回归**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312:src" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: EXIT=0，基线 589 → 589+新增（Task1 +7 / Task2 +9 / Task3 +7 / Task4 +5 ≈ 617±，以实际为准记录进交付说明）

- [ ] **Step 2: 生产数据库临时副本上验证选周 = 8（不启动真实 w8）**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
cp state/runs.sqlite /tmp/runs_autoweek_verify.sqlite
PYTHONPATH="$HOME/pylibs312:src" python3.12 - <<'EOF'
import sqlite3
from pathlib import Path
from geo.orchestrate.graph import build_graph
from geo.orchestrate.auto_week import select_week

conn = sqlite3.connect("/tmp/runs_autoweek_verify.sqlite")
app = build_graph(conn)
sel = select_week(app, conn, Path("."))
print(f"max_completed={sel.max_completed} week={sel.week} mode={sel.mode} note={sel.note}")
assert sel.week == 8 and sel.mode == "new" and sel.max_completed == 7
conn.close()
print("OK: 生产库副本自动选周 = 8")
EOF
rm -f /tmp/runs_autoweek_verify.sqlite /tmp/runs_probe_copy.sqlite
```
Expected: `OK: 生产库副本自动选周 = 8`

- [ ] **Step 3: 交付说明核对单**（写入最终汇报，不新增文件）

- 修改文件清单（auto_week.py 新增；graph/config/collector/reporter/run.yaml×2/README/测试×7）
- 选周规则一句话：最大完成生产周 + 1，checkpoint 完成判定，异常报错不降级
- 失败续跑行为：同周 `invoke(None)` 只跑 pending 节点（既有语义保留）
- 测试结果：全量 EXIT=0 + 新增用例数 + 副本验证 = 8
- 范围确认：未动评分/规则迭代/生成/站点；keeper rule_version 写回保留

---

## Self-Review 记录（计划自审，执行者无需处理）

1. **Spec 覆盖**：§1 核实→无任务需做（信息性）；§2 模块=Task1/2；§3 完成判定=Task1；§4 算法场景=Task2/3；§5 移除清单=Task3(--next-week 族)/Task4(独立入口)/Task5(RunSpec.week 族)；§6 错误+锁=Task1/2/3；§7 测试 13 项→Task1(1,5数值前提,6,7)/Task2(1,2,4,5,6,7,10)/Task3(3,8,9,12,13)/Task4(11)/Task7(收口)；§8 README=Task6。无缺口。
2. **占位符扫描**：全部步骤含完整代码/命令，无 TBD。
3. **类型一致性**：`select_week(app, conn, repo)` 三参签名在 Task2 定义、Task3/7 调用一致；`run_pipeline(week=None, force_new_run=False)` 在 Task3 定义、Task3 测试调用一致；`Classification` 三桶字段名在 Task1/2 一致。
4. **红窗检查**：Task3 同任务删 `_bump_run_yaml_week` 与其 io_utils 测试；Task5 同 commit 删 RunSpec.week 与 run.yaml 键（键集锁不红）；Task5 前置依赖 Task3/4 已消除读者——任务顺序已排定。
