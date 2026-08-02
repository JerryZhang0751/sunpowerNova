import hashlib
from pathlib import Path
from geo.shared.config import REPO

def sha1_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()

def source_dir(sha1: str) -> Path:
    p = REPO/"data"/"sources"/sha1[:12]; p.mkdir(parents=True, exist_ok=True); return p

def l1_path(week:int, model:str, pid:str, run:int) -> Path:
    p = REPO/"data"/"raw"/f"w{week}"/model/pid; p.mkdir(parents=True, exist_ok=True)
    return p/f"r{run}.json"

def snapshot_dir(week:int) -> Path:
    p = REPO/"data"/"snapshots"/f"w{week}"; p.mkdir(parents=True, exist_ok=True); return p
