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
