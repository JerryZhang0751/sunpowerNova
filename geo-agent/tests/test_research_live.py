# tests/test_research_live.py
import pytest
from geo.research.run import run_research

@pytest.mark.live
def test_live_research_w1_real_kemi():
    """Real w1 corpus + real Kimi K3. Run manually: python3.11 -m pytest -m live tests/test_research_live.py -v
    Requires network + Clash 7890 + valid Moonshot key. Not a text-quality assertion (human-audit)."""
    res = run_research(1, kimi_enabled=True)
    assert res["playbook"].endswith("playbook.md")
    # human audits playbook.md + platform-profiles.md for factual accuracy after this passes
