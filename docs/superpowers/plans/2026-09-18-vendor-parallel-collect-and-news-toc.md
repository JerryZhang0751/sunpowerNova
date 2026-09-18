# 供应商级并行采集 + news 章节导航 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 采集改为供应商级并行调度（每家最多 1 个在途请求）；8 篇 news 文章统一接入章节目录（TOC）并配构建产物完整性检查。

**Architecture:** 采集侧保留同步客户端与线程池，改为主循环 FIRST_COMPLETED 补位调度器（每家初始 1 条，完成即落盘并补同家下一条），接口/重试/manifest 语义零变化。站点侧新增 `NewsArticleLayout`（包现有 `Layout`，透传 canonical 语义）+ `ArticleToc`（桌面 sticky 侧栏 / 移动 `<details>` 折叠，锚点纯原生、脚本只做高亮增强），页面显式声明 toc 数组，独立 Node 脚本扫 dist 校验目录↔正文一致并接入 CI。

**Tech Stack:** Python 3.11（CI）/3.12（本地，`~/pylibs312`）、pytest、concurrent.futures；Astro 5、原生 HTML/CSS/JS（零新 npm 依赖）、Node 脚本、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-09-18-vendor-parallel-collect-and-news-toc-design.md`（已批准）

## Global Constraints

- Python 全量测试：`cd geo-agent && PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`，**以 EXIT=0 为准**（summary 行偶被吞）。
- 站点检查：`cd site && npm run check` 必须 **0 errors / 0 warnings / 0 hints**；`npm run build` 成功不作为导航验收替代。
- 不调用付费 API；采集测试全部走 `_iso`（tmp_path + 假客户端），不写生产周数据。
- **禁止 `git add -A`**；每个提交只显式 add 本任务列出的文件。
- 不碰工作树用户文件：`docs/ppt-*` 三目录、`docs/SunPower-Nova项目演讲汇报文稿.md`、`docs/SunPower Nova项目信息概览.html`、`geo-agent/scripts/gsc_page_impressions_probe.py`。
- 不推送远端、不部署站点、不修改模型/提示词/评分规则/历史快照/文章事实内容。
- Python 代码须 3.11 兼容（CI 为 3.11）；站点零新增 npm 依赖。
- 提交信息末尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 提交结构：Task 1-4 = 采集独立提交（commit 1）；Task 5-9 = 站点独立提交（commit 2）；Task 6 末尾有**用户预览关口**。

---

### Task 1: 并发契约测试（红）

**Files:**
- Modify: `geo-agent/tests/test_collector.py`（文件末尾追加新测试块）

**Interfaces:**
- Consumes: 既有 `_iso(tmp_path, monkeypatch, clients=...)` 隔离助手（本文件 48 行）、`run_collection(week, models, prompt_ids, runs, rule_version) -> list[RunRecord]`、`geo.collect.collector.CLIENTS`。
- Produces: 本任务的测试函数名（Task 2 实现后须全绿）：`test_first_batch_contains_all_vendors`、`test_blocked_vendor_does_not_stall_others`。

- [ ] **Step 1: 追加测试代码**

在 `test_collector.py` 文件末尾追加（含分节注释与 mid-file import，沿用本文件 45 行 `import json as _json` 先例）：

```python
# ---- spec 2026-09-18 §5.1: 供应商级并行调度(每家最多1个在途,总并发≤3) --------

import threading
import time as _time


def _ok_answer(name):
    def client(prompt, **k):
        return {"answer": f"A {name}", "search_results": [], "usage": {}, "elapsed_s": 0.1}
    return client


def _wait_until(cond, timeout=10.0, what="condition"):
    """有界等待。轮询用 Event.wait(0.01) —— 不经 time.sleep(退避测试会 patch 它)。"""
    dummy = threading.Event()
    deadline = _time.monotonic() + timeout
    while not cond():
        if _time.monotonic() > deadline:
            raise AssertionError(f"timeout waiting: {what}")
        dummy.wait(0.01)


def test_first_batch_contains_all_vendors(tmp_path, monkeypatch):
    """三家均有多条任务 → 首批请求必须包含三家(不能全是同一家);
    且每家最多1个在途 —— 全部阻塞期间恰好只发生3次调用。"""
    started: list[str] = []
    lock = threading.Lock()
    release = threading.Event()

    def mk(name):
        def client(prompt, **k):
            with lock:
                started.append(name)
            assert release.wait(timeout=10), "客户端未获释放(测试挂起)"
            return {"answer": f"A {name}", "search_results": [], "usage": {}, "elapsed_s": 0.1}
        return client

    _iso(tmp_path, monkeypatch,
         clients={m: mk(m) for m in ("qwen", "doubao", "zhipu")})
    th = threading.Thread(target=lambda: run_collection(
        week=91, models=["qwen", "doubao", "zhipu"],
        prompt_ids=["C01", "D01", "B02"], runs=1, rule_version="t"))
    try:
        th.start()
        _wait_until(lambda: len(started) >= 3, what="首批三家请求进入")
        assert set(started) == {"qwen", "doubao", "zhipu"}, started
        assert len(started) == 3, f"每家应只有1个在途请求: {started}"
    finally:
        release.set()
        th.join(timeout=10)
    assert not th.is_alive()


def test_blocked_vendor_does_not_stall_others(tmp_path, monkeypatch):
    """qwen 单条阻塞期间:doubao/zhipu 的全部任务完成并逐条落盘;
    qwen 其余任务不被拉起(每家1在途)。"""
    unblock = threading.Event()
    qwen_started: list[str] = []

    def qwen_slow(prompt, **k):
        qwen_started.append(prompt)
        assert unblock.wait(timeout=10), "qwen 未获释放(测试挂起)"
        return {"answer": "A qwen", "search_results": [], "usage": {}, "elapsed_s": 0.1}

    _iso(tmp_path, monkeypatch, clients={"qwen": qwen_slow,
                                         "doubao": _ok_answer("doubao"),
                                         "zhipu": _ok_answer("zhipu")})
    th = threading.Thread(target=lambda: run_collection(
        week=92, models=["qwen", "doubao", "zhipu"],
        prompt_ids=["C01", "D01", "B02"], runs=1, rule_version="t"))
    manifest = tmp_path / "data" / "raw" / "w92" / "runs.jsonl"
    try:
        th.start()
        def others_done():
            if not manifest.exists():
                return False
            lines = manifest.read_text(encoding="utf-8").splitlines()
            return sum(1 for l in lines if '"status":"ok"' in l
                       and ('"model":"doubao"' in l or '"model":"zhipu"' in l)) >= 6
        _wait_until(others_done, what="qwen 阻塞期间 doubao/zhipu 6 条 ok 落盘")
        assert len(qwen_started) == 1, f"qwen 应只有1条在途: {qwen_started}"
        still_running = th.is_alive()          # qwen 未完成 → 管线仍在运行
    finally:
        unblock.set()
        th.join(timeout=10)
    assert not th.is_alive()
    assert still_running
```

- [ ] **Step 2: 运行验证失败（红）**

```bash
cd geo-agent && PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/test_collector.py::test_first_batch_contains_all_vendors tests/test_collector.py::test_blocked_vendor_does_not_stall_others -p no:cacheprovider --timeout=120 -v
```
Expected: 两个测试 **FAIL**（现实现首批 3 个请求全是 qwen → set 断言失败；或 doubao/zhipu 被占满的 worker 饿死 → timeout waiting）。若出现挂起，`--timeout=120` 会兜底杀掉；确认失败原因属于上述两类。

---

### Task 2: 供应商级并行调度器实现（绿）

**Files:**
- Modify: `geo-agent/src/geo/collect/collector.py:4`（import 行）
- Modify: `geo-agent/src/geo/collect/collector.py:117-150`（`run_collection` 的执行段抽出为 `_run_vendor_parallel`，新增 `_one_logged`）

**Interfaces:**
- Consumes: 既有 `_one(model, row, run, week, rule_version, brand, comp)`、`_mk_rec(...)`、`append_run_records(week, recs)`、`RunRecord`。
- Produces: `_run_vendor_parallel(todo: list[tuple], week: int, rule_version: str) -> list[RunRecord]`（模块内私有，Task 1 测试经 `run_collection` 间接验证）；`run_collection` 签名与返回类型**不变**。

- [ ] **Step 1: 改 import 行**

`collector.py:4` 由：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
```

改为：

```python
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait as futures_wait
```

- [ ] **Step 2: 新增调度函数（插在 `collection_health` 之前）**

```python
def _one_logged(job):
    """工作线程侧: 单条计时+开始/结束日志(spec §3.3);结果记录仍在主线程。"""
    m, row, run = job[0], job[1], job[2]
    t0 = time.monotonic()
    log.info("collect %s %s r%d start", m, row.id, run)
    try:
        rec = _one(*job)
    except Exception:
        log.info("collect %s %s r%d failed after %.1fs", m, row.id, run, time.monotonic() - t0)
        raise
    log.info("collect %s %s r%d ok %.1fs", m, row.id, run, time.monotonic() - t0)
    return rec


def _run_vendor_parallel(todo, week, rule_version):
    """供应商级并行调度(spec 2026-09-18 §3.1): 每家最多1个在途请求、总数≤3;
    一家等待响应或退避重试时,不占用另外两家的执行机会。
    主线程等待任意完成 → 立即落 manifest → 补位同一家下一条。"""
    queues: dict[str, list] = {}
    for j in todo:
        queues.setdefault(j[0], []).append(j)
    recs: list[RunRecord] = []
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=3) as ex:
        inflight: dict = {}

        def _submit_next(m):
            j = queues[m].pop(0)
            inflight[ex.submit(_one_logged, j)] = j

        for m in list(queues):
            _submit_next(m)
        while inflight:
            done, _ = futures_wait(inflight, return_when=FIRST_COMPLETED)
            for fut in done:
                j = inflight.pop(fut)
                try:
                    rec = fut.result()
                except Exception as e:
                    log.error("fail %s %s r%d: %s", j[0], j[1].id, j[2], e)
                    rec = _mk_rec(week, j[0], j[1].id, j[2], rule_version,
                                  "failed", error=str(e))
                recs.append(rec)
                append_run_records(week, [rec])   # 完成即落盘(主线程写清单)
                if queues[j[0]]:
                    _submit_next(j[0])
    if todo:
        log.info("collection round done: %d tasks, %.1fs", len(todo), time.monotonic() - t0)
    return recs
```

- [ ] **Step 3: 改 `run_collection` 执行段**

`run_collection` 中删除整个 `with ThreadPoolExecutor(max_workers=3) as ex: ...` 块（138-149 行），替换为：

```python
    recs.extend(_run_vendor_parallel(todo, week, rule_version))
    return recs
```

（其上的 jobs 生成、skipped_exists 循环、todo 过滤、planned 批量注册 126-137 行**逐行不动**。）

- [ ] **Step 4: 运行 Task 1 测试验证通过**

```bash
cd geo-agent && PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/test_collector.py::test_first_batch_contains_all_vendors tests/test_collector.py::test_blocked_vendor_does_not_stall_others -p no:cacheprovider --timeout=120 -v
```
Expected: 2 passed。

- [ ] **Step 5: 运行既有 collector 全部测试**

```bash
cd geo-agent && PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/test_collector.py -p no:cacheprovider --timeout=120 -v
```
Expected: 全部 passed（含既有 resume/失败落盘/重试/健康门测试——接口未变应全绿）。

---

### Task 3: 补充场景测试（spec §5.1 其余行）

**Files:**
- Modify: `geo-agent/tests/test_collector.py`（Task 1 块内追加）

**Interfaces:**
- Consumes: Task 1 的 `_ok_answer` / `_wait_until` 助手、Task 2 调度器。
- Produces: `test_backoff_in_one_vendor_does_not_block_others`、`test_completed_vendor_not_called_again`、`test_subset_and_repeat_runs_complete_exactly_once`。

- [ ] **Step 1: 追加三个测试**

```python
def test_backoff_in_one_vendor_does_not_block_others(tmp_path, monkeypatch):
    """某家传输类失败进入退避(重试 sleep)期间:另两家照常完成;
    退避释放后该家重试成功。"""
    in_backoff = threading.Event()
    backoff_done = threading.Event()

    def fake_sleep(s):
        in_backoff.set()
        assert backoff_done.wait(timeout=10), "退避未获释放(测试挂起)"

    monkeypatch.setattr("time.sleep", fake_sleep)   # 与本文件既有测试同法
    calls = {"qwen": 0}

    def flaky(prompt, **k):
        calls["qwen"] += 1
        if calls["qwen"] == 1:
            raise RuntimeError("Response ended prematurely")   # 传输类 → 可重试
        return {"answer": "A qwen", "search_results": [], "usage": {}, "elapsed_s": 0.1}

    _iso(tmp_path, monkeypatch, clients={"qwen": flaky,
                                         "doubao": _ok_answer("doubao"),
                                         "zhipu": _ok_answer("zhipu")})
    th = threading.Thread(target=lambda: run_collection(
        week=90, models=["qwen", "doubao", "zhipu"], prompt_ids=["C01"], runs=1,
        rule_version="t"))
    manifest = tmp_path / "data" / "raw" / "w90" / "runs.jsonl"
    try:
        th.start()
        assert in_backoff.wait(timeout=10), "qwen 未进入退避"
        def others_done():
            # 逐行查 model+prompt_id+status 三元组:RunRecord 字段序为
            # week,model,prompt_id,run,prompt_set_version,rule_snapshot_version,status,...
            # prompt_id 与 status 不相邻,跨字段连续子串永不匹配(2026-09-18 勘误)
            if not manifest.exists():
                return False
            lines = manifest.read_text(encoding="utf-8").splitlines()
            return (any('"model":"doubao"' in l and '"prompt_id":"C01"' in l
                        and '"status":"ok"' in l for l in lines) and
                    any('"model":"zhipu"' in l and '"prompt_id":"C01"' in l
                        and '"status":"ok"' in l for l in lines))
        _wait_until(others_done, what="退避期间 doubao/zhipu 完成")
        assert calls["qwen"] == 1, "退避中:第二次尝试尚未发起"
    finally:
        backoff_done.set()
        th.join(timeout=10)
    assert not th.is_alive()
    assert calls["qwen"] == 2          # 退避释放后重试成功


def test_completed_vendor_not_called_again(tmp_path, monkeypatch):
    """某家全部已有有效 L1 → 只走 skipped_exists,不再调用该家接口。"""
    l1 = _iso(tmp_path, monkeypatch, clients={"doubao": _ok_answer("doubao")})
    for pid in ("C01", "D01"):
        p = l1(88, "qwen", pid, 1)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"answer": "already there"}), encoding="utf-8")

    def must_not_call(prompt, **k):
        raise AssertionError("已完成供应商不得再调用")

    monkeypatch.setattr(collector, "CLIENTS",
                        {**collector.CLIENTS, "qwen": must_not_call})
    recs = run_collection(week=88, models=["qwen", "doubao"],
                          prompt_ids=["C01", "D01"], runs=1, rule_version="t")
    st = {(r.model, r.status) for r in recs}
    assert ("qwen", "skipped_exists") in st and ("doubao", "ok") in st


def test_subset_and_repeat_runs_complete_exactly_once(tmp_path, monkeypatch):
    """供应商子集 + 多 run: 任务不遗漏不重复;全部完成后再跑不发起请求。"""
    calls: list[tuple[str, str]] = []

    def counting(name):
        def client(prompt, **k):
            calls.append((name, prompt))
            return {"answer": f"A {name}", "search_results": [], "usage": {}, "elapsed_s": 0.1}
        return client

    _iso(tmp_path, monkeypatch, clients={"qwen": counting("qwen"),
                                         "zhipu": counting("zhipu")})
    recs = run_collection(week=87, models=["qwen", "zhipu"],
                          prompt_ids=["C01", "D01"], runs=2, rule_version="t")
    assert len(calls) == 8                       # 2家 × 2题 × 2run
    keys = {(r.model, r.prompt_id, r.run) for r in recs if r.status == "ok"}
    assert len(keys) == 8
    calls.clear()
    recs2 = run_collection(week=87, models=["qwen", "zhipu"],
                           prompt_ids=["C01", "D01"], runs=2, rule_version="t")
    assert calls == []
    assert len(recs2) == 8 and all(r.status == "skipped_exists" for r in recs2)
```

注（2026-09-18 勘误）：原稿的跨字段连续子串 `"model":"doubao","prompt_id":"C01","status":"ok"` 依赖字段邻接，而 RunRecord 字段序（week, model, prompt_id, run, prompt_set_version, rule_snapshot_version, status, ...，见 `models.py:45-51`）中 prompt_id 与 status 隔三字段，永不匹配——Task 3 实现时改逐行三元组检查（如上），断言强度不降反升。

- [ ] **Step 2: 运行新测试**

```bash
cd geo-agent && PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/test_collector.py -p no:cacheprovider --timeout=120 -v
```
Expected: 全部 passed（Task 2 后这些场景应直接绿；若红，按失败信息修调度器——不是修测试预期）。

---

### Task 4: 全量回归 + 采集独立提交

**Files:**
- 无新文件；验证 + 提交 Task 1-3 产物。

**Interfaces:**
- Consumes: Task 1-3 的 `collector.py` + `test_collector.py` 改动。
- Produces: commit 1（采集优化完整交付）。

- [ ] **Step 1: Python 全量回归**

```bash
cd geo-agent && PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120
```
Expected: EXIT=0，passed 数 = 584 + 新增 5 = **589**（+2s 不变；任何既有测试变红 = 调度器破坏了保留行为，回 Task 2 修）。

- [ ] **Step 2: 提交（commit 1）**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/src/geo/collect/collector.py geo-agent/tests/test_collector.py
git commit -m "feat(collect): 供应商级并行调度 —— 每家最多1个在途请求

- 主循环 FIRST_COMPLETED 补位: 一家等待/退避不占另外两家执行机会
- run_collection 接口/CLIENTS/重试规则/manifest 语义零变化
- +5 并发契约测试(Event/Barrier 有界等待,不用 sleep 判并发)
- spec: docs/superpowers/specs/2026-09-18-vendor-parallel-collect-and-news-toc-design.md

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: ArticleToc + NewsArticleLayout 组件

**Files:**
- Create: `site/src/components/ArticleToc.astro`
- Create: `site/src/layouts/NewsArticleLayout.astro`

**Interfaces:**
- Consumes: 现有 `Layout.astro` Props（title/description/path/ogImage/jsonLd/noindex）。
- Produces: `TocItem = { id: string; text: string; depth: 2 | 3 }`（named type export，自 `ArticleToc.astro`）；`<ArticleToc items={TocItem[]} />`；`<NewsArticleLayout {...LayoutProps} toc={TocItem[]}>`（slot = 正文）。Task 6/7 页面按此消费。

- [ ] **Step 1: 写 `site/src/components/ArticleToc.astro`**

```astro
---
export interface TocItem {
  id: string;
  text: string;
  depth: 2 | 3;
}
interface Props {
  items: TocItem[];
}
const { items } = Astro.props;
---
<nav class="toc-col" aria-label="Table of contents">
  <p class="toc-title">On this page</p>
  <div class="toc-list">
    {items.map((it) => (
      <a class="toc-link" href={`#${it.id}`} data-depth={it.depth}>{it.text}</a>
    ))}
  </div>
</nav>

<details class="toc-mobile">
  <summary>On this page</summary>
  <div class="toc-list">
    {items.map((it) => (
      <a class="toc-link" href={`#${it.id}`} data-depth={it.depth}>{it.text}</a>
    ))}
  </div>
</details>

<style>
  .toc-title {
    margin: 0 0 10px;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--c-ink-soft);
  }
  .toc-link {
    display: block;
    padding: 5px 0 5px 10px;
    border-left: 2px solid var(--c-border);
    font-size: 0.88rem;
    line-height: 1.35;
    color: var(--c-ink-soft);
    text-decoration: none;
  }
  .toc-link[data-depth="3"] {
    padding-left: 26px;
    font-size: 0.84rem;
  }
  .toc-link:hover {
    color: var(--c-ink);
    border-left-color: var(--c-sun);
  }
  .toc-link:focus-visible {
    outline: 2px solid var(--c-sky);
    outline-offset: 2px;
  }
  .toc-link[aria-current="location"] {
    color: var(--c-ink);
    font-weight: 600;
    border-left-color: var(--c-sun-deep);
  }
  /* 桌面: 左侧 sticky 目录(避开 64px 顶部导航,过长独立滚动); 移动: 折叠块 */
  .toc-col {
    position: sticky;
    top: 88px;
    max-height: calc(100vh - 136px);
    overflow-y: auto;
    padding-top: 4px;
  }
  .toc-mobile {
    display: none;
    margin: 0 0 20px;
    border: 1px solid var(--c-border);
    border-radius: 8px;
    padding: 10px 14px;
    background: var(--c-bg-alt);
  }
  .toc-mobile summary {
    cursor: pointer;
    font-weight: 600;
    font-size: 0.92rem;
    color: var(--c-ink);
  }
  @media (max-width: 960px) {
    .toc-col { display: none; }
    .toc-mobile { display: block; }
  }
  @media print {
    .toc-col,
    .toc-mobile { display: none !important; }
  }
</style>

<script>
  // 增强脚本: 滚动高亮当前章节(aria-current="location")。
  // 纯增强 —— 无 JS 时目录与原生锚点跳转完全可用。
  const links = Array.from(document.querySelectorAll<HTMLAnchorElement>("a.toc-link"));
  const targets = links
    .map((l) => document.getElementById((l.getAttribute("href") ?? "").slice(1)))
    .filter((el): el is HTMLElement => el !== null);
  function setActive(id: string | null) {
    for (const l of links) {
      if (id && l.getAttribute("href") === `#${id}`) {
        l.setAttribute("aria-current", "location");
      } else {
        l.removeAttribute("aria-current");
      }
    }
  }
  function update() {
    const line = window.scrollY + 100;   // 略低于顶部导航的"当前位置线"
    let current: HTMLElement | null = null;
    for (const h of targets) {
      if (h.offsetTop <= line) current = h;   // 页顶→null;长章节间隙→保持上一个;文末→最后一个
      else break;
    }
    setActive(current ? current.id : null);
  }
  let queued = false;
  function onScroll() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      update();
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  update();
</script>
```

设计要点（勿偏离）：目录条目是 `<a>` + padding 缩进，**不用 ul/ol**（GEO 抓取器统计列表数）；标题 `.toc-title` 是 `<p>` 非 heading（H2/H3 计数不变）；sticky top 88px = 64px header + 24px 间隙。

- [ ] **Step 2: 写 `site/src/layouts/NewsArticleLayout.astro`**

```astro
---
import Layout from "./Layout.astro";
import ArticleToc from "../components/ArticleToc.astro";
import type { TocItem } from "../components/ArticleToc.astro";

interface Props {
  title: string;
  description?: string;
  path?: string;
  ogImage?: string;
  jsonLd?: object | object[];
  noindex?: boolean;
  toc: TocItem[];
}

const { title, description, path, ogImage, jsonLd, noindex, toc } = Astro.props;
---
<Layout title={title} description={description} path={path} ogImage={ogImage} jsonLd={jsonLd} noindex={noindex}>
  <section class="section">
    <div class="wrap article-shell">
      <ArticleToc items={toc} />
      <div class="article-main">
        <slot />
      </div>
    </div>
  </section>
</Layout>

<style>
  .article-shell {
    display: grid;
    grid-template-columns: 240px minmax(0, 1fr);
    gap: 48px;
    align-items: start;
  }
  /* 正文标题锚点定位偏移: 跳转后不被 64px 顶部导航遮住 */
  .article-main :global(h2[id]),
  .article-main :global(h3[id]) {
    scroll-margin-top: 88px;
  }
  @media (max-width: 960px) {
    .article-shell {
      display: block;
    }
  }
  @media print {
    .article-shell {
      display: block;
    }
  }
</style>
```

宽度账：`.wrap` = `--maxw:1120px` − padding 48 = 1072 可用；240 + 48 gap + 正文列 ≈ 784；`.prose` 自身 `max-width:760px` 生效——**无需加宽 wrap、不产生嵌套收窄**。

- [ ] **Step 3: 检查 + 构建验证（组件尚无消费者）**

```bash
cd site && npm run check && npm run build
```
Expected: check 0/0/0；build 成功 20 页（新组件未接入不改变产物）。若 astro check 对 `import type { TocItem } from "../components/ArticleToc.astro"` 报错（类型导出不支持），fallback：在两个组件内各自声明同名接口（结构类型，无需共享导出）。

---

### Task 6: 样例文章迁移（deep-dive）+ 预览关口

**Files:**
- Modify: `site/src/pages/news/home-solar-battery-deep-dive.astro`

**Interfaces:**
- Consumes: Task 5 的 `NewsArticleLayout` + `TocItem`。
- Produces: 迁移模式模板（Task 7 复刻）；预览截图（桌面+移动）给用户确认。

- [ ] **Step 1: 记录修改前基线（计数快照）**

```bash
cd site && npm run build && for f in dist/news/*/index.html; do
  echo "$f h1=$(grep -o '<h1\b' $f | wc -l) h2=$(grep -o '<h2\b' $f | wc -l) h3=$(grep -o '<h3\b' $f | wc -l) table=$(grep -o '<table\b' $f | wc -l) ul=$(grep -o '<ul\b' $f | wc -l) ol=$(grep -o '<ol\b' $f | wc -l)"
done | tee /tmp/toc-counts-baseline.txt
```
Expected: 8 行计数（deep-dive 应为 h2=9 h3=6）。

- [ ] **Step 2: frontmatter 改导入 + 声明 toc 数组**

`home-solar-battery-deep-dive.astro:2` 的 `import Layout ...` 改为：

```ts
import NewsArticleLayout from "../../layouts/NewsArticleLayout.astro";
import type { TocItem } from "../../components/ArticleToc.astro";
```

frontmatter 末尾（`</script>` 等价位置：两个 schema 常量之后）追加：

```ts
const toc: TocItem[] = [
  { id: "what-a-residential-solar-and-storage-system-includes", text: "What a residential solar and storage system includes", depth: 2 },
  { id: "key-definitions", text: "Key definitions", depth: 2 },
  { id: "hardware-specifications-at-a-glance", text: "Hardware specifications at a glance", depth: 2 },
  { id: "battery-sizing-start-from-evening-consumption", text: "Battery sizing: start from evening consumption", depth: 2 },
  { id: "solar-with-a-battery-vs-solar-without", text: "Solar with a battery vs solar without", depth: 2 },
  { id: "roof-suitability-and-installation-time", text: "Roof suitability and installation time", depth: 2 },
  { id: "warranty-coverage", text: "Warranty coverage", depth: 2 },
  { id: "frequently-asked-questions", text: "Frequently asked questions", depth: 2 },
  { id: "faq-what-does-a-residential-solar-and-storage-system-include", text: "What does a residential solar and storage system include?", depth: 3 },
  { id: "faq-how-big-should-my-battery-be", text: "How big should my battery be?", depth: 3 },
  { id: "faq-do-i-need-a-battery-with-solar-panels", text: "Do I need a battery with solar panels?", depth: 3 },
  { id: "faq-what-roof-types-are-suitable", text: "What roof types are suitable?", depth: 3 },
  { id: "faq-how-long-does-installation-take", text: "How long does installation take?", depth: 3 },
  { id: "faq-what-warranty-do-you-offer", text: "What warranty do you offer?", depth: 3 },
  { id: "sources", text: "Sources", depth: 2 },
];
```

（顺序 = 文档序；FAQ 的 6 个 H3 位于 "Frequently asked questions" 与 "Sources" 之间。）

- [ ] **Step 3: 模板改布局 + 正文加 id**

开标签（77-84 行）由：

```astro
<Layout
  title="Home Solar & Battery: A Data-Driven Deep Dive · SunHestia"
  description="..."
  path="news/home-solar-battery-deep-dive"
  jsonLd={[articleSchema, faqSchema]}
>
  <section class="section">
    <div class="wrap prose">
```

改为：

```astro
<NewsArticleLayout
  title="Home Solar & Battery: A Data-Driven Deep Dive · SunHestia"
  description="..."
  path="news/home-solar-battery-deep-dive"
  jsonLd={[articleSchema, faqSchema]}
  toc={toc}
>
  <div class="prose">
```

（description 原文保留不动。）闭标签（344-346 行）`</div></section></Layout>` → `</div></NewsArticleLayout>`。

15 个标题逐个加 id（text 保持原样）：`<h2>What a residential...` → `<h2 id="what-a-residential-solar-and-storage-system-includes">`，其余 14 个按 Step 2 数组的 id 对应加。

- [ ] **Step 4: 检查 + 构建 + 计数对照**

```bash
cd site && npm run check && npm run build
for f in dist/news/home-solar-battery-deep-dive/index.html; do
  echo "$f h1=$(grep -o '<h1\b' $f | wc -l) h2=$(grep -o '<h2\b' $f | wc -l) h3=$(grep -o '<h3\b' $f | wc -l) table=$(grep -o '<table\b' $f | wc -l) ul=$(grep -o '<ul\b' $f | wc -l) ol=$(grep -o '<ol\b' $f | wc -l) toc=$(grep -o 'class="toc-link"' $f | wc -l) nav=$(grep -o '<nav\b' $f | wc -l)"
done
grep -c 'rel="canonical"' dist/news/home-solar-battery-deep-dive/index.html
grep -o 'rel="canonical" href="[^"]*"' dist/news/home-solar-battery-deep-dive/index.html
```
Expected: h1=1 h2=9 h3=6 table=2 ul=1 ol=0 **与基线一致**；toc=30（15 条 × 桌面+移动两份）nav=1；canonical 恰 1 条且仍指向 `https://sunhestia.com/news/home-solar-battery-deep-dive/`。

- [ ] **Step 5: 预览截图（Chrome headless，零新依赖）**

```bash
cd site && (npm run preview >/tmp/astro-preview.log 2>&1 &) && sleep 2
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1440,2400 --screenshot=/tmp/toc-preview-desktop.png "http://127.0.0.1:4173/news/home-solar-battery-deep-dive/"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=390,1600 --screenshot=/tmp/toc-preview-mobile.png "http://127.0.0.1:4173/news/home-solar-battery-deep-dive/"
pkill -f "astro preview" || true
```
用 Read 工具查看两张 PNG 自查：桌面左侧 sticky 目录、H3 缩进、正文宽度未收窄；移动端 `<details>` 折叠块在正文上方、无横向溢出。自查不过先修再给用户。

- [ ] **Step 6: 🔴 用户预览关口**

将两张截图交付用户确认桌面+移动效果。**用户明确通过前不得开始 Task 7。**（本任务不提交——与 Task 7-9 合成 commit 2。）

---

### Task 7: 迁移剩余 7 篇文章

**Files:**
- Modify: `site/src/pages/news/what-is-self-consumption.astro`
- Modify: `site/src/pages/news/lifepo4-home-batteries.astro`
- Modify: `site/src/pages/news/self-consumption-guide.astro`
- Modify: `site/src/pages/news/solar-only-vs-solar-plus-battery-storage.astro`
- Modify: `site/src/pages/news/solar-only-vs-solar-plus-battery.astro`
- Modify: `site/src/pages/news/glossary.astro`
- Modify: `site/src/pages/news/about-the-team.astro`

**Interfaces:**
- Consumes: Task 5 组件、Task 6 迁移模式。
- Produces: 8/8 文章接入 TOC。

- [ ] **Step 1: 逐篇迁移（每篇四步，与 Task 6 完全同型）**

每篇：①import 换 `NewsArticleLayout` + `TocItem`；②frontmatter 加 `const toc: TocItem[] = [...]`；③开/闭标签换布局、`<section class="section"><div class="wrap prose">` → `<div class="prose">`；④全部 H2/H3 加 id。页面既有 `<style>` 块、日期行、表格、JSON-LD、正文文本**原样保留**。

**id 规则（确定性）**：`id = slug(标题文本)`；`slug` = 小写、`&` 与所有非 `[a-z0-9]+` 折叠为 `-`、去首尾 `-`；**FAQ 小节的 H3 加 `faq-` 前缀**（父 H2 为 "Frequently asked questions" 或 "FAQ"）。

各篇标题清单（→ id | depth），text 逐字取标题原文：

- `what-is-self-consumption`（3×H2）: why-self-consumption-beats-export | how-storage-raises-it | the-takeaway
- `lifepo4-home-batteries`（3×H2）: long-cycle-life | inherent-stability | cobalt-free
- `self-consumption-guide`（8×H2, 4×H3）: what-is-self-consumption | why-self-consumption-matters | the-core-system-for-self-consumption | hardware-at-a-glance | solar-only-vs-solar-with-storage | sizing-your-battery-for-self-consumption | warranty-and-longevity | frequently-asked-questions；H3: faq-do-i-need-a-battery-with-solar-panels | faq-how-big-should-my-battery-be | faq-how-long-does-installation-take | faq-what-roof-types-are-suitable
- `solar-only-vs-solar-plus-battery-storage`（4×H2, 9×H3）: at-a-glance-solar-only-vs-solar-battery | key-specifications | which-configuration-fits-you | frequently-asked-questions；H3: sunhestia-solar-pv-modules | sunhestia-home-battery | hybrid-inverter-energy-manager | solar-pv-only-may-fit-if-you | solar-pv-battery-may-fit-if-you | faq-do-i-need-a-battery-with-solar-panels | faq-how-big-should-my-battery-be | faq-how-long-does-installation-take | faq-what-warranty-do-you-offer
- `solar-only-vs-solar-plus-battery`（5×H2, 7×H3）: key-terms | side-by-side-at-a-glance | hardware-spec-cards | what-storage-changes | faq；H3: sunhestia-solar-pv-modules | sunhestia-home-battery | hybrid-inverter-energy-manager | faq-do-i-need-a-battery-with-solar-panels | faq-how-big-should-my-battery-be | faq-what-warranty-do-you-offer | faq-how-long-does-installation-take
- `glossary`（5×H2, 6×H3）: self-consumption | lifepo4 | hybrid-inverter | quick-reference-spec-cards | frequently-asked-questions；H3: sunhestia-home-battery | sunhestia-solar-pv-modules | hybrid-inverter-energy-manager | faq-what-does-a-residential-solar-and-storage-system-include | faq-how-big-should-my-battery-be | faq-what-warranty-do-you-offer
- `about-the-team`（6×H2, 7×H3）: how-your-system-is-designed | the-hardware-our-teams-install | installation-often-a-single-day-on-site | the-guarantees-behind-the-work | frequently-asked-questions | sources；H3: sunhestia-solar-pv-modules | sunhestia-home-battery | hybrid-inverter-energy-manager | faq-what-does-a-residential-solar-and-storage-system-include | faq-do-i-need-a-battery-with-solar-panels | faq-how-long-does-installation-take | faq-what-warranty-do-you-offer

（标题原文以各文件内 grep `<h2`/`<h3` 为准；`Hybrid Inverter &amp; Energy Manager` 的 toc text 用解码后文本 `Hybrid Inverter & Energy Manager`。）

- [ ] **Step 2: 检查 + 构建 + 全站计数对照**

```bash
cd site && npm run check && npm run build
for f in dist/news/*/index.html; do
  echo "$f h2=$(grep -o '<h2\b' $f | wc -l) h3=$(grep -o '<h3\b' $f | wc -l) table=$(grep -o '<table\b' $f | wc -l) ul=$(grep -o '<ul\b' $f | wc -l) ol=$(grep -o '<ol\b' $f | wc -l) toc=$(grep -o 'class="toc-link"' $f | wc -l)"
done
```
Expected: 每篇 h2/h3/table/ul/ol 与 `/tmp/toc-counts-baseline.txt` 一致；`toc = (h2+h3) × 2`。抽验 2 篇 canonical 仍为自引用全路径。

---

### Task 8: 目录完整性检查脚本 + CI + lastmod

**Files:**
- Create: `site/scripts/check-news-toc.mjs`
- Modify: `site/package.json`（scripts 加 `checktoc`）
- Modify: `.github/workflows/ci.yml`（site job Build 后加一步）
- Modify: `site/astro.config.mjs`（news 专属 lastmod 依赖）

**Interfaces:**
- Consumes: Task 5 组件的确定性标记（`<nav class="toc-col">` / `a.toc-link` + `data-depth` / `h2[id] h3[id]`）。
- Produces: `npm run checktoc`（exit 非 0 = 失败）；CI site job 第 4 个 run 步骤；`/news/<article>/` 路径 lastmod 计入新组件 mtime（列表页与全站其他页不受影响）。

- [ ] **Step 1: 写 `site/scripts/check-news-toc.mjs`**

```js
// 目录完整性检查(spec 2026-09-18 §5.2): 遍历 dist/news/*/index.html(排除列表页),
// 校验目录锚点与正文标题完全一致 —— 目录缺失/悬空链接/文字或顺序或层级不符/重复 id 均 fail。
// 零依赖;退出码非 0 = CI 失败。用法: npm run build && npm run checktoc
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const distNews = join(fileURLToPath(new URL("../dist/news/", import.meta.url)));

const norm = (s) =>
  s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
   .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
   .replace(/\s+/g, " ").trim();

function navLinks(html) {
  const nav = html.match(/<nav class="toc-col"[^>]*>([\s\S]*?)<\/nav>/);
  if (!nav) return null;
  const out = [];
  const re = /<a\b([^>]*)>([^<]*)<\/a>/g;
  let m;
  while ((m = re.exec(nav[1]))) {
    const href = m[1].match(/href="#([^"]+)"/);
    const depth = m[1].match(/data-depth="(\d)"/);
    if (href && depth) out.push({ id: href[1], text: norm(m[2]), depth: Number(depth[1]) });
  }
  return out;
}

function headings(html) {
  const out = [];
  const re = /<(h[23])\b([^>]*)>([^<]*)<\/\1>/g;
  let m;
  while ((m = re.exec(html))) {
    const id = m[2].match(/\bid="([^"]+)"/);
    out.push({ tag: m[1], id: id ? id[1] : null, text: norm(m[3]) });
  }
  return out;
}

let pages;
try {
  pages = readdirSync(distNews, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => join(distNews, d.name, "index.html"));
} catch {
  console.error("FAIL dist/news/ 不存在 —— 先 npm run build");
  process.exit(1);
}
if (pages.length === 0) {
  console.error("FAIL 未发现任何 dist/news/*/index.html");
  process.exit(1);
}

let failures = 0;
for (const p of pages) {
  const html = readFileSync(p, "utf8");
  const errs = [];
  const nav = navLinks(html);
  if (!nav || nav.length === 0) errs.push('缺少 <nav class="toc-col"> 目录');
  const hs = headings(html);
  const noId = hs.filter((h) => !h.id);
  if (noId.length) errs.push(`正文标题缺 id: ${noId.map((h) => h.text).join(" / ")}`);
  const counts = {};
  for (const h of hs) if (h.id) counts[h.id] = (counts[h.id] ?? 0) + 1;
  const dup = Object.entries(counts).filter(([, n]) => n > 1);
  if (dup.length) errs.push(`正文标题 id 重复: ${dup.map(([k]) => k).join(", ")}`);
  if (nav) {
    const seen = new Set();
    for (const l of nav) {
      if (seen.has(l.id)) errs.push(`目录重复链接 #${l.id}`);
      seen.add(l.id);
    }
    const want = hs.filter((h) => h.id)
      .map((h) => ({ id: h.id, text: h.text, depth: Number(h.tag[1]) }));
    if (JSON.stringify(nav) !== JSON.stringify(want)) {
      errs.push(`目录与正文标题不一致(逐条比对 id/text/depth/顺序):\n    toc : ${JSON.stringify(nav)}\n    body: ${JSON.stringify(want)}`);
    }
  }
  if (errs.length) {
    failures++;
    console.error(`FAIL ${p}\n  ${errs.join("\n  ")}`);
  } else {
    console.log(`ok   ${p} (${nav.length} 条目录)`);
  }
}
process.exit(failures ? 1 : 0);
```

- [ ] **Step 2: package.json 加脚本**

scripts 增加一行（保持既有项不动）：

```json
"checktoc": "node scripts/check-news-toc.mjs"
```

- [ ] **Step 3: 本地跑通（先故意制造一处不一致验证真门禁，再还原）**

```bash
cd site && npm run checktoc
```
Expected: 8 行 `ok`，EXIT=0。验证门禁有效性：临时改任一篇 toc 数组中一条 text → 重跑应 FAIL 且指出不一致 → 还原后复绿。

- [ ] **Step 4: CI site job 加步骤**

`.github/workflows/ci.yml` site job 的 `- name: Build` 之后加：

```yaml
      - name: TOC integrity (news articles)
        run: npm run checktoc
```

- [ ] **Step 5: astro.config.mjs news 专属 lastmod**

在 `sharedChromeMs` 定义之后加：

```js
// News-article chrome: TOC 布局与组件只影响 /news/<article>/ 页的 <lastmod>,
// 不进 sharedChrome —— 目录组件变化不得刷新全站其他页面(spec §4.3.7)。
const newsArticleMs = [
  'src/layouts/NewsArticleLayout.astro',
  'src/components/ArticleToc.astro',
]
  .map((f) => mtimeMs(`${root}${f}`))
  .filter((ms) => ms > 0);
```

`lastmodFor` 内（38 行）`const latest = Math.max(pageMs, ...sharedChromeMs);` 改为：

```js
  const latest = Math.max(
    pageMs,
    ...sharedChromeMs,
    ...(seg.startsWith('news/') && seg !== 'news' ? newsArticleMs : []),
  );
```

- [ ] **Step 6: 构建验证 lastmod 隔离**

```bash
cd site && npm run build && grep -o '<lastmod>[^<]*' dist/sitemap-0.xml | head -3 && grep -c '<url>' dist/sitemap-0.xml
```
Expected: build 成功；sitemap URL 数不变（20）；`/news/*` 条目带 lastmod；首页/legal 等条目 lastmod 不因新组件 mtime 变化（对比无组件时代的值——新组件文件 mtime 晚于页面，故只有 news 文章 lastmod 更新）。

---

### Task 9: 全量验收 + 站点独立提交 + 交付

**Files:**
- 无新文件；验证 + 提交 Task 5-8 产物。

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: commit 2；交付报告（修改清单/测试结果/预览/未验证项）。

- [ ] **Step 1: 站点全量验收**

```bash
cd site && npm run check && npm run build && npm run checktoc
```
Expected: check 0/0/0；build 20 页；checktoc 8 ok EXIT=0。

- [ ] **Step 2: Python 全量复跑（确认零波及）**

```bash
cd geo-agent && PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120
```
Expected: EXIT=0，589 passed + 2 skipped（与 commit 1 后一致）。

- [ ] **Step 3: 提交（commit 2）**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add site/src/components/ArticleToc.astro site/src/layouts/NewsArticleLayout.astro \
  site/src/pages/news/what-is-self-consumption.astro site/src/pages/news/lifepo4-home-batteries.astro \
  site/src/pages/news/self-consumption-guide.astro site/src/pages/news/solar-only-vs-solar-plus-battery-storage.astro \
  site/src/pages/news/solar-only-vs-solar-plus-battery.astro site/src/pages/news/glossary.astro \
  site/src/pages/news/about-the-team.astro site/src/pages/news/home-solar-battery-deep-dive.astro \
  site/scripts/check-news-toc.mjs site/package.json site/package-lock.json \
  site/astro.config.mjs .github/workflows/ci.yml
git commit -m "feat(site): news 全部 8 篇文章接入章节目录 —— NewsArticleLayout + ArticleToc

- 桌面左侧 sticky 目录(避开 64px nav),移动 <details> 折叠,禁 JS 可用
- 原生锚点跳转+scroll-margin-top;脚本仅增强 aria-current 高亮
- TOC 不用 ul/ol/heading,H2/H3/表格/列表计数与改前一致
- check-news-toc.mjs 产物级完整性检查入 CI;news 专属 lastmod 依赖
- spec: docs/superpowers/specs/2026-09-18-vendor-parallel-collect-and-news-toc-design.md

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

（`site/package-lock.json` 若无变化则从 add 列表去掉——`checktoc` 是纯脚本不加依赖，lock 大概率无 diff。）

- [ ] **Step 4: 交付报告**

向用户报告：修改文件清单、两个提交哈希、pytest/astro check/build/checktoc 结果、计数对照结论、预览截图位置、**尚未验证项**——真实三家接口的并行性能（本次未调用付费接口，留生产周观察；不预宣称提速倍数）、CI 远端运行（未推送，推送后 Actions 出结果）。

---

## Self-Review 记录（写计划时已核）

- **Spec 覆盖**：§3 采集（Task 1-4）｜§4.1-4.3 站点（Task 5-8）｜§5.1 十行场景（Task 1 三家首批/并发上限、Task 1 阻塞隔离、Task 3 退避隔离/失败即时/已完成不调/子集多run/全完成不请求——最后者由既有 `test_run_writes_l1_and_resumes` 覆盖；质量门由既有 graph 测试覆盖不改）｜§5.2 两层（Task 8 脚本 + Task 6 预览）｜§6 执行顺序（任务序=提交序，Task 6 关口）。
- **占位符扫描**：无 TBD/「适当处理」；全部代码块完整可执行。
- **类型一致性**：`TocItem` 定义（Task 5 ArticleToc）↔ Layout Props（Task 5）↔ 页面 `toc: TocItem[]`（Task 6/7）一致；`_run_vendor_parallel(todo, week, rule_version)` 定义与调用一致；测试 helper `_iso`/`_ok_answer`/`_wait_until` 定义先于使用。
