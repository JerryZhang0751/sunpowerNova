# tests/test_research_kimi.py
# T12(2026-09-02): research 墙钟预算（D5）——每平台 600s + 全局 3600s（monotonic deadline），
# 耗尽平台诚实降级「外部未验证」+ budget_exhausted 标记，绝不崩；SDK 层重试关（单轮 ≤timeout）。
from types import SimpleNamespace as NS


def _tool_call(id="call_1", name="$web_search", args='{"query":"qwen crawler"}'):
    return NS(id=id, function=NS(name=name, arguments=args))


# ---- web_search_verify 预算门 ----

def test_web_search_verify_global_budget_exhaustion(monkeypatch):
    from geo.research import kimi as K
    calls = []
    def slow_chat(messages, tools=None, timeout=180, **kw):
        calls.append(messages[1]["content"])           # 记录查证的平台
        return "结论 来源:https://x.com/a 置信度:high"
    items = [{"platform": p} for p in ["A", "B", "C"]]
    out = K.web_search_verify(items, chat_fn=slow_chat, platform_budget_s=600,
                              global_budget_s=0)        # 全局预算=0 → 全部跳过
    assert all(v["confidence"] == "外部未验证" and v["budget_exhausted"] == "global"
               for v in out.values()) and calls == []


def test_web_search_verify_global_exhaustion_mid_run(monkeypatch):
    # 前一平台正常查证，全局预算在后续平台预检时耗尽 → 只跳过剩余平台
    from geo.research import kimi as K
    seq = iter([0.0,            # t0
                0.0, 10.0, 20.0,        # A：全局预检 / 算 deadline / 后验检查
                3600.0])                # B：预检即超全局 → skip
    monkeypatch.setattr(K.time, "monotonic", lambda: next(seq, 3600.0))
    calls = []
    def chat(messages, tools=None, timeout=180, **kw):
        calls.append(messages[1]["content"])
        return "结论：A 爬虫。\n来源：https://a.com/x\n置信度：mid"
    out = K.web_search_verify([{"platform": "A"}, {"platform": "B"}], chat_fn=chat,
                              platform_budget_s=600, global_budget_s=3600)
    assert len(calls) == 1 and "A" in calls[0]           # B 零 API 调用
    assert out["A"]["confidence"] == "mid" and "budget_exhausted" not in out["A"]
    assert out["B"]["confidence"] == "外部未验证" and out["B"]["budget_exhausted"] == "global"


def test_web_search_verify_platform_overrun_marked_post_hoc(monkeypatch):
    # 单轮（一次 create 内）耗时超过平台预算：不中断（无轮次可省）但后验标记 budget_exhausted=platform
    from geo.research import kimi as K
    seq = iter([0.0,     # t0
                0.0, 100.0,      # 全局预检 / 算 deadline（min(3600, 100+600)=700）
                800.0])          # 后验：800 > 700 → 超平台预算
    monkeypatch.setattr(K.time, "monotonic", lambda: next(seq, 800.0))
    def chat(messages, tools=None, timeout=180, **kw):
        return "结论：X\n来源：https://a.com/x\n置信度：high"
    out = K.web_search_verify([{"platform": "A"}], chat_fn=chat,
                              platform_budget_s=600, global_budget_s=3600)
    assert out["A"]["budget_exhausted"] == "platform"
    assert out["A"]["confidence"] == "high"              # 后验标记不推翻答案本身


# ---- _drive_web_search deadline 逐轮检查 ----

def test_drive_web_search_expired_deadline_makes_zero_extra_calls(monkeypatch):
    # D5：deadline 到点后不再发起下一轮 create（零额外 API 调用），返回 ""（非异常路径）
    from geo.research import kimi as K
    calls = []
    def create(**kw):
        calls.append(kw)
        msg = NS(content="", tool_calls=[_tool_call()])
        return NS(choices=[NS(finish_reason="tool_calls", message=msg)])
    seq = iter([100.0, 1000000.0])   # 第 1 轮预检未过期 → create×1；第 2 轮预检已过期 → 放弃
    monkeypatch.setattr(K.time, "monotonic", lambda: next(seq, 1000000.0))
    out = K._drive_web_search(create, [{"role": "user", "content": "q"}],
                              max_rounds=5, deadline=500.0)
    assert out == "" and len(calls) == 1


def test_drive_web_search_no_deadline_keeps_all_rounds(monkeypatch):
    # deadline=None（既有调用方/测试）不触发预算门
    from geo.research import kimi as K
    calls = []
    def create(**kw):
        calls.append(kw)
        return NS(choices=[NS(finish_reason="stop",
                              message=NS(content="终答 来源：https://a.com/b 置信度：low",
                                         tool_calls=None))])
    monkeypatch.setattr(K.time, "monotonic",
                        lambda: (_ for _ in ()).throw(AssertionError("deadline=None 不得读钟")))
    assert "终答" in K._drive_web_search(create, [{"role": "user", "content": "q"}])
    assert len(calls) == 1


# ---- _web_search_chat 重接线（T4 make_kimi_client + max_retries=0 + deadline 透传）----

def test_web_search_chat_no_sdk_retries():
    # max_retries=0（SDK 层重试关闭，单轮 ≤timeout）
    import inspect
    from geo.research.kimi import _web_search_chat
    src = inspect.getsource(_web_search_chat)
    assert "max_retries=0" in src


def test_web_search_chat_wires_make_kimi_client_max_retries_zero(monkeypatch):
    import geo.research.kimi as K
    seen = {}
    class _Completions:
        @staticmethod
        def create(**kw):
            return NS(choices=[NS(finish_reason="stop",
                                  message=NS(content="终答 来源：https://a.com/b 置信度：low",
                                             tool_calls=None))])
    def fake_make(*, timeout, max_retries):
        seen.update(timeout=timeout, max_retries=max_retries)
        return NS(chat=NS(completions=_Completions()))
    monkeypatch.setattr("geo.shared.kimi_client.make_kimi_client", fake_make)
    out = K._web_search_chat([{"role": "user", "content": "q"}], timeout=180)
    assert seen == {"timeout": 180, "max_retries": 0}
    assert "终答" in out


# ---- run.py 汇总（budget_exhausted 键）----

_SYNTH_OK = '{"conclusions":[{"id":"c1","category":"source","conclusion":"外部权威站被引多","sample_n":3,"platforms":["qwen"],"confidence":"mid","action":"优先补权威外链","bucket_key":""}]}'


def _mini_repo(tmp_path):
    """镜像 research fixture 为隔离 repo（tests/test_run.py 既有模式）。"""
    import shutil
    from pathlib import Path
    FIX = Path(__file__).parent / "fixtures" / "research"
    for sub in ["data/raw", "data/sources", "data/snapshots", "input"]:
        src = FIX / sub
        if src.exists():
            shutil.copytree(src, tmp_path / sub, dirs_exist_ok=True)
    return tmp_path


def test_run_research_reports_budget_exhausted(tmp_path, monkeypatch):
    import geo.research.run as R
    repo = _mini_repo(tmp_path)
    def fake_verify(items, **kw):
        return {"Qwen": {"answer": "x", "sources": ["https://a.com"], "confidence": "mid"},
                "Doubao": {"answer": "", "sources": [], "confidence": "外部未验证",
                           "budget_exhausted": "global"},
                "ChatGPT": {"answer": "", "sources": [], "confidence": "外部未验证",
                            "budget_exhausted": "platform"}}
    monkeypatch.setattr(R, "web_search_verify", fake_verify)
    res = R.run_research(1, kimi_enabled=True, synth_fn=lambda m, **k: _SYNTH_OK,
                         fetch_n=0, repo=repo)
    assert res["budget_exhausted"] == ["ChatGPT", "Doubao"]   # sorted


def test_run_research_budget_exhausted_empty_when_no_kimi(tmp_path):
    from geo.research.run import run_research
    repo = _mini_repo(tmp_path)
    res = run_research(1, kimi_enabled=False, fetch_n=0, repo=repo)
    assert res["budget_exhausted"] == []
