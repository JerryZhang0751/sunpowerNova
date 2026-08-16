# src/geo/generate/run.py
from __future__ import annotations
import json, logging, sys
from datetime import date, datetime
from pathlib import Path
import yaml
from geo.shared.config import REPO
from geo.generate.brand import load_brand, slugify, run_bootstrap
from geo.generate.topics import suggest_topics
from geo.generate.kimi import playbook_digest, generate_draft, skeleton_draft
from geo.generate.validate import validate_draft

log = logging.getLogger("generate.run")

def _fm_update(text: str, updates: dict) -> str:
    parts = text.split("---")
    fm = yaml.safe_load(parts[1])
    fm.update(updates)
    parts[1] = "\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
    return "---".join(parts)

def run_generate(topic: str, page_type: str = "guide", week: int = 1,
                 allow_no_playbook: bool = False, kimi: bool = True,
                 chat_fn=None, repo: Path = REPO, today: str = None) -> dict:
    repo = Path(repo)
    try:
        brand = load_brand(repo / "knowledge" / "brand.yaml")
    except Exception as e:
        raise SystemExit(f"brand.yaml 加载失败: {e}")
    playbook_path = repo / "knowledge" / "playbook.md"
    if not playbook_path.exists() and not allow_no_playbook:
        raise SystemExit("playbook.md 不存在：先运行 python3.11 -m geo.research.run --week "
                         f"{week}（或显式 --allow-no-playbook 降级）")
    digest = playbook_digest(playbook_path.read_text(encoding="utf-8")) if playbook_path.exists() \
        else {"week": None, "formats": [], "templates_note": "playbook 缺失，通用 GEO 实践"}
    if kimi:
        draft = generate_draft(topic, page_type, brand, digest, chat_fn=chat_fn)
    else:
        draft = skeleton_draft(topic, page_type, brand)
    fm = {"topic": topic, "page_type": page_type,
          "slug": draft["frontmatter"].get("slug") or slugify(topic),
          "created": today or date.today().isoformat(),
          "playbook_week": digest["week"], "brand_version": brand["version"],
          "status": "draft", "validation": "pending"}
    result = validate_draft({**draft, "frontmatter": {**fm}}, brand)
    fm["validation"] = "passed" if result.ok else "flagged"
    blocks = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    if digest["week"] is None:
        blocks.append("> ⚠️ 未经研究校准（--allow-no-playbook）：本草稿未使用 playbook 被引特征。")
        blocks.append("")
    blocks.append(draft["body_md"].strip() + "\n")
    blocks.append("## Suggested JSON-LD\n")
    for obj in draft.get("json_ld", []) or []:
        blocks.append("```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```\n")
    blocks.append("<!-- AUTO-GENERATED 事实核对清单（校验器产出，人审加速器）\n"
                  + result.appendix_md + "\n-->")
    out_dir = repo / "content" / "drafts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{fm['slug']}.md"
    out.write_text("\n".join(blocks), encoding="utf-8")
    summary = {"path": str(out), "validation": fm["validation"],
               "issues": result.issues, "playbook_week": digest["week"]}
    log.info("draft 写入 %s validation=%s issues=%d", out, fm["validation"], len(result.issues))
    return summary

def run_review(slug: str, verdict: str, notes: str = "", *, repo: Path = REPO, now: str = None) -> dict:
    repo = Path(repo)
    draft = repo / "content" / "drafts" / f"{slug}.md"
    if not draft.exists():
        existing = [p.stem for p in (repo / "content" / "drafts").glob("*.md")] \
            if (repo / "content" / "drafts").exists() else []
        print(f"草稿不存在: {slug}；现有: {existing}")
        raise SystemExit(1)
    text = draft.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---")[1])
    if verdict not in ("pass", "minor", "reject"):
        raise SystemExit(f"verdict 非法: {verdict}（pass|minor|reject）")
    if verdict == "reject":
        draft.write_text(_fm_update(text, {"status": "rejected"}), encoding="utf-8")
    rec = {"slug": slug, "verdict": verdict, "notes": notes,
           "ts": now or datetime.now().isoformat(timespec="seconds"),
           "brand_version": fm.get("brand_version"), "playbook_week": fm.get("playbook_week")}
    reviews = repo / "content" / "reviews.jsonl"
    reviews.parent.mkdir(parents=True, exist_ok=True)
    with reviews.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log.info("review 记录: %s", rec)
    return rec

def run_mark_published(slug: str, *, repo: Path = REPO) -> dict:
    repo = Path(repo)
    draft = repo / "content" / "drafts" / f"{slug}.md"
    if not draft.exists():
        raise SystemExit(f"草稿不存在: {slug}")
    text = draft.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---")[1])
    if fm.get("status") == "rejected":
        import sys
        print(f"草稿 {slug} 状态为 rejected，不予归档发布（人审三档见 content/reviews.jsonl）", file=sys.stderr)
        raise SystemExit(1)
    pub_dir = repo / "content" / "published"
    pub_dir.mkdir(parents=True, exist_ok=True)
    (pub_dir / f"{slug}.md").write_text(_fm_update(text, {"status": "published"}), encoding="utf-8")
    draft.unlink()
    log.info("归档发布: %s", slug)
    return {"slug": slug, "path": str(pub_dir / f"{slug}.md")}

def run_suggest(week: int, *, repo: Path = REPO) -> dict:
    out, missing = suggest_topics(week, repo=repo)
    for m in missing:
        print(f"⚠️ 缺失数据源: {m}")
    for i, s in enumerate(out, 1):
        print(f"{i}. [{s['source']}: {s['detail']}] {s['topic']}  (page_type={s['page_type']})")
    if not out:
        print("（无建议——检查 eval_report/gsc 数据源）")
    return {"suggestions": out, "missing": missing}

def main() -> None:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="geo.generate.run", description="P2 生成 agent CLI")
    ap.add_argument("--week", type=int, default=1)
    ap.add_argument("--topic")
    ap.add_argument("--page-type", default="guide", choices=("faq", "spec", "comparison", "guide"))
    ap.add_argument("--suggest", action="store_true")
    ap.add_argument("--allow-no-playbook", action="store_true")
    ap.add_argument("--no-kimi", action="store_true")
    ap.add_argument("--review")
    ap.add_argument("--verdict", choices=("pass", "minor", "reject"))
    ap.add_argument("--notes", default="")
    ap.add_argument("--mark-published")
    ap.add_argument("--bootstrap-brand", action="store_true")
    a = ap.parse_args()
    if a.suggest:
        run_suggest(a.week)
    elif a.bootstrap_brand:
        res = run_bootstrap()
        print(res)
        if res["violations"]:
            sys.exit(1)
    elif a.review:
        if not a.verdict:
            ap.error("--review 需要 --verdict pass|minor|reject")
        run_review(a.review, a.verdict, a.notes)
    elif a.mark_published:
        print(run_mark_published(a.mark_published))
    elif a.topic:
        res = run_generate(a.topic, a.page_type, a.week,
                           allow_no_playbook=a.allow_no_playbook, kimi=not a.no_kimi)
        print(res)
        if res["validation"] == "flagged":
            sys.exit(2)
    else:
        ap.error("需要 --suggest / --topic / --review / --mark-published / --bootstrap-brand 之一")

if __name__ == "__main__":
    main()
