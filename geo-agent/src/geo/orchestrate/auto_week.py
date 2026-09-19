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
    测试保留带 [900,999] 与非正数在解析层即排除,不参与完成统计;
    ≥900 的数字(含 wYYYYMMDD 日期误写)一并排除。"""
    m = _THREAD_NORMAL.match(thread_id)
    force = False
    if not m:
        m = _THREAD_FORCE.match(thread_id)
        force = True
        if not m:
            return None
    week = int(m.group(1))
    if week < 1 or week >= 900:
        return None
    return week, force


def list_root_threads(conn: sqlite3.Connection) -> list[str]:
    """枚举根命名空间(checkpoint_ns='')的线程名。只读 TEXT 列,不解码
    checkpoint/metadata BLOB;每线程状态读取由调用方经 app.get_state() 进行。
    库损坏/读取失败 → WeekSelectionError(不降级 w1);
    库在但 checkpoints 表不存在(空白库,从未跑过任何线程)→ 零线程,不算损坏。"""
    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoints'"
        ).fetchone()
        if has_table is None:
            return []
        rows = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns = ''"
        ).fetchall()
    except sqlite3.DatabaseError as e:
        raise WeekSelectionError(f"执行数据库读取失败,无法自动选周(不降级 w1): {e};请人工核查或显式传 --week") from e
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
                f"生产线程 {tid} 状态读取失败,无法自动选周(不降级 w1): {e};请人工核查或显式传 --week") from e
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
