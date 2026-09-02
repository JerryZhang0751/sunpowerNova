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

def test_run_generate_flags_near_duplicate_draft(tmp_path):
    """codex w3 修改五: Kimi 改写主题后与已发布页近重复(Jaccard≥0.8) → 草稿
    照常写盘但 validation=flagged,issue 写明 near_duplicate:<已发布 slug>;
    不自动删除,人工经既有 review/override 流程裁决。"""
    repo = _mini_repo(tmp_path)
    pub = repo / "content" / "published"
    pub.mkdir(parents=True)
    (pub / "solar-only-vs-solar-plus-battery-storage.md").write_text(
        "---\ntopic: Solar only vs solar plus battery storage\npage_type: comparison\n"
        "slug: solar-only-vs-solar-plus-battery-storage\n---\n\n# body\n", encoding="utf-8")

    def chat_dup(messages, tools=None, timeout=120):
        return json.dumps({
            "frontmatter": {"topic": "Solar only vs solar plus battery",
                            "page_type": "comparison",
                            "slug": "solar-only-vs-solar-plus-battery"},
            "title": "Solar only vs solar plus battery",
            "body_md": "# Solar only vs solar plus battery\n\nStart at 5–15 kWh with a 10-year warranty.",
            "json_ld": [{"@context": "https://schema.org", "@type": "Article",
                         "headline": "Solar only vs solar plus battery"}],
            "fact_anchors": [
                {"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
                {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}],
        }, ensure_ascii=False)

    res = run_generate("Solar only vs solar plus battery", page_type="comparison",
                       chat_fn=chat_dup, repo=repo, today="2026-09-02")
    assert res["validation"] == "flagged"
    assert any("near_duplicate:solar-only-vs-solar-plus-battery-storage" in i
               for i in res["issues"])
    assert Path(res["path"]).exists(), "近重复草稿必须写盘(不自动删除)"

def test_run_generate_normalizes_article_url_to_news_path(tmp_path):
    """codex w3 修改六: 生成器在结构化 json_ld 写盘前把 Article.mainEntityOfPage
    规范化为 /news/<slug>/ 最终 URL(禁止生成后用正则改 JSON code fence)——
    w2/w3 连续两篇草稿缺 /news/ 前缀的生成器已知偏差从此源头消除。"""
    repo = _mini_repo(tmp_path)
    res = run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-09-02")
    text = Path(res["path"]).read_text(encoding="utf-8")
    assert '"mainEntityOfPage": "https://sunhestia.com/news/battery-sizing/"' in text
    assert res["validation"] == "passed"

def test_run_mark_published_rejects_url_mismatch_then_archives_consistent(tmp_path):
    """codex w3 修改六: --url 与草稿 Article URL 不一致 → 失败关闭保留原草稿、
    提示先修正;一致 → 归档 Markdown 的 JSON-LD 与 published_url 完全相同。"""
    repo = _mini_repo(tmp_path)
    run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-09-02")
    run_review("battery-sizing", "pass", repo=repo, now="2026-09-02T10:00:00")
    with pytest.raises(SystemExit, match="mainEntityOfPage"):
        run_mark_published("battery-sizing", url="https://sunhestia.com/news/somewhere-else/",
                           repo=repo)
    assert (repo / "content" / "drafts" / "battery-sizing.md").exists()   # 草稿保留
    run_mark_published("battery-sizing", url="https://sunhestia.com/news/battery-sizing/",
                       repo=repo)
    pub = (repo / "content" / "published" / "battery-sizing.md").read_text(encoding="utf-8")
    assert '"mainEntityOfPage": "https://sunhestia.com/news/battery-sizing/"' in pub
    fm = yaml.safe_load(pub.split("---")[1])
    assert fm["published_url"] == "https://sunhestia.com/news/battery-sizing/"

def test_generate_refuses_published_slug(tmp_path):
    """backlog 2026-09-02 守卫补强: 同 slug 已有发布文 → 拒写影子草稿(w3 根因之一
    是 Kimi 改写主题后与已发布页同 slug);--allow-published-overwrite 显式放行。"""
    repo = _mini_repo(tmp_path)
    pub = repo / "content" / "published"
    pub.mkdir(parents=True)
    (pub / "battery-sizing.md").write_text(
        "---\ntopic: battery sizing\npage_type: guide\nslug: battery-sizing\n---\n\n# 已发布\n",
        encoding="utf-8")
    with pytest.raises(SystemExit, match="已有发布文"):
        run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-09-02")
    assert not (repo / "content" / "drafts" / "battery-sizing.md").exists(), \
        "拒绝时不得落盘影子草稿"
    res = run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-09-02",
                       allow_published_overwrite=True)
    assert Path(res["path"]).exists()

def test_mark_published_refuses_existing_published(tmp_path):
    """backlog 2026-09-02 守卫补强: published/<slug>.md 已存在时归档将覆写已发布文
    → SystemExit 拒绝;--override --reason 显式放行。"""
    repo = _mini_repo(tmp_path)
    run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-09-02")
    run_review("battery-sizing", "pass", repo=repo, now="2026-09-02T10:00:00")
    pub = repo / "content" / "published"
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "battery-sizing.md").write_text("---\ntopic: battery sizing\n---\n\n# 旧发布文\n",
                                           encoding="utf-8")
    with pytest.raises(SystemExit, match="已存在"):
        run_mark_published("battery-sizing", repo=repo)
    # 拒绝时三方均不改动: 草稿还在、旧发布文原样
    assert (repo / "content" / "drafts" / "battery-sizing.md").exists()
    assert "旧发布文" in (pub / "battery-sizing.md").read_text(encoding="utf-8")
    run_mark_published("battery-sizing", override=True, reason="人工确认重发布",
                       repo=repo, now="2026-09-02T11:00:00")
    fm = yaml.safe_load((pub / "battery-sizing.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["status"] == "published" and fm["override_reason"] == "人工确认重发布"
    assert not (repo / "content" / "drafts" / "battery-sizing.md").exists()

# ---- 回归锁(2026-09-02 审核缺口 A5): --suggest 的 901 拦截必须接到 CLI 入口 ----
def test_cli_suggest_rejects_test_band_week_end_to_end(monkeypatch):
    """--suggest --week 901 走 main() 全链路:入口校验(validate_production_week)必须
    在 run_suggest 之前拦截 → ValueError;run_suggest 若被触达即测试失败
    (防测试带周号误触真实 API)。库函数级门另见 tests/test_weeks.py。"""
    import sys
    import geo.generate.run as GR

    def boom(*a, **k):
        raise AssertionError("run_suggest 不得被测试保留带周号触达")
    monkeypatch.setattr(GR, "run_suggest", boom)
    monkeypatch.setattr(sys, "argv", ["geo.generate.run", "--suggest", "--week", "901"])
    with pytest.raises(ValueError, match="测试保留带"):
        GR.main()


def test_cli_suggest_passes_production_week_to_run_suggest(monkeypatch):
    """对照组: --suggest --week 3 过校验且 week=3 原样传入 run_suggest
    (patch 捕获,禁真实 API)。"""
    import sys
    import geo.generate.run as GR
    seen = {}

    def fake_suggest(week, **k):
        seen["week"] = week
        return {"suggestions": [], "missing": [], "suppressed": []}
    monkeypatch.setattr(GR, "run_suggest", fake_suggest)
    monkeypatch.setattr(sys, "argv", ["geo.generate.run", "--suggest", "--week", "3"])
    GR.main()
    assert seen["week"] == 3
