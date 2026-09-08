# tests/test_run.py
import json
from pathlib import Path
from geo.research.run import run_research

def test_run_research_deterministic_path_writes_files(tmp_path):
    import shutil
    FIX = Path(__file__).parent / "fixtures" / "research"
    # mirror fixture mini-repo into tmp (isolated reads + writes; no monkeypatch of module REPO)
    for sub in ["data/raw", "data/sources", "data/snapshots", "input"]:
        src = FIX / sub
        if src.exists():
            shutil.copytree(src, tmp_path / sub, dirs_exist_ok=True)
    # fetch_n=0 → select_topn returns [] → no fetch/network
    res = run_research(1, kimi_enabled=False, fetch_n=0, repo=tmp_path)
    assert (tmp_path/"knowledge"/"playbook.md").exists()
    assert (tmp_path/"knowledge"/"platform-profiles.md").exists()
    assert (tmp_path/"data"/"analysis"/"w1"/"research_aggregates.json").exists()
    agg = json.loads((tmp_path/"data"/"analysis"/"w1"/"research_aggregates.json").read_text())
    assert agg["week"] == 1

# ---- 追加到 tests/test_run.py(文件头已有 import json / from pathlib import Path)

def _mini_repo(tmp_path):
    """镜像 research fixture 为隔离 repo(既有模式)。"""
    import shutil
    FIX = Path(__file__).parent / "fixtures" / "research"
    for sub in ["data/raw", "data/sources", "data/snapshots", "input"]:
        src = FIX / sub
        if src.exists():
            shutil.copytree(src, tmp_path / sub, dirs_exist_ok=True)
    return tmp_path

_SYNTH_OK = '{"conclusions":[{"id":"c1","category":"source","conclusion":"外部权威站被引多","sample_n":3,"platforms":["qwen"],"confidence":"mid","action":"优先补权威外链","bucket_key":""}]}'

def test_kimi_failure_keeps_playbook_writes_draft(tmp_path):
    repo = _mini_repo(tmp_path)
    pb = repo / "knowledge" / "playbook.md"; pf = repo / "knowledge" / "platform-profiles.md"
    (repo / "knowledge").mkdir(parents=True, exist_ok=True)
    pb.write_text("OLD PLAYBOOK", encoding="utf-8"); pf.write_text("OLD PROFILES", encoding="utf-8")
    def boom(*a, **k): raise RuntimeError("kimi down")
    res = run_research(1, kimi_enabled=True, synth_fn=boom, web_fn=boom, fetch_n=0, repo=repo)
    assert pb.read_text(encoding="utf-8") == "OLD PLAYBOOK"      # 正式文件不动
    assert pf.read_text(encoding="utf-8") == "OLD PROFILES"
    draft_pb = repo / "knowledge" / "playbook.md.draft"
    assert draft_pb.exists() and "Kimi 综合不可用" in draft_pb.read_text(encoding="utf-8")
    assert (repo / "knowledge" / "platform-profiles.md.draft").exists()
    assert res["degraded"] is True and len(res["drafts"]) == 2

def test_success_promotes_and_backs_up(tmp_path):
    repo = _mini_repo(tmp_path)
    pb = repo / "knowledge" / "playbook.md"
    (repo / "knowledge").mkdir(parents=True, exist_ok=True)
    pb.write_text("OLD PLAYBOOK", encoding="utf-8")
    web_text = "GPTBot 爬虫存在。来源：https://openai.com/gptbot 置信度：high"
    res = run_research(1, kimi_enabled=True, synth_fn=lambda m, **k: _SYNTH_OK,
                       web_fn=lambda m, **k: web_text, fetch_n=0, repo=repo)
    assert res["degraded"] is False and res["drafts"] == []
    assert "OLD PLAYBOOK" not in pb.read_text(encoding="utf-8")  # 已更新
    hist = list((repo / "knowledge" / ".history").glob("playbook-w1-*.md"))
    assert len(hist) == 1 and hist[0].read_text(encoding="utf-8") == "OLD PLAYBOOK"
    assert not (repo / "knowledge" / "playbook.md.draft").exists()

def test_no_kimi_writes_direct_with_banner(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_research(1, kimi_enabled=False, fetch_n=0, repo=repo)
    pb = repo / "knowledge" / "playbook.md"
    assert pb.exists() and "确定性模式" in pb.read_text(encoding="utf-8")
    assert res["degraded"] is False and not (repo / "knowledge" / "playbook.md.draft").exists()

def test_profiles_independent_gate(tmp_path):
    """synthesize 成功但 web_search 全失败 → playbook 晋升、profiles 走草稿。"""
    repo = _mini_repo(tmp_path)
    def web_boom(*a, **k): raise RuntimeError("net down")
    res = run_research(1, kimi_enabled=True, synth_fn=lambda m, **k: _SYNTH_OK,
                       web_fn=web_boom, fetch_n=0, repo=repo)
    assert (repo / "knowledge" / "playbook.md").exists()
    assert (repo / "knowledge" / "platform-profiles.md.draft").exists()
    assert res["degraded"] is True


# ---- research_findings.json 落盘(2026-09-09):advisory-only 存档 Kimi 结论+平台查证 ----

_FINDINGS_REL = "data/analysis/w1/research_findings.json"

def _read_findings(repo):
    return json.loads((repo / _FINDINGS_REL).read_text(encoding="utf-8"))

def test_findings_ok_on_kimi_success(tmp_path):
    """Kimi 成功:全部结论落盘(render 只渲染 format 类,source 类只在本 JSON 保留)。"""
    repo = _mini_repo(tmp_path)
    web_text = "GPTBot 爬虫存在。来源：https://openai.com/gptbot 置信度：high"
    res = run_research(1, kimi_enabled=True, synth_fn=lambda m, **k: _SYNTH_OK,
                       web_fn=lambda m, **k: web_text, fetch_n=0, repo=repo)
    fpath = repo / _FINDINGS_REL
    assert fpath.exists() and res["findings"] == str(fpath)
    d = json.loads(fpath.read_text(encoding="utf-8"))
    assert d["schema_version"] == 1 and d["week"] == 1
    assert d["source_scope"] == "answer_citations_only"
    assert d["usage"] == "advisory_only" and d["rules_applied"] is False
    assert d["synthesis_status"] == "ok"
    assert d["verification_status"] == "ok"      # 7 平台全有非空 answer
    # source 类结论不进 playbook(render 只取 format)但必须完整保存在 findings
    assert "source" not in (repo / "knowledge" / "playbook.md").read_text(encoding="utf-8")
    src = [c for c in d["conclusions"] if c["category"] == "source"]
    assert len(src) == 1 and src[0]["id"] == "c1"
    assert src[0]["conclusion"] == "外部权威站被引多"
    assert src[0]["sample_n"] == 1              # synthesize 钳制到 fixture l3_resolved=1
    assert src[0]["platforms"] == ["qwen"] and src[0]["confidence"] == "mid"

def test_findings_degraded_on_kimi_failure(tmp_path):
    """Kimi 失败:findings 仍落盘、如实记 degraded;正式 playbook 不动。"""
    repo = _mini_repo(tmp_path)
    pb = repo / "knowledge" / "playbook.md"
    (repo / "knowledge").mkdir(parents=True, exist_ok=True)
    pb.write_text("OLD PLAYBOOK", encoding="utf-8")
    def boom(*a, **k): raise RuntimeError("kimi down")
    res = run_research(1, kimi_enabled=True, synth_fn=boom, web_fn=boom, fetch_n=0, repo=repo)
    d = _read_findings(repo)
    assert d["synthesis_status"] == "degraded" and d["conclusions"] == []
    assert d["verification_status"] == "degraded"  # 逐平台吞异常 → 全空 answer
    assert pb.read_text(encoding="utf-8") == "OLD PLAYBOOK"
    assert res["findings"].endswith("research_findings.json")

def test_findings_disabled_when_no_kimi(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_research(1, kimi_enabled=False, fetch_n=0, repo=repo)
    d = _read_findings(repo)
    assert d["synthesis_status"] == "disabled" and d["verification_status"] == "disabled"
    assert d["conclusions"] == [] and d["platform_verification"] == {}
    assert res["findings"].endswith("research_findings.json")

def test_findings_partial_verification_and_budget_exhausted(tmp_path, monkeypatch):
    """Qwen 查证成功、其余 6 平台全局预算耗尽 → partial;answer/sources/confidence 原样保存。"""
    from geo.research import kimi as K
    seq = iter([0.0,                    # t0
                0.0, 0.0, 10.0,         # Qwen:全局预检/deadline/后验(10<600 不标 platform)
                *([3600.0] * 6)])       # 其余 6 平台:预检即超全局 → 跳过
    monkeypatch.setattr(K.time, "monotonic", lambda: next(seq, 3600.0))
    answer = "QwenBot 存在。来源：https://example.com/qwenbot 置信度：high"
    def web_qwen_only(messages, tools=None, timeout=180, **kw):
        assert "平台：Qwen" in messages[1]["content"]   # 其它平台不应发起调用
        return answer
    run_research(1, kimi_enabled=True, synth_fn=lambda m, **k: _SYNTH_OK,
                 web_fn=web_qwen_only, fetch_n=0, repo=_mini_repo(tmp_path))
    d = _read_findings(tmp_path)
    assert d["verification_status"] == "partial"
    v = d["platform_verification"]["Qwen"]
    assert v["answer"] == answer
    assert v["sources"] == ["https://example.com/qwenbot"] and v["confidence"] == "high"
    assert d["budget_exhausted"] == ["ChatGPT", "Claude", "Doubao", "Gemini", "Perplexity", "Zhipu"]
    assert d["platform_verification"]["Doubao"]["budget_exhausted"] == "global"

def test_findings_evidence_ref_and_coverage_match_aggregates(tmp_path):
    repo = _mini_repo(tmp_path)
    run_research(1, kimi_enabled=False, fetch_n=0, repo=repo)
    d = _read_findings(repo)
    a = json.loads((repo / "data" / "analysis" / "w1" / "research_aggregates.json").read_text())
    assert d["evidence_ref"] == "data/analysis/w1/research_aggregates.json"
    assert d["coverage"] == a["coverage"]
    assert d["coverage"] == {"total_l1": 1, "total_cited_sources": 3, "l3_resolved": 1,
                             "l3_missing": 1, "l3_js_only": 1}
    assert d["budget_exhausted"] == [] and a["budget_exhausted"] == []
