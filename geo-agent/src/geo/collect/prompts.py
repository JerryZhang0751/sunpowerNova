from __future__ import annotations
import csv
from pathlib import Path
from geo.shared.config import REPO
from geo.shared.models import PromptRow, prompt_set_version

CSV = REPO / "input" / "prompts.csv"

def load_prompts(scope: str = "core") -> list[PromptRow]:
    rows = []
    with CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(PromptRow(id=r["id"], category=r["category"], prompt=r["prompt"],
                                  market=r["market"], intent=r["intent"],
                                  core=str(r.get("core", "0")).strip() == "1"))
    if scope == "core":
        rows = [r for r in rows if r.core]
    return sorted(rows, key=lambda x: x.id)

# 控制变量指纹：永远基于全量 csv，与 scope 无关
_ALL = load_prompts("full")
PROMPT_SET_VERSION = prompt_set_version(_ALL)
