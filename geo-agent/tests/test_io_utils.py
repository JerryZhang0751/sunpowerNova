# tests/test_io_utils.py
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from geo.shared.io_utils import atomic_write_text

def test_atomic_write_creates_file(tmp_path):
    p = tmp_path / "a.json"
    atomic_write_text(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"

def test_atomic_write_replaces_existing(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("old", encoding="utf-8")
    atomic_write_text(p, "new")
    assert p.read_text(encoding="utf-8") == "new"

def test_atomic_write_failure_leaves_original_intact(tmp_path):
    """写入中断(替换前异常)不得损坏原文件——覆写保护的底线。"""
    p = tmp_path / "a.md"
    p.write_text("GOOD", encoding="utf-8")
    with patch("geo.shared.io_utils.os.replace", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            atomic_write_text(p, "BAD")
    assert p.read_text(encoding="utf-8") == "GOOD"
