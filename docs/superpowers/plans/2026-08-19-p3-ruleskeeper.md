# P3 RulesKeeper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让规则文件真正驱动评分(信号注册表),实现确定性规则迭代环 RulesKeeper(条目 draft→active 证据门槛 + 权重证据强度公式 + 版本归档/重算/回滚),并把 research/generate/rules 接进 LangGraph 全链 DAG。

**Architecture:** 先做 P2 尾巴加固(Task 0:mark-published 守卫/发布 stamp/竞品 static={});再把两个 scorer 的硬编码公式逐字搬进信号注册表、成员关系改由 YAML `signals:` 驱动(v1 语义零漂移,黄金锁死;已知死路径 list_count 保持,spec §1 澄清 2);再建 `geo/rules/` 迭代器(evidence→gate→weights→keeper),证据**唯一 URL 口径**(features.py 扩 unique 桶)、权重带 2 周同向持续性,升版时归档旧规则到 `rules/history/`(manifest 绑 code_commit)、回滚产新单调版本;最后 graph.py 增 research/generate/rules 三节点闭环(**assess 提前于 research/generate**)+ `--force-new-run` + reporter 渲染 §5 规则迭代摘要 + research 反哺 playbook。

> **v1.1 修订(2026-08-19,外部评审 8 条逐条核实,处置见 spec §10)**:证据唯一 URL 计数(Task 5/6;w1 BreadcrumbList 7/34=20.6%、平台 3 家);权重 2 周同向持续性(Task 7/8;w1 不调权);DAG 重排 + --force-new-run(Task 12);rollback 新单调版本 + manifest(Task 8/9);Task 0 新增(P2 尾巴加固)。

**Tech Stack:** Python 3.11(系统解释器,非 .venv)、pytest、PyYAML、LangGraph(现有 DAG)。

**Spec:** `docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md`(已批准)

## Global Constraints

- 全部命令从 `geo-agent/` 目录用系统 `python3.11` 执行(canonical:`cd "/Users/jerry/AiProject/sunpower nova/geo-agent" && python3.11 -m pytest tests/ -q`);**不得**用 `.venv/bin/python`。
- 网络操作(Kimi/GSC/fetch)需 `dangerouslyDisableSandbox`;本计划所有新增测试**零网络**。
- **禁 `git add -A`**——只 add 明确文件;`data/`、`rules/history/`(运行期产物)不入库,fixture 拷入 `tests/fixtures/rules/` 提交。
- RulesKeeper 全链**零 LLM**(纯确定性),Kimi 只留在 research/generate 现有路径。
- 现有 247 tests 必须全绿;`score_geo/score_seo` 对外签名向后兼容(只增可选参数)。
- 提交信息风格沿用 repo:`feat(assess): ...` / `feat(rules): ...` 等,结尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。

## File Structure(决定)

| 文件 | 职责 |
|---|---|
| `src/geo/assess/registry.py` **(新)** | 信号注册表:`GEO_SIGNALS` / `SEO_SIGNALS`(id→checker 纯函数),含 3 个候选池 checker |
| `src/geo/assess/geo_scorer.py` **(重写)** | 薄解释器:按 rules.signals 成员求均值 |
| `src/geo/assess/seo_scorer.py` **(重写)** | 同上 |
| `src/geo/rules/loader.py` **(改)** | `load_rules(name, version=None)` 读历史快照;entries 字段 |
| `src/geo/rules/evidence.py` **(新)** | 证据提取:候选(声明式映射表)+ 维度证据强度 |
| `src/geo/rules/gate.py` **(新)** | 条目门槛状态机 draft/active/rejected/retired |
| `src/geo/rules/weights.py` **(新)** | 权重证据强度公式:步长/夹值/最大余数归一 |
| `src/geo/rules/keeper.py` **(新)** | 单轮迭代编排:归档/升版/changelog/run.yaml/rules_iteration.json |
| `src/geo/rules/run.py` **(新)** | CLI:iterate / recalc / rollback / show |
| `src/geo/assess/analyst.py` **(改)** | `assemble` 增可选 rules 注入 + 输出名(recalc 用);竞品评分 `static={}`(Task 0) |
| `src/geo/research/features.py` **(改)** | unique 桶聚合:`sources.unique_n/schema_unique/schema_unique_platforms` + formats `unique_*`(Task 5) |
| `src/geo/research/run.py`、`render.py` **(改)** | 反哺输入 + playbook 第 6 节 + header rule_version 修死值 |
| `src/geo/generate/run.py` **(改)** | mark-published 守卫 + published_at/--url stamp + targets 提示(Task 0) |
| `src/geo/report/templates/report.html.j2` **(改)** | §5 填真实 rules_iteration |
| `src/geo/orchestrate/graph.py` **(改)** | 全链 DAG + --next-week |
| `rules/{geo,seo}-rules.yaml` **(改)** | v1 成员校正 + `entries: []` |
| `tests/fixtures/rules/` **(新)** | w1 真实数据 fixture(拷贝提交) |

**任务依赖链**:0→1→2→3→4→(5,6,7 可并行)→8→9→(10,11,12)→13→14。(Task 0 与 RulesKeeper 无耦合,位置可挪但先做防遗忘。)

---

### Task 0: P2 尾巴加固(发布守卫 + 发布元数据 + 竞品评分上下文)

**Files:**
- Modify: `src/geo/generate/run.py`、`src/geo/assess/analyst.py`
- Test: `tests/test_generate_hardening.py`(新)、`tests/test_analyst_competitors.py`(新)

**Interfaces:**
- Consumes: `content/reviews.jsonl`(append-only)、draft frontmatter、`run_mark_published` 现签名。
- Produces: `run_mark_published(slug, *, url=None, override=False, reason="", repo=REPO, now=None)`(守卫版,向后兼容调用形态);`_latest_review(repo, slug) -> dict | None`;`analyst._score_competitors(week, static_signals) -> list`(竞品循环抽函数,内部传 `static={}`)。

- [ ] **Step 1: 写失败测试**

```python
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
```

```python
# tests/test_analyst_competitors.py
def test_competitors_get_empty_static_not_site_signals(monkeypatch):
    import geo.assess.analyst as A
    from geo.shared.models import L3Source
    calls = []
    monkeypatch.setattr(A, "competitor_domains_by_count", lambda w, n: ["example.com"])
    monkeypatch.setattr(A, "_load_l3_source",
                        lambda url: L3Source(url=url, sha1="s", text="t"))
    monkeypatch.setattr(A, "score_geo",
                        lambda src, brand, static, **kw: calls.append(static))
    A._score_competitors(1, {"robots_ai": {"GPTBot": True}, "https": True, "pages": [{"path": "/about"}]})
    assert calls == [{}]        # 竞品不再借 SunHestia 静态信号(下界 proxy;v1.1 修正)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_generate_hardening.py tests/test_analyst_competitors.py -q`
Expected: FAIL(现实现只挡 rejected;`_score_competitors` 不存在)

- [ ] **Step 3: 实现 run.py 守卫与 stamp**(替换 `run_mark_published`;`_fm_update`/`settings` 若未导入则补)

```python
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
    updates = {"status": "published",
               "published_at": now or datetime.now().isoformat(timespec="seconds")}
    if url:
        updates["published_url"] = url
    if override:
        updates["override_reason"] = reason
    pub_dir = repo / "content" / "published"
    pub_dir.mkdir(parents=True, exist_ok=True)
    (pub_dir / f"{slug}.md").write_text(_fm_update(text, updates), encoding="utf-8")
    if url:
        from urllib.parse import urlparse
        path = urlparse(url).path.rstrip("/")
        pages = (settings.targets.get("site", {}) or {}).get("pages", [])
        if path and path not in pages:
            print(f"⚠️ {path} 不在 targets.yaml site.pages —— 请手动追加,否则静态自审不覆盖此页")
    draft.unlink()
    log.info("归档发布: %s%s", slug, f"(override: {reason})" if override else "")
    return {"slug": slug, "path": str(pub_dir / f"{slug}.md")}
```

CLI:`--mark-published` 分支改调 `run_mark_published(a.mark_published, url=a.url, override=a.override, reason=a.reason)`;argparse 增 `--url`/`--override`(action="store_true")/`--reason` 三参。

- [ ] **Step 4: 实现 analyst 竞品上下文**

把 assemble 中竞品循环抽为模块级函数(逻辑逐字保留,仅 `score_geo` 第三参改 `{}`):

```python
def _score_competitors(week: int, static_signals: dict | None) -> list:
    """竞品 GEO 评分:score_geo 第三参传 {} —— 竞品无全站快照,静态类信号按 0 计(下界 proxy)。
    不得借用目标站 static_signals(含 pages 列表):否则 about_page_present 等站点级
    信号会让全体竞品白拿分(v1.1 修正,外部评审 item 6)。"""
    comp_geos = []
    for comp_domain in competitor_domains_by_count(week, 5):
        comp_url = f"https://{comp_domain}"
        comp_l3 = _load_l3_source(comp_url)
        if comp_l3:
            comp_brand_signals = {"mention": 0, "cited": 0, "sov": 0.0, "entity_known": False,
                                  "on_youtube": False, "on_reddit": False,
                                  "on_wikipedia": False, "on_linkedin": False}
            try:
                comp_geos.append(score_geo(comp_l3, comp_brand_signals, {}))
            except (KeyError, TypeError, ValueError):
                continue
    return comp_geos
```

assemble 原竞品循环处替换为 `comp_geos = _score_competitors(week, static_signals)`(参数保留以显式表达"有意不用")。报告 gap 注记随 Task 11 模板一并加。

- [ ] **Step 5: 跑测试 + 全量**

Run: `python3.11 -m pytest tests/test_generate_hardening.py tests/test_analyst_competitors.py tests/ -q`
Expected: 全 PASS。⚠️ 若存量 generate 测试断言"无 review 也能 mark-published"的旧行为,按守卫语义更新该用例(守卫 = P2 spec §6.1"发布归档仅属 pass/minor 分支"的实现补齐)。

- [ ] **Step 6: Commit**

```bash
git add src/geo/generate/run.py src/geo/assess/analyst.py tests/test_generate_hardening.py tests/test_analyst_competitors.py
git commit -m "feat(generate+assess): publish gate guard + publish stamps + competitor empty static (P2 tail hardening)"
```

---

### Task 1: 信号注册表 `registry.py`

**Files:**
- Create: `src/geo/assess/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `geo.shared.models.L3Source`
- Produces: `GEO_SIGNALS: dict[str, Callable[[L3Source, dict, dict], float]]`;`SEO_SIGNALS: dict[str, Callable[[dict, dict, dict], float]]`——Task 3 的 scorer 解释器直接迭代调用;checker 值域 0–100。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_registry.py
from geo.assess.registry import GEO_SIGNALS, SEO_SIGNALS
from geo.shared.models import L3Source

SRC = L3Source(url="https://sunhestia.com", sha1="x", text="t",
    structural={"schema_types": ["FAQPage", "Organization", "Product", "Article", "BreadcrumbList"],
                "h_counts": {"h1": 1, "h2": 3, "ul_count": 2}, "table_count": 2,
                "canonical": "https://sunhestia.com"},
    semantic={"has_definition_segment": True, "faq_block_count": 2, "datapoint_count": 5,
              "has_author_byline": True, "has_publish_date": True,
              "cites_external_sources": True})
BRAND = {"mention": 1, "cited": 0, "sov": 0.0, "entity_known": False,
         "on_youtube": False, "on_reddit": False, "on_wikipedia": False, "on_linkedin": False}
STATIC = {"robots_ai": {"GPTBot": True, "ClaudeBot": True}, "https": True,
          "pages": [{"path": "/about"}, {"path": "/faq"}]}

def test_geo_checker_values():  # 逐 checker 与旧硬编码公式对数
    g = lambda sid: GEO_SIGNALS[sid](SRC, BRAND, STATIC)
    assert g("has_definition_segment") == 100.0
    assert g("faq_block_count") == 66.7          # _ratio(2,0,3)
    assert g("table_count") == 100.0             # _ratio(2,0,2)
    assert g("datapoint_count") == 100.0         # _ratio(5,0,5)
    assert g("list_count") == 66.7               # _ratio(ul_count=2,0,3)
    assert g("mention_count") == 33.3            # _ratio(1,0,3)
    assert g("entity_known") == 0.0
    assert g("org_or_person_schema") == 100.0
    assert g("robots_gptbot") == 100.0 and g("robots_claudebot") == 100.0
    assert g("canonical_present") == 100.0       # truthy canonical
    assert g("schema_type_count") == 100.0       # _ratio(5,0,3)
    assert g("has_faqpage") == 100.0 and g("has_organization") == 100.0
    assert g("has_breadcrumblist") == 100.0      # 候选池
    assert g("about_page_present") == 100.0      # 候选池(pages 含 /about)
    assert g("author_schema") == 0.0             # 候选池(无 Person)

def test_geo_none_safe():
    empty = L3Source(url="u", sha1="s")
    for sid in GEO_SIGNALS:
        v = GEO_SIGNALS[sid](empty, {}, {})      # 空 src/brand/static 不崩,返回 float
        assert isinstance(v, float) and 0.0 <= v <= 100.0

def test_seo_checker_values():
    p = {"http_status": 200, "in_sitemap": True, "robots_not_blocked": True,
         "canonical_self": True, "https": True, "has_viewport": True,
         "title": "SunHestia Solar Battery Storage Guides", "h_counts": {"h1": 1, "h2": 2},
         "meta_desc": "Guides"}
    gsc = {"impressions": 500, "clicks": 25, "ctr": 0.05}
    c = {"word_count": 800, "has_author_byline": True, "has_publish_date": True,
         "cites_external_sources": True}
    s = lambda sid: SEO_SIGNALS[sid](p, gsc, c)
    assert s("http_200") == 100.0 and s("in_sitemap") == 100.0
    assert s("title_len_ok") == 100.0            # len 40..60
    assert s("single_h1") == 100.0 and s("heading_hierarchy_ok") == 100.0
    assert s("word_count_band") == 100.0         # _ratio(800,300,1500)
    assert s("gsc_impressions") == 50.0          # _ratio(500,0,1000)
    assert s("gsc_ctr") == 100.0                 # _ratio(0.05,0,0.05)
    assert s("backlinks_est") == 0.0             # P2+ unknown 恒 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "/Users/jerry/AiProject/sunpower nova/geo-agent" && python3.11 -m pytest tests/test_registry.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'geo.assess.registry'`

- [ ] **Step 3: 实现 registry.py(公式从两 scorer 逐字搬迁)**

```python
# src/geo/assess/registry.py
"""信号注册表:checker 纯函数,值域 0–100。
GEO 签名 (src: L3Source, brand: dict, static: dict) -> float
SEO 签名 (p: dict, gsc: dict, c: dict) -> float
公式自 geo_scorer/seo_scorer 逐字搬迁(v1 语义零漂移);None 一律安全降 0。"""
from __future__ import annotations
from geo.shared.models import L3Source


def _pct(ok) -> float:
    return 100.0 if ok else 0.0


def _ratio(n, lo, hi) -> float:      # n in [lo,hi] → 0..100
    if n is None:
        return 0.0
    if n <= lo:
        return 0.0
    if n >= hi:
        return 100.0
    return round(100 * (n - lo) / (hi - lo), 1)


GEO_SIGNALS = {
    # citability(旧公式均值 5 项)
    "has_definition_segment": lambda s, b, st: _pct((s.semantic or {}).get("has_definition_segment")),
    "faq_block_count":        lambda s, b, st: _ratio((s.semantic or {}).get("faq_block_count", 0), 0, 3),
    "table_count":            lambda s, b, st: _ratio((s.structural or {}).get("table_count", 0), 0, 2),
    "datapoint_count":        lambda s, b, st: _ratio((s.semantic or {}).get("datapoint_count", 0), 0, 5),
    "list_count":             lambda s, b, st: _ratio((s.structural or {}).get("h_counts", {}).get("ul_count", 0), 0, 3),
    # brand
    "mention_count":          lambda s, b, st: _ratio(b.get("mention", 0), 0, 3),
    "cited_count":            lambda s, b, st: _ratio(b.get("cited", 0), 0, 2),
    "sov_share":              lambda s, b, st: _ratio(b.get("sov", 0.0), 0, 0.2),
    "entity_known":           lambda s, b, st: _pct(b.get("entity_known")),
    # eeat
    "has_author_byline":      lambda s, b, st: _pct((s.semantic or {}).get("has_author_byline")),
    "has_publish_date":       lambda s, b, st: _pct((s.semantic or {}).get("has_publish_date")),
    "cites_external_sources": lambda s, b, st: _pct((s.semantic or {}).get("cites_external_sources")),
    "org_or_person_schema":   lambda s, b, st: _pct("Organization" in (s.structural or {}).get("schema_types", [])
                                                    or "Person" in (s.structural or {}).get("schema_types", [])),
    # technical_geo
    "robots_gptbot":          lambda s, b, st: _pct((st.get("robots_ai") or {}).get("GPTBot")),
    "robots_claudebot":       lambda s, b, st: _pct((st.get("robots_ai") or {}).get("ClaudeBot")),
    "https":                  lambda s, b, st: _pct(st.get("https")),
    "canonical_present":      lambda s, b, st: _pct((s.structural or {}).get("canonical")),
    # schema
    "schema_type_count":      lambda s, b, st: _ratio(len((s.structural or {}).get("schema_types", [])), 0, 3),
    "has_faqpage":            lambda s, b, st: _pct("FAQPage" in (s.structural or {}).get("schema_types", [])),
    "has_product":            lambda s, b, st: _pct("Product" in (s.structural or {}).get("schema_types", [])),
    "has_organization":       lambda s, b, st: _pct("Organization" in (s.structural or {}).get("schema_types", [])),
    "has_article":            lambda s, b, st: _pct("Article" in (s.structural or {}).get("schema_types", [])),
    # platform(brand dict)
    "on_youtube":             lambda s, b, st: _pct(b.get("on_youtube")),
    "on_reddit":              lambda s, b, st: _pct(b.get("on_reddit")),
    "on_wikipedia":           lambda s, b, st: _pct(b.get("on_wikipedia")),
    "on_linkedin":            lambda s, b, st: _pct(b.get("on_linkedin")),
    # —— 候选池(v1 不进成员,draft 条目激活对象)——
    "about_page_present":     lambda s, b, st: _pct(any(p.get("path") == "/about" for p in (st.get("pages") or []))),
    "author_schema":          lambda s, b, st: _pct("Person" in (s.structural or {}).get("schema_types", [])),
    "has_breadcrumblist":     lambda s, b, st: _pct("BreadcrumbList" in (s.structural or {}).get("schema_types", [])),
}

SEO_SIGNALS = {
    # crawlability_index
    "http_200":               lambda p, g, c: _pct(p.get("http_status") == 200),
    "in_sitemap":             lambda p, g, c: _pct(p.get("in_sitemap")),
    "robots_not_blocked":     lambda p, g, c: _pct(p.get("robots_not_blocked")),
    "canonical_self":         lambda p, g, c: _pct(p.get("canonical_self")),
    "https":                  lambda p, g, c: _pct(p.get("https")),
    # technical_foundation
    "mobile_viewport":        lambda p, g, c: _pct(p.get("has_viewport")),
    "http2":                  lambda p, g, c: _pct(p.get("http2", True)),
    "renderable_static":      lambda p, g, c: _pct(p.get("renderable_static", True)),
    # on_page
    "unique_title":           lambda p, g, c: _pct(bool(p.get("title"))),
    "title_len_ok":           lambda p, g, c: _pct(40 <= len(p.get("title") or "") <= 60),
    "meta_desc_present":      lambda p, g, c: _pct(p.get("meta_desc")),
    "single_h1":              lambda p, g, c: _pct(p.get("h_counts", {}).get("h1", 0) == 1),
    "heading_hierarchy_ok":   lambda p, g, c: _pct(p.get("h_counts", {}).get("h2", 0) >= 1
                                                   and p.get("h_counts", {}).get("h3", 0) >= 0),
    # content_eeat
    "word_count_band":        lambda p, g, c: _ratio(c.get("word_count", 0), 300, 1500),
    # authority
    "gsc_impressions":        lambda p, g, c: _ratio(g.get("impressions", 0), 0, 1000),
    "gsc_clicks":             lambda p, g, c: _ratio(g.get("clicks", 0), 0, 50),
    "gsc_ctr":                lambda p, g, c: _ratio(g.get("ctr") or 0, 0, 0.05),
    "backlinks_est":          lambda p, g, c: 0.0,   # P2+ unknown → 恒 0(p2plus_missing)
}
```

注:SEO `has_author_byline/has_publish_date/cites_external_sources` 与 GEO 同名不同签——分属两 dict,互不冲突;SEO 侧在 Task 3 的 seo_scorer 里以 `c` 为 content 参数引用同名 checker(见 Task 3 代码,不重复入 SEO dict 会导致 KeyError,故 SEO_SIGNALS **必须**也含这三项,实现为读 `c`):

```python
    # content_eeat(读 content 参数 c,与 GEO 同名不同源)
    "has_author_byline":      lambda p, g, c: _pct(c.get("has_author_byline")),
    "has_publish_date":       lambda p, g, c: _pct(c.get("has_publish_date")),
    "cites_external_sources": lambda p, g, c: _pct(c.get("cites_external_sources")),
```

⚠️ 旧行为对齐说明:旧 on_page `unique_title` 是 `_pct(title and title == p.get("title"))`(恒等于 bool(title));`heading_hierarchy_ok` 旧行为 `_pct(h2>=1 and h3>=0)` 恒等 `h2>=1`。搬迁保持等值。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3.11 -m pytest tests/test_registry.py -q`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/geo/assess/registry.py tests/test_registry.py
git commit -m "feat(assess): signal registry — checkers lifted verbatim from scorers + 3 candidate-pool checkers"
```

---

### Task 2: loader 增版本参数与 entries

**Files:**
- Modify: `src/geo/rules/loader.py`
- Test: `tests/test_rules_loader.py`(扩展)

**Interfaces:**
- Consumes: 现有 `REPO`。
- Produces: `load_rules(name: str, version: str | None = None)`;返回的 SimpleNamespace 新增 `entries: list`(默认 `[]`);历史路径 `RULES_DIR/"history"/{version}/{name}-rules.yaml`。Task 3/8/9 依赖此签名。

- [ ] **Step 1: 写失败测试(追加到 tests/test_rules_loader.py)**

```python
from geo.rules.loader import load_rules, assert_normalized
import yaml, pytest
from geo.rules.loader import RULES_DIR

def test_load_with_version_reads_history(tmp_path):
    hist = tmp_path / "history" / "geo-seo-v1"
    hist.mkdir(parents=True)
    (hist / "geo-rules.yaml").write_text(yaml.safe_dump({
        "version": "geo-seo-v1", "composite": "geo",
        "weights": {"citability": 25}, "signals": {"citability": ["has_definition_segment"]},
        "entries": [{"id": "add-x", "type": "signal_add", "target": "schema",
                     "signal": "has_breadcrumblist", "status": "draft",
                     "statement": "s", "evidence": {"share": 0.19}, "since_version": None}]}))
    orig = RULES_DIR   # monkeypatch 注入 tmp
    import geo.rules.loader as L
    L.RULES_DIR = tmp_path
    try:
        r = load_rules("geo", version="geo-seo-v1")
        assert r.version == "geo-seo-v1" and r.entries[0]["signal"] == "has_breadcrumblist"
        with pytest.raises(FileNotFoundError):
            load_rules("geo", version="geo-seo-v99")
    finally:
        L.RULES_DIR = orig

def test_entries_default_empty():
    r = load_rules("geo")
    assert r.entries == []            # v1 文件尚无 entries → 默认空
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_rules_loader.py -q`
Expected: FAIL `TypeError: load_rules() got an unexpected keyword argument 'version'`

- [ ] **Step 3: 实现**

```python
def _load(p: Path):
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    return SimpleNamespace(
        version=d["version"], composite=d["composite"], weights=d["weights"],
        signals=d.get("signals", {}), severity_bands=d.get("severity_bands", {}),
        p2plus_missing=d.get("p2plus_missing", []), entries=d.get("entries", [])
    )


def load_rules(name: str, version: str | None = None):
    """Load rules by name (geo or seo); version=None 读当前,否则读 rules/history/{version}/。"""
    p = (RULES_DIR / "history" / version / f"{name}-rules.yaml") if version \
        else RULES_DIR / f"{name}-rules.yaml"
    if not p.exists():
        raise FileNotFoundError(f"rules not found: {p}")
    return _load(p)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3.11 -m pytest tests/test_rules_loader.py -q`
Expected: PASS(含存量用例)

- [ ] **Step 5: Commit**

```bash
git add src/geo/rules/loader.py tests/test_rules_loader.py
git commit -m "feat(rules): loader version param (history snapshots) + entries field"
```

---

### Task 3: scorer 重写为解释器(签名向后兼容)

**Files:**
- Modify: `src/geo/assess/geo_scorer.py`(整体重写)、`src/geo/assess/seo_scorer.py`(整体重写)
- Test: `tests/test_geo_scorer.py`、`tests/test_seo_scorer.py`(存量不动,必须原样通过;新增解释器用例)

**Interfaces:**
- Consumes: Task 1 `GEO_SIGNALS/SEO_SIGNALS`;Task 2 `load_rules`。
- Produces: `score_geo(src, brand, static, rules=None) -> CompositeScore`;`score_seo(p, gsc, c, rules=None) -> CompositeScore`。`DimScore.signals` 载荷变为 `{signal_id: 计算值}`(下游 reporter/analyst 不消费该载荷,已核实)。

- [ ] **Step 1: 新增解释器测试(追加到 test_geo_scorer.py)**

```python
from geo.rules.loader import load_rules

def test_membership_driven_and_rules_injection():
    """成员关系驱动:注入裁剪版规则 → 只算剩余维度;权重取注入值。"""
    brand = {"mention": 1, "cited": 0, "sov": 0.0, "entity_known": False}
    static = {"robots_ai": {"GPTBot": True, "ClaudeBot": True}, "https": True}
    full = score_geo(SRC, brand, static)
    assert full.total == 65.0                       # 与旧硬编码一致(见 Task1 fixture 对数)
    import types
    tiny = types.SimpleNamespace(
        version="geo-seo-v1", composite="geo",
        weights={"citability": 100}, signals={"citability": ["has_definition_segment"]},
        severity_bands={}, p2plus_missing=[], entries=[])
    one = score_geo(SRC, brand, static, rules=tiny)
    assert [d.name for d in one.dims] == ["citability"]
    assert one.dims[0].score == 100.0 and one.total == 100.0
    assert one.dims[0].signals == {"has_definition_segment": 100.0}

def test_unknown_signal_id_rejected():
    import types
    bad = types.SimpleNamespace(version="x", composite="geo",
        weights={"citability": 100}, signals={"citability": ["no_such_signal"]},
        severity_bands={}, p2plus_missing=[], entries=[])
    import pytest
    with pytest.raises(ValueError, match="no_such_signal"):
        score_geo(SRC, {}, {}, rules=bad)
```

(同样在 test_seo_scorer.py 追加一个 membership 驱动用例:构造只含 `crawlability_index` 的注入规则,断言维度分 = 5 checker 均值。)

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_geo_scorer.py -q`
Expected: FAIL `TypeError: score_geo() takes 3 positional arguments but 4 were given`

- [ ] **Step 3: 重写 geo_scorer.py**

```python
# src/geo/assess/geo_scorer.py
from __future__ import annotations
from geo.shared.models import L3Source, DimScore, CompositeScore
from geo.rules.loader import load_rules
from geo.assess.registry import GEO_SIGNALS


def score_geo(src: L3Source, brand: dict, static: dict, rules=None) -> CompositeScore:
    """Membership-driven GEO scoring:维度分 = 成员 checker 均值,权重读 rules。"""
    r = rules or load_rules("geo")
    unknown = [s for ids in r.signals.values() for s in ids if s not in GEO_SIGNALS]
    if unknown:
        raise ValueError(f"unknown geo signals: {unknown}; available: {sorted(GEO_SIGNALS)}")
    if set(r.signals) != set(r.weights):
        raise ValueError(f"signals dims {sorted(r.signals)} != weights dims {sorted(r.weights)}")
    dims = []
    for dim, sig_ids in r.signals.items():          # YAML 顺序 = 维度顺序(与旧硬编码一致)
        vals = {sid: GEO_SIGNALS[sid](src, brand, static) for sid in sig_ids}
        score = round(sum(vals.values()) / len(vals), 1)
        dims.append(DimScore(name=dim, score=score, weight=r.weights[dim], signals=vals))
    total = round(sum(d.score * d.weight for d in dims) / 100.0, 1)
    return CompositeScore(total=total, dims=dims)
```

- [ ] **Step 4: 重写 seo_scorer.py(同构)**

```python
# src/geo/assess/seo_scorer.py
from __future__ import annotations
from geo.shared.models import DimScore, CompositeScore
from geo.rules.loader import load_rules
from geo.assess.registry import SEO_SIGNALS


def score_seo(p: dict, gsc: dict, c: dict, rules=None) -> CompositeScore:
    """Membership-driven SEO scoring:维度分 = 成员 checker 均值,权重读 rules。"""
    r = rules or load_rules("seo")
    unknown = [s for ids in r.signals.values() for s in ids if s not in SEO_SIGNALS]
    if unknown:
        raise ValueError(f"unknown seo signals: {unknown}; available: {sorted(SEO_SIGNALS)}")
    if set(r.signals) != set(r.weights):
        raise ValueError(f"signals dims {sorted(r.signals)} != weights dims {sorted(r.weights)}")
    dims = []
    for dim, sig_ids in r.signals.items():
        vals = {sid: SEO_SIGNALS[sid](p, gsc, c) for sid in sig_ids}
        score = round(sum(vals.values()) / len(vals), 1)
        dims.append(DimScore(name=dim, score=score, weight=r.weights[dim], signals=vals))
    total = round(sum(d.score * d.weight for d in dims) / 100.0, 1)
    return CompositeScore(total=total, dims=dims)
```

- [ ] **Step 5: 校正两个 YAML(必须与 scorer 重写同任务落地——否则全量套件因旧 YAML 含未注册 id 而炸)**

`rules/geo-rules.yaml`(weights/severity_bands/p2plus_missing 不动,signals 替换 + 文末 `entries: []`):

```yaml
signals:        # 成员 = 代码实际计算集(2026-08-19 校正,语义无操作)
  citability: [has_definition_segment, faq_block_count, table_count, datapoint_count, list_count]
  brand: [mention_count, cited_count, sov_share, entity_known]
  eeat: [has_author_byline, has_publish_date, cites_external_sources, org_or_person_schema]
  technical_geo: [robots_gptbot, robots_claudebot, https, canonical_present]
  schema: [schema_type_count, has_faqpage, has_product, has_organization, has_article]
  platform: [on_youtube, on_reddit, on_wikipedia, on_linkedin]
```

`rules/seo-rules.yaml` signals 替换为:

```yaml
signals:
  crawlability_index: [http_200, in_sitemap, robots_not_blocked, canonical_self, https]
  technical_foundation: [https, mobile_viewport, http2, renderable_static]
  on_page: [unique_title, title_len_ok, meta_desc_present, single_h1, heading_hierarchy_ok]
  content_eeat: [word_count_band, has_author_byline, has_publish_date, cites_external_sources]
  authority: [gsc_impressions, gsc_clicks, gsc_ctr, backlinks_est]
```

文末加 `entries: []`。`rules/changelog.md` 追加:

```markdown
## geo-seo-v1(成员校正)— 2026-08-19
- signals 成员与代码实际计算集对齐(P3 数据驱动化前置):eeat 撤下从未生效的
  about_page_present/author_schema;technical_geo 收敛为实际 4 项;brand/authority
  信号名对齐 checker id;SEO authority 落回实际 4 项(backlinks_est=unknown 恒 0)。
- 语义无操作(撤下的项本就不计分);分数零漂移由 tests/test_v1_semantics.py 黄金锁死(Task 4)。
- status: active. weights 不变(和=100)。version 保持 geo-seo-v1。
```

并新增成员一致性测试(追加到 test_geo_scorer.py):

```python
def test_v1_yaml_membership_matches_registry():
    from geo.assess.registry import GEO_SIGNALS, SEO_SIGNALS
    from geo.rules.loader import load_rules
    for name, reg in (("geo", GEO_SIGNALS), ("seo", SEO_SIGNALS)):
        r = load_rules(name)
        assert r.entries == []
        for dim, ids in r.signals.items():
            assert ids, f"{name}.{dim} 成员为空"
            assert all(i in reg for i in ids), f"{name}.{dim} 含未注册信号"
    g = load_rules("geo")
    assert "about_page_present" not in g.signals.get("eeat", [])      # 校正点:从未生效者不得回流
    assert "llms_txt_present" not in g.signals.get("technical_geo", [])
```

- [ ] **Step 6: 跑两个 scorer 测试 + 全量**

Run: `python3.11 -m pytest tests/test_geo_scorer.py tests/test_seo_scorer.py -q && python3.11 -m pytest tests/ -q`
Expected: 全 PASS。若存量 scorer 用例失败,是搬迁走样,**修实现不修测试**(存量断言即 v1 语义锁)。已知例外:`test_seo_scorer` 若断言 authority 分母为 4(含未知 0 项),保持 `backlinks_est` checker 恒 0 即可对齐;若断言 payload 形状(key 名),更新该断言为 `{signal_id: 值}`(载荷非语义)。

- [ ] **Step 7: Commit**

```bash
git add src/geo/assess/geo_scorer.py src/geo/assess/seo_scorer.py rules/geo-rules.yaml rules/seo-rules.yaml rules/changelog.md tests/test_geo_scorer.py tests/test_seo_scorer.py
git commit -m "feat(assess): membership-driven scorers + v1 YAML reconciliation (same-task, no-op semantics)"
```

---

### Task 4: w1 真实 fixture + 语义零漂移黄金锁

**Files:**
- Create: `scripts/capture_w1_fixtures.py`、`tests/fixtures/rules/`(w1 真实数据拷贝)
- Test: `tests/test_v1_semantics.py`

**Interfaces:**
- Consumes: Task 1-3(校正后 v1 YAML + 新引擎)。
- Produces: fixture `tests/fixtures/rules/{research_aggregates.json, eval_report.json}`(Task 8 keeper 测试输入);真实数据黄金守卫。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_v1_semantics.py
import json
import pytest
from geo.shared.config import REPO
from geo.assess.analyst import assemble

@pytest.mark.skipif(not (REPO / "data" / "raw" / "w1").exists(),
                    reason="需本地真实 w1 数据(data/ gitignored)")
def test_v1_semantics_unchanged_on_real_w1():
    archived = json.loads((REPO / "data" / "analysis" / "w1" / "eval_report.json").read_text(encoding="utf-8"))
    rep = assemble(1)                                   # 新引擎重算(幂等覆写)
    assert rep["self_geo"]["total"] == archived["self_geo"]["total"] == 47.6
    assert rep["self_seo"]["total"] == archived["self_seo"]["total"] == 49.8
    for a, b in zip(rep["self_geo"]["dims"], archived["self_geo"]["dims"]):
        assert a["name"] == b["name"] and a["score"] == b["score"] and a["weight"] == b["weight"]
    for a, b in zip(rep["self_seo"]["dims"], archived["self_seo"]["dims"]):
        assert a["name"] == b["name"] and a["score"] == b["score"] and a["weight"] == b["weight"]
```

- [ ] **Step 2: 跑测试(本机有真实数据,应直接 PASS——这正是黄金的意义;若 FAIL 即搬迁走样,回 Task 3 修)**

Run: `python3.11 -m pytest tests/test_v1_semantics.py -q`
Expected: PASS(47.6 / 49.8 分毫不差)

- [ ] **Step 3: 采集 w1 真实 fixture(供 Task 8 keeper 测试,提交入库)**

```python
# scripts/capture_w1_fixtures.py  ——一次性:从 gitignored 真实数据拷 fixture
"""Capture real w1 aggregates/eval_report into tests/fixtures/rules/ (committed)."""
import shutil
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "tests" / "fixtures" / "rules"; OUT.mkdir(parents=True, exist_ok=True)
for src in ("data/analysis/w1/research_aggregates.json", "data/analysis/w1/eval_report.json"):
    shutil.copy(REPO / src, OUT / Path(src).name)
print("captured ->", OUT)
```

Run: `python3.11 scripts/capture_w1_fixtures.py`(本机真实数据存在,零网络)

- [ ] **Step 4: 确认 fixture 就位**

Run: `ls tests/fixtures/rules/`
Expected: `eval_report.json  research_aggregates.json`

(⚠️ 此 fixture 为出现口径版本;Task 5 Step 0 重生成含 unique 桶的 aggregates 后**重跑本脚本刷新** research_aggregates.json——Task 5/8 测试读 unique 字段。)

- [ ] **Step 5: Commit**

```bash
git add scripts/capture_w1_fixtures.py tests/fixtures/rules/ tests/test_v1_semantics.py
git commit -m "test(rules): real w1 fixtures + v1-semantics golden lock (47.6/49.8)"
```

---

### Task 5: 证据提取 `evidence.py`(唯一 URL 口径)+ features.py unique 桶

**Files:**
- Create: `src/geo/rules/evidence.py`
- Modify: `src/geo/research/features.py`(unique 桶聚合,v1.1)
- Test: `tests/test_rules_evidence.py`(输入用 `tests/fixtures/rules/research_aggregates.json` + `eval_report.json`)

**Interfaces:**
- Consumes: fixture JSON 结构(v1.1 扩展后:`formats: [{key, cited_n, sample_n, platforms, unique_cited_n, unique_n, unique_platforms}]`;`sources.schema`(出现口径,P1 展示用)、`sources.unique_n`、`sources.schema_unique: {type: 唯一页数}`、`sources.schema_unique_platforms: {type: [平台]}`;`eval_report.gap.metrics.{mention_rate, citation_rate}`)。
- Produces: `collect_evidence(agg: dict) -> list[dict]`(元素 `{signal, kind, bucket, with_n, unique_n, platforms, share}`,share = with_n/unique_n);`dimension_strengths(agg, evalrep) -> dict[str, float | None]`(unique 口径)。Task 6/8 消费。

- [ ] **Step 0: features.py 增 unique 桶聚合 + 重生成 w1 aggregates(零网络,v1.1)**

`aggregate()` 内与现有出现口径并行增 per-URL 去重收集(**不改动现有字段**——P1 playbook 渲染与存量测试不变):

```python
    # —— v1.1:唯一 URL(页-周)口径聚合(RulesKeeper 证据用)——
    uniq = {}                                   # url -> {"plats": set(), "l3": L3Source}
    for it in corpus.items:
        m = it.l1.model
        for cited, l3 in it.sources:
            if l3 is None:
                continue
            e = uniq.setdefault(cited.url, {"plats": set(), "l3": l3})
            e["plats"].add(m)
    schema_u, schema_u_plats = Counter(), {}
    fmt_u = {k: {"with": 0, "plats": set()} for k in fmt}
    for url, e in uniq.items():
        st, se = (e["l3"].structural or {}), (e["l3"].semantic or {})
        for s in st.get("schema_types", []):
            schema_u[s] += 1
            schema_u_plats.setdefault(s, set()).update(e["plats"])
        if st.get("table_count", 0) > 0: fmt_u["comparison_table"]["with"] += 1; fmt_u["comparison_table"]["plats"].update(e["plats"])
        if se.get("has_faq_block"): fmt_u["qa"]["with"] += 1; fmt_u["qa"]["plats"].update(e["plats"])
        if st.get("ul_count", 0) > 0: fmt_u["list"]["with"] += 1; fmt_u["list"]["plats"].update(e["plats"])
        if se.get("has_definition_segment"): fmt_u["definition"]["with"] += 1; fmt_u["definition"]["plats"].update(e["plats"])
        if se.get("page_type") == "product" or se.get("datapoint_count", 0) >= 8:
            fmt_u["spec_card"]["with"] += 1; fmt_u["spec_card"]["plats"].update(e["plats"])
```

输出侧:`src_dim["unique_n"] = len(uniq)`;`src_dim["schema_unique"] = dict(schema_u)`;`src_dim["schema_unique_platforms"] = {k: sorted(v) for k, v in schema_u_plats.items()}`;每个 formats FeatureBucket 增 `unique_cited_n`/`unique_n`/`unique_platforms` 三字段(模型 dataclass 同步加,默认 0/0/None 保持向后兼容)。

Run: `python3.11 -m geo.research.run --week 1 --no-kimi`(磁盘重算零网络;sample 已抓全不补抓)
Expected: 重生成 `data/analysis/w1/research_aggregates.json` 含 `unique_n=34`、`schema_unique.BreadcrumbList=7`、`schema_unique_platforms.BreadcrumbList=["doubao","qwen","zhipu"]`(实测预期;不符则停下以脚本重算核对,勿改断言凑数)。
⚠️ `run_research` 会**无条件重渲染** `knowledge/playbook.md` + `knowledge/platform-profiles.md`(run.py:39-40)——`--no-kimi` 下 conclusions 为空会把含 Kimi 综合的 live playbook 覆写掉。两文件 git 已追踪且本任务不改它们 → 重跑后立即 `git restore geo-agent/knowledge/playbook.md geo-agent/knowledge/platform-profiles.md` 还原(若 git status 显示它们被改)。本任务只保留 features.py 代码变更 + fixture 刷新。
随后 `python3.11 scripts/capture_w1_fixtures.py` **刷新 fixture**(Task 4 脚本复用,供本任务与 Task 8 测试)。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rules_evidence.py
import json
from pathlib import Path
from geo.rules.evidence import collect_evidence, dimension_strengths, ADD_CANDIDATES, REMOVE_CANDIDATES
FIX = Path(__file__).parent / "fixtures" / "rules"

def setup_module():
    global AGG, EVAL
    AGG = json.loads((FIX / "research_aggregates.json").read_text(encoding="utf-8"))
    EVAL = json.loads((FIX / "eval_report.json").read_text(encoding="utf-8"))

def test_collect_evidence_w1():
    ev = {e["signal"]: e for e in collect_evidence(AGG)}
    bc = ev["has_breadcrumblist"]                       # add 候选(唯一 URL 口径)
    assert bc["kind"] == "signal_add" and bc["with_n"] == 7 and bc["unique_n"] == 34
    assert abs(bc["share"] - 7 / 34) < 0.001
    assert bc["platforms"] == ["doubao", "qwen", "zhipu"]
    qa = ev["faq_block_count"]                          # remove 候选:qa 0/34(唯一)
    assert qa["kind"] == "signal_remove" and qa["with_n"] == 0 and qa["share"] == 0.0

def test_dimension_strengths_w1():
    s = dimension_strengths(AGG, EVAL)
    assert s["citability"] == max(b["unique_cited_n"] / b["unique_n"]      # unique 口径最大格式桶
                                  for b in AGG["formats"] if b.get("unique_n"))
    assert abs(s["schema"] - 7 / 34) < 0.001            # BreadcrumbList 唯一最大
    assert abs(s["brand"] - (0.133 + 0.0887) / 2) < 0.0005
    assert s["eeat"] is None and s["platform"] is None and s["technical_geo"] is None

def test_candidate_maps_static():
    assert ADD_CANDIDATES == {"has_breadcrumblist": "schema.BreadcrumbList"}
    assert REMOVE_CANDIDATES == {"faq_block_count": "qa"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_rules_evidence.py -q`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现**

```python
# src/geo/rules/evidence.py
"""确定性证据提取:候选(声明式映射) + 维度证据强度。零 LLM。
证据口径 = 唯一 URL(页-周)计数(v1.1):with_n/unique_n/share/platforms 全部去重口径;
出现次数仅留在 aggregates 供 P1 展示,不进门槛。"""
from __future__ import annotations

# 声明式映射:checker id -> research_aggregates 桶。不在表内 = 无证据源,不会被提名。
ADD_CANDIDATES: dict[str, str] = {
    "has_breadcrumblist": "schema.BreadcrumbList",      # sources.schema_unique 桶
}
REMOVE_CANDIDATES: dict[str, str] = {
    "faq_block_count": "qa",                            # formats 桶 key
}


def _format_bucket(agg: dict, key: str) -> dict | None:
    for b in agg.get("formats", []):
        if b.get("key") == key:
            return b
    return None


def _schema_bucket(agg: dict, type_: str) -> dict | None:
    src = agg.get("sources", {}) or {}
    with_n = src.get("schema_unique", {}).get(type_)
    unique_n = src.get("unique_n", 0)
    if with_n is None or not unique_n:
        return None
    return {"with_n": with_n, "unique_n": unique_n,
            "platforms": list(src.get("schema_unique_platforms", {}).get(type_, []))}


def _evidence(signal: str, kind: str, bucket_label: str, b: dict) -> dict:
    share = round(b["with_n"] / b["unique_n"], 4) if b["unique_n"] else 0.0
    return {"signal": signal, "kind": kind, "bucket": bucket_label,
            "with_n": b["with_n"], "unique_n": b["unique_n"],
            "platforms": list(b.get("platforms", [])), "share": share}


def collect_evidence(agg: dict) -> list[dict]:
    out = []
    for sig, spec in ADD_CANDIDATES.items():
        b = _schema_bucket(agg, spec.split(".", 1)[1])
        if b:
            out.append(_evidence(sig, "signal_add", spec, b))
    for sig, fmt_key in REMOVE_CANDIDATES.items():
        b = _format_bucket(agg, fmt_key)
        if b and b.get("unique_n"):
            out.append(_evidence(sig, "signal_remove", f"formats.{fmt_key}",
                                 {"with_n": b.get("unique_cited_n", 0), "unique_n": b["unique_n"],
                                  "platforms": b.get("unique_platforms", [])}))
    return out


def dimension_strengths(agg: dict, evalrep: dict) -> dict[str, float | None]:
    """GEO 维度证据强度(唯一 URL 口径);无证据流的维度为 None(不参与权重调整)。SEO 全维度暂无流。"""
    fmts = [b.get("unique_cited_n", 0) / b["unique_n"]
            for b in agg.get("formats", []) if b.get("unique_n")]
    src = agg.get("sources", {}) or {}
    unique_n = src.get("unique_n", 0)
    schema_shares = [c / unique_n for t, c in src.get("schema_unique", {}).items() if t and unique_n]
    m = ((evalrep.get("gap", {}) or {}).get("metrics", {}) or {})
    mention, citation = m.get("mention_rate"), m.get("citation_rate")
    return {
        "citability": max(fmts) if fmts else None,
        "schema": max(schema_shares) if schema_shares else None,
        "brand": (mention + citation) / 2 if (mention is not None and citation is not None) else None,
        "eeat": None, "technical_geo": None, "platform": None,
    }
```

注(v1.1):平台归因来自 features.py 真实 per-URL 归集(`schema_unique_platforms`,Step 0 产出)——w1 BreadcrumbList = `["doubao","qwen","zhipu"]`(3 家,过 Task 6 的 platforms≥2 门)。**不再使用**借用 formats 桶平台并集的推导 hack(出现口径残留,v1.1 删除)。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3.11 -m pytest tests/test_rules_evidence.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/geo/rules/evidence.py tests/test_rules_evidence.py
git commit -m "feat(rules): deterministic evidence extraction (candidates + dimension strengths)"
```

---

### Task 6: 条目门槛状态机 `gate.py`

**Files:**
- Create: `src/geo/rules/gate.py`
- Test: `tests/test_rules_gate.py`

**Interfaces:**
- Consumes: Task 5 `collect_evidence` 输出元素形状。
- Produces: `evaluate(candidates: list[dict], existing: list[dict], week: int, signal_target: dict[str, str]) -> list[EntryDecision]`;`EntryDecision` 字段 `signal/kind/target/status/change/evidence`;`evidence` 含 `history: [{week, with_n, unique_n, share, platforms}]`(累积,同周幂等去重;全部唯一 URL 口径,v1.1)。Task 8 消费。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rules_gate.py
from geo.rules.gate import evaluate, ACTIVATE_UNIQUE_N, ACTIVATE_SHARE

TGT = {"has_breadcrumblist": "schema", "faq_block_count": "citability"}
W1_ADD = {"signal": "has_breadcrumblist", "kind": "signal_add", "bucket": "schema.BreadcrumbList",
          "with_n": 7, "unique_n": 34, "platforms": ["doubao", "qwen", "zhipu"], "share": 0.2059}
W1_RM = {"signal": "faq_block_count", "kind": "signal_remove", "bucket": "formats.qa",
         "with_n": 0, "unique_n": 34, "platforms": [], "share": 0.0}

def test_add_promotes_when_gate_met():
    out = evaluate([W1_ADD], [], 1, TGT)
    d = out[0]
    assert d.status == "active" and d.change == "promoted" and d.target == "schema"
    assert d.evidence["history"][-1]["week"] == 1

def test_add_stays_draft_when_boundary_fails():
    just_under = {**W1_ADD, "with_n": 5, "share": 0.149}             # share 0.149 < 0.15
    d = evaluate([just_under], [], 1, TGT)[0]
    assert d.status == "draft" and d.change == "draft"
    small_n = {**W1_ADD, "unique_n": 29, "with_n": 29}              # unique 29 < 30(share=1)
    d2 = evaluate([small_n], [], 1, TGT)[0]
    assert d2.status == "draft"

def test_add_rejected_needs_two_zero_weeks():
    d1 = evaluate([W1_ADD], [], 1, TGT)[0]                          # 正常转正
    active = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
               "status": "active", "evidence": d1.evidence}]
    zero = {**W1_ADD, "with_n": 0, "share": 0.0, "platforms": []}
    d2 = evaluate([zero], active, 2, TGT)[0]                        # 第 1 周零 → 仍 active
    assert d2.status == "active"
    active2 = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
                "status": "active", "evidence": d2.evidence}]
    d3 = evaluate([zero], active2, 3, TGT)[0]                       # 第 2 周零 → rejected
    assert d3.status == "rejected" and d3.change == "rejected"

def test_retire_needs_two_failing_weeks():
    weak = {**W1_ADD, "with_n": 5, "share": 0.149, "platforms": ["qwen"]}
    d1 = evaluate([weak], [], 1, TGT)[0]                            # draft(不达标)
    entry = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
              "status": "active", "evidence": {"history": [
                  {"week": 0, "with_n": 7, "unique_n": 34, "share": 0.206,
                   "platforms": ["qwen", "zhipu"]}]}}]
    d2 = evaluate([weak], entry, 1, TGT)[0]                         # 跌破第 1 周 → 仍 active
    assert d2.status == "active"
    entry2 = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
               "status": "active", "evidence": d2.evidence}]
    d3 = evaluate([weak], entry2, 2, TGT)[0]                        # 跌破第 2 周 → retired
    assert d3.status == "retired" and d3.change == "retired"

def test_remove_needs_two_negative_weeks():
    d1 = evaluate([W1_RM], [], 1, TGT)[0]                           # 首周 → draft
    assert d1.status == "draft" and d1.kind == "signal_remove"
    d2 = evaluate([W1_RM], [{"signal": "faq_block_count", "type": "signal_remove",
                             "target": "citability", "status": "draft",
                             "evidence": d1.evidence}], 2, TGT)[0]  # 次周 → active(移除生效)
    assert d2.status == "active" and d2.change == "promoted"

def test_existing_without_candidate_kept_unchanged():
    orphan = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
               "status": "draft", "evidence": {"history": []}}]
    out = evaluate([], orphan, 5, TGT)                              # 本周无候选(数据缺失)
    assert out[0].change == "unchanged" and out[0].status == "draft"

def test_same_week_rerun_idempotent():
    d1 = evaluate([W1_ADD], [], 1, TGT)[0]
    d1b = evaluate([W1_ADD], [{"signal": "has_breadcrumblist", "type": "signal_add",
                               "target": "schema", "status": "active",
                               "evidence": d1.evidence}], 1, TGT)[0]
    assert len(d1b.evidence["history"]) == 1 and d1b.change == "unchanged"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_rules_gate.py -q`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现**

```python
# src/geo/rules/gate.py
"""条目门槛状态机:纯确定性。阈值常数集中于此,可调。"""
from __future__ import annotations
from dataclasses import dataclass

ACTIVATE_UNIQUE_N = 30   # 唯一 URL(页-周)口径;每周抽样 top-N≈30–50(v1.1,原出现口径 100 已弃)
ACTIVATE_SHARE = 0.15
ACTIVATE_PLATFORMS = 2
REJECT_WEEKS = 2      # 连续负证据周数(add→rejected / remove→active)
RETIRE_WEEKS = 2      # 现役 add 条目连续跌破门槛周数 → retired


@dataclass
class EntryDecision:
    signal: str
    kind: str            # signal_add | signal_remove
    target: str
    status: str          # draft | active | rejected | retired
    change: str          # promoted | rejected | retired | draft | stays_draft | unchanged
    evidence: dict       # {bucket, history: [...], weeks, share, unique_n, platforms}


def _meets(h: dict) -> bool:
    return (h["unique_n"] >= ACTIVATE_UNIQUE_N
            and h["share"] >= ACTIVATE_SHARE
            and len(h.get("platforms", [])) >= ACTIVATE_PLATFORMS)


def _negative(h: dict) -> bool:
    return h["share"] == 0 and h["unique_n"] >= ACTIVATE_UNIQUE_N


def evaluate(candidates: list[dict], existing: list[dict], week: int,
             signal_target: dict[str, str]) -> list[EntryDecision]:
    by_signal = {e["signal"]: e for e in existing}
    out: list[EntryDecision] = []
    for cand in candidates:
        sig, kind = cand["signal"], cand["kind"]
        target = signal_target[sig]
        prev = by_signal.get(sig) or {}
        prev_status = prev.get("status", "new")
        hist = [h for h in (prev.get("evidence", {}) or {}).get("history", [])
                if h.get("week") != week]                       # 同周重跑幂等
        cur = {"week": week, "with_n": cand["with_n"], "unique_n": cand["unique_n"],
               "share": cand["share"], "platforms": list(cand["platforms"])}
        hist.append(cur)
        ev = {"bucket": cand["bucket"], "history": hist,
              "weeks": [h["week"] for h in hist],
              "share": cur["share"], "unique_n": cur["unique_n"],
              "platforms": cur["platforms"]}
        tail = hist[-REJECT_WEEKS:]

        if kind == "signal_add" and prev_status == "active":
            ftail = hist[-RETIRE_WEEKS:]
            if len(ftail) >= RETIRE_WEEKS and all(not _meets(h) for h in ftail):
                out.append(EntryDecision(sig, kind, target, "retired", "retired", ev))
                continue

        if kind == "signal_remove":
            if len(tail) >= REJECT_WEEKS and all(_negative(h) for h in tail):
                ch = "unchanged" if prev_status == "active" else "promoted"
                out.append(EntryDecision(sig, kind, target, "active", ch, ev))
            else:
                ch = "stays_draft" if prev_status == "draft" else "draft"
                out.append(EntryDecision(sig, kind, target, "draft", ch, ev))
            continue

        if len(tail) >= REJECT_WEEKS and all(_negative(h) for h in tail):
            out.append(EntryDecision(sig, kind, target, "rejected", "rejected", ev))
            continue
        if _meets(cur):
            ch = "unchanged" if prev_status == "active" else "promoted"
            out.append(EntryDecision(sig, kind, target, "active", ch, ev))
            continue
        ch = "stays_draft" if prev_status == "draft" else "draft"
        out.append(EntryDecision(sig, kind, target, "draft", ch, ev))

    cand_sigs = {c["signal"] for c in candidates}
    for e in existing:                                         # 本周无候选 → 原样保留
        if e["signal"] not in cand_sigs:
            out.append(EntryDecision(e["signal"], e.get("type", "signal_add"),
                                     e.get("target", ""), e.get("status", "draft"),
                                     "unchanged", e.get("evidence", {})))
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3.11 -m pytest tests/test_rules_gate.py -q`
Expected: PASS(7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/geo/rules/gate.py tests/test_rules_gate.py
git commit -m "feat(rules): evidence-gate state machine (draft/active/rejected/retired)"
```

---

### Task 7: 权重公式 `weights.py`

**Files:**
- Create: `src/geo/rules/weights.py`
- Test: `tests/test_rules_weights.py`

**Interfaces:**
- Consumes: Task 5 `dimension_strengths` 返回形状;上期 `rules_iteration.json` 的 `dimension_strengths`(keeper 注入,v1.1)。
- Produces: `compute_deltas(strengths, weights) -> dict[str, int]`(空 dict = 无变更);`persisted_deltas(strengths, prev_strengths, weights) -> dict[str, int]`(**v1.1:2 周同向持续性**——本期与上期 delta 同号才保留;prev 缺失 → {});`apply_deltas(weights, deltas) -> dict[str, int]`(和恰 100)。Task 8 消费。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rules_weights.py
import pytest
from geo.rules.weights import compute_deltas, persisted_deltas, apply_deltas, STEP, W_MIN, W_MAX
from geo.rules.loader import assert_normalized
import types

W = {"citability": 25, "brand": 20, "eeat": 20, "technical_geo": 15, "schema": 10, "platform": 10}
S_W1 = {"citability": 0.657, "schema": 7/34, "brand": (0.133 + 0.0887)/2,
        "eeat": None, "technical_geo": None, "platform": None}

def test_raw_delta_computation():
    d = compute_deltas(S_W1, W)                                # 数学不变(出现口径数值仅参考)
    assert d.get("citability") == 1 and d.get("brand") == -1
    nw = apply_deltas(W, d)
    assert nw == {**W, "citability": 26, "brand": 19}
    assert_normalized(types.SimpleNamespace(composite="geo", weights=nw))   # 和恰 100

def test_first_week_persistence_gate_blocks():
    assert persisted_deltas(S_W1, None, W) == {}               # v1.1:首周无上期 → 不调权

def test_second_week_same_direction_applies():
    prev = {**S_W1, "citability": 0.65, "schema": 0.15, "brand": 0.11}
    d = persisted_deltas(S_W1, prev, W)
    assert d.get("citability") == 1 and d.get("brand") == -1   # 两周同向 → 通过
    assert sum(apply_deltas(W, d).values()) == 100

def test_direction_flip_not_applied():
    prev = {**S_W1, "citability": 0.05, "schema": 0.9, "brand": 0.4}
    d = persisted_deltas(S_W1, prev, W)                        # 上期 citability 向下、本期向上
    assert "citability" not in d and "brand" not in d          # 反向维度被持续性门挡下

def test_all_zero_no_change():
    s = {"citability": 0.5, "schema": 0.5, "brand": 0.5,
         "eeat": None, "technical_geo": None, "platform": None}
    assert compute_deltas(s, W) == {}

def test_no_streams_no_change():
    assert compute_deltas({k: None for k in W}, W) == {}

def test_step_cap_and_clamp():
    extreme = {"citability": 1.0, "schema": 0.0, "brand": 0.0,
               "eeat": None, "technical_geo": None, "platform": None}
    d = compute_deltas(extreme, W)
    assert all(abs(v) <= STEP for v in d.values())             # 步长 ≤3
    nw = apply_deltas(W, d)
    assert all(W_MIN <= v <= W_MAX for v in nw.values())
    assert sum(nw.values()) == 100                              # 归一恒真

def test_clamp_collision_still_sums_100():
    # platform(10) 若被连续压到 5 后再压:clamp 保 5,余量由其他维度消化
    w2 = {"a": 35, "b": 5, "c": 20, "d": 20, "e": 10, "f": 10}
    d = {"a": 3, "b": -3, "c": 0, "d": 0, "e": 0, "f": 0}      # b 5-3=2 <W_MIN → clamp 5
    nw = apply_deltas(w2, d)
    assert nw["b"] == W_MIN and sum(nw.values()) == 100
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_rules_weights.py -q`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现**

```python
# src/geo/rules/weights.py
"""权重证据强度公式:delta = round(STEP*(S_i - S̄)),夹值 [W_MIN,W_MAX],
最大余数式归一到恰好 100(确定性:按 |原始delta| 降序、同名 ASCII 升序消化余量)。
v1.1:persisted_deltas 施加 2 周同向持续性——观察性证据无对照基线,单周方向不作数。"""
from __future__ import annotations

STEP = 3
W_MIN = 5
W_MAX = 35


def compute_deltas(strengths: dict[str, float | None], weights: dict[str, int]) -> dict[str, int]:
    vals = {k: v for k, v in strengths.items() if v is not None and k in weights}
    if not vals:
        return {}
    mean = sum(vals.values()) / len(vals)
    deltas = {k: round(STEP * (v - mean)) for k, v in vals.items()}
    return {k: v for k, v in deltas.items() if v != 0} or {}


def persisted_deltas(strengths: dict[str, float | None],
                     prev_strengths: dict[str, float | None] | None,
                     weights: dict[str, int]) -> dict[str, int]:
    """v1.1:2 周同向持续性——本期与上期 delta 同号才 apply;首周(prev=None)只记录不调权。"""
    if not prev_strengths:
        return {}
    cur = compute_deltas(strengths, weights)
    prev = compute_deltas(prev_strengths, weights)
    return {k: v for k, v in cur.items() if k in prev and (v > 0) == (prev[k] > 0)}


def _clamp(w: int) -> int:
    return max(W_MIN, min(W_MAX, w))


def apply_deltas(weights: dict[str, int], deltas: dict[str, int]) -> dict[str, int]:
    raw = {k: weights[k] + deltas.get(k, 0) for k in weights}
    out = {k: _clamp(v) for k, v in raw.items()}
    diff = 100 - sum(out.values())
    if diff:
        # 按 |原始 delta| 降序、名升序逐维度 ±1,直到和恰 100(跳过已到边界的维度)
        order = sorted(out, key=lambda k: (-abs(deltas.get(k, 0)), k))
        step = 1 if diff > 0 else -1
        i = 0
        while diff != 0 and order:
            k = order[i % len(order)]
            if W_MIN <= out[k] + step <= W_MAX:
                out[k] += step
                diff -= step
            i += 1
            if i > 1000:      # 安全阀(理论不可达:总夹值区间 [6*5,6*35] 含 100)
                break
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3.11 -m pytest tests/test_rules_weights.py -q`
Expected: PASS(8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/geo/rules/weights.py tests/test_rules_weights.py
git commit -m "feat(rules): evidence-strength weight formula (step cap, clamp, exact-100 renorm)"
```

---

### Task 8: 迭代编排 `keeper.py`(归档/升版/changelog/rules_iteration)

**Files:**
- Create: `src/geo/rules/keeper.py`
- Test: `tests/test_rules_keeper.py`(tmp repo + Task 4 fixture)

**Interfaces:**
- Consumes: Task 2 `load_rules`;Task 5 `collect_evidence/dimension_strengths`;Task 6 `evaluate/EntryDecision`;Task 7 `persisted_deltas/apply_deltas`(v1.1:持续性门);Task 1 注册表(校验)。
- Produces: `iterate(week: int, *, repo: Path = REPO) -> dict`——返回即写入 `data/analysis/wN/rules_iteration.json` 的 dict:`{week, from_version, to_version|None, entries: [...], weights_before, weights_after, dimension_strengths, observations}`(strengths 供次周持续性对照,v1.1)。副作用:升版时归档旧 YAML → `rules/history/{旧版本}/`(含 `manifest.json` 绑 code_commit,v1.1)、写新 `{geo,seo}-rules.yaml`、追加 `rules/changelog.md`、更新 `run.yaml` 的 `rule_version`。Task 9 CLI / Task 12 rules 节点调用。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rules_keeper.py
import json, yaml
from pathlib import Path
import geo.rules.keeper as K
from geo.rules.keeper import iterate, SIGNAL_TARGET

def _mk_repo(tmp_path):
    repo = tmp_path / "repo"; (repo / "rules").mkdir(parents=True)
    (repo / "data" / "analysis" / "w1").mkdir(parents=True)
    fix = Path(__file__).parent / "fixtures" / "rules"
    for f in ("research_aggregates.json", "eval_report.json"):
        (repo / "data" / "analysis" / "w1" / f).write_text((fix / f).read_text(encoding="utf-8"))
    (repo / "rules" / "geo-rules.yaml").write_text((fix / "geo_rules_v1.yaml").read_text())
    (repo / "rules" / "seo-rules.yaml").write_text((fix / "seo_rules_v1.yaml").read_text())
    (repo / "rules" / "changelog.md").write_text("# Rules changelog\n")
    (repo / "run.yaml").write_text(yaml.safe_dump(
        {"week": 1, "mode": "audit", "scope": "core", "runs": 1,
         "rule_version": "geo-seo-v1", "providers": ["qwen"]}, sort_keys=False))
    return repo

def test_iterate_w1_promotes_breadcrumblist_weights_hold(tmp_path):
    repo = _mk_repo(tmp_path)
    it = iterate(1, repo=repo)
    assert it["from_version"] == "geo-seo-v1" and it["to_version"] == "geo-seo-v2"
    st = {e["signal"]: e["status"] for e in it["entries"]}
    assert st["has_breadcrumblist"] == "active"            # 唯一口径 7/34=20.6%、3 家 → 转正
    assert st["faq_block_count"] == "draft"                # 0/34 首周 → 草稿(移除需 2 周)
    assert it["weights_after"] == it["weights_before"]     # v1.1:首周持续性门槛 → 权重不动
    assert it["dimension_strengths"]["schema"] == round(7 / 34, 4)   # strengths 已记录供次周
    # 归档(含 manifest)+ 新文件 + run.yaml + changelog + rules_iteration.json
    assert (repo / "rules" / "history" / "geo-seo-v1" / "geo-rules.yaml").exists()
    assert (repo / "rules" / "history" / "geo-seo-v1" / "manifest.json").exists()
    new_geo = yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text())
    assert new_geo["version"] == "geo-seo-v2"
    assert "has_breadcrumblist" in new_geo["signals"]["schema"]      # membership 生效
    assert sum(new_geo["weights"].values()) == 100
    assert yaml.safe_load((repo / "run.yaml").read_text())["rule_version"] == "geo-seo-v2"
    cl = (repo / "rules" / "changelog.md").read_text()
    assert "geo-seo-v2" in cl and "has_breadcrumblist" in cl
    ri = json.loads((repo / "data" / "analysis" / "w1" / "rules_iteration.json").read_text())
    assert ri["to_version"] == "geo-seo-v2"
    # seo 文件只升版本号,结构不变
    new_seo = yaml.safe_load((repo / "rules" / "seo-rules.yaml").read_text())
    assert new_seo["version"] == "geo-seo-v2" and "entries" in new_seo

def test_iterate_no_change_no_bump(tmp_path):
    repo = _mk_repo(tmp_path)
    ana = repo / "data" / "analysis" / "w1"
    agg = json.loads((ana / "research_aggregates.json").read_text())
    for b in agg["formats"]:
        b["unique_cited_n"] = 17; b["unique_n"] = 34; b["unique_platforms"] = ["qwen", "zhipu"]
    agg["sources"]["schema_unique"] = {"BreadcrumbList": 17}
    (ana / "research_aggregates.json").write_text(json.dumps(agg, ensure_ascii=False))
    ev = json.loads((ana / "eval_report.json").read_text())
    ev["gap"]["metrics"]["mention_rate"] = 0.5             # 三个证据流全部 = 0.5
    ev["gap"]["metrics"]["citation_rate"] = 0.5            # → raw deltas 全 0
    (ana / "eval_report.json").write_text(json.dumps(ev, ensure_ascii=False))
    it1 = iterate(1, repo=repo)                            # 首轮:breadcrumblist 转正 → v2(权重不动)
    assert it1["to_version"] == "geo-seo-v2"
    it2 = iterate(1, repo=repo)                            # 同周重跑 → 幂等,无变更不升版
    assert it2["to_version"] is None
    assert yaml.safe_load((repo / "run.yaml").read_text())["rule_version"] == "geo-seo-v2"
```

fixture 需两份 v1 YAML 拷贝——Step 2 从真实 `rules/` 拷入 `tests/fixtures/rules/{geo_rules_v1.yaml, seo_rules_v1.yaml}`。

- [ ] **Step 2: 准备 fixture**

```bash
cp rules/geo-rules.yaml tests/fixtures/rules/geo_rules_v1.yaml
cp rules/seo-rules.yaml tests/fixtures/rules/seo_rules_v1.yaml
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_rules_keeper.py -q`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 4: 实现 keeper.py**

```python
# src/geo/rules/keeper.py
"""RulesKeeper 单轮迭代:证据 → 门槛 → 权重 → 归档/升版/changelog/run.yaml。
纯确定性、零 LLM;升版自动(v1.1),人可在 changelog/files 事后回滚。"""
from __future__ import annotations
import json, shutil
from datetime import date
from pathlib import Path
import yaml
from geo.shared.config import REPO
from geo.assess.registry import GEO_SIGNALS, SEO_SIGNALS
from geo.rules.evidence import collect_evidence, dimension_strengths
from geo.rules.gate import evaluate
from geo.rules.weights import persisted_deltas, apply_deltas

# signal → 目标维度(候选必须已在注册表)
SIGNAL_TARGET = {"has_breadcrumblist": "schema", "faq_block_count": "citability"}


def _bump(v: str) -> str:
    return f"geo-seo-v{int(v.rsplit('v', 1)[1]) + 1}"


def _git_head(repo: Path) -> str:
    """归档绑定代码(v1.1):recalc 精确性 = 版本↔commit + 黄金锁。非 git 环境(测试 tmp)→ unknown。"""
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _converge_membership(signals: dict, decisions) -> dict:
    """按条目终态收敛 membership(幂等):
    add+active → 在;add rejected/retired → 不在;remove+active → 不在;remove 其他 → 不动。"""
    sig = {k: list(v) for k, v in signals.items()}
    for d in decisions:
        t = d.target
        if t not in sig:
            continue
        if d.kind == "signal_add":
            if d.status == "active":
                if d.signal not in sig[t]:
                    sig[t].append(d.signal)
            else:                                   # draft/rejected/retired 一律不在成员里
                sig[t] = [s for s in sig[t] if s != d.signal]
        elif d.kind == "signal_remove" and d.status == "active":
            sig[t] = [s for s in sig[t] if s != d.signal]
    return sig


def _entries_yaml(decisions, week, new_version, prev_map: dict) -> list[dict]:
    out = []
    for d in decisions:
        prev = prev_map.get(d.signal) or {}
        # since_version:状态首次离开 draft 时记录;状态不变则沿用旧值
        if prev.get("status") == d.status and prev.get("since_version"):
            since = prev["since_version"]
        elif d.status == "draft":
            since = None
        else:
            since = new_version
        out.append({
            "id": f"{'add' if d.kind == 'signal_add' else 'remove'}-{d.signal}",
            "type": d.kind, "target": d.target, "signal": d.signal, "status": d.status,
            "statement": (f"{d.evidence.get('bucket', '')} 被检索源唯一页 share "
                          f"{d.evidence.get('share', 0.0):.1%} "
                          f"(unique_n={d.evidence.get('unique_n', 0)}, "
                          f"platforms={len(d.evidence.get('platforms', []))})"),
            "evidence": d.evidence,
            "since_version": since,
            "decided_at_week": week,
        })
    return out


def render_changelog(week: int, from_v: str, to_v: str | None, decisions,
                     w_before: dict, w_after: dict, observations: list[str]) -> str:
    L = [f"\n## {to_v or from_v} — {date.today().isoformat()} (week {week})"]
    if to_v is None:
        L.append("- 无变更(证据/权重均未达调整条件);version 不变。")
    else:
        L.append(f"- version: {from_v} → {to_v}(本周评分用 {from_v},变更自下周生效)")
        for d in decisions:
            if d.change in ("promoted", "rejected", "retired", "draft"):
                L.append(f"- entry {d.signal} [{d.kind}→{d.target}]: {d.change} "
                         f"(share={d.evidence.get('share', 0.0):.1%}, "
                         f"unique_n={d.evidence.get('unique_n', 0)}, "
                         f"platforms={len(d.evidence.get('platforms', []))})")
        if w_after != w_before:
            L.append("- weights: " + ", ".join(
                f"{k} {w_before[k]}→{w_after[k]}" for k in w_before if w_before[k] != w_after.get(k)))
        L.append(f"- rollback: python3.11 -m geo.rules.run rollback --to {from_v}")
    for o in observations:
        L.append(f"- 观察: {o}")
    return "\n".join(L) + "\n"


def iterate(week: int, *, repo: Path = REPO) -> dict:
    repo = Path(repo)
    ana = repo / "data" / "analysis" / f"w{week}"
    agg = json.loads((ana / "research_aggregates.json").read_text(encoding="utf-8"))
    evalrep = json.loads((ana / "eval_report.json").read_text(encoding="utf-8"))

    geo_raw = yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text(encoding="utf-8"))
    seo_raw = yaml.safe_load((repo / "rules" / "seo-rules.yaml").read_text(encoding="utf-8"))
    for e in (*SIGNAL_TARGET,):
        assert e in GEO_SIGNALS or e in SEO_SIGNALS, f"候选 {e} 不在注册表"

    candidates = collect_evidence(agg)
    decisions = evaluate(candidates, geo_raw.get("entries", []), week, SIGNAL_TARGET)

    strengths = dimension_strengths(agg, evalrep)
    prev_ri = repo / "data" / "analysis" / f"w{week - 1}" / "rules_iteration.json"
    prev_strengths = (json.loads(prev_ri.read_text(encoding="utf-8")).get("dimension_strengths")
                      if prev_ri.exists() else None)
    deltas = persisted_deltas(strengths, prev_strengths, geo_raw["weights"])   # v1.1:2 周同向
    w_before = dict(geo_raw["weights"])
    w_after = apply_deltas(w_before, deltas) if deltas else w_before

    changed = any(d.change in ("promoted", "rejected", "retired", "draft") for d in decisions) \
        or bool(deltas)
    from_v = geo_raw["version"]
    to_v = _bump(from_v) if changed else None

    observations = ["SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠",
                    "证据口径 = 被检索源唯一 URL(页-周);观察性相关、无未检索对照组",
                    "权重调整施加 2 周同向持续性门(v1.1)"]
    if not deltas and any(v is not None for v in strengths.values()):
        observations.append("GEO 权重证据已记录(dimension_strengths),待与上期同向后调整(首周或方向反转)")

    if changed:
        hist_dir = repo / "rules" / "history" / from_v
        hist_dir.mkdir(parents=True, exist_ok=True)
        for f in ("geo-rules.yaml", "seo-rules.yaml"):
            shutil.copy2(repo / "rules" / f, hist_dir / f)
        manifest = {"code_commit": _git_head(repo), "week": week,
                    "archived_at": date.today().isoformat()}          # v1.1:版本↔代码绑定
        (hist_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    new_signals = _converge_membership(geo_raw.get("signals", {}), decisions)
    if to_v:
        geo_raw.update({"version": to_v, "weights": w_after, "signals": new_signals,
                        "entries": _entries_yaml(decisions, week, to_v,
                                                  {e["signal"]: e for e in geo_raw.get("entries", [])})})
        seo_raw.update({"version": to_v})
        (repo / "rules" / "geo-rules.yaml").write_text(
            yaml.safe_dump(geo_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        (repo / "rules" / "seo-rules.yaml").write_text(
            yaml.safe_dump(seo_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        run_raw = yaml.safe_load((repo / "run.yaml").read_text(encoding="utf-8"))
        run_raw["rule_version"] = to_v
        (repo / "run.yaml").write_text(
            yaml.safe_dump(run_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")

    with (repo / "rules" / "changelog.md").open("a", encoding="utf-8") as f:
        f.write(render_changelog(week, from_v, to_v, decisions, w_before, w_after, observations))

    iteration = {
        "week": week, "from_version": from_v, "to_version": to_v,
        "entries": [{"signal": d.signal, "type": d.kind, "target": d.target,
                     "status": d.status, "change": d.change,
                     "evidence": {"bucket": d.evidence.get("bucket"),
                                  "share": d.evidence.get("share"),
                                  "with_n": d.evidence.get("with_n"),
                                  "unique_n": d.evidence.get("unique_n"),
                                  "platforms": d.evidence.get("platforms"),
                                  "weeks": d.evidence.get("weeks", [])}}
                    for d in decisions],
        "weights_before": w_before, "weights_after": w_after if changed else w_before,
        "dimension_strengths": {k: (round(v, 4) if v is not None else None)
                                for k, v in strengths.items()},          # v1.1:供次周持续性对照
        "observations": observations,
    }
    ana.mkdir(parents=True, exist_ok=True)
    (ana / "rules_iteration.json").write_text(
        json.dumps(iteration, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return iteration
```

注:同周幂等重跑的判定依赖 gate 的 history 去重 + `change=unchanged/stays_draft` → 第二次 `changed=False` → 不升版,只追加"无变更"changelog 行与重写 rules_iteration.json(内容一致)。

- [ ] **Step 5: 跑测试确认通过**

Run: `python3.11 -m pytest tests/test_rules_keeper.py -q`
Expected: PASS(2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/geo/rules/keeper.py tests/test_rules_keeper.py tests/fixtures/rules/geo_rules_v1.yaml tests/fixtures/rules/seo_rules_v1.yaml
git commit -m "feat(rules): keeper iteration orchestration (archive/version/changelog/run.yaml/rules_iteration.json)"
```

---

### Task 9: recalc 注入 + CLI(iterate/recalc/rollback/show)

**Files:**
- Modify: `src/geo/assess/analyst.py`(`assemble` 增可选参数)
- Create: `src/geo/rules/run.py`
- Test: `tests/test_rules_run.py`

**Interfaces:**
- Consumes: Task 2 `load_rules(version=)`;Task 8 `iterate`。
- Produces: `assemble(week, *, rules_geo=None, rules_seo=None, out_name="eval_report.json", rule_version=None) -> dict`(向后兼容);CLI `python3.11 -m geo.rules.run iterate|recalc|rollback|show`。Task 12 rules 节点用 `iterate`;报告变体 `report.recalc-{v}.html`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rules_run.py
import json, yaml
from pathlib import Path
import pytest
from geo.rules.run import do_recalc, do_rollback

@pytest.fixture
def repo(tmp_path):
    """v1 归档 + v2 当前(模拟 Task 8 迭代后状态)。"""
    r = tmp_path / "repo"
    fix = Path(__file__).parent / "fixtures" / "rules"
    for sub in ("rules", "rules/history/geo-seo-v1", "data/analysis/w1", "data/raw/w1/r0"):
        (r / sub).mkdir(parents=True, exist_ok=True)
    (r / "rules" / "geo-rules.yaml").write_text((fix / "geo_rules_v1.yaml").read_text())
    (r / "rules" / "seo-rules.yaml").write_text((fix / "seo_rules_v1.yaml").read_text())
    v1 = yaml.safe_load((fix / "geo_rules_v1.yaml").read_text())
    v2 = dict(v1); v2["version"] = "geo-seo-v2"
    v2["weights"] = {**v1["weights"], "citability": 26, "brand": 19}
    (r / "rules" / "geo-rules.yaml").write_text(yaml.safe_dump(v2, sort_keys=False))
    (r / "rules" / "history" / "geo-seo-v1" / "geo-rules.yaml").write_text(
        (fix / "geo_rules_v1.yaml").read_text())
    (r / "rules" / "history" / "geo-seo-v1" / "seo-rules.yaml").write_text(
        (fix / "seo_rules_v1.yaml").read_text())
    (r / "rules" / "changelog.md").write_text("# Rules changelog\n")
    (r / "run.yaml").write_text(yaml.safe_dump(
        {"week": 1, "mode": "audit", "scope": "core", "runs": 1,
         "rule_version": "geo-seo-v2", "providers": ["qwen"]}, sort_keys=False))
    return r

def test_rollback_creates_new_monotonic_version(repo):
    do_rollback(repo, "geo-seo-v1")
    g = yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text())
    assert g["version"] == "geo-seo-v3"                    # v1.1:不倒退到 v1,产新单调版本
    assert g["restores"] == "geo-seo-v1"                   # 内容 = v1 快照
    assert g["weights"]["citability"] == 25                # (v2 的 26 不残留)
    assert yaml.safe_load((repo / "run.yaml").read_text())["rule_version"] == "geo-seo-v3"
    assert (repo / "rules" / "history" / "geo-seo-v2" / "geo-rules.yaml").exists()  # 现行 v2 先归档
    assert "rollback" in (repo / "rules" / "changelog.md").read_text()

def test_recalc_writes_separate_file_never_overwrites(repo, monkeypatch):
    ana = repo / "data" / "analysis" / "w1"
    (ana / "eval_report.json").write_text('{"self_geo": {"total": 50.0}}')
    called = {}
    def fake_assemble(week, **kw):
        called.update(kw); return {"self_geo": {"total": 47.6}, "rule_version": kw.get("rule_version")}
    import geo.rules.run as R
    monkeypatch.setattr(R, "assemble", fake_assemble)
    out = do_recalc(repo, week=1, rule_version="geo-seo-v1", render=False)
    assert called["rule_version"] == "geo-seo-v1" and called["out_name"] == "eval_report.recalc-geo-seo-v1.json"
    assert out["rule_version"] == "geo-seo-v1"
    assert (ana / "eval_report.recalc-geo-seo-v1.json").exists()
    assert json.loads((ana / "eval_report.json").read_text())["self_geo"]["total"] == 50.0  # 原件未动
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_rules_run.py -q`
Expected: FAIL `ModuleNotFoundError: geo.rules.run`

- [ ] **Step 3: 改 analyst.assemble(向后兼容注入)**

在 `analyst.py` 中:签名改为

```python
def assemble(week: int, *, rules_geo=None, rules_seo=None,
             out_name: str = "eval_report.json", rule_version: str | None = None) -> dict:
```

函数体内三处替换:`rule_version = rule_version or settings.run.rule_version`;`score_geo(brand_l3, brand_metrics, static_signals)` → 末尾加 `, rules=rules_geo`;`score_seo(page_data, gsc_snapshot, content_signals)` → 末尾加 `, rules=rules_seo`。报告落盘路径中文件名改用 `out_name`(搜索 `eval_report.json` 的写入处替换;`data/raw` 读取逻辑不变)。其余不动。

- [ ] **Step 4: 实现 CLI**

```python
# src/geo/rules/run.py
"""RulesKeeper CLI:iterate / recalc / rollback / show。零 LLM。"""
from __future__ import annotations
import json, shutil
from pathlib import Path
import yaml
from geo.shared.config import REPO, settings
from geo.rules.keeper import iterate
from geo.assess.analyst import assemble


def do_recalc(repo: Path, week: int, rule_version: str, render: bool = False) -> dict:
    from geo.rules.loader import load_rules
    rg = load_rules("geo", version=rule_version)
    rs = load_rules("seo", version=rule_version)
    rep = assemble(week, rules_geo=rg, rules_seo=rs,
                   out_name=f"eval_report.recalc-{rule_version}.json",
                   rule_version=rule_version)
    if render:
        from geo.report.reporter import render as _render
        out = repo / "reports" / f"w{week}" / f"report.recalc-{rule_version}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        _render(rep, out)
        print(out)
    return rep


def _known_versions(repo: Path) -> list[str]:
    vers = [yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text(encoding="utf-8"))["version"]]
    hist = repo / "rules" / "history"
    if hist.exists():
        vers += [d.name for d in hist.iterdir() if d.is_dir()]
    return vers


def _next_version(repo: Path) -> str:
    ns = [int(v.rsplit("v", 1)[1]) for v in _known_versions(repo) if v.startswith("geo-seo-v")]
    return f"geo-seo-v{max(ns) + 1}"


def do_rollback(repo: Path, to_version: str) -> None:
    """v1.1:回滚 = 创建新单调版本(内容 = to_version 快照,restores 元数据),不倒退版本号。
    直接改回旧号会在下次迭代产出与 history/ 不可变归档同名不同容的版本 → recalc 语义歧义。"""
    src = repo / "rules" / "history" / to_version
    if not src.exists():
        raise SystemExit(f"历史版本不存在: {src}")
    cur_v = yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text(encoding="utf-8"))["version"]
    if cur_v == to_version:
        raise SystemExit(f"当前已是 {to_version},无需回滚")
    new_v = _next_version(repo)
    hist_cur = repo / "rules" / "history" / cur_v          # 现行版本先归档(若未归档)
    hist_cur.mkdir(parents=True, exist_ok=True)
    for f in ("geo-rules.yaml", "seo-rules.yaml"):
        shutil.copy2(repo / "rules" / f, hist_cur / f)
    for name in ("geo", "seo"):
        d = yaml.safe_load((src / f"{name}-rules.yaml").read_text(encoding="utf-8"))
        d["version"] = new_v
        d["restores"] = to_version
        (repo / "rules" / f"{name}-rules.yaml").write_text(
            yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
    run_raw = yaml.safe_load((repo / "run.yaml").read_text(encoding="utf-8"))
    run_raw["rule_version"] = new_v
    (repo / "run.yaml").write_text(
        yaml.safe_dump(run_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with (repo / "rules" / "changelog.md").open("a", encoding="utf-8") as fh:
        fh.write(f"\n## rollback — {new_v} restores {to_version}(现行 {cur_v} 已归档;不倒退版本号)\n")
    print(f"rolled back: {new_v} restores {to_version}")


def do_show(repo: Path) -> None:
    for name in ("geo", "seo"):
        d = yaml.safe_load((repo / "rules" / f"{name}-rules.yaml").read_text(encoding="utf-8"))
        print(f"[{name}] version={d['version']} weights={d['weights']} entries={len(d.get('entries', []))}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="geo.rules.run", description="P3 RulesKeeper CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("iterate"); p1.add_argument("--week", type=int, required=True)
    p2 = sub.add_parser("recalc"); p2.add_argument("--week", type=int, required=True)
    p2.add_argument("--rule-version", required=True); p2.add_argument("--render", action="store_true")
    p3 = sub.add_parser("rollback"); p3.add_argument("--to", required=True)
    sub.add_parser("show")
    a = ap.parse_args()
    if a.cmd == "iterate":
        print(json.dumps(iterate(a.week), ensure_ascii=False, indent=2))
    elif a.cmd == "recalc":
        do_recalc(REPO, a.week, a.rule_version, a.render)
    elif a.cmd == "rollback":
        do_rollback(REPO, a.to)
    else:
        do_show(REPO)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 跑测试 + 全量**

Run: `python3.11 -m pytest tests/test_rules_run.py tests/ -q`
Expected: 全 PASS(analyst 存量用例不受可选参数影响)

- [ ] **Step 6: Commit**

```bash
git add src/geo/rules/run.py src/geo/assess/analyst.py tests/test_rules_run.py
git commit -m "feat(rules): CLI iterate/recalc/rollback/show + assemble rules injection"
```

---

### Task 10: research 反哺 playbook(第 6 节 + header 修死值)

**Files:**
- Modify: `src/geo/research/run.py`、`src/geo/research/render.py`
- Test: `tests/test_render.py`(扩展)

**Interfaces:**
- Consumes: `data/analysis/w{N-1}/eval_report.json`(可选存在)、`content/published/`、`rules/changelog.md`、`settings.run.rule_version`。
- Produces: `render_playbook(conclusions, aggregates, week, feed: dict | None = None)`;`_collect_feed(week, repo) -> dict | None`(`{"published": [{slug, created}], "latest": {...}|None, "prev": {...}|None}`);header 的 rule_version 动态取(feed 或 settings)。playbook 末尾新增「6. 上期动作→指标对照」。Task 12 research 节点无需改 `run_research` 调用(内部自动采集 feed)。

- [ ] **Step 1: 写失败测试(追加 test_render.py)**

```python
def test_render_playbook_feedback_section():
    from geo.research.render import render_playbook
    from geo.research.models import FeatureAggregates
    agg = FeatureAggregates(week=1,
        coverage=type("C", (), {"total_l1": 45, "total_cited_sources": 1469, "l3_resolved": 134,
                                "l3_missing": 1315, "l3_js_only": 20})(),
        formats=[], sources={}, platforms={}, problem_space={})
    feed = {"published": [{"slug": "self-consumption", "created": "2026-08-18"}],
            "latest": {"week": 1, "mention_rate": 0.133, "citation_rate": 0.089,
                       "sov": 3.78, "self_geo": 47.6, "self_seo": 49.8},
            "prev": None, "rule_version": "geo-seo-v1"}
    md = render_playbook([], agg, 2, feed=feed)
    assert "## 6. 上期动作→指标对照" in md
    assert "self-consumption" in md and "47.6" in md and "首期" in md   # prev=None → 首期基线注
    md2 = render_playbook([], agg, 2, feed=None)
    assert "无对照" in md2

def test_render_playbook_rule_version_live():
    from geo.research.render import render_playbook
    from geo.research.models import FeatureAggregates
    from geo.shared.config import settings
    agg = FeatureAggregates(week=1,
        coverage=type("C", (), {"total_l1": 0, "total_cited_sources": 0, "l3_resolved": 0,
                                "l3_missing": 0, "l3_js_only": 0})(),
        formats=[], sources={}, platforms={}, problem_space={})
    md = render_playbook([], agg, 3, feed=None)
    header = md.split("\n")[1]
    assert f"rule_version {settings.run.rule_version}" in header   # 动态读,不再硬编码
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_render.py -q`
Expected: FAIL `TypeError: render_playbook() got an unexpected keyword argument 'feed'`

- [ ] **Step 3: 实现**

`render.py`:

```python
def _feedback_section(feed: dict | None) -> list[str]:
    if not feed:
        return ["\n## 6. 上期动作→指标对照", "- 无对照(数据缺失)。"]
    L = ["\n## 6. 上期动作→指标对照"]
    pub = feed.get("published") or []
    if pub:
        L.append("- 上期发布: " + "; ".join(f"{p['slug']}({p['created']})" for p in pub))
    else:
        L.append("- 上期发布: 无")
    lat, prev = feed.get("latest"), feed.get("prev")
    def row(k, label):
        if lat is None:
            return f"- {label}: 无数据"
        v = lat[k]
        if prev:
            return f"- {label}: {v} → 前期 {prev[k]}(Δ{round(v - prev[k], 1):+})"
        return f"- {label}: {v}(首期基线,无环比)"
    L += [row("mention_rate", "mention_rate"), row("citation_rate", "citation_rate"),
          row("sov", "sov"), row("self_geo", "self_geo"), row("self_seo", "self_seo")]
    L.append(f"- 规则版本: {feed.get('rule_version', '—')}")
    L.append("- ⚠️ 收录有延迟、单周样本小;对照为观察性相关,非因果归因。")
    return L
```

`render_playbook` 签名加 `feed: dict | None = None`;header 行 `f"> rule_version geo-seo-v1 | ..."` 改为动态取值(feed 携带则用之,否则懒加载当前 `settings.run.rule_version`,与存量测试期望一致):

```python
def _rule_version(feed: dict | None) -> str:
    rv = (feed or {}).get("rule_version")
    if rv:
        return rv
    from geo.shared.config import settings
    return settings.run.rule_version
```

header 行用 `f"> rule_version {_rule_version(feed)} | ..."`;列表末尾 `L += _feedback_section(feed)`。

`run.py` 增采集函数并在 `run_research` 里调用、传给 render:

```python
def _collect_feed(week: int, repo: Path) -> dict | None:
    """确定性反哺输入:上期 eval_report + 已发布清单 + 当前规则版本。零 Kimi。"""
    def _metrics(w):
        p = repo / "data" / "analysis" / f"w{w}" / "eval_report.json"
        if not p.exists():
            return None
        r = json.loads(p.read_text(encoding="utf-8"))
        m = (r.get("gap", {}) or {}).get("metrics", {}) or {}
        return {"week": w, "mention_rate": m.get("mention_rate"), "citation_rate": m.get("citation_rate"),
                "sov": m.get("sov"), "self_geo": (r.get("self_geo") or {}).get("total"),
                "self_seo": (r.get("self_seo") or {}).get("total")}
    published = []
    pub_dir = repo / "content" / "published"
    if pub_dir.exists():
        import yaml as _y
        for f in sorted(pub_dir.glob("*.md")):
            try:
                fm = _y.safe_load(f.read_text(encoding="utf-8").split("---")[1])
                published.append({"slug": fm.get("slug") or f.stem, "created": fm.get("created", "")})
            except Exception:
                continue
    latest, prev = _metrics(week - 1), _metrics(week - 2)
    if latest is None and not published:
        return None
    return {"published": published, "latest": latest, "prev": prev}
```

`run_research` 中:`feed = _collect_feed(week, repo)`,`render_playbook(conclusions, agg, week, feed=feed)`。

- [ ] **Step 4: 跑测试确认通过(含存量 render/research 用例)**

Run: `python3.11 -m pytest tests/test_render.py tests/ -q`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add src/geo/research/run.py src/geo/research/render.py tests/test_render.py
git commit -m "feat(research): eval feedback into playbook (deterministic section 6 + live rule_version header)"
```

---

### Task 11: 报告 §5 规则迭代摘要

**Files:**
- Modify: `src/geo/report/templates/report.html.j2`(⑤节,约 53–57 行)
- Test: `tests/test_reporter.py`(扩展)

**Interfaces:**
- Consumes: report dict 可选键 `rules_iteration`(Task 8 的 rules_iteration.json 内容;由 Task 12 report 节点合并)。
- Produces: 模板渲染 §5;确定性(同输入同字节)。

- [ ] **Step 1: 写失败测试(追加 test_reporter.py;沿用该文件现有 report fixture 构造方式)**

```python
def test_rules_iteration_section_rendered(tmp_path):
    from geo.report.reporter import render
    base = {"week": 1, "rule_version": "geo-seo-v1", "prompt_set_version": "x",
            "metrics": {}, "self_geo": {"total": 47.6, "dims": []},
            "self_seo": {"total": 49.8, "dims": []}, "gap": {}}
    rep = {**base, "rules_iteration": {
        "week": 1, "from_version": "geo-seo-v1", "to_version": "geo-seo-v2",
        "entries": [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
                     "status": "active", "change": "promoted",
                     "evidence": {"share": 0.206, "with_n": 7, "unique_n": 34,
                                  "platforms": ["doubao", "qwen", "zhipu"], "weeks": [1]}}],
        "weights_before": {"citability": 25}, "weights_after": {"citability": 25},
        "observations": ["SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠",
                         "GEO 权重证据已记录,待 2 周同向后调整(v1.1 持续性门)"]}}
    out1 = render(rep, tmp_path / "a.html"); out2 = render(rep, tmp_path / "b.html")
    html = out1.read_text(encoding="utf-8")
    assert out1.read_bytes() == out2.read_bytes()               # 字节级确定性
    assert "geo-seo-v1 → geo-seo-v2" in html
    assert "has_breadcrumblist" in html and "promoted" in html
    assert "25→26" not in html and "(无)" in html          # v1.1:首周持续性门 → 权重不变
    assert "本期休眠" in html and "持续性" in html

def test_rules_iteration_section_absent_graceful(tmp_path):
    from geo.report.reporter import render
    base = {"week": 1, "rule_version": "geo-seo-v1", "prompt_set_version": "x",
            "metrics": {}, "self_geo": {"total": 47.6, "dims": []},
            "self_seo": {"total": 49.8, "dims": []}, "gap": {}}
    html = render(base, tmp_path / "c.html").read_text(encoding="utf-8")
    assert "本期无规则迭代记录" in html
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_reporter.py -q`
Expected: FAIL `assert 'geo-seo-v1 → geo-seo-v2' ...`(⑤节仍是占位)

- [ ] **Step 3: 改模板 ⑤节(替换现有 53–57 行占位)**

```html
<section>
<h2>⑤规则迭代摘要</h2>
<p>当前规则版本: <code>{{ report.rule_version }}</code></p>
{% if report.rules_iteration %}
{% set ri = report.rules_iteration %}
<p>本期迭代: <code>{{ ri.from_version }}</code> → <code>{{ ri.to_version or ri.from_version }}</code>
(本周评分用 {{ ri.from_version }},变更自下周生效)</p>
<table border=1>
<tr><th>signal</th><th>type</th><th>target</th><th>status</th><th>change</th><th>share</th><th>unique_n</th><th>platforms</th><th>weeks</th></tr>
{% for e in ri.entries %}
<tr><td>{{ e.signal }}</td><td>{{ e.type }}</td><td>{{ e.target }}</td><td>{{ e.status }}</td>
<td>{{ e.change }}</td><td>{{ "{:.1%}".format(e.evidence.share or 0) }}</td>
<td>{{ e.evidence.unique_n }}</td><td>{{ e.evidence.platforms | length }}</td>
<td>{{ e.evidence.weeks | join(',') }}</td></tr>
{% endfor %}
</table>
<p>权重调整:
{% for k in ri.weights_before %}{% if ri.weights_after.get(k) != ri.weights_before[k] %}{{ k }} {{ ri.weights_before[k] }}→{{ ri.weights_after[k] }}; {% endif %}{% endfor %}
{% if ri.weights_after == ri.weights_before %}(无){% endif %}</p>
<ul>{% for o in ri.observations %}<li>{{ o }}</li>{% endfor %}</ul>
{% else %}
<p>本期无规则迭代记录。</p>
{% endif %}
</section>
```

(同任务顺带:竞争差值(gap)节加一行注记 `<p class="note">竞品评分为下界代理(静态信号按 0 计),gap 不可直读。</p>`——Task 0 竞品 static={} 的报告侧配套;若字节级 golden 断言失败,同步更新 golden fixture 属预期变更。)

- [ ] **Step 4: 跑测试确认通过**

Run: `python3.11 -m pytest tests/test_reporter.py tests/ -q`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add src/geo/report/templates/report.html.j2 tests/test_reporter.py
git commit -m "feat(report): section 5 rules-iteration summary (deterministic render)"
```

---

### Task 12: DAG 全链(重排)+ --next-week + --force-new-run

**Files:**
- Modify: `src/geo/orchestrate/graph.py`
- Test: `tests/test_graph.py`(扩展;沿用其现有 fake/monkeypatch 模式)

**Interfaces:**
- Consumes: `run_research(week)`;`run_suggest/run_generate`;`iterate(week)`(Task 8)。
- Produces: 图 `collect → fetch → snapshot → assess → research → generate → rules → report`(**v1.1 重排**:P2 `--suggest --week N` 读本周 `eval_report.json`,assess 必须在前,否则 generate 新周恒跳过);`run_pipeline(week, next_week=False, force_new_run=False)`(--force-new-run 时间戳 thread 从头跑,修复既有 checkpoint 早退 no-op);report dict 合并 `rules_iteration`。

- [ ] **Step 1: 写失败测试(追加 test_graph.py;先读该文件沿用其 monkeypatch 风格)**

```python
def test_full_chain_order_and_generate_skip(tmp_path, monkeypatch):
    import geo.orchestrate.graph as G
    calls = []
    monkeypatch.setattr(G, "REPO", tmp_path)              # 隔离真实 drafts/eval_report 路径
    monkeypatch.setattr(G, "collect_node", lambda s: (calls.append("collect"), s)[1])
    monkeypatch.setattr(G, "fetch_node", lambda s: (calls.append("fetch"), s)[1])
    monkeypatch.setattr(G, "snapshot_node", lambda s: (calls.append("snapshot"), s)[1])
    import geo.research.run as RR
    monkeypatch.setattr(RR, "run_research", lambda w, **k: calls.append("research") or {})
    import geo.generate.run as GR
    monkeypatch.setattr(GR, "run_suggest", lambda w, **k: calls.append("suggest")
                        or {"suggestions": [{"topic": "t", "page_type": "guide"}]})
    monkeypatch.setattr(GR, "run_generate", lambda *a, **k: calls.append("generate") or {})
    monkeypatch.setattr(G, "assess_node", lambda s: (calls.append("assess"), s)[1])
    import geo.rules.keeper as KP
    monkeypatch.setattr(KP, "iterate", lambda w, **k: calls.append("rules") or {})
    monkeypatch.setattr(G, "report_node", lambda s: (calls.append("report"), s)[1])
    g = G.build_graph()
    g.invoke({"week": 9}, config={"configurable": {"thread_id": "test-full"}})
    assert calls == ["collect", "fetch", "snapshot", "assess", "research", "suggest",
                     "generate", "rules", "report"]          # v1.1:assess 提前(generate 需本周报告)

def test_force_new_run_uses_fresh_thread(tmp_path, monkeypatch):
    import geo.orchestrate.graph as G
    seen = {}
    class FakeApp:
        def invoke(self, state, config=None):
            seen["thread"] = config["configurable"]["thread_id"]
    monkeypatch.setattr(G, "build_graph", lambda: FakeApp())
    G.run_pipeline(9, force_new_run=True)
    assert seen["thread"].startswith("w9-")                  # 时间戳新 thread,不受旧 checkpoint 影响

def test_generate_node_skips_when_unreviewed_draft(tmp_path, monkeypatch):
    import geo.orchestrate.graph as G
    from geo.shared.config import REPO
    drafts = REPO / "content" / "drafts"
    had = drafts.exists() and list(drafts.glob("*.md"))
    if had:                                            # 本机若有真草稿,挪开避免干扰
        for f in drafts.glob("*.md"): f.rename(f.with_suffix(".md.bak"))
    try:
        (drafts).mkdir(parents=True, exist_ok=True)
        (drafts / "pending.md").write_text("---\nslug: pending\n---\nbody", encoding="utf-8")
        import geo.generate.run as GR
        boom = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not generate"))
        monkeypatch.setattr(GR, "run_generate", boom)
        G.generate_node({"week": 9})                    # 不抛 = 跳过成功
    finally:
        (drafts / "pending.md").unlink(missing_ok=True)
        if had:
            for f in drafts.glob("*.md.bak"): f.rename(f.with_suffix(".md"))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.11 -m pytest tests/test_graph.py -q`
Expected: FAIL `AttributeError: module 'geo.orchestrate.graph' has no attribute 'research_node'`(或顺序断言失败)

- [ ] **Step 3: 实现 graph.py 改动**

在现有节点后追加:

```python
def research_node(state):
    from geo.research.run import run_research
    run_research(state["week"])
    return state


def generate_node(state):
    # 只产草稿、永不发布(🔴发布在 DAG 之外人工执行,§10 不变式)。
    # 队列纪律:已有未人审草稿 → 跳过(一次只积压一篇)。
    from geo.generate.run import run_suggest, run_generate
    w = state["week"]
    drafts_dir = REPO / "content" / "drafts"
    pending = list(drafts_dir.glob("*.md")) if drafts_dir.exists() else []
    if pending:
        print(f"[generate] 跳过:存在未人审草稿 {[p.stem for p in pending]}(人工 --review 后自动恢复)")
        return state
    sugg = run_suggest(w).get("suggestions") or []
    if not sugg:
        print("[generate] 跳过:无候选(检查 gsc/playbook 数据源)")
        return state
    top = sugg[0]
    run_generate(top["topic"], top.get("page_type", "guide"), w)
    return state


def rules_node(state):
    from geo.rules.keeper import iterate
    iterate(state["week"])
    return state
```

`report_node` 读取处合并(在 `rep = json.loads(...)` 之后加):

```python
    ri = REPO / "data" / "analysis" / f"w{w}" / "rules_iteration.json"
    if ri.exists():
        rep["rules_iteration"] = json.loads(ri.read_text(encoding="utf-8"))
```

`build_graph` 边改为:

```python
    g.add_edge(START, "collect")
    g.add_edge("collect", "fetch")
    g.add_edge("fetch", "snapshot")
    g.add_edge("snapshot", "assess")          # v1.1:assess 提前(generate 需本周 eval_report)
    g.add_edge("assess", "research")
    g.add_edge("research", "generate")
    g.add_edge("generate", "rules")
    g.add_edge("rules", "report")
    g.add_edge("report", END)
```

(节点注册 `g.add_node("research", research_node)` 等三条同步加。)

`run_pipeline` 增参 `next_week: bool = False, force_new_run: bool = False`(v1.1:--force-new-run 时间戳 thread `w{N}-{YYYYmmdd-HHMMSS}` 从头跑全链——既有实现见完整 checkpoint 即早退 no-op,复跑同周必须换 thread;节点文件级幂等,重跑安全),尾部:

```python
    if next_week:
        import yaml as _y
        run_raw = _y.safe_load((REPO / "run.yaml").read_text(encoding="utf-8"))
        run_raw["week"] = week + 1
        (REPO / "run.yaml").write_text(
            _y.safe_dump(run_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"run.yaml week → {week + 1}")
```

`__main__` 块改用 argparse:

```python
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="geo.orchestrate.graph")
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--next-week", action="store_true", help="跑完当前周后把 run.yaml 周次 +1")
    ap.add_argument("--force-new-run", action="store_true",
                    help="忽略既有 checkpoint,时间戳新 thread 从头跑全周(补页/改规则后复跑用)")
    a = ap.parse_args()
    run_pipeline(a.week or settings.run.week, next_week=a.next_week, force_new_run=a.force_new_run)
```

- [ ] **Step 4: 跑测试确认通过(含存量 test_graph)**

Run: `python3.11 -m pytest tests/test_graph.py tests/ -q`
Expected: 全 PASS。⚠️ 注意 `assess_node`/`report_node` 现有实现不带 rules 注入——不改其行为(评分用当前 run.yaml 版本,符合"本周用 vN"时序)。

- [ ] **Step 5: Commit**

```bash
git add src/geo/orchestrate/graph.py tests/test_graph.py
git commit -m "feat(orchestrate): full-chain DAG (research/generate/rules nodes) + --next-week"
```

---

### Task 13: 集成验证 —— w1 真实迭代 + 全量绿

**Files:**
- 无新文件(运行验证;若发现 bug 修对应模块并补测试)
- 产物(不入库,gitignored):`rules/history/geo-seo-v1/`、`rules/geo-rules.yaml`(v2)、`data/analysis/w1/rules_iteration.json`、`reports/w1/report.html`

**Interfaces:**
- Consumes: Task 1–12 全部。

- [ ] **Step 1: 全量测试**

Run: `python3.11 -m pytest tests/ -q`
Expected: 全 PASS(247 存量 + P3 新增,0 失败 0 错误)

- [ ] **Step 2: 真实 w1 迭代(纯磁盘,零网络;前置 = Task 5 Step 0 已重生成含 unique 桶的 w1 aggregates)**

Run: `cd "/Users/jerry/AiProject/sunpower nova/geo-agent" && python3.11 -m geo.rules.run iterate --week 1`
Expected 输出:`from_version=geo-seo-v1 → to_version=geo-seo-v2`;entries:`has_breadcrumblist promoted(active,唯一页 7/34=20.6%、3 家)`、`faq_block_count draft(0/34)`;**weights 不变(首周持续性门,v1.1)**;observations 含 SEO 休眠 + 权重证据已记录待 2 周同向。

- [ ] **Step 3: 核对迭代产物**

```bash
ls rules/history/geo-seo-v1/                       # 两份归档 YAML
grep version rules/geo-rules.yaml                  # geo-seo-v2
grep rule_version run.yaml                         # geo-seo-v2
tail -20 rules/changelog.md                        # v2 变更记录 + rollback 提示
python3.11 -m geo.rules.run show
```

- [ ] **Step 4: 重算回归 + 报告 §5**

```bash
python3.11 -m geo.rules.run recalc --week 1 --rule-version geo-seo-v1 --render
# → data/analysis/w1/eval_report.recalc-geo-seo-v1.json:total 应 = 47.6 / 49.8(v1 语义重算不漂移)
python3.11 -m geo.report.reporter                  # → reports/w1/report.html 含 ⑤ 规则迭代摘要
grep -c "has_breadcrumblist" reports/w1/report.html   # ≥1
```

- [ ] **Step 5: 回滚演练(不留痕:回滚后再迭代回来)**

```bash
python3.11 -m geo.rules.run rollback --to geo-seo-v1
python3.11 -m geo.rules.run show                   # v3(restores: geo-seo-v1;不倒退版本号)
python3.11 -m geo.rules.run iterate --week 1       # 重新迭代 → v4(单调;幂等同结果)
```

- [ ] **Step 6: Commit(如有修复)**

```bash
git add <明确文件>
git commit -m "fix(rules): integration fixes from w1 live iteration"
```

(无修复则跳过本步。)

---

### Task 14: 文档同步(spec 偏差回写 + 状态行)

**Files:**
- Modify: `docs/superpowers/specs/2026-07-29-sunpower-nova-integration-design.md`(§7/§10/§11 + footer)
- Modify: `docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md`(状态行)

**Interfaces:**
- Consumes: Task 13 实测结果。

- [ ] **Step 1: 整合 spec 回写偏差**

§10「触发」行与 §11 P3 行的"定时复跑(launchd/cron)"处补注:`(P3 落地为手动随时复跑,决策 2026-08-19,定时器不接)`;
§7 增一行:`P3 落地:v1 成员已与代码实际计算集对齐(语义无操作,changelog 2026-08-19);条目/权重迭代详见 2026-08-19 P3 spec`;
footer 分期进度行追加:`P3 ✅ <日期>(signal registry + RulesKeeper + 全链 DAG + 反哺;w1 首轮迭代 geo-seo-v1→v2)`。

- [ ] **Step 2: P3 spec 状态行更新**

`> 状态:设计定稿...` 行改为 `> 状态:已实现(2026-08-XX,plan=docs/superpowers/plans/2026-08-19-p3-ruleskeeper.md)`。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-07-29-sunpower-nova-integration-design.md docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md
git commit -m "docs(specs): sync integration + P3 specs with implemented reality"
```

---

## Self-Review 记录(写计划后自查;v1.1 修订后复核)

1. **Spec 覆盖**:§1 注册表→Task 1/3;§1 v1 校正+映射表+黄金→Task 4;§2 条目模型+唯一口径门槛→Task 5(含 features unique 桶)+Task 6(+8 序列化);§3 权重公式+2 周持续性→Task 7;§4 版本/changelog/重算/回滚(manifest+单调版本)→Task 8/9;§5 DAG(重排+force)+竞品上下文→Task 12+Task 0;§6 反哺→Task 10;§7 报告§5→Task 11;§8 测试→各任务 TDD+Task 13;§9 交付物/偏差(含 Task 0 尾巴加固)→Task 14。无缺口。
2. **占位符扫描**:无 TBD/TODO;所有代码块完整可写。
3. **类型一致性**:`collect_evidence → evaluate → keeper` 的 dict 形状已对齐(v1.1 唯一口径:`{signal,kind,bucket,with_n,unique_n,platforms,share}`;EntryDecision.evidence.history 元素 `{week,with_n,unique_n,share,platforms}`);`load_rules(version=)`/`score_*(rules=)`/`assemble(rules_geo=…,out_name=…)`/`persisted_deltas(strengths,prev,weights)` 跨任务签名一致。
4. **v1.1 修订自审**:①证据唯一口径贯穿 features→evidence→gate→keeper→报告(Task 11 模板 sample_n 列已改 unique_n);②持续性门槛的 prev strengths 存取闭环(rules_iteration.json `dimension_strengths` ↔ keeper 读取);③回滚单调性:rollback 把当前置为最大版本号,keeper `_bump` +1 恒安全,`restores` 元数据可溯;④Task 4 fixture 捕获先于 Task 5 重生成——Task 5 Step 0 末尾必须重跑 capture 脚本刷新 fixture(含 unique 字段),否则 Task 5/8 测试读不到 unique 桶;⑤w1 首轮预期改为"条目转正、权重不动"(unique 7/34=20.6%、3 家平台实测过门);⑥Task 0 与 RulesKeeper 零耦合,先行落地不依赖 Task 1-4。
