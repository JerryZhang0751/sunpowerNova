# tests/test_generate_topics.py
import json, shutil
from pathlib import Path
from geo.generate.topics import suggest_topics

FIX = Path(__file__).parent / "fixtures" / "generate"

def test_suggest_topics_eval_gaps_first():
    out, missing, _ = suggest_topics(1, repo=FIX)
    assert missing == []
    gaps = [s for s in out if s["source"] == "eval_gap"]
    # score<50 的三个维度：content_eeat(1.4) < eeat(25) < citability(32)，升序
    assert [g["detail"] for g in gaps] == ["content_eeat=1.4", "eeat=25.0", "citability=32.0"]
    assert gaps[0]["page_type"] in ("faq", "spec", "comparison", "guide")
    assert all(g["topic"] for g in gaps)

def test_suggest_topics_gsc_by_impressions():
    out, _, _s = suggest_topics(1, repo=FIX)
    gsc = [s for s in out if s["source"] == "gsc"]
    assert [s["topic"] for s in gsc] == ["lifepo4 battery", "photovoltaic self consumption", "hestia solar"]
    assert gsc[0]["detail"] == "impressions=9"

def test_suggest_topics_missing_sources_reported(tmp_path):
    out, missing, _ = suggest_topics(2, repo=tmp_path)   # 空 repo
    assert out == []
    assert len(missing) == 2 and any("eval_report" in m for m in missing)

def _repo_with_content(tmp_path, files):
    """拷 FIX 的 w1 数据源 + 落 published/drafts 文件;files = [(sub, name, fm_text)]"""
    import shutil
    for src in ("data/analysis/w1/eval_report.json", "data/snapshots/w1/gsc.json"):
        dst = tmp_path / src
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIX / src, dst)
    for sub, name, fm in files:
        d = tmp_path / "content" / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(f"---\n{fm}\n---\n\n# body\n", encoding="utf-8")
    return tmp_path

_EVAL_GAP_TOPIC = "Deep-dive article with dates, sources and concrete data points"   # content_eeat 模板文案

def test_suggest_suppresses_published_exact_match(tmp_path):
    repo = _repo_with_content(tmp_path, [
        ("published", "deep.md", f"topic: {_EVAL_GAP_TOPIC}\npage_type: guide"),
    ])
    out, missing, suppressed = suggest_topics(1, repo=repo)
    assert missing == []
    assert _EVAL_GAP_TOPIC not in [s["topic"] for s in out]
    assert any(s["topic"].startswith("About-the-team") for s in out)     # 其余照常通过
    assert len(suppressed) == 1 and suppressed[0]["source"] == "eval_gap"

def test_suggest_suppresses_drafts_too(tmp_path):
    repo = _repo_with_content(tmp_path, [
        ("drafts", "wip.md", "topic: lifepo4 battery\npage_type: guide"),   # GSC 榜首查询
    ])
    out, _, suppressed = suggest_topics(1, repo=repo)
    assert "lifepo4 battery" not in [s["topic"] for s in out]
    assert any(s["source"] == "gsc" for s in suppressed)

def test_suggest_skips_corrupt_frontmatter(tmp_path):
    for src in ("data/analysis/w1/eval_report.json", "data/snapshots/w1/gsc.json"):
        dst = tmp_path / src
        dst.parent.mkdir(parents=True, exist_ok=True)
        import shutil; shutil.copy(FIX / src, dst)
    pub = tmp_path / "content" / "published"
    pub.mkdir(parents=True)
    (pub / "garbage.md").write_text("no frontmatter here\n", encoding="utf-8")      # 无 --- 块
    (pub / "broken-yaml.md").write_text("---\n: : not yaml [\n---\n", encoding="utf-8")  # yaml 解析炸
    (pub / "ok.md").write_text(
        "---\ntopic: 'About-the-team page: who designs and installs, credentials, process'\n"
        "page_type: guide\n---\n", encoding="utf-8")
    out, missing, suppressed = suggest_topics(1, repo=tmp_path)
    assert missing == [] and len(suppressed) == 1                       # 只有 ok.md 生效,坏文件不炸
    assert "About-the-team page: who designs and installs, credentials, process" \
        not in [s["topic"] for s in out]

def test_suggest_unrelated_pass_through(tmp_path):
    repo = _repo_with_content(tmp_path, [
        ("published", "other.md", "topic: Something entirely different\npage_type: spec"),
    ])
    out, _, suppressed = suggest_topics(1, repo=repo)
    assert suppressed == [] and len(out) == 6                            # 3 eval_gap + 3 gsc 全通过
