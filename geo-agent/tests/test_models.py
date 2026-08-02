import hashlib
from geo.shared.models import PromptRow, CitedSource, L2Record, L1Record, dedup_key, prompt_set_version

def test_prompt_row_core_is_bool():
    r = PromptRow(id="C01", category="category", prompt="x", market="EU", intent="c", core=1)
    assert r.core is True

def test_l1_dedup_key_and_version():
    h = prompt_set_version([PromptRow(id="C01", category="c", prompt="x", market="EU", intent="i", core=True)])
    assert h == hashlib.sha1(b"x").hexdigest()[:12]   # 全 prompt 文本拼接的 sha1[:12]
    l1 = L1Record(week=1, model="qwen", prompt_id="C01", run=1, answer="a",
                  l2=L2Record(cited_sources=[], mentioned=False, cited_with_link=False,
                              citation_position=None, sentiment=None, competitors_mentioned=[]),
                  usage={}, elapsed_s=1.0, search_triggered=True, ts_iso="2026-08-02T00:00:00Z",
                  prompt_set_version=h)
    assert dedup_key(l1) == (1, "qwen", "C01", 1)
