# 三项 Backlog 修复实现计划（①归一化吞孤立 delta ②suggest 去重 ③w2 gap 回填）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 w3 遗留三个 backlog——权重引擎补偿语义（孤立 delta 不再被吞）、suggest 已发布去重（防 w4 撞题）、w2 gap=null 回填（补数据洞）。

**Architecture:** ②①为独立 TDD 代码改动（互不依赖，各一提交）；③为纯数据操作零代码（`data/` gitignored）。三项相互独立，按 ②→①→③ 顺序实施，收口 merge --no-ff。

**Tech Stack:** Python 3.11（运行时）/ pytest（python3.12 + `/tmp/pylibs312`）/ PyYAML。

**Spec:** `docs/superpowers/specs/2026-09-01-backlog-fixes-design.md`（§0 用户决策表）

## Global Constraints

- 工作目录：项目根 `/Users/jerry/AiProject/sunpower nova`；代码在 `geo-agent/`。
- 测试命令（唯一 canonical，勿改）：`cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`（不加 `-q`——summary 行会被吞；以工具退出码为准）。单测定向跑同命令加文件路径。
- 运行时（Task 3 操作）用系统 `python3.11`（geo 已 editable 安装）；`.venv` 被沙箱硬封禁用。
- **禁 `git add -A`**——精确 add 文件路径（历史事故：漏进 49MB venv）。
- 测试严禁触碰真实 `data/`（一律 `tmp_path`）；Task 3 是唯一动真实数据的任务。
- 分支 `backlog-fixes` 自 main 切出（主 checkout，非 worktree——项目惯例）；commit message 中文 conventional 风格，尾行 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 现有基线：414 passed + 2 skipped；本计划只增不改存量断言（②的 3 处 unpack 除外，属签名变更必然）。
- 网络：Task 3 常规步骤零网络（全读盘）；仅守卫分支需要代理 10808 + dangerouslyDisableSandbox。
- 不跑 `geo.orchestrate.graph`、不动 `run.yaml`。

---

### Task 1: ② suggest 精确去重（防 w4 撞题）

**Files:**
- Modify: `geo-agent/src/geo/generate/topics.py`（全文 43 行，改 import + 新增 `_published_keys` + `suggest_topics` 过滤与返回值扩展）
- Modify: `geo-agent/src/geo/generate/run.py:140-148`（`run_suggest` 消费三元组 + 抑制摘要）
- Test: `geo-agent/tests/test_generate_topics.py`（更新 3 处 unpack + 新增 4 用例）
- Test: `geo-agent/tests/test_generate_run.py`（新增 1 用例）

**Interfaces:**
- Consumes: 无（自包含）。
- Produces: `suggest_topics(week: int, *, repo: Path) -> tuple[list[dict], list[str], list[dict]]`（第三元素 = 被抑制建议列表，dict 结构与 `out` 相同：`source/detail/topic/page_type`）；`_published_keys(repo: Path) -> set[tuple[str, str]]`。`run_suggest` 返回 dict 增键 `"suppressed"`。

- [ ] **Step 0: 切分支**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git checkout -b backlog-fixes
```

- [ ] **Step 1: 写失败测试（test_generate_topics.py 末尾追加）**

```python
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
        "---\ntopic: About-the-team page: who designs and installs, credentials, process\n"
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
```

同时把现有 3 处 unpack 改为三元组（`test_generate_topics.py:9,18,24`）：
`out, missing = ` → `out, missing, _ = `；`out, _ = ` → `out, _, _s = `。

- [ ] **Step 2: 跑测试确认红**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_generate_topics.py -p no:cacheprovider --timeout=120`
Expected: FAIL——新用例 `ValueError: not enough values to unpack (expected 2, got 3)` 或 `ImportError`（`_repo_with_content` 内 shutil late import 不影响）；存量用例同样因 unpack 数报错（预期，Step 3 一并转绿）。

- [ ] **Step 3: 实现（topics.py 全量替换为）**

```python
# src/geo/generate/topics.py
from __future__ import annotations
import json
from pathlib import Path
import yaml

GAP_TEMPLATES = {
    "citability":       ("Guide with concrete sizing/how-to numbers drawn from brand facts", "guide"),
    "eeat":             ("About-the-team page: who designs and installs, credentials, process", "guide"),
    "schema":           ("FAQ page adding FAQPage JSON-LD", "faq"),
    "platform":         ("Side-by-side comparison page suited for AI platform pickup", "comparison"),
    "technical_geo":    ("Spec sheet page with structured product data", "spec"),
    "on_page":          ("Spec sheet page with structured headings and product data", "spec"),
    "content_eeat":     ("Deep-dive article with dates, sources and concrete data points", "guide"),
    "authority":        ("Glossary/definition hub page for core terminology", "guide"),
}
_DEFAULT_TEMPLATE = ("Content targeting this weak dimension (generic)", "guide")

def _published_keys(repo: Path) -> set[tuple[str, str]]:
    """已发布+草稿的 (page_type, topic) 键集;坏/缺 frontmatter 文件跳过不炸。"""
    keys: set[tuple[str, str]] = set()
    for sub in ("published", "drafts"):
        d = repo / "content" / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                parts = f.read_text(encoding="utf-8").split("---")
                fm = yaml.safe_load(parts[1]) if len(parts) >= 3 else None
                if isinstance(fm, dict) and fm.get("topic") and fm.get("page_type"):
                    keys.add((fm["page_type"], fm["topic"]))
            except Exception:
                continue          # 只读诊断命令:单文件损坏不整体失败
    return keys

def suggest_topics(week: int, *, repo: Path) -> tuple[list[dict], list[str], list[dict]]:
    repo = Path(repo)
    candidates: list[dict] = []
    missing: list[str] = []
    er = repo / "data" / "analysis" / f"w{week}" / "eval_report.json"
    if er.exists():
        rep = json.loads(er.read_text(encoding="utf-8"))
        dims = [d for sec in ("self_geo", "self_seo") for d in rep.get(sec, {}).get("dims", [])
                if d.get("score", 100) < 50]
        for d in sorted(dims, key=lambda x: x["score"]):
            topic, ptype = GAP_TEMPLATES.get(d["name"], _DEFAULT_TEMPLATE)
            candidates.append({"source": "eval_gap", "detail": f"{d['name']}={d['score']}",
                               "topic": topic, "page_type": ptype})
    else:
        missing.append(str(er))
    gsc = repo / "data" / "snapshots" / f"w{week}" / "gsc.json"
    if gsc.exists():
        snap = json.loads(gsc.read_text(encoding="utf-8"))
        for row in sorted(snap.get("rows", []), key=lambda r: -r.get("impressions", 0))[:8]:
            q = " ".join(row.get("keys", [])).strip()
            if q:
                candidates.append({"source": "gsc", "detail": f"impressions={row.get('impressions', 0)}",
                                   "topic": q, "page_type": "guide"})
    else:
        missing.append(str(gsc))
    pub = _published_keys(repo)                     # 已发布/草稿精确去重(spec §3)
    out = [s for s in candidates if (s["page_type"], s["topic"]) not in pub]
    suppressed = [s for s in candidates if (s["page_type"], s["topic"]) in pub]
    return out, missing, suppressed
```

- [ ] **Step 4: 跑测试确认绿**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_generate_topics.py -p no:cacheprovider --timeout=120`
Expected: 全 PASS（存量 3 + 新增 4）。

- [ ] **Step 5: 写 run_suggest 失败测试（test_generate_run.py 末尾追加）**

注意 `capsys.readouterr()` 只能消费一次，先存变量再断言：

```python
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
```

- [ ] **Step 6: 跑确认红**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_generate_run.py::test_run_suggest_prints_suppression_summary -p no:cacheprovider --timeout=120`
Expected: FAIL（`run_suggest` 返回 dict 无 `suppressed` 键 → KeyError，且无摘要输出）。

- [ ] **Step 7: 改 run_suggest（run.py:140-148 替换为）**

```python
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
    if not out:
        print("（无建议——检查 eval_report/gsc 数据源）")
    return {"suggestions": out, "missing": missing, "suppressed": suppressed}
```

- [ ] **Step 8: 跑确认绿 + 全量**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_generate_run.py tests/test_generate_topics.py -p no:cacheprovider --timeout=120`
Expected: 全 PASS。
Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: 414+5 passed + 2 skipped（零 fail）。

- [ ] **Step 9: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/src/geo/generate/topics.py geo-agent/src/geo/generate/run.py \
        geo-agent/tests/test_generate_topics.py geo-agent/tests/test_generate_run.py
git commit -m "feat(generate): suggest 已发布/草稿精确去重——(page_type,topic) 命中即抑制并打印摘要

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: ① apply_deltas 补偿语义修复（孤立 delta 不再被吞）

**Files:**
- Modify: `geo-agent/src/geo/rules/weights.py:1-53`（docstring + `apply_deltas` 重写）
- Modify: `geo-agent/src/geo/rules/keeper.py:137`（传 strengths）
- Test: `geo-agent/tests/test_rules_weights.py`（新增 6 用例）
- Test: `geo-agent/tests/test_rules_keeper.py`（新增 1 集成用例）

**Interfaces:**
- Consumes: Task 1 无关（独立）。
- Produces: `apply_deltas(weights: dict[str, int], deltas: dict[str, int], strengths: dict[str, float | None] | None = None) -> dict[str, int]`——第三参可选（None → 零-delta 维按名字序回退）；keeper 调用点传 `strengths`。

- [ ] **Step 1: 写失败测试（test_rules_weights.py 末尾追加）**

```python
def test_isolated_positive_delta_weakest_zero_delta_dim_absorbs():
    # w3 实例数值:citability 孤立 +1 → brand(测量最弱零-delta 维 0.0777)让 1
    s = {"citability": 0.92, "schema": 0.28, "brand": 0.0777,
         "eeat": None, "technical_geo": None, "platform": None}
    nw = apply_deltas(W, {"citability": 1}, s)
    assert nw == {**W, "citability": 26, "brand": 19}
    assert_normalized(types.SimpleNamespace(composite="geo", weights=nw))

def test_isolated_negative_delta_strongest_zero_delta_dim_gains():
    s = {"citability": 0.05, "schema": 0.9, "brand": 0.3,
         "eeat": None, "technical_geo": None, "platform": None}
    nw = apply_deltas(W, {"citability": -1}, s)
    assert nw["citability"] == 24 and nw["schema"] == 11   # schema(0.9 最强零-delta)受益
    assert sum(nw.values()) == 100

def test_measured_dim_preferred_over_none_stream():
    # 同有无流维 f 在场,测量最弱维 b(0.05)优先让权
    w = {"a": 30, "b": 10, "c": 20, "d": 20, "e": 15, "f": 5}      # sum 100
    s = {"a": 0.9, "b": 0.05, "c": 0.5, "d": 0.4, "e": 0.3}       # f 缺席 = 无流
    nw = apply_deltas(w, {"a": 1}, s)
    assert nw["a"] == 31 and nw["b"] == 9 and nw["f"] == 5

def test_none_stream_last_resort_all_measured_at_boundary():
    # 测量零-delta 维(b 0.1 / c 0.2)全在 W_MIN → 才动无流维(名字序 d 先)
    w = {"a": 30, "b": 5, "c": 5, "d": 25, "e": 30, "f": 5}       # sum 100
    s = {"a": 0.9, "b": 0.1, "c": 0.2}                            # d/e/f 无流
    nw = apply_deltas(w, {"a": 1}, s)
    assert nw["a"] == 31 and nw["b"] == 5 and nw["c"] == 5 and nw["d"] == 24

def test_compensation_skips_boundary_dims():
    # 最弱测量维 b 已在 W_MIN → 跳到次弱 c 承接
    w = {"a": 30, "b": 5, "c": 20, "d": 20, "e": 20, "f": 5}      # sum 100
    s = {"a": 0.9, "b": 0.05, "c": 0.2, "d": 0.4, "e": 0.3}
    nw = apply_deltas(w, {"a": 1}, s)
    assert nw["a"] == 31 and nw["b"] == 5 and nw["c"] == 19

def test_no_strengths_deterministic_name_fallback():
    nw1 = apply_deltas(W, {"citability": 1})
    nw2 = apply_deltas(W, {"citability": 1})
    assert nw1 == nw2 == {**W, "citability": 26, "brand": 19}     # 零-delta 名字序:brand 最先
    assert sum(nw1.values()) == 100
```

- [ ] **Step 2: 跑确认红**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_rules_weights.py -p no:cacheprovider --timeout=120`
Expected: 6 个新用例 FAIL（现实现把补偿落回 delta 维自身 → `citability` 26 后被 −1 回 25、brand 不动）；存量 6 用例仍 PASS。

- [ ] **Step 3: 实现（weights.py 的 docstring 与 apply_deltas 替换）**

模块 docstring（weights.py:1-4）替换为：

```python
# src/geo/rules/weights.py
"""权重证据强度公式:delta = round(STEP*(S_i - S̄)),夹值 [W_MIN,W_MAX],
最大余数式归一到恰好 100(确定性)。
v1.2 补偿语义:总和校正只动零-delta 维——有证据裁决的维度不被染指;
零-delta 池内有测量强度者优先于无流维;diff<0 弱者让权(强度升序)、diff>0 强者受益(降序);
同分名字 ASCII 兜底。孤立 ±delta 不再被自身吃回(2026-09-01 缺口修复)。"""
```

`apply_deltas`（weights.py:36-53）替换为：

```python
def apply_deltas(weights: dict[str, int], deltas: dict[str, int],
                 strengths: dict[str, float | None] | None = None) -> dict[str, int]:
    raw = {k: weights[k] + deltas.get(k, 0) for k in weights}
    out = {k: _clamp(v) for k, v in raw.items()}
    diff = 100 - sum(out.values())
    if diff:
        measured = {k: v for k, v in (strengths or {}).items()
                    if v is not None and k in weights}
        sign = 1.0 if diff < 0 else -1.0     # 减→强度升序(弱者先让);加→强度降序(强者先得)
        order = sorted(weights, key=lambda k: (deltas.get(k, 0) != 0,      # 零-delta 优先
                                               k not in measured,           # 有流优先于无流
                                               sign * measured.get(k, 0.0),
                                               k))
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

keeper.py:137 替换为：

```python
    w_after = apply_deltas(w_before, deltas, strengths) if deltas else w_before
```

- [ ] **Step 4: 跑确认绿**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_rules_weights.py -p no:cacheprovider --timeout=120`
Expected: 全 PASS（存量 6 + 新增 6）。

- [ ] **Step 5: 写 keeper 集成失败测试（test_rules_keeper.py 末尾追加）**

数值已推演：w2 strengths = citability 0.9（36/40）/ schema 0.5（20/40）/ brand 0.48（(0.46+0.5)/2）→ 均值 0.6267 → 孤立 delta {citability: +1}；w1 prev_strengths = {citability 0.8, schema 0.5, brand 0.48} → 上期 delta {citability: +1} 同向过门 → apply 后 citability 25→26、brand（测量最弱零-delta 0.48）20→19。

```python
def test_iterate_isolated_delta_moves_weights(tmp_path):
    repo = _mk_repo(tmp_path)
    ana1 = repo / "data" / "analysis" / "w1"
    ana2 = repo / "data" / "analysis" / "w2"
    ana2.mkdir(parents=True)
    agg = json.loads((ana1 / "research_aggregates.json").read_text(encoding="utf-8"))
    for b in agg["formats"]:
        b["unique_cited_n"] = 36; b["unique_n"] = 40                 # citability 0.9
    agg["sources"]["unique_n"] = 40
    agg["sources"]["schema_unique"] = {"BreadcrumbList": 20}         # schema 0.5
    (ana2 / "research_aggregates.json").write_text(json.dumps(agg, ensure_ascii=False))
    ev = json.loads((ana1 / "eval_report.json").read_text(encoding="utf-8"))
    ev["gap"]["metrics"]["mention_rate"] = 0.46                       # brand (0.46+0.5)/2=0.48
    ev["gap"]["metrics"]["citation_rate"] = 0.5
    (ana2 / "eval_report.json").write_text(json.dumps(ev, ensure_ascii=False))
    (ana1 / "rules_iteration.json").write_text(json.dumps(           # 上期同向记录
        {"dimension_strengths": {"citability": 0.8, "schema": 0.5, "brand": 0.48}}))
    it = iterate(2, repo=repo)
    assert it["weights_before"] != it["weights_after"]
    assert it["weights_after"] == {**it["weights_before"], "citability": 26, "brand": 19}
    assert it["to_version"] is not None                              # 权重动了 → 升版
```

- [ ] **Step 6: 跑确认红→绿**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_rules_keeper.py::test_iterate_isolated_delta_moves_weights -p no:cacheprovider --timeout=120`
Expected: Step 3 已含 keeper 传参改动——若 Step 3 未含则此处红（weights_after == weights_before）；含则直接绿。红时核对 keeper.py:137 是否已传 `strengths`。

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_rules_keeper.py -p no:cacheprovider --timeout=120`
Expected: 全 PASS。

- [ ] **Step 7: 全量回归**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: 414+12 passed + 2 skipped（零 fail；黄金锁 43.4/49.8 不受影响——scorer 层与权重引擎解耦）。

- [ ] **Step 8: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/src/geo/rules/weights.py geo-agent/src/geo/rules/keeper.py \
        geo-agent/tests/test_rules_weights.py geo-agent/tests/test_rules_keeper.py
git commit -m "fix(rules): 归一化补偿只动零-delta 维——孤立 delta 不再被自身吃回

diff<0 弱者让权(强度升序)/diff>0 强者受益(降序),无流维最后兜底;
keeper 传 strengths;w3 实例反事实=citability 25→26、brand 20→19

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: ③ w2 gap=null 回填（纯数据操作，零代码零提交）

**Files:**
- Create: `geo-agent/data/analysis/w2/eval_report.gap-null-archived.json`（原版备份，gitignored）
- Modify: `geo-agent/data/analysis/w2/eval_report.json`（gap 回填，gitignored）
- Create: `geo-agent/reports/w2/report.html`（重渲覆盖，gitignored）

**Interfaces:**
- Consumes: `python3.11 -m geo.rules.run recalc --week 2 --rule-version geo-seo-v2`（已存在 CLI）；`geo.report.reporter.render(report, out)`。
- Produces: 无代码接口；数据产物供 w4 research 读 w3/w2 两份报告时 gap 可比。

- [ ] **Step 1: 记录前置校验基线**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
shasum geo-agent/data/analysis/w3/rules_iteration.json geo-agent/rules/changelog.md \
       geo-agent/rules/geo-rules.yaml geo-agent/run.yaml > /tmp/w3-guard-before.txt
python3.11 -c "
import json
d = json.load(open('geo-agent/data/analysis/w2/eval_report.json'))
assert d['gap'] is None, 'w2 gap 已非 null,回填前提不成立'
print('baseline: gap=None, self_geo', d['self_geo']['total'], '/ self_seo', d['self_seo']['total'])"
```
Expected: `baseline: gap=None, self_geo 41.2 / self_seo 49.9`。

- [ ] **Step 2: recalc（零网络，全读盘）**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && python3.11 -m geo.rules.run recalc --week 2 --rule-version geo-seo-v2
```
Expected: 产出 `geo-agent/data/analysis/w2/eval_report.recalc-geo-seo-v2.json`。

- [ ] **Step 3: 核验门（任一失败即中止上报，canonical 不动）**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && python3.11 -c "
import json
rec = json.load(open('geo-agent/data/analysis/w2/eval_report.recalc-geo-seo-v2.json'))
old = json.load(open('geo-agent/data/analysis/w2/eval_report.json'))
g = rec.get('gap') or {}
assert g.get('comp_avg_total') is not None and g.get('dim_diff'), f'gap 仍不可算: {g}'
assert rec['self_geo']['total'] == old['self_geo']['total'] == 41.2, 'self_geo 漂移'
assert rec['self_seo']['total'] == old['self_seo']['total'] == 49.9, 'self_seo 漂移'
assert rec['rule_version'] == 'geo-seo-v2'
print('核验过门: gap =', json.dumps(g['dim_diff'], ensure_ascii=False))"
```
Expected: `核验过门: gap = {...}`。
**守卫分支**：若断言 `gap 仍不可算` 失败 → 竞品 L3 缺失。诊断：`python3.11 -c "from geo.assess.analyst import competitor_domains_by_count; print(competitor_domains_by_count(2, n=5))"` 列出 top-5 域名后**上报控制器/用户再决定补抓**（补抓需代理 10808 + dangerouslyDisableSandbox），勿自行续跑。

- [ ] **Step 4: 备份 + 提升 canonical + 重渲报告**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && python3.11 -c "
import json, shutil
from pathlib import Path
ana = Path('geo-agent/data/analysis/w2')
rec = json.loads((ana / 'eval_report.recalc-geo-seo-v2.json').read_text(encoding='utf-8'))
shutil.copy2(ana / 'eval_report.json', ana / 'eval_report.gap-null-archived.json')
shutil.copy2(ana / 'eval_report.recalc-geo-seo-v2.json', ana / 'eval_report.json')
(ana / 'eval_report.recalc-geo-seo-v2.json').unlink()
from geo.report.reporter import render
render(rec, Path('geo-agent/reports/w2/report.html'))
print('promoted + rendered')"
```
Expected: `promoted + rendered`。

- [ ] **Step 5: 终验（含 w3 零触碰守卫）**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
shasum -c /tmp/w3-guard-before.txt
python3.11 -c "
import json
d = json.load(open('geo-agent/data/analysis/w2/eval_report.json'))
assert d['gap'] and d['gap']['comp_avg_total'] is not None
html = open('geo-agent/reports/w2/report.html', encoding='utf-8').read()
assert 'gap' in html.lower() or '竞品' in html
print('w2 gap 回填完成; 备份在 eval_report.gap-null-archived.json')"
git status --short   # 预期:无新增 tracked 改动(data/reports 均 gitignored)
```
Expected: shasum 全 OK；打印完成行；`git status` 与分支开工前一致（仅既有 5 个 untracked）。

---

### Task 4: 收口——merge、push、CI 双绿

**Files:** 无代码文件（git 操作）。

**Interfaces:**
- Consumes: Task 1/2 的两个提交 + Task 3 的数据产物（不入库）。
- Produces: main 合并提交 + CI 绿。

- [ ] **Step 1: 分支上全量回归终跑**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: 全 PASS + 2 skipped（414 + 17 新用例 = 431 passed 附近，以零 fail 为准）。

- [ ] **Step 2: merge --no-ff 回 main**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git checkout main && git merge --no-ff backlog-fixes \
  -m "merge: 三项 backlog 修复 —— 归一化补偿语义 + suggest 去重 + w2 gap 回填(数据)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

- [ ] **Step 3: 合并树全量测试（恒等验证）**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: 与分支上同数全 PASS。

- [ ] **Step 4: 推送（HTTPS 通道，SSH 已知不稳）**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git -c http.https://github.com.proxy=http://127.0.0.1:10808 \
  -c credential.helper='!gh auth git-credential' \
  push https://github.com/JerryZhang0751/sunpowerNova.git main:main
git update-ref refs/remotes/origin/main main   # 显式 URL 推送不更新跟踪 ref,手动对齐
```
Expected: 推送成功（TLS 抖动重试即过）。若 push 事件丢失（GitHub Actions 偶发）：`gh workflow run CI --ref main`。

- [ ] **Step 5: CI 双绿核验**

```bash
gh run list --branch main --limit 3
gh run watch <最新 run id> --exit-status   # 或轮询 gh run view
```
Expected: test + site 两 job 全绿。分支删除：`git branch -d backlog-fixes`。

---

## Self-Review 记录

- **Spec coverage**：spec §2（①）→ Task 2；§3（②）→ Task 1；§4（③）→ Task 3；§5 验收（全量绿/单测演示/CI 双绿）→ Task 1 Step 8、Task 2 Step 7、Task 4。无缺口。
- **Placeholder scan**：无 TBD/“适当处理”/“类似 Task N”；所有代码步骤含完整代码（含 capsys 单次消费注记）。
- **Type consistency**：`suggest_topics` 三元组在 Task 1 测试/实现/run_suggest 三处一致；`apply_deltas(weights, deltas, strengths=None)` 在 Task 2 测试/实现/keeper 调用一致；Task 3 只用既有接口。
