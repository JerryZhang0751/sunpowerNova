import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
from geo.shared.config import REPO
from geo.shared.models import RunRecord

log = logging.getLogger("storage")

def sha1_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()

def source_dir(week: int, sha1: str) -> Path:
    """2026-09-02 D1: 周目录隔离——每周独立快照自洽,历史 SEO 重算可复现(w3 起)。"""
    p = REPO/"data"/"sources"/f"w{week}"/sha1[:12]; p.mkdir(parents=True, exist_ok=True); return p

def legacy_source_dirs(week: int, repo: Path = REPO) -> list[Path]:
    """周 L3 查找回退链: w{week} + (week<3 时回退 w3=迁移前共享缓存的终态;week==3
    即自身目录,不重复列出)。
    w1/w2/w3 的历史评估消费的就是这份态(黄金锁通路);w4+ 不回退——miss=诚实缺失。
    注意: 需 monkeypatch/注入 repo 的调用方必须显式传 repo(默认值绑定的 REPO 是
    storage 模块导入时的对象),否则 patch 不到——analyst/corpus 均在调用点传各自 REPO。"""
    dirs = [repo / "data" / "sources" / f"w{week}"]
    if week < 3:   # week==3 不重复列 w3(评审修复去重;查找集不变)
        dirs.append(repo / "data" / "sources" / "w3")
    return dirs

def l1_path(week:int, model:str, pid:str, run:int) -> Path:
    p = REPO/"data"/"raw"/f"w{week}"/model/pid; p.mkdir(parents=True, exist_ok=True)
    return p/f"r{run}.json"

def snapshot_dir(week:int) -> Path:
    p = REPO/"data"/"snapshots"/f"w{week}"; p.mkdir(parents=True, exist_ok=True); return p

# ---- 采集运行清单(2026-08-24 审查#5):planned/ok/failed 全量落盘 ----
# 追加式 JSONL。分母(planned)以唯一 (model,prompt_id,run) 键计,失败不得消失。
# (2026-08-25 二次审查#7) 崩溃/并发安全: 追加走 flock + O_APPEND 单次 write +
# fsync(进程并发不交错、崩溃至多损末行);读取跳过残缺行并告警,不让一次写入
# 中断把后续读取永久卡死在 JSONDecodeError。

def runs_manifest_path(week:int) -> Path:
    return REPO/"data"/"raw"/f"w{week}"/"runs.jsonl"

def append_run_records(week:int, recs:list[RunRecord]) -> None:
    p = runs_manifest_path(week)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)               # 跨进程串行化追加
        data = "".join(r.model_dump_json() + "\n" for r in recs).encode("utf-8")
        os.write(fd, data)                           # O_APPEND + 单次 write: 不产生交错半行
        os.fsync(fd)                                 # 崩溃前先落盘
    finally:
        os.close(fd)

def read_run_records(week:int) -> list[RunRecord]:
    p = runs_manifest_path(week)
    if not p.exists():
        return []
    out, skipped = [], 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(RunRecord(**json.loads(line)))
        except (json.JSONDecodeError, TypeError, ValueError):
            skipped += 1                             # 写入中断的残缺尾行/损坏行
    if skipped:
        log.warning("runs.jsonl(w%s) 跳过 %d 行残缺记录(写入中断或损坏)", week, skipped)
    return out
