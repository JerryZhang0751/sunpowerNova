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
