# src/geo/shared/io_utils.py
from __future__ import annotations
import os
from pathlib import Path

def atomic_write_text(path: Path, text: str) -> None:
    """tmp + os.replace 原子写:读方要么看到完整旧文件、要么看到完整新文件。"""
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
