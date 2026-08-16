# src/geo/generate/kimi.py
from __future__ import annotations
import re

_WEEK_RE = re.compile(r"Playbook · w(\d+)")
_FMT_HDR_RE = re.compile(r"^### (\w+)（.+?）", re.M)
_FMT_LINE_RE = re.compile(r"- cited_n=(\d+) sample_n=(\d+) confidence=(\w+)")

def playbook_digest(playbook_text: str) -> dict:
    text = playbook_text or ""
    m = _WEEK_RE.search(text)
    formats: list[dict] = []
    lines = text.splitlines()
    current_key = None
    for line in lines:
        h = _FMT_HDR_RE.match(line)
        if h:
            current_key = h.group(1)
            continue
        if current_key:
            fm = _FMT_LINE_RE.search(line)
            if fm:
                formats.append({"key": current_key, "cited_n": int(fm.group(1)),
                                "sample_n": int(fm.group(2)), "confidence": fm.group(3)})
                current_key = None
    return {"week": int(m.group(1)) if m else None, "formats": formats,
            "templates_note": "高被引骨架：对比表 / 定义段 / 规格卡（见 playbook §5）"}
