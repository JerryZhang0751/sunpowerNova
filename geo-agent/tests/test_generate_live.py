# tests/test_generate_live.py
import json, shutil
from pathlib import Path
import pytest
from geo.generate.run import run_generate

FIX = Path(__file__).parent / "fixtures" / "generate"

@pytest.mark.live
def test_live_generate_real_kimi(tmp_path):
    """真 Kimi K3 生成一篇。手动跑: python3.11 -m pytest -m live tests/test_generate_live.py -v
    需网络 + 有效 Moonshot key。只验链路通，不判文本质量（人审验收另做）。"""
    repo = tmp_path
    shutil.copytree(FIX / "knowledge", repo / "knowledge")
    res = run_generate("How to size a home battery", "guide", chat_fn=None, repo=repo,
                       today="2026-08-16")
    text = Path(res["path"]).read_text(encoding="utf-8")
    assert "## Suggested JSON-LD" in text and "事实核对清单" in text
    assert res["validation"] in ("passed", "flagged")   # flagged 也算链路通
