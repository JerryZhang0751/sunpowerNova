# tests/test_generate_run.py
import json, shutil, yaml
from pathlib import Path
import pytest
from geo.generate.run import run_generate, run_review, run_mark_published

FIX = Path(__file__).parent / "fixtures" / "generate"

def _mini_repo(tmp_path: Path) -> Path:
    """复制 fixture 的 knowledge+data 到 tmp mini-repo（site/bootstrap 已在 Task 3 测过）。"""
    for sub in ("knowledge", "data"):
        src = FIX / sub
        if src.exists():
            shutil.copytree(src, tmp_path / sub)
    return tmp_path

def _chat_ok(messages, tools=None, timeout=120):
    return json.dumps({
        "frontmatter": {"topic": "battery sizing", "page_type": "guide", "slug": "battery-sizing"},
        "title": "battery sizing",
        "body_md": "# Battery sizing\n\nStart at 5–15 kWh with a 10-year warranty.",
        "json_ld": [{"@context": "https://schema.org", "@type": "Article", "headline": "battery sizing"}],
        "fact_anchors": [
            {"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
            {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}],
    }, ensure_ascii=False)

def test_run_generate_writes_valid_draft(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    p = Path(res["path"])
    assert p == repo / "content" / "drafts" / "battery-sizing.md"
    text = p.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["status"] == "draft" and fm["validation"] == "passed"
    assert fm["playbook_week"] == 1 and fm["brand_version"] == 1 and fm["created"] == "2026-08-16"
    assert "未经研究校准" not in text and "## Suggested JSON-LD" in text
    assert res["validation"] == "passed"

def test_run_generate_requires_playbook(tmp_path):
    repo = _mini_repo(tmp_path)
    (repo / "knowledge" / "playbook.md").unlink()
    with pytest.raises(SystemExit, match="playbook"):
        run_generate("t", chat_fn=_chat_ok, repo=repo)

def test_run_generate_allow_no_playbook_marks_draft(tmp_path):
    repo = _mini_repo(tmp_path)
    (repo / "knowledge" / "playbook.md").unlink()
    res = run_generate("battery sizing", allow_no_playbook=True, chat_fn=_chat_ok,
                       repo=repo, today="2026-08-16")
    text = Path(res["path"]).read_text(encoding="utf-8")
    assert "未经研究校准" in text
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["playbook_week"] is None

def test_run_generate_no_kimi_skeleton(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_generate("battery sizing", kimi=False, repo=repo, today="2026-08-16")
    assert Path(res["path"]).exists() and res["validation"] == "flagged"   # 骨架无 anchors → flagged

def test_run_review_and_publish(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    slug = "battery-sizing"
    out = run_review(slug, "pass", notes="事实核对通过", repo=repo, now="2026-08-16T12:00:00")
    reviews = [json.loads(l) for l in (repo / "content" / "reviews.jsonl").read_text(encoding="utf-8").splitlines()]
    assert reviews[-1] == {"slug": slug, "verdict": "pass", "notes": "事实核对通过",
                           "ts": "2026-08-16T12:00:00", "brand_version": 1, "playbook_week": 1}
    run_mark_published(slug, repo=repo)
    assert (repo / "content" / "published" / f"{slug}.md").exists()
    assert not (repo / "content" / "drafts" / f"{slug}.md").exists()
    fm = yaml.safe_load((repo / "content" / "published" / slug).with_suffix(".md").read_text(encoding="utf-8").split("---")[1])
    assert fm["status"] == "published"

def test_run_review_reject_marks_status(tmp_path):
    repo = _mini_repo(tmp_path)
    run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    run_review("battery-sizing", "reject", repo=repo, now="2026-08-16T12:00:00")
    fm = yaml.safe_load((repo / "content" / "drafts" / "battery-sizing.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["status"] == "rejected"

def test_run_review_unknown_slug_lists_existing(tmp_path, capsys):
    repo = _mini_repo(tmp_path)
    run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    with pytest.raises(SystemExit):
        run_review("nope", "pass", repo=repo, now="2026-08-16T12:00:00")
    assert "battery-sizing" in capsys.readouterr().out

def test_run_mark_published_rejects_rejected_drafts(tmp_path, capsys):
    """Final review finding F2: run_mark_published must NOT publish rejected drafts.
    When status=rejected, should raise SystemExit with honest message and leave draft unchanged.
    Updated for P3 guard semantics - error message in SystemExit exception, not stderr."""
    repo = _mini_repo(tmp_path)
    run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    slug = "battery-sizing"

    # Reject the draft
    run_review(slug, "reject", notes="Factual errors found", repo=repo, now="2026-08-16T12:00:00")

    # Attempt to publish rejected draft - should fail with SystemExit
    with pytest.raises(SystemExit, match="rejected"):
        run_mark_published(slug, repo=repo)

    # Verify draft still exists with rejected status
    draft_path = repo / "content" / "drafts" / f"{slug}.md"
    assert draft_path.exists(), "Draft file should still exist after rejected publish attempt"
    fm = yaml.safe_load(draft_path.read_text(encoding="utf-8").split("---")[1])
    assert fm["status"] == "rejected", "Draft status should remain rejected"

def test_run_suggest_prints_suppression_summary(tmp_path, capsys):
    import shutil
    from pathlib import Path
    fix = Path(__file__).parent / "fixtures" / "generate"
    for src in ("data/analysis/w1/eval_report.json", "data/snapshots/w1/gsc.json"):
        dst = tmp_path / src
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(fix / src, dst)
    pub = tmp_path / "content" / "published"
    pub.mkdir(parents=True)
    (pub / "deep.md").write_text(
        "---\ntopic: Deep-dive article with dates, sources and concrete data points\n"
        "page_type: guide\n---\n", encoding="utf-8")
    from geo.generate.run import run_suggest
    res = run_suggest(1, repo=tmp_path)
    out_text = capsys.readouterr().out
    assert len(res["suppressed"]) == 1
    assert "已抑制 1 条" in out_text and "content_eeat" in out_text

def test_run_suggest_all_suppressed_no_misleading_empty_msg(tmp_path, capsys):
    """全部建议被精确去重抑制时,不打印误导性的"无建议——检查数据源"
    (真实成因 = 全被抑制,抑制行已给足信息)。"""
    import shutil
    fix = Path(__file__).parent / "fixtures" / "generate"
    er_dst = tmp_path / "data" / "analysis" / "w1" / "eval_report.json"
    er_dst.parent.mkdir(parents=True)
    rep = json.loads((fix / "data/analysis/w1/eval_report.json").read_text(encoding="utf-8"))
    for sec in ("self_geo", "self_seo"):
        for d in rep.get(sec, {}).get("dims", []):
            d["score"] = 60.0                                  # 无弱维度 → 无 eval_gap 建议
    er_dst.write_text(json.dumps(rep), encoding="utf-8")
    gsc_dst = tmp_path / "data" / "snapshots" / "w1" / "gsc.json"
    gsc_dst.parent.mkdir(parents=True)
    shutil.copy(fix / "data/snapshots/w1/gsc.json", gsc_dst)
    pub = tmp_path / "content" / "published"
    pub.mkdir(parents=True)
    for name, topic in [("a.md", "lifepo4 battery"), ("b.md", "photovoltaic self consumption"),
                        ("c.md", "hestia solar")]:              # GSC 3 条全发布过
        (pub / name).write_text(f"---\ntopic: {topic}\npage_type: guide\n---\n", encoding="utf-8")
    from geo.generate.run import run_suggest
    res = run_suggest(1, repo=tmp_path)
    out_text = capsys.readouterr().out
    assert res["suggestions"] == [] and len(res["suppressed"]) == 3
    assert "已抑制 3 条" in out_text
    assert "无建议" not in out_text
