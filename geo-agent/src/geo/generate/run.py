# src/geo/generate/run.py
from __future__ import annotations
import json, logging, sys
from datetime import date, datetime
from pathlib import Path
import yaml
from geo.shared.config import REPO, settings
from geo.shared.weeks import validate_production_week
from geo.generate.brand import load_brand, slugify, run_bootstrap
from geo.generate.topics import suggest_topics, near_duplicate_issues, _published_index
from geo.generate.kimi import playbook_digest, generate_draft, skeleton_draft
from geo.generate.validate import validate_draft

log = logging.getLogger("generate.run")

def _fm_update(text: str, updates: dict) -> str:
    parts = text.split("---")
    fm = yaml.safe_load(parts[1])
    fm.update(updates)
    parts[1] = "\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
    return "---".join(parts)

def _latest_review(repo: Path, slug: str) -> dict | None:
    rj = repo / "content" / "reviews.jsonl"
    if not rj.exists():
        return None
    latest = None
    for line in rj.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("slug") == slug:
            latest = rec                     # append-only,最后一条 = 最新
    return latest

def _site_url() -> str:
    return ((settings.targets.get("site") or {}).get("url") or "https://sunhestia.com").rstrip("/")


def _article_urls(text: str) -> tuple[list, bool]:
    """从草稿 Markdown 的 ```json fence 提取 Article.mainEntityOfPage
    (字符串或 WebPage.@id;缺失记 None)。返回 (urls, has_article);
    无 Article/坏 JSON → has_article=False(URL 一致性校验不适用)。"""
    import re as _re
    urls: list = []
    has = False
    for m in _re.finditer(r"```json\n(.*?)```", text, _re.S):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get("@type") == "Article":
            has = True
            mep = obj.get("mainEntityOfPage")
            if isinstance(mep, str):
                urls.append(mep)
            elif isinstance(mep, dict):
                urls.append(mep.get("@id"))
            else:
                urls.append(None)
    return urls, has


def run_generate(topic: str, page_type: str = "guide", week: int = 1,
                 allow_no_playbook: bool = False, kimi: bool = True,
                 chat_fn=None, repo: Path = REPO, today: str = None,
                 allow_published_overwrite: bool = False) -> dict:
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
    # codex w3 修改六(2026-09-02):默认 canonical = {site}/news/{slug}/,写盘前在
    # 结构化 json_ld 上规范化(禁止生成后再用正则改 JSON code fence)——w2/w3
    # 连续两篇草稿缺 /news/ 前缀的生成器偏差从源头消除。
    expected_url = f"{_site_url()}/news/{fm['slug']}/"
    for obj in draft.get("json_ld", []) or []:
        if isinstance(obj, dict) and obj.get("@type") == "Article":
            obj["mainEntityOfPage"] = expected_url
    result = validate_draft({**draft, "frontmatter": {**fm}}, brand, expected_url=expected_url)
    # codex w3 修改五(2026-09-02):Kimi 改写主题后可能与已发布页近同题(w3 根因)
    # → 近重复只做阻断提示(草稿照常写盘、validation=flagged),人工 override 裁决。
    issues = list(result.issues) + near_duplicate_issues(fm["slug"], _published_index(repo))
    fm["validation"] = "passed" if not issues else "flagged"
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
    # backlog 2026-09-02 守卫补强: 同 slug 已有发布文 → 拒写影子草稿(落盘前拦截,
    # 拒绝路径零副作用)。Kimi 改写主题后可能与已发布页同 slug(w3 近重复同根因);
    # 确认换题,或 --allow-published-overwrite 显式放行。
    pub_existing = repo / "content" / "published" / f"{fm['slug']}.md"
    if pub_existing.exists() and not allow_published_overwrite:
        raise SystemExit(f"slug {fm['slug']!r} 已有发布文 {pub_existing}——拒绝生成影子草稿"
                         "(确认换题,或 --allow-published-overwrite 显式放行)")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{fm['slug']}.md"
    out.write_text("\n".join(blocks), encoding="utf-8")
    summary = {"path": str(out), "validation": fm["validation"],
               "issues": issues, "playbook_week": digest["week"]}
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

def run_mark_published(slug: str, *, url: str | None = None, override: bool = False,
                       reason: str = "", repo: Path = REPO, now: str = None) -> dict:
    repo = Path(repo)
    draft = repo / "content" / "drafts" / f"{slug}.md"
    if not draft.exists():
        raise SystemExit(f"草稿不存在: {slug}")
    text = draft.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---")[1])
    if fm.get("status") == "rejected":
        raise SystemExit(f"草稿 {slug} 状态为 rejected,不予归档发布")
    review = _latest_review(repo, slug)
    if review is None or review.get("verdict") not in ("pass", "minor"):
        raise SystemExit(
            f"草稿 {slug} 缺少 pass/minor 人审记录(最新 verdict="
            f"{(review or {}).get('verdict', '无')})——先 --review 再归档")
    if fm.get("validation") == "flagged" and not (override and reason):
        raise SystemExit(f"草稿 {slug} validation=flagged:需 --override 且 --reason 显式放行")
    # codex w3 修改六(2026-09-02):归档前核对 Article canonical 与最终 URL 一致——
    # 不一致失败关闭、保留原草稿提示先修正(发布函数不用正则改写归档内容)。
    # 不传 url 时以 /news/{slug}/ 默认值为权威。
    final_url = url or f"{_site_url()}/news/{slug}/"
    urls, has_article = _article_urls(text)
    if has_article:
        bad = [u for u in urls if u != final_url]
        if bad:
            raise SystemExit(
                f"草稿 {slug} 的 Article mainEntityOfPage {bad} 与最终 URL {final_url} "
                f"不一致——先修正草稿 JSON-LD 再归档(发布函数不改写内容)")
    updates = {"status": "published",
               "published_at": now or datetime.now().isoformat(timespec="seconds")}
    if url:
        updates["published_url"] = url
    if override:
        updates["override_reason"] = reason
    pub_dir = repo / "content" / "published"
    pub_dir.mkdir(parents=True, exist_ok=True)
    # backlog 2026-09-02 守卫补强: published/<slug>.md 已存在 → 归档会覆写已发布文,
    # 默认拒绝;确需覆写用 --override --reason 显式放行(写盘前拦截)。
    pub_file = pub_dir / f"{slug}.md"
    if pub_file.exists() and not override:
        raise SystemExit(f"{pub_file} 已存在——归档将覆写已发布文;确需覆写用 --override --reason")
    pub_file.write_text(_fm_update(text, updates), encoding="utf-8")
    if url:
        from urllib.parse import urlparse
        path = urlparse(url).path.rstrip("/")
        pages = (settings.targets.get("site", {}) or {}).get("pages", [])
        if path and path not in pages:
            print(f"⚠️ {path} 不在 targets.yaml site.pages —— 请手动追加,否则静态自审不覆盖此页")
    draft.unlink()
    log.info("归档发布: %s%s", slug, f"(override: {reason})" if override else "")
    return {"slug": slug, "path": str(pub_dir / f"{slug}.md")}

def run_suggest(week: int, *, repo: Path = REPO) -> dict:
    out, missing, suppressed = suggest_topics(week, repo=repo)
    for m in missing:
        print(f"⚠️ 缺失数据源: {m}")
    for i, s in enumerate(out, 1):
        print(f"{i}. [{s['source']}: {s['detail']}] {s['topic']}  (page_type={s['page_type']})")
    if suppressed:
        dims = sorted({s["detail"].split("=")[0] for s in suppressed if s["source"] == "eval_gap"})
        note = f"（覆盖弱维度: {', '.join(dims)}）" if dims else ""
        print(f"ℹ️ 已抑制 {len(suppressed)} 条与已发布/草稿重复的建议{note}")
    if not out and not suppressed:
        print("（无建议——检查 eval_report/gsc 数据源）")
    return {"suggestions": out, "missing": missing, "suppressed": suppressed}

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
    ap.add_argument("--url")
    ap.add_argument("--override", action="store_true")
    ap.add_argument("--reason", default="")
    ap.add_argument("--allow-published-overwrite", action="store_true",
                    help="同 slug 已有发布文时仍生成/归档(显式放行影子草稿/覆写)")
    ap.add_argument("--bootstrap-brand", action="store_true")
    a = ap.parse_args()
    if a.suggest:
        run_suggest(validate_production_week(a.week))
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
        print(run_mark_published(a.mark_published, url=a.url, override=a.override, reason=a.reason))
    elif a.topic:
        res = run_generate(a.topic, a.page_type, validate_production_week(a.week),
                           allow_no_playbook=a.allow_no_playbook, kimi=not a.no_kimi,
                           allow_published_overwrite=a.allow_published_overwrite)
        print(res)
        if res["validation"] == "flagged":
            sys.exit(2)
    else:
        ap.error("需要 --suggest / --topic / --review / --mark-published / --bootstrap-brand 之一")

if __name__ == "__main__":
    main()
