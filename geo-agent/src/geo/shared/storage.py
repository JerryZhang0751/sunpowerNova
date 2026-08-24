import hashlib
import json
from pathlib import Path
from geo.shared.config import REPO
from geo.shared.models import RunRecord

def sha1_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()

def source_dir(sha1: str) -> Path:
    p = REPO/"data"/"sources"/sha1[:12]; p.mkdir(parents=True, exist_ok=True); return p

def l1_path(week:int, model:str, pid:str, run:int) -> Path:
    p = REPO/"data"/"raw"/f"w{week}"/model/pid; p.mkdir(parents=True, exist_ok=True)
    return p/f"r{run}.json"

def snapshot_dir(week:int) -> Path:
    p = REPO/"data"/"snapshots"/f"w{week}"; p.mkdir(parents=True, exist_ok=True); return p

# ---- 采集运行清单(2026-08-24 审查#5):planned/ok/failed 全量落盘 ----
# 追加式 JSONL。分母(planned)以唯一 (model,prompt_id,run) 键计,失败不得消失。

def runs_manifest_path(week:int) -> Path:
    return REPO/"data"/"raw"/f"w{week}"/"runs.jsonl"

def append_run_records(week:int, recs:list[RunRecord]) -> None:
    p = runs_manifest_path(week)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for r in recs:
            f.write(r.model_dump_json() + "\n")

def read_run_records(week:int) -> list[RunRecord]:
    p = runs_manifest_path(week)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(RunRecord(**json.loads(line)))
    return out
