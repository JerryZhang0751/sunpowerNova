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

def test_atomic_write_fsync_and_no_tmp_left(tmp_path, monkeypatch):
    import os
    from geo.shared.io_utils import atomic_write_text
    target = tmp_path / "run.yaml"
    seen = {}
    real_fsync = os.fsync
    def spy(fd):
        seen["fsync"] = True
        return real_fsync(fd)
    monkeypatch.setattr(os, "fsync", spy)
    atomic_write_text(target, "week: 3\n")
    assert target.read_text(encoding="utf-8") == "week: 3\n"
    assert not (tmp_path / "run.yaml.tmp").exists()
    assert seen.get("fsync") is True          # fsync 真被调用(耐久性)

def test_graph_next_week_writes_run_yaml_atomically(monkeypatch):
    """graph --next-week 的 run.yaml 写入必须走 atomic_write_text——抽 _bump_run_yaml_week 直测
    (run_pipeline 的 next_week 段不易直调;monkeypatch 后真实 run.yaml 只读不写)。"""
    import yaml
    import geo.orchestrate.graph as G
    from geo.shared import io_utils
    calls = []
    monkeypatch.setattr(io_utils, "atomic_write_text",
                        lambda p, t: calls.append((p, t)))
    G._bump_run_yaml_week(3)
    assert calls, "next_week 段必须经 atomic_write_text 写 run.yaml"
    path, text = calls[0]
    assert path.name == "run.yaml"
    assert yaml.safe_load(text)["week"] == 4          # 内容 week+1
