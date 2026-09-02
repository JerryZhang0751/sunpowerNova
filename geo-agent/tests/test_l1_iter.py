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
