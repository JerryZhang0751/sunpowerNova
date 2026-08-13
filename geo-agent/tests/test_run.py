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
    # Kimi disabled + source already mirrored → select_topn returns [] (no fetch/network)
    res = run_research(1, kimi_enabled=False, repo=tmp_path)
    assert (tmp_path/"knowledge"/"playbook.md").exists()
    assert (tmp_path/"knowledge"/"platform-profiles.md").exists()
    assert (tmp_path/"data"/"analysis"/"w1"/"research_aggregates.json").exists()
    agg = json.loads((tmp_path/"data"/"analysis"/"w1"/"research_aggregates.json").read_text())
    assert agg["week"] == 1
