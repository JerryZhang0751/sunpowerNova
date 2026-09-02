"""L1 记录迭代(2026-09-02 §4:analyst/corpus 两份实现合一 + 逐条容错)。
单条坏 JSON/坏 schema 跳过并告警,不再炸掉整个 assemble/build_corpus;
sorted 保证跨运行确定性(旧 rglob 顺序依赖文件系统)。"""
from __future__ import annotations
import json, logging
from pathlib import Path
from typing import Iterator
from geo.shared.config import REPO
from geo.shared.models import L1Record

log = logging.getLogger("shared.l1")

def iter_l1(week: int, repo: Path = REPO) -> Iterator[L1Record]:
    root = repo / "data" / "raw" / f"w{week}"
    if not root.exists():
        return
    for jp in sorted(root.rglob("r*.json")):
        try:
            yield L1Record(**json.loads(jp.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            log.warning("w%s L1 残缺跳过 %s: %s", week, jp.name, e)
