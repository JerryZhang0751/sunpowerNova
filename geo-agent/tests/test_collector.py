import json
import geo.collect.collector as collector
import geo.shared.storage as storage
from geo.collect.collector import run_collection

def _fake_collect(prompt, **k):
    return {"answer":"A SunHestia","search_results":[{"url":"https://e.com","title":""}],
            "usage":{},"elapsed_s":0.1,"raw":{}}

def _iso_repo(tmp_path, monkeypatch, clients=None):
    """l1 落盘 + manifest 全部指向 tmp repo;CLIENTS 按测试覆盖。

    注意必须 patch collector.CLIENTS 字典本身——_one 在 import 时已把原函数
    绑进字典,patch 模块属性(旧写法)从不生效,旧测试实际靠 data/raw/w99
    残留走 skipped_exists 空转(2026-08-24 审查#5 期间发现并修复)。
    """
    monkeypatch.setattr(storage, "REPO", tmp_path)
    def fake_l1(w, m, pid, run):
        q = tmp_path / "data" / "raw" / f"w{w}" / m / pid
        q.mkdir(parents=True, exist_ok=True)
        return q / f"r{run}.json"
    monkeypatch.setattr(collector, "l1_path", fake_l1)
    if clients is not None:
        merged = dict(collector.CLIENTS); merged.update(clients)
        monkeypatch.setattr(collector, "CLIENTS", merged)
    return fake_l1

def test_run_writes_l1_and_resumes(tmp_path, monkeypatch):
    l1 = _iso_repo(tmp_path, monkeypatch, clients={"qwen": _fake_collect})
    recs1 = run_collection(week=99, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
    p = l1(99, "qwen", "C01", 1)
    assert p.exists() and json.loads(p.read_text())["model"] == "qwen"
    assert all(r.status == "ok" for r in recs1)
    # 续跑：已存在不重采（真实调用会 AssertionError）
    def _must_not_call(prompt, **k):
        raise AssertionError("不应重采")
    monkeypatch.setattr(collector, "CLIENTS", {"qwen": _must_not_call})
    recs2 = run_collection(week=99, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
    assert len(recs2) == 1 and recs2[0].status == "skipped_exists"


# ---- Fix(2026-08-24 审查#5): 采集失败不得从分母消失 ---------------------------
import json as _json
from geo.shared.models import RunRecord

def _iso(tmp_path, monkeypatch, clients=None):
    """新测试块复用统一隔离:见 _iso_repo 注释。"""
    return _iso_repo(tmp_path, monkeypatch, clients)

def test_failures_persisted_to_manifest(tmp_path, monkeypatch):
    """一家成功、一家全败:manifest 必须记下 failed(含 error),不得只剩成功侧。"""
    def boom(prompt, **k):
        raise RuntimeError("provider down")
    _iso(tmp_path, monkeypatch, clients={"qwen": _fake_collect, "zhipu": boom})
    recs = run_collection(week=97, models=["qwen", "zhipu"], prompt_ids=["C01"], runs=1,
                          rule_version="t")
    by_status = {r.status for r in recs}
    assert "ok" in by_status and "failed" in by_status
    failed = [r for r in recs if r.status == "failed"]
    assert failed and failed[0].model == "zhipu" and "provider down" in failed[0].error
    manifest = (tmp_path / "data" / "raw" / "w97" / "runs.jsonl")
    assert manifest.exists()
    lines = [RunRecord(**_json.loads(l)) for l in manifest.read_text().splitlines() if l.strip()]
    statuses = {(r.model, r.status) for r in lines}
    assert ("qwen", "planned") in statuses and ("qwen", "ok") in statuses
    assert ("zhipu", "planned") in statuses and ("zhipu", "failed") in statuses

def test_collection_health_denominator(tmp_path, monkeypatch):
    """manifest 记 2 个 job、盘上只有 1 个 L1 → planned=2/valid=1/success=0.5。"""
    fake_l1 = _iso(tmp_path, monkeypatch)
    import geo.shared.storage as storage
    mp = tmp_path / "data" / "raw" / "w96" / "runs.jsonl"
    mp.parent.mkdir(parents=True)
    recs = [RunRecord(week=96, model="qwen", prompt_id="C01", run=1, prompt_set_version="p",
                      rule_snapshot_version="t", status="planned", l1_path=""),
            RunRecord(week=96, model="qwen", prompt_id="D01", run=1, prompt_set_version="p",
                      rule_snapshot_version="t", status="failed", l1_path="", error="x")]
    mp.write_text("\n".join(r.model_dump_json() for r in recs), encoding="utf-8")
    p = fake_l1(96, "qwen", "C01", 1); p.write_text("{}", encoding="utf-8")
    from geo.collect.collector import collection_health
    h = collection_health(96)
    assert h["manifest"] is True
    assert h["per_model"]["qwen"] == {"planned": 2, "valid": 1, "success_rate": 0.5}
    assert h["min_success_rate"] == 0.5

def test_collection_health_no_manifest(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    from geo.collect.collector import collection_health
    h = collection_health(95)
    assert h["manifest"] is False and h["min_success_rate"] is None
