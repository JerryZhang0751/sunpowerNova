import json
def test_iter_l1_skips_corrupt_and_sorted(tmp_path):
    from geo.shared.l1 import iter_l1
    from geo.shared.models import L1Record
    d = tmp_path / "data" / "raw" / "w901" / "qwen" / "C01"; d.mkdir(parents=True)
    good = L1Record(week=901, model="qwen", prompt_id="C01", run=1, answer="a",
                    l2={"cited_sources": [], "mentioned": False}, ts_iso="t",
                    prompt_set_version="v")
    (d / "r2.json").write_text(json.dumps({**good.model_dump(), "run": 2}), encoding="utf-8")
    (d / "r1.json").write_text("{broken", encoding="utf-8")            # 坏 JSON
    (d / "r0.json").write_text(json.dumps({"no": "schema"}), encoding="utf-8")  # 坏 schema
    recs = list(iter_l1(901, repo=tmp_path))
    assert [r.run for r in recs] == [2]      # 坏行跳过、好行保留
def test_iter_l1_missing_dir_empty(tmp_path):
    from geo.shared.l1 import iter_l1
    assert list(iter_l1(999, repo=tmp_path)) == []

def test_iter_l1_corrupt_lines_emit_warning(tmp_path, caplog):
    """回归锁(2026-09-02 审核缺口 A4): 坏行跳过必须可见——每条坏行一条 WARNING,
    消息含 "L1 残缺跳过"+文件名;好行照常产出不受影响。"""
    import json, logging
    from geo.shared.l1 import iter_l1
    from geo.shared.models import L1Record
    d = tmp_path / "data" / "raw" / "w901" / "qwen" / "C01"; d.mkdir(parents=True)
    good = L1Record(week=901, model="qwen", prompt_id="C01", run=1, answer="a",
                    l2={"cited_sources": [], "mentioned": False}, ts_iso="t",
                    prompt_set_version="v")
    (d / "r2.json").write_text(json.dumps({**good.model_dump(), "run": 2}), encoding="utf-8")
    (d / "r1.json").write_text("{broken", encoding="utf-8")            # 坏 JSON
    (d / "r0.json").write_text(json.dumps({"no": "schema"}), encoding="utf-8")  # 坏 schema
    with caplog.at_level(logging.WARNING):
        recs = list(iter_l1(901, repo=tmp_path))
    assert [r.run for r in recs] == [2]                                # 好行不受影响
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) == 2, "坏 JSON 与坏 schema 各应产出一条 WARNING(静默降级不可接受)"
    joined = " ".join(r.getMessage() for r in warns)
    assert "L1 残缺跳过" in joined
    assert "r1.json" in joined and "r0.json" in joined                 # 定位到具体坏行
    assert "w901" in joined                                            # 定位到具体周
