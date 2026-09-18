import json
import httpx
import geo.collect.collector as collector
import geo.shared.storage as storage
from geo.collect.collector import run_collection
from geo.collect.qwen_client import QwenAPIError

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
    """manifest 记 2 个 job、盘上只有 1 个可用 L1 → planned=2/valid=1/success=0.5。
    (二次审查 2026-08-25: valid 判据从"文件存在"收紧为"可解析且带非空答案"。)"""
    fake_l1 = _iso(tmp_path, monkeypatch)
    import geo.shared.storage as storage
    mp = tmp_path / "data" / "raw" / "w96" / "runs.jsonl"
    mp.parent.mkdir(parents=True)
    recs = [RunRecord(week=96, model="qwen", prompt_id="C01", run=1, prompt_set_version="p",
                      rule_snapshot_version="t", status="planned", l1_path=""),
            RunRecord(week=96, model="qwen", prompt_id="D01", run=1, prompt_set_version="p",
                      rule_snapshot_version="t", status="failed", l1_path="", error="x")]
    mp.write_text("\n".join(r.model_dump_json() for r in recs), encoding="utf-8")
    p = fake_l1(96, "qwen", "C01", 1)
    p.write_text(json.dumps({"answer": "a real answer"}), encoding="utf-8")
    from geo.collect.collector import collection_health
    h = collection_health(96)
    assert h["manifest"] is True
    assert h["per_model"]["qwen"] == {"planned": 2, "valid": 1, "success_rate": 0.5}
    assert h["min_success_rate"] == 0.5

def test_collection_health_rejects_empty_or_torn_l1(tmp_path, monkeypatch):
    """二次审查(2026-08-25)#5: 空答案 L1、截断 JSON L1 不得进有效分子——
    "文件存在即成功"会让超时空答/崩溃残留绕过 95% 数据质量门。"""
    fake_l1 = _iso(tmp_path, monkeypatch)
    mp = tmp_path / "data" / "raw" / "w98" / "runs.jsonl"
    mp.parent.mkdir(parents=True)
    recs = [RunRecord(week=98, model="qwen", prompt_id=p, run=1, prompt_set_version="p",
                      rule_snapshot_version="t", status="planned", l1_path="")
            for p in ("C01", "D01", "B02")]
    mp.write_text("\n".join(r.model_dump_json() for r in recs), encoding="utf-8")
    fake_l1(98, "qwen", "C01", 1).write_text(json.dumps({"answer": "ok"}), encoding="utf-8")
    fake_l1(98, "qwen", "D01", 1).write_text(json.dumps({"answer": "   "}), encoding="utf-8")
    fake_l1(98, "qwen", "B02", 1).write_text('{"answer": "tor', encoding="utf-8")  # 截断
    from geo.collect.collector import collection_health
    h = collection_health(98)
    assert h["per_model"]["qwen"]["planned"] == 3
    assert h["per_model"]["qwen"]["valid"] == 1
    assert h["per_model"]["qwen"]["success_rate"] == round(1 / 3, 3)

def test_timeout_or_empty_answer_is_failure_not_ok(tmp_path, monkeypatch):
    """二次审查(2026-08-25)#5: qwen timeout=True / 任意家空答案 → failed,
    不写 L1、error 落 manifest;不得 status=ok 进成功率分子。"""
    def timeout_client(prompt, **k):
        return {"answer": "", "search_results": [], "usage": {}, "elapsed_s": 600.0,
                "timeout": True}
    def empty_client(prompt, **k):
        return {"answer": "   ", "search_results": [], "usage": {}, "elapsed_s": 1.0}
    l1 = _iso(tmp_path, monkeypatch,
              clients={"qwen": timeout_client, "zhipu": empty_client})
    recs = run_collection(week=94, models=["qwen", "zhipu"], prompt_ids=["C01"], runs=1,
                          rule_version="t")
    assert all(r.status == "failed" for r in recs), [r.status for r in recs]
    assert not l1(94, "qwen", "C01", 1).exists()
    assert not l1(94, "zhipu", "C01", 1).exists()
    lines = [json.loads(l) for l in (tmp_path / "data" / "raw" / "w94" / "runs.jsonl")
             .read_text(encoding="utf-8").splitlines() if l.strip()]
    assert any(l["model"] == "qwen" and l["status"] == "failed" and "超时" in l["error"]
               for l in lines)
    assert any(l["model"] == "zhipu" and l["status"] == "failed" and "空答案" in l["error"]
               for l in lines)

def test_resume_ignores_invalid_existing_l1(tmp_path, monkeypatch):
    """续跑对截断/空答案 L1 不得 skipped_exists——重采覆盖,否则坏文件永久占位。"""
    l1 = _iso(tmp_path, monkeypatch, clients={"qwen": _fake_collect})
    p = l1(93, "qwen", "C01", 1)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"answer": "tor', encoding="utf-8")               # 崩溃残留
    recs = run_collection(week=93, models=["qwen"], prompt_ids=["C01"], runs=1,
                          rule_version="t")
    assert all(r.status == "ok" for r in recs)
    assert json.loads(p.read_text(encoding="utf-8"))["answer"] == "A SunHestia"  # 已重采覆写

def test_collection_health_no_manifest(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    from geo.collect.collector import collection_health
    h = collection_health(95)
    assert h["manifest"] is False and h["min_success_rate"] is None

def test_qwen_api_error_preserved_in_manifest(tmp_path, monkeypatch):
    """codex w3 修改一(2026-09-02): QwenAPIError(如额度耗尽 AllocationQuota.
    FreeTierOnly)经 tenacity 重试用尽后,runs.jsonl failed.error 必须保留真实
    错误码——不得降格为"返回空答案"吞掉账号侧根因。"""
    from geo.collect.qwen_client import QwenAPIError

    def quota_dead(prompt, **k):
        raise QwenAPIError("DashScope API 错误(status_code=429, code=): "
                           "AllocationQuota.FreeTierOnly")
    _iso(tmp_path, monkeypatch, clients={"qwen": quota_dead})
    recs = run_collection(week=96, models=["qwen"], prompt_ids=["C01"], runs=1,
                          rule_version="t")
    failed = [r for r in recs if r.status == "failed"]
    assert failed and "AllocationQuota.FreeTierOnly" in failed[0].error
    assert "空答案" not in failed[0].error
    # manifest 落盘同查
    from geo.shared.storage import read_run_records
    lines = read_run_records(96)
    assert any(l.model == "qwen" and l.status == "failed"
               and "AllocationQuota.FreeTierOnly" in l.error for l in lines)

# ---- Bug#4(w4): 传输类瞬时故障单 pass 内重试 ---------------------------------

def test_retryable_transport_error_retried_to_success(tmp_path, monkeypatch):
    calls = {"n": 0}
    def flaky(prompt, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("Response ended prematurely")
        return {"answer": "ok text", "usage": {}, "elapsed_s": 0.1}
    monkeypatch.setattr("time.sleep", lambda s: None)
    _iso(tmp_path, monkeypatch, clients={"qwen": flaky})
    recs = run_collection(week=96, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
    assert calls["n"] == 3
    assert [r.status for r in recs if r.model == "qwen" and r.status != "planned"] == ["ok"]

def test_retry_exhausted_records_failed(tmp_path, monkeypatch):
    calls = {"n": 0}
    def always_dead(prompt, **k):
        calls["n"] += 1
        raise httpx.ConnectError("connection reset")
    monkeypatch.setattr("time.sleep", lambda s: None)
    _iso(tmp_path, monkeypatch, clients={"qwen": always_dead})
    recs = run_collection(week=96, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
    assert calls["n"] == 3
    failed = [r for r in recs if r.status == "failed"]
    assert len(failed) == 1 and "connection reset" in failed[0].error

def test_qwen_api_error_not_retried(tmp_path, monkeypatch):
    calls = {"n": 0}
    def quota(prompt, **k):
        calls["n"] += 1
        raise QwenAPIError("AllocationQuota.FreeTierOnly")
    monkeypatch.setattr("time.sleep", lambda s: None)
    _iso(tmp_path, monkeypatch, clients={"qwen": quota})
    recs = run_collection(week=96, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
    assert calls["n"] == 1          # 配额类不重试(w3 教训:烧额度且无效)
    assert [r.status for r in recs if r.status == "failed"]

def test_http_status_error_not_retried(tmp_path, monkeypatch):
    calls = {"n": 0}
    req = httpx.Request("GET", "https://ark.cn-beijing.volces.com/api/v3/responses")
    def limited(prompt, **k):
        calls["n"] += 1
        raise httpx.HTTPStatusError("429", request=req, response=httpx.Response(429))
    monkeypatch.setattr("time.sleep", lambda s: None)
    _iso(tmp_path, monkeypatch, clients={"qwen": limited})
    run_collection(week=96, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
    assert calls["n"] == 1

# ---- spec 2026-09-18 §5.1: 供应商级并行调度(每家最多1个在途,总并发≤3) --------

import threading
import time as _time


def _ok_answer(name):
    def client(prompt, **k):
        return {"answer": f"A {name}", "search_results": [], "usage": {}, "elapsed_s": 0.1}
    return client


def _wait_until(cond, timeout=10.0, what="condition"):
    """有界等待。轮询用 Event.wait(0.01) —— 不经 time.sleep(退避测试会 patch 它)。"""
    dummy = threading.Event()
    deadline = _time.monotonic() + timeout
    while not cond():
        if _time.monotonic() > deadline:
            raise AssertionError(f"timeout waiting: {what}")
        dummy.wait(0.01)


def test_first_batch_contains_all_vendors(tmp_path, monkeypatch):
    """三家均有多条任务 → 首批请求必须包含三家(不能全是同一家);
    且每家最多1个在途 —— 全部阻塞期间恰好只发生3次调用。"""
    started: list[str] = []
    lock = threading.Lock()
    release = threading.Event()

    def mk(name):
        def client(prompt, **k):
            with lock:
                started.append(name)
            assert release.wait(timeout=10), "客户端未获释放(测试挂起)"
            return {"answer": f"A {name}", "search_results": [], "usage": {}, "elapsed_s": 0.1}
        return client

    _iso(tmp_path, monkeypatch,
         clients={m: mk(m) for m in ("qwen", "doubao", "zhipu")})
    th = threading.Thread(target=lambda: run_collection(
        week=91, models=["qwen", "doubao", "zhipu"],
        prompt_ids=["C01", "D01", "B02"], runs=1, rule_version="t"))
    try:
        th.start()
        _wait_until(lambda: len(started) >= 3, what="首批三家请求进入")
        assert set(started) == {"qwen", "doubao", "zhipu"}, started
        assert len(started) == 3, f"每家应只有1个在途请求: {started}"
    finally:
        release.set()
        th.join(timeout=10)
    assert not th.is_alive()


def test_blocked_vendor_does_not_stall_others(tmp_path, monkeypatch):
    """qwen 单条阻塞期间:doubao/zhipu 的全部任务完成并逐条落盘;
    qwen 其余任务不被拉起(每家1在途)。"""
    unblock = threading.Event()
    qwen_started: list[str] = []

    def qwen_slow(prompt, **k):
        qwen_started.append(prompt)
        assert unblock.wait(timeout=10), "qwen 未获释放(测试挂起)"
        return {"answer": "A qwen", "search_results": [], "usage": {}, "elapsed_s": 0.1}

    _iso(tmp_path, monkeypatch, clients={"qwen": qwen_slow,
                                         "doubao": _ok_answer("doubao"),
                                         "zhipu": _ok_answer("zhipu")})
    th = threading.Thread(target=lambda: run_collection(
        week=92, models=["qwen", "doubao", "zhipu"],
        prompt_ids=["C01", "D01", "B02"], runs=1, rule_version="t"))
    manifest = tmp_path / "data" / "raw" / "w92" / "runs.jsonl"
    try:
        th.start()
        def others_done():
            if not manifest.exists():
                return False
            lines = manifest.read_text(encoding="utf-8").splitlines()
            return sum(1 for l in lines if '"status":"ok"' in l
                       and ('"model":"doubao"' in l or '"model":"zhipu"' in l)) >= 6
        _wait_until(others_done, what="qwen 阻塞期间 doubao/zhipu 6 条 ok 落盘")
        assert len(qwen_started) == 1, f"qwen 应只有1条在途: {qwen_started}"
        still_running = th.is_alive()          # qwen 未完成 → 管线仍在运行
    finally:
        unblock.set()
        th.join(timeout=10)
    assert not th.is_alive()
    assert still_running


def test_backoff_in_one_vendor_does_not_block_others(tmp_path, monkeypatch):
    """某家传输类失败进入退避(重试 sleep)期间:另两家照常完成;
    退避释放后该家重试成功。"""
    in_backoff = threading.Event()
    backoff_done = threading.Event()

    def fake_sleep(s):
        in_backoff.set()
        assert backoff_done.wait(timeout=10), "退避未获释放(测试挂起)"

    monkeypatch.setattr("time.sleep", fake_sleep)   # 与本文件既有测试同法
    calls = {"qwen": 0}

    def flaky(prompt, **k):
        calls["qwen"] += 1
        if calls["qwen"] == 1:
            raise RuntimeError("Response ended prematurely")   # 传输类 → 可重试
        return {"answer": "A qwen", "search_results": [], "usage": {}, "elapsed_s": 0.1}

    _iso(tmp_path, monkeypatch, clients={"qwen": flaky,
                                         "doubao": _ok_answer("doubao"),
                                         "zhipu": _ok_answer("zhipu")})
    th = threading.Thread(target=lambda: run_collection(
        week=90, models=["qwen", "doubao", "zhipu"], prompt_ids=["C01"], runs=1,
        rule_version="t"))
    manifest = tmp_path / "data" / "raw" / "w90" / "runs.jsonl"
    try:
        th.start()
        assert in_backoff.wait(timeout=10), "qwen 未进入退避"
        def others_done():
            # 逐行查 model+prompt_id+status 三元组:RunRecord 字段序为
            # week,model,prompt_id,run,prompt_set_version,rule_snapshot_version,status,...
            # prompt_id 与 status 不相邻,跨字段连续子串永不匹配(2026-09-18 修正)
            if not manifest.exists():
                return False
            lines = manifest.read_text(encoding="utf-8").splitlines()
            return (any('"model":"doubao"' in l and '"prompt_id":"C01"' in l
                        and '"status":"ok"' in l for l in lines) and
                    any('"model":"zhipu"' in l and '"prompt_id":"C01"' in l
                        and '"status":"ok"' in l for l in lines))
        _wait_until(others_done, what="退避期间 doubao/zhipu 完成")
        assert calls["qwen"] == 1, "退避中:第二次尝试尚未发起"
    finally:
        backoff_done.set()
        th.join(timeout=10)
    assert not th.is_alive()
    assert calls["qwen"] == 2          # 退避释放后重试成功


def test_completed_vendor_not_called_again(tmp_path, monkeypatch):
    """某家全部已有有效 L1 → 只走 skipped_exists,不再调用该家接口。"""
    l1 = _iso(tmp_path, monkeypatch, clients={"doubao": _ok_answer("doubao")})
    for pid in ("C01", "D01"):
        p = l1(88, "qwen", pid, 1)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"answer": "already there"}), encoding="utf-8")

    def must_not_call(prompt, **k):
        raise AssertionError("已完成供应商不得再调用")

    monkeypatch.setattr(collector, "CLIENTS",
                        {**collector.CLIENTS, "qwen": must_not_call})
    recs = run_collection(week=88, models=["qwen", "doubao"],
                          prompt_ids=["C01", "D01"], runs=1, rule_version="t")
    st = {(r.model, r.status) for r in recs}
    assert ("qwen", "skipped_exists") in st and ("doubao", "ok") in st


def test_subset_and_repeat_runs_complete_exactly_once(tmp_path, monkeypatch):
    """供应商子集 + 多 run: 任务不遗漏不重复;全部完成后再跑不发起请求。"""
    calls: list[tuple[str, str]] = []

    def counting(name):
        def client(prompt, **k):
            calls.append((name, prompt))
            return {"answer": f"A {name}", "search_results": [], "usage": {}, "elapsed_s": 0.1}
        return client

    _iso(tmp_path, monkeypatch, clients={"qwen": counting("qwen"),
                                         "zhipu": counting("zhipu")})
    recs = run_collection(week=87, models=["qwen", "zhipu"],
                          prompt_ids=["C01", "D01"], runs=2, rule_version="t")
    assert len(calls) == 8                       # 2家 × 2题 × 2run
    keys = {(r.model, r.prompt_id, r.run) for r in recs if r.status == "ok"}
    assert len(keys) == 8
    calls.clear()
    recs2 = run_collection(week=87, models=["qwen", "zhipu"],
                           prompt_ids=["C01", "D01"], runs=2, rule_version="t")
    assert calls == []
    assert len(recs2) == 8 and all(r.status == "skipped_exists" for r in recs2)
