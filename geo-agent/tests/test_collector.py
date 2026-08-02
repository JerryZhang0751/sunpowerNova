import json
from unittest.mock import patch
from geo.collect.collector import run_collection
from geo.shared.storage import l1_path

def _fake_collect(prompt, **k):
    return {"answer":"A SunHestia","search_results":[{"url":"https://e.com","title":""}],
            "usage":{},"elapsed_s":0.1,"raw":{}}

def test_run_writes_l1_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setenv("GEO_REPO", str(tmp_path))
    with patch("geo.collect.collector.collect_qwen", _fake_collect), \
         patch("geo.collect.collector.collect_doubao", _fake_collect), \
         patch("geo.collect.collector.collect_zhipu", _fake_collect):
        recs1 = run_collection(week=99, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
        p = l1_path(99,"qwen","C01",1)
        assert p.exists() and json.loads(p.read_text())["model"]=="qwen"
        # 续跑：已存在不重采
        with patch("geo.collect.collector.collect_qwen", side_effect=AssertionError("不应重采")):
            recs2 = run_collection(week=99, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
        assert len(recs2)==1
