# tests/test_generate_hardening.py
import json, yaml, pytest
from geo.generate.run import run_mark_published

def _mk_draft(repo, slug, validation="passed"):
    d = repo / "content" / "drafts"; d.mkdir(parents=True, exist_ok=True)
    fm = {"topic": "t", "page_type": "guide", "slug": slug, "created": "2026-08-19",
          "playbook_week": 1, "brand_version": 1, "status": "draft", "validation": validation}
    (d / f"{slug}.md").write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\nbody",
                                  encoding="utf-8")

def _review(repo, slug, verdict, ts):
    rj = repo / "content" / "reviews.jsonl"; rj.parent.mkdir(parents=True, exist_ok=True)
    with rj.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"slug": slug, "verdict": verdict, "notes": "", "ts": ts,
                            "brand_version": 1, "playbook_week": 1}) + "\n")

def test_unreviewed_draft_rejected(tmp_path):
    _mk_draft(tmp_path, "x")
    with pytest.raises(SystemExit):
        run_mark_published("x", repo=tmp_path)
    assert (tmp_path / "content" / "drafts" / "x.md").exists()      # 草稿原样保留

def test_latest_reject_wins_even_after_pass(tmp_path):
    _mk_draft(tmp_path, "x"); _review(tmp_path, "x", "pass", "2026-08-19T10:00:00")
    _review(tmp_path, "x", "reject", "2026-08-19T11:00:00")
    with pytest.raises(SystemExit):
        run_mark_published("x", repo=tmp_path)

def test_pass_publishes_with_stamps_and_targets_warning(tmp_path, capsys):
    _mk_draft(tmp_path, "x"); _review(tmp_path, "x", "pass", "2026-08-19T10:00:00")
    res = run_mark_published("x", repo=tmp_path,
                             url="https://sunhestia.com/news/new-guide/", now="2026-08-19T12:00:00")
    pub = (tmp_path / "content" / "published" / "x.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(pub.split("---")[1])
    assert fm["status"] == "published"
    assert fm["published_at"] == "2026-08-19T12:00:00"
    assert fm["published_url"] == "https://sunhestia.com/news/new-guide/"
    out = capsys.readouterr().out
    assert "/news/new-guide" in out and "targets.yaml" in out    # 不在 pages 清单 → 提示待加行

def test_flagged_needs_override_with_reason(tmp_path):
    _mk_draft(tmp_path, "x", validation="flagged"); _review(tmp_path, "x", "pass", "2026-08-19T10:00:00")
    with pytest.raises(SystemExit):
        run_mark_published("x", repo=tmp_path)
    run_mark_published("x", repo=tmp_path, override=True, reason="人工核对数字无误")   # ok
    fm = yaml.safe_load((tmp_path / "content" / "published" / "x.md").read_text(encoding="utf-8").split("---")[1])
    assert fm.get("override_reason") == "人工核对数字无误"
