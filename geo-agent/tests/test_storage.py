# tests/test_storage.py
"""runs.jsonl 崩溃/并发安全(2026-08-25 二次审查#7):

- 追加: flock + O_APPEND 单次 write + fsync —— 进程并发不交错,崩溃不产生
  中途行以外的损坏;
- 读取: 残缺尾行(写入中断)跳过并告警,不得让后续读取永久 JSONDecodeError。
"""
import json
from concurrent.futures import ThreadPoolExecutor

import geo.shared.storage as storage
from geo.shared.models import RunRecord


def _rec(pid: str) -> RunRecord:
    return RunRecord(week=93, model="qwen", prompt_id=pid, run=1,
                     prompt_set_version="p", rule_snapshot_version="t", status="ok",
                     l1_path="")


def test_append_is_interleaving_free(tmp_path, monkeypatch):
    """4 线程各追加 50 条 → 200 行全部完整可解析,无交错半行。"""
    monkeypatch.setattr(storage, "REPO", tmp_path)

    def worker(i: int):
        for j in range(50):
            storage.append_run_records(93, [_rec(f"P{i}-{j}")])

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(worker, range(4)))

    lines = (tmp_path / "data" / "raw" / "w93" / "runs.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert len(lines) == 200
    for l in lines:
        RunRecord(**json.loads(l))


def test_read_tolerates_torn_tail(tmp_path, monkeypatch):
    """崩溃残留的半行 JSON 不得让 read 永久崩;完好行照常读出。"""
    monkeypatch.setattr(storage, "REPO", tmp_path)
    p = tmp_path / "data" / "raw" / "w93" / "runs.jsonl"
    p.parent.mkdir(parents=True)
    p.write_text(_rec("Pa").model_dump_json() + "\n"
                 + '{"week": 93, "model": "qwe', encoding="utf-8")   # 截断尾行
    recs = storage.read_run_records(93)
    assert len(recs) == 1 and recs[0].prompt_id == "Pa"


def test_read_skips_schema_mismatch_with_warning(tmp_path, monkeypatch, caplog):
    """字段结构不符的行(如磁盘腐化)跳过并记 warning,不静默、不崩。"""
    import logging
    monkeypatch.setattr(storage, "REPO", tmp_path)
    p = tmp_path / "data" / "raw" / "w93" / "runs.jsonl"
    p.parent.mkdir(parents=True)
    p.write_text(_rec("Pa").model_dump_json() + "\n"
                 + json.dumps({"nonsense": 1}) + "\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="storage"):
        recs = storage.read_run_records(93)
    assert len(recs) == 1
    assert any("跳过" in r.message for r in caplog.records)
