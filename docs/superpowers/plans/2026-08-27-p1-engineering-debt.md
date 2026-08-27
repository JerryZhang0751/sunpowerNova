# P1 工程债修复实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-08-24 工程审查 P1 全部五项：playbook 覆写保护 / fetcher 缓存毒化 / 依赖锁+黄金锁路径 / 周编号防线+快照冻结守卫 / cost_budget 删除。

**Architecture:** 五项相互独立，按 spec（`docs/superpowers/specs/2026-08-27-p1-engineering-debt-design.md`）审计序实施。新增两个共享小模块（`shared/io_utils.py` 原子写、`shared/weeks.py` 周编号校验），其余改动落在既有文件。全 TDD 红→绿。

**Tech Stack:** Python 3.11（代码）/ 3.12（测试运行时）、pytest + unittest.mock、pip requirements.lock、GitHub Actions。

## Global Constraints

- 分支：`p1-eng-debt`，自 main=8865cbb 切出；每任务独立 commit；完成后 merge --no-ff。
- 测试命令（.venv 被沙箱封锁的既定替代，/tmp/pylibs312 已装好）：
  `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
- 单测：同上加 `tests/test_x.py::test_name -v`。
- 基线：376 passed + 2 skipped；黄金锁 43.4/49.8 零漂移（`tests/test_v1_semantics.py` 必须保持 pass）。
- 所有新测试离线（全 mock），不加 `@pytest.mark.live`。
- **禁 `git add -A`**——一律显式路径。仓库根在 `sunpower nova/`，代码在 `geo-agent/`（下文相对路径均以 geo-agent/ 为根，CI 文件除外）。
- `git restore knowledge/` 纪律：任何测试若意外触碰生产 `knowledge/playbook.md`（tracked），任务结束时 `git status` 必须干净。

---

### Task 1: 共享原子写 helper `io_utils`

**Files:**
- Create: `src/geo/shared/io_utils.py`
- Test: `tests/test_io_utils.py`

**Interfaces:**
- Consumes: 无（仅 stdlib）。
- Produces: `atomic_write_text(path: Path, text: str) -> None`（写 `<path>.tmp` 后 `os.replace`）。Task 2、Task 5 依赖此函数。

- [ ] **Step 0: 建分支**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git checkout -b p1-eng-debt main
```

- [ ] **Step 1: 写失败测试**

```python
# tests/test_io_utils.py
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from geo.shared.io_utils import atomic_write_text

def test_atomic_write_creates_file(tmp_path):
    p = tmp_path / "a.json"
    atomic_write_text(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"

def test_atomic_write_replaces_existing(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("old", encoding="utf-8")
    atomic_write_text(p, "new")
    assert p.read_text(encoding="utf-8") == "new"

def test_atomic_write_failure_leaves_original_intact(tmp_path):
    """写入中断(替换前异常)不得损坏原文件——覆写保护的底线。"""
    p = tmp_path / "a.md"
    p.write_text("GOOD", encoding="utf-8")
    with patch("geo.shared.io_utils.os.replace", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            atomic_write_text(p, "BAD")
    assert p.read_text(encoding="utf-8") == "GOOD"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_io_utils.py -v -p no:cacheprovider`
Expected: FAIL（ModuleNotFoundError: geo.shared.io_utils）

- [ ] **Step 3: 最小实现**

```python
# src/geo/shared/io_utils.py
from __future__ import annotations
import os
from pathlib import Path

def atomic_write_text(path: Path, text: str) -> None:
    """tmp + os.replace 原子写:读方要么看到完整旧文件、要么看到完整新文件。"""
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同 Step 2。Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git add geo-agent/src/geo/shared/io_utils.py geo-agent/tests/test_io_utils.py && git commit -m "feat(shared): atomic_write_text 原子写 helper"
```

---

### Task 2: playbook/profiles 保旧+草稿（覆写保护）

**Files:**
- Modify: `src/geo/research/run.py`（run_research 写入段，约 42-71 行）
- Modify: `src/geo/research/render.py`（render_playbook / render_profiles 加 banner 参数）
- Modify: `src/geo/research/kimi.py:32`（失败日志升格）
- Test: `tests/test_run.py`（追加）

**Interfaces:**
- Consumes: `atomic_write_text`（Task 1）。
- Produces: `run_research` 返回 dict 新增键 `degraded: bool`、`drafts: list[str]`（既有键不变）；`render_playbook(..., banner: str = "")`、`render_profiles(..., banner: str = "")`；模块级 `_promote(target, text, *, week, draft, repo) -> Path`。

- [ ] **Step 1: 写失败测试（追加到 tests/test_run.py）**

```python
# ---- 追加到 tests/test_run.py(文件头已有 import json / from pathlib import Path)

def _mini_repo(tmp_path):
    """镜像 research fixture 为隔离 repo(既有模式)。"""
    import shutil
    FIX = Path(__file__).parent / "fixtures" / "research"
    for sub in ["data/raw", "data/sources", "data/snapshots", "input"]:
        src = FIX / sub
        if src.exists():
            shutil.copytree(src, tmp_path / sub, dirs_exist_ok=True)
    return tmp_path

_SYNTH_OK = '{"conclusions":[{"id":"c1","category":"source","conclusion":"外部权威站被引多","sample_n":3,"platforms":["qwen"],"confidence":"mid","action":"优先补权威外链","bucket_key":""}]}'

def test_kimi_failure_keeps_playbook_writes_draft(tmp_path):
    repo = _mini_repo(tmp_path)
    pb = repo / "knowledge" / "playbook.md"; pf = repo / "knowledge" / "platform-profiles.md"
    (repo / "knowledge").mkdir(parents=True, exist_ok=True)
    pb.write_text("OLD PLAYBOOK", encoding="utf-8"); pf.write_text("OLD PROFILES", encoding="utf-8")
    def boom(*a, **k): raise RuntimeError("kimi down")
    res = run_research(1, kimi_enabled=True, synth_fn=boom, web_fn=boom, fetch_n=0, repo=repo)
    assert pb.read_text(encoding="utf-8") == "OLD PLAYBOOK"      # 正式文件不动
    assert pf.read_text(encoding="utf-8") == "OLD PROFILES"
    draft_pb = repo / "knowledge" / "playbook.md.draft"
    assert draft_pb.exists() and "Kimi 综合不可用" in draft_pb.read_text(encoding="utf-8")
    assert (repo / "knowledge" / "platform-profiles.md.draft").exists()
    assert res["degraded"] is True and len(res["drafts"]) == 2

def test_success_promotes_and_backs_up(tmp_path):
    repo = _mini_repo(tmp_path)
    pb = repo / "knowledge" / "playbook.md"
    (repo / "knowledge").mkdir(parents=True, exist_ok=True)
    pb.write_text("OLD PLAYBOOK", encoding="utf-8")
    web_text = "GPTBot 爬虫存在。来源：https://openai.com/gptbot 置信度：high"
    res = run_research(1, kimi_enabled=True, synth_fn=lambda m, **k: _SYNTH_OK,
                       web_fn=lambda m, **k: web_text, fetch_n=0, repo=repo)
    assert res["degraded"] is False and res["drafts"] == []
    assert "OLD PLAYBOOK" not in pb.read_text(encoding="utf-8")  # 已更新
    hist = list((repo / "knowledge" / ".history").glob("playbook-w1-*.md"))
    assert len(hist) == 1 and hist[0].read_text(encoding="utf-8") == "OLD PLAYBOOK"
    assert not (repo / "knowledge" / "playbook.md.draft").exists()

def test_no_kimi_writes_direct_with_banner(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_research(1, kimi_enabled=False, fetch_n=0, repo=repo)
    pb = repo / "knowledge" / "playbook.md"
    assert pb.exists() and "确定性模式" in pb.read_text(encoding="utf-8")
    assert res["degraded"] is False and not (repo / "knowledge" / "playbook.md.draft").exists()

def test_profiles_independent_gate(tmp_path):
    """synthesize 成功但 web_search 全失败 → playbook 晋升、profiles 走草稿。"""
    repo = _mini_repo(tmp_path)
    def web_boom(*a, **k): raise RuntimeError("net down")
    res = run_research(1, kimi_enabled=True, synth_fn=lambda m, **k: _SYNTH_OK,
                       web_fn=web_boom, fetch_n=0, repo=repo)
    assert (repo / "knowledge" / "playbook.md").exists()
    assert (repo / "knowledge" / "platform-profiles.md.draft").exists()
    assert res["degraded"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_run.py -v -p no:cacheprovider`
Expected: 新增 4 条 FAIL（正式文件被覆写 / degraded 键不存在）；既有 `test_run_research_deterministic_path_writes_files` PASS。

- [ ] **Step 3: 实现**

`render.py` — 两函数加 `banner: str = ""` 参数，插入位置为标题行之后：

```python
def render_playbook(conclusions, aggregates, week, feed=None, banner: str = "") -> str:
    c = aggregates.coverage
    L = [f"# SunHestia GEO Playbook · w{week}",
         f"> rule_version {_rule_version(feed)} | L1={c.total_l1} | 被引源分析 sample_n={c.l3_resolved}(缺失{c.l3_missing}/js_only{c.l3_js_only})",
         "> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。\n"]
    if banner:
        L.insert(1, banner)          # 标题正下方、元信息行之上
    ...

def render_profiles(platforms_metrics, verified_facts, week, banner: str = "") -> str:
    L = [f"# 平台引用画像 · w{week}", ""]
    if banner:
        L.insert(1, banner)
    ...
```

`run.py` — 顶部补 `import shutil, time` 与 `from geo.shared.io_utils import atomic_write_text`；新增 `_promote`；`run_research` 尾段（从写 aggregates 到 return）替换为：

```python
def _promote(target: Path, text: str, *, week: int, draft: bool, repo: Path) -> Path:
    """draft=True → 写 <name>.draft 不动正式文件;否则晋升(旧文件备份 knowledge/.history/)。"""
    out = target.parent / (target.name + ".draft") if draft else target
    if not draft:
        if target.exists():
            hist = repo / "knowledge" / ".history"; hist.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            shutil.copy2(target, hist / f"{target.stem}-w{week}-{ts}{target.suffix}")
        stale = target.parent / (target.name + ".draft")
        if stale.exists(): stale.unlink()
    atomic_write_text(out, text)
    return out

# run_research 内,替换原 62-71 行:
    (repo/"data"/"analysis"/f"w{week}").mkdir(parents=True, exist_ok=True)
    atomic_write_text(repo/"data"/"analysis"/f"w{week}"/"research_aggregates.json",
                      json.dumps(_agg_jsonable(agg), ensure_ascii=False, indent=2))
    (repo/"knowledge").mkdir(parents=True, exist_ok=True)
    pb_path = repo/"knowledge"/"playbook.md"; pf_path = repo/"knowledge"/"platform-profiles.md"
    pb_degraded = kimi_enabled and not conclusions
    pf_degraded = kimi_enabled and not any((v or {}).get("answer") for v in verified.values())
    ts = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    pb_banner = (f"> ⚠️ 本轮 Kimi 综合不可用（{ts}），结论为空——确定性聚合仍有效。"
                 "此为草稿，未晋升；正式 playbook 保持上一成功轮。") if pb_degraded else \
                ("> 确定性模式（--no-kimi）：本 playbook 未含 Kimi 综合结论。" if not kimi_enabled else "")
    pf_banner = (f"> ⚠️ 本轮联网查证不可用（{ts}）——画像为确定性数据+草稿，未晋升。"
                 ) if pf_degraded else ""
    _promote(pb_path, render_playbook(conclusions, agg, week, feed=feed, banner=pb_banner),
             week=week, draft=pb_degraded, repo=repo)
    _promote(pf_path, render_profiles(agg.platforms, verified, week, banner=pf_banner),
             week=week, draft=pf_degraded, repo=repo)
    drafts = [str(p) for p, d in ((pb_path, pb_degraded), (pf_path, pf_degraded)) if d
              for p in [p.parent / (p.name + ".draft")]]
    return {"playbook": str(pb_path), "profiles": str(pf_path),
            "conclusions": len(conclusions), "verified_platforms": len(verified),
            "degraded": pb_degraded or pf_degraded, "drafts": drafts}
```

`kimi.py:32` 日志升格：

```python
        log.warning("synthesize failed (%s: %s); returning [] — run_research 将走草稿不覆写正式文件",
                    type(e).__name__, e)
```

另：项目根 `.gitignore`（`sunpower nova/.gitignore`）追加一行 `geo-agent/knowledge/.history/`。

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_run.py tests/test_render.py tests/test_kimi.py -v -p no:cacheprovider`，然后全量。
Expected: 新 4 条 PASS；test_render 既有断言若因 banner 默认空而不受影响则 PASS（若有对 render 输出行序的精确断言失败，仅因默认行为未变——不该失败，失败则修实现而非测试）。

- [ ] **Step 5: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git add geo-agent/src/geo/research/run.py geo-agent/src/geo/research/render.py geo-agent/src/geo/research/kimi.py geo-agent/tests/test_run.py .gitignore && git commit -m "feat(research): playbook/profiles 保旧+草稿 —— Kimi 失败不再覆写,晋升前备份,三处原子写"
```

---

### Task 3: fetcher 失败不落缓存 + 存量毒化自愈

**Files:**
- Modify: `src/geo/fetch/fetcher.py`（fetch_source 全函数体 + 新增 FetchError）
- Modify: `src/geo/research/sample.py:21-33`（fetch_topn 计数）
- Test: `tests/test_fetcher.py`（追加）、`tests/test_sample.py`（追加）

**Interfaces:**
- Consumes: 无新依赖。
- Produces: `FetchError(RuntimeError)`（`geo.fetch.fetcher.FetchError`）——传输异常与非 2xx 终态上抛、不落盘；调用方（graph.fetch_node / fetch_topn）既有 `except Exception` 兼容，不需改。

- [ ] **Step 1: 写失败测试（追加到 tests/test_fetcher.py）**

```python
import httpx as _httpx  # 文件头若无则补
from geo.fetch.fetcher import FetchError  # 文件头 import 行扩展

def _clean(url):
    import shutil
    sd = source_dir(sha1_url(url))
    shutil.rmtree(sd, ignore_errors=True)
    return sd

def test_transport_error_raises_no_cache():
    url = "https://transient.example/x"
    sd = _clean(url)
    with patch("geo.fetch.fetcher._safe_get", side_effect=_httpx.ConnectError("net down")):
        with pytest.raises(FetchError):
            fetch_source(url, fetcher_kimi=False)
    assert not (sd/"text.md").exists() and not (sd/"meta.json").exists()

def test_http_error_raises_no_cache():
    url = "https://blocked.example/y"
    sd = _clean(url)
    r = MagicMock(status_code=403, text="<html>forbidden</html>")
    with patch("geo.fetch.fetcher._safe_get", return_value=r):
        with pytest.raises(FetchError, match="403"):
            fetch_source(url, fetcher_kimi=False)
    assert not (sd/"meta.json").exists()

def test_200_empty_body_caches_js_only():
    url = "https://jsshell.example/z"
    sd = _clean(url)
    r = MagicMock(status_code=200, text="<html><body><div id='app'></div></body></html>")
    with patch("geo.fetch.fetcher._safe_get", return_value=r):
        rec = fetch_source(url, fetcher_kimi=False)
    assert rec.js_only is True and rec.http_status == 200
    assert (sd/"meta.json").exists()          # 真 JS-only 照常缓存

def test_poisoned_cache_entry_is_refetched():
    """存量毒化条目(js_only+http_status None)命中时视为 miss 重抓。"""
    url = "https://poisoned.example/p"
    sd = _clean(url)
    sd.mkdir(parents=True, exist_ok=True)
    (sd/"text.md").write_text("", encoding="utf-8")
    (sd/"meta.json").write_text(json.dumps(
        {"url": url, "sha1": sha1_url(url), "http_status": None, "text": "",
         "structural": {}, "semantic": {}, "js_only": True, "fetched_iso": "2026-08-01T00:00:00Z"}),
        encoding="utf-8")
    r = MagicMock(status_code=200, text="<html><body><p>Real article text paragraph.</p></body></html>")
    with patch("geo.fetch.fetcher._safe_get", return_value=r):
        rec = fetch_source(url, fetcher_kimi=False)
    assert rec.http_status == 200 and rec.js_only is False   # 已被新结果覆写
```

`tests/test_sample.py` 追加：

```python
def test_fetch_topn_counts_js_only(monkeypatch):
    from geo.research.sample import fetch_topn
    from unittest.mock import MagicMock
    # 三个 URL 依序返回: js_only / 正常 / 抛错(失败)
    results = [MagicMock(js_only=True), MagicMock(js_only=False), None]
    it = iter(results)
    def fake(u):
        v = next(it)
        if v is None: raise RuntimeError("x")
        return v
    monkeypatch.setattr("geo.fetch.fetcher.fetch_source", fake)
    st = fetch_topn(["a/js", "b/doc", "c/dead"])
    assert st.requested == 3 and st.fetched == 2 and st.failed == 1 and st.js_only == 1
```

（注：`fetch_topn` 内 `from geo.fetch.fetcher import fetch_source` 是函数内 import，patch `geo.fetch.fetcher.fetch_source` 生效。）

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_fetcher.py tests/test_sample.py -v -p no:cacheprovider`
Expected: 新增 5 条 FAIL（ImportError FetchError / 行为不符）；若既有测试依赖"异常→js_only 缓存"旧行为而失败，按新语义修正该测试期望（同 r2 修 health denominator 的先例）。

- [ ] **Step 3: 实现**

`fetcher.py` — 顶部 `UnsafeURLError` import 行下补：

```python
class FetchError(RuntimeError):
    """传输失败或非 2xx 终态:不落缓存、上抛,下次运行自然重试(2026-08-27 P1②)。"""
```

`fetch_source` 主体替换（保留缓存命中判断的结构，加毒化自愈）：

```python
def fetch_source(url: str, fetcher_kimi=True, transport=None) -> L3Source:
    sha = sha1_url(url); sd = source_dir(sha)
    text_path = sd/"text.md"; meta_path = sd/"meta.json"
    if text_path.exists():
        import json
        cached = L3Source(**json.loads(meta_path.read_text(encoding="utf-8")))
        if cached.js_only and cached.http_status is None:
            pass   # 存量毒化条目(异常路径从不带 status)→ 视为 miss 重抓
        else:
            return cached
    t0 = time.time(); status = None; text = ""; js_only = False; structural = {}
    try:
        r = _safe_get(url, transport); status = r.status_code
        if not (200 <= status < 300):
            raise FetchError(f"HTTP {status}: {url}")
        text = trafilatura.extract(r.text) or ""
        if not text.strip(): js_only = True
        structural = extract_structural(BeautifulSoup(r.text, "lxml"))
    except (UnsafeURLError, FetchError):
        # UnsafeURLError=安全拦截、FetchError=传输/HTTP失败:均上抛且不落盘。
        # 落盘空文本会永久毒化缓存(2026-08-24 审查 P1-2)。
        raise
    except Exception as e:
        raise FetchError(f"{type(e).__name__}: {e} ({url})") from e
    semantic = extract_semantic(text) if (fetcher_kimi and text.strip()) else {}
    rec = L3Source(url=url, sha1=sha, http_status=status, text=text,
                   structural=structural, semantic=semantic, js_only=js_only,
                   fetched_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    atomic_write_text(sd/"text.md", text)  # text 用原子写;meta 同
    import json; atomic_write_text(meta_path, rec.model_dump_json())
    return rec
```

（顶部补 `from geo.shared.io_utils import atomic_write_text`。）

`sample.py` — `fetch_topn` 替换为：

```python
def fetch_topn(urls: list[str]) -> FetchStats:
    from geo.fetch.fetcher import fetch_source
    fetched = failed = js = 0
    for u in urls:
        try:
            rec = fetch_source(u)
            fetched += 1
            if getattr(rec, "js_only", False): js += 1
        except Exception:
            failed += 1
    return FetchStats(requested=len(urls), fetched=fetched, failed=failed, js_only=js)
```

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: 全量套件。Expected: 全绿（376+新增）。黄金锁不受影响（L1/分析路径未动）。

- [ ] **Step 5: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git add geo-agent/src/geo/fetch/fetcher.py geo-agent/src/geo/research/sample.py geo-agent/tests/test_fetcher.py geo-agent/tests/test_sample.py && git commit -m "feat(fetch): 失败不落缓存(FetchError) + 存量毒化自愈 + js_only 计数接通"
```

---

### Task 4: 周编号防线（weeks.py + 入口接线 + 测试迁移 + 残留清理）

**Files:**
- Create: `src/geo/shared/weeks.py`、`tests/test_weeks.py`
- Modify: `src/geo/orchestrate/graph.py`（run_pipeline 首行）、`src/geo/collect/collector.py`（__main__）、`src/geo/research/run.py`（__main__）、`src/geo/rules/run.py`（main 的 iterate/recalc 分支）、`src/geo/generate/run.py`（main 的 --topic 分支）
- Modify: `tests/test_gsc.py`、`tests/test_site_signals.py`（week=99 → TEST_WEEK + snapshot_dir 隔离）
- Test: `tests/test_weeks.py`（新）、`tests/test_graph.py`（追加 1 条）

**Interfaces:**
- Produces: `TEST_WEEK_MIN=900`、`TEST_WEEK_MAX=999`、`TEST_WEEK=901`、`validate_production_week(week: int) -> int`（非法 raise ValueError）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_weeks.py
import pytest
from geo.shared.weeks import validate_production_week, TEST_WEEK, TEST_WEEK_MIN, TEST_WEEK_MAX

@pytest.mark.parametrize("w", [1, 2, 8, 53, 100, 899])
def test_production_weeks_pass(w):
    assert validate_production_week(w) == w

@pytest.mark.parametrize("w", [0, -1, -100])
def test_nonpositive_rejected(w):
    with pytest.raises(ValueError, match="week"):
        validate_production_week(w)

def test_test_band_rejected():
    for w in (TEST_WEEK_MIN, TEST_WEEK, 950, TEST_WEEK_MAX):
        with pytest.raises(ValueError, match="测试保留带"):
            validate_production_week(w)
```

`tests/test_graph.py` 追加：

```python
def test_run_pipeline_rejects_test_band_week(monkeypatch, tmp_path):
    """入口接线:测试保留带周号在生产入口被拒。"""
    monkeypatch.setattr(G, "REPO", tmp_path)
    with pytest.raises(ValueError, match="测试保留带"):
        G.run_pipeline(901)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_weeks.py "tests/test_graph.py::test_run_pipeline_rejects_test_band_week" -v -p no:cacheprovider`
Expected: FAIL（模块不存在 / run_pipeline 未拒）。

- [ ] **Step 3: 实现**

```python
# src/geo/shared/weeks.py
from __future__ import annotations

TEST_WEEK_MIN = 900
TEST_WEEK_MAX = 999
TEST_WEEK = 901   # 无法注入 repo 的测试(snapshot 等)统一用此带,与生产周空间隔离

def validate_production_week(week: int) -> int:
    """生产入口周号校验:正数且不落在测试保留带。库函数不加(测试带 tmp repo 直调合法)。"""
    if not isinstance(week, int) or isinstance(week, bool) or week < 1:
        raise ValueError(f"week 必须为正整数: {week!r}")
    if TEST_WEEK_MIN <= week <= TEST_WEEK_MAX:
        raise ValueError(f"week {week} 落在测试保留带 [{TEST_WEEK_MIN},{TEST_WEEK_MAX}];"
                         f"生产周请用 1–{TEST_WEEK_MIN-1},测试请 from geo.shared.weeks import TEST_WEEK")
    return week
```

入口接线（各一处、最小改动）：
- `graph.py run_pipeline` 首行（`from datetime import datetime` 之前）：`from geo.shared.weeks import validate_production_week`（顶部 import）+ 函数体首行 `validate_production_week(week)`。
- `collector.py __main__`：`run_collection(validate_production_week(settings.run.week), ...)`（顶部 import）。
- `research/run.py __main__`：`print(run_research(validate_production_week(a.week), kimi_enabled=not a.no_kimi))`。
- `rules/run.py main`：parse 后加 `if a.cmd in ("iterate", "recalc"): validate_production_week(a.week)`。
- `generate/run.py main`：`--topic` 分支 `run_generate(a.topic, a.page_type, validate_production_week(a.week), ...)`。

- [ ] **Step 4: 测试迁移（test_gsc / test_site_signals）**

两文件统一改法：文件头加

```python
from geo.shared.weeks import TEST_WEEK
```

`week=99` 全部替换为 `week=TEST_WEEK`；**删除函数签名里从未使用的 `tmp_path, monkeypatch` 形参**（如 `test_gsc_degrades_on_auth_error(tmp_path, monkeypatch)` → `test_gsc_degrades_on_auth_error()`）。同时在两文件加 snapshot_dir 隔离 fixture（放 `tests/conftest.py` 更好——两个文件共用）：

```python
# tests/conftest.py 追加
import pytest

@pytest.fixture
def iso_snapshots(tmp_path, monkeypatch):
    """把 snapshot_dir 重定向到 tmp,隔离生产 data/snapshots(周编号带子之外的第二道防线)。"""
    def fake_dir(week):
        p = tmp_path / f"w{week}"; p.mkdir(parents=True, exist_ok=True); return p
    import geo.fetch.gsc as _g, geo.fetch.site_signals as _s
    monkeypatch.setattr(_g, "snapshot_dir", fake_dir)
    monkeypatch.setattr(_s, "snapshot_dir", fake_dir)
    return tmp_path
```

`test_gsc.py` / `test_site_signals.py` 中**真正调用 snapshot_gsc / snapshot_static_signals 的测试**加 `iso_snapshots` fixture 形参（纯 `_build_service` mock 类测试不用）。
（注意：实现时先确认两模块的 import 形式——若为 `from geo.shared.storage import snapshot_dir`，patch 模块属性即生效；若直接 `from geo.shared.storage import ...` 已绑定，patch 目标就是 `geo.fetch.gsc.snapshot_dir`。）

- [ ] **Step 5: 残留清理（一次性，删前逐个核实）**

```bash
cd geo-agent
for d in data/analysis/w42 data/analysis/w77 data/analysis/w88 data/analysis/w99 data/analysis/w101 data/analysis/w123 data/analysis/w202 data/raw/w99 data/snapshots/w5 data/snapshots/w99; do
  echo "== $d =="; ls -la "$d" 2>/dev/null | head -5
done
```

核实标准：目录内容为测试产物（research_aggregates.json 单文件 / mock rows 的 gsc.json / 空 runs.jsonl），**绝不含真实周数据**（w1 的 eval_report 有 43.4/49.8 与完整维度）。w5 的 gsc.json 打开确认 rows 为 mock（真 GSC 有 site=sc-domain:sunhestia.com）。核实后：

```bash
rm -rf data/analysis/w42 data/analysis/w77 data/analysis/w88 data/analysis/w99 data/analysis/w101 data/analysis/w123 data/analysis/w202 data/raw/w99 data/snapshots/w5 data/snapshots/w99
```

**绝不碰 `data/analysis/w1`、`data/raw/w1`、`data/snapshots/w1`。**

- [ ] **Step 6: 全量回归**

Run: 全量套件。Expected: 全绿；`git status` 干净（data/ gitignored）。

- [ ] **Step 7: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git add geo-agent/src/geo/shared/weeks.py geo-agent/tests/test_weeks.py geo-agent/tests/test_graph.py geo-agent/tests/test_gsc.py geo-agent/tests/test_site_signals.py geo-agent/tests/conftest.py geo-agent/src/geo/orchestrate/graph.py geo-agent/src/geo/collect/collector.py geo-agent/src/geo/research/run.py geo-agent/src/geo/rules/run.py geo-agent/src/geo/generate/run.py && git commit -m "feat(shared): 周编号防线 —— 测试保留带 900-999 + 五入口校验 + snapshot 测试隔离 + 残留清理"
```

---

### Task 5: 快照冻结守卫（gsc + static_signals，含原子写）

**Files:**
- Modify: `src/geo/fetch/gsc.py:34-46`（snapshot_gsc）
- Modify: `src/geo/fetch/site_signals.py:59-84`（snapshot_static_signals）
- Test: `tests/test_gsc.py`、`tests/test_site_signals.py`（追加）

**Interfaces:**
- Consumes: `atomic_write_text`（Task 1）；`iso_snapshots` fixture（Task 4）。
- Produces: `snapshot_gsc(week, rule_version, days=28) -> dict`——输出已存在且 `degraded != True` → 直接返回现有内容（跳过重冻结）；`snapshot_static_signals` 同（存在即返回，无 degraded 概念）。语义对 graph.snapshot_node 透明（幂等续跑）。

- [ ] **Step 1: 写失败测试（追加）**

`tests/test_gsc.py`：

```python
def test_gsc_clean_snapshot_is_frozen(iso_snapshots):
    """干净快照不可重冻结——GSC 28 天窗口会移动,重冻结=毁历史基线。"""
    from geo.shared.storage import snapshot_dir
    import json as _json
    p = snapshot_dir(TEST_WEEK) / "gsc.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "geo-seo-v2",
                              "site": "sc-domain:x", "rows": [{"keys": ["frozen"]}], "degraded": False}),
                 encoding="utf-8")
    svc = MagicMock()
    svc.searchanalytics().query().execute.return_value = {"rows": [{"keys": ["NEW!"]}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="geo-seo-v2")
    assert out["rows"] == [{"keys": ["frozen"]}]          # 返回现有,未重取
    svc.searchanalytics().query().execute.assert_not_called()

def test_gsc_degraded_snapshot_can_be_refrozen(iso_snapshots):
    from geo.shared.storage import snapshot_dir
    import json as _json
    p = snapshot_dir(TEST_WEEK) / "gsc.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "t", "site": "s",
                              "rows": [], "degraded": True, "error": "SSLEOFError"}),
                 encoding="utf-8")
    svc = MagicMock()
    svc.searchanalytics().query().execute.return_value = {"rows": [{"keys": ["ok"]}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is False and out["rows"] == [{"keys": ["ok"]}]
```

（08-13 的 SSLEOFError 合法重跑 = degraded 场景，第二测试锁死该口径。）

`tests/test_site_signals.py`：

```python
def test_static_signals_existing_snapshot_frozen(iso_snapshots):
    from geo.shared.storage import snapshot_dir
    import json as _json
    p = snapshot_dir(TEST_WEEK) / "static_signals.json"
    p.write_text(_json.dumps({"week": TEST_WEEK, "rule_version": "t", "site": "s",
                              "pages": [{"url": "FROZEN"}]}), encoding="utf-8")
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        out = snapshot_static_signals(week=TEST_WEEK, rule_version="t")
    C.assert_not_called()                                  # 不发任何请求
    assert out["pages"] == [{"url": "FROZEN"}]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_gsc.py tests/test_site_signals.py -v -p no:cacheprovider`
Expected: 新 3 条 FAIL（现实现无条件重取重写）。

- [ ] **Step 3: 实现**

`gsc.py` — 顶部补 `import logging`、`from geo.shared.io_utils import atomic_write_text`、`log = logging.getLogger("fetch.gsc")`；snapshot_gsc 函数体开头加守卫、写盘改原子：

```python
def snapshot_gsc(week:int, rule_version:str, days=28) -> dict:
    out_path = snapshot_dir(week)/"gsc.json"
    if out_path.exists():                       # 冻结守卫(2026-08-27 P1④)
        prev = json.loads(out_path.read_text(encoding="utf-8"))
        if not prev.get("degraded"):
            if prev.get("rule_version") != rule_version:
                log.warning("w%s gsc 快照已存在(规则版本 %s ≠ 请求 %s),按冻结语义跳过重取",
                            week, prev.get("rule_version"), rule_version)
            return prev                         # 干净快照=历史基线,不可被今日窗口重冻结
    site = _gsc_site_url()
    ...                                          # 其余不变
    atomic_write_text(out_path, json.dumps(out, ensure_ascii=False, indent=2))
    return out
```

`site_signals.py` — 同法：

```python
def snapshot_static_signals(week:int, rule_version:str) -> dict:
    out_path = snapshot_dir(week)/"static_signals.json"
    if out_path.exists():                       # 存在即冻结(无 degraded 概念)
        prev = json.loads(out_path.read_text(encoding="utf-8"))
        log.info("w%s static_signals 快照已存在,跳过重取(冻结)", week)
        return prev
    ...
    atomic_write_text(out_path, json.dumps(out, ensure_ascii=False, indent=2))
    return out
```

（site_signals.py 同样补 logging 与 atomic_write_text import。）

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: 全量套件。Expected: 全绿。注意 `test_graph.py` 若有驱动 snapshot_node 的集成测试，快照守卫使其幂等跳过——断言若依赖"重取"需按冻结语义更新。

- [ ] **Step 5: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git add geo-agent/src/geo/fetch/gsc.py geo-agent/src/geo/fetch/site_signals.py geo-agent/tests/test_gsc.py geo-agent/tests/test_site_signals.py && git commit -m "feat(fetch): 快照冻结守卫 —— 干净快照不可重冻结(degraded 例外),原子写"
```

---

### Task 6: 依赖锁 requirements.lock + CI 切换 + 黄金锁路径统一

**Files:**
- Create: `scripts/gen_lockfile.py`、`requirements.lock`（生成产物，提交）
- Modify: `../.github/workflows/ci.yml:20`（仓根相对）
- Modify: `tests/test_v1_semantics.py:21-24`（skipif）
- Test: `tests/test_lockfile.py`（新）

**Interfaces:**
- Produces: `requirements.lock`（全量 `pkg==ver` 含 dev）；CI 安装源。一致性测试锁定「pyproject 直接依赖 ⊆ lock」。

- [ ] **Step 1: 写一致性失败测试**

```python
# tests/test_lockfile.py
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _norm(name: str) -> str:
    return name.lower().replace("_", "-").strip()

def _parse_req(req: str) -> str:
    for sep in (">=", "==", "~=", ">", "<", "!="):
        if sep in req:
            return _norm(req.split(sep)[0])
    return _norm(req)

def test_lockfile_covers_all_pyproject_direct_deps():
    proj = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wanted = [_parse_req(d) for d in proj["project"]["dependencies"]]
    wanted += [_parse_req(d) for d in proj["project"]["optional-dependencies"]["dev"]]
    locked = set()
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"lock 行必须精确锁版本: {line!r}"
        locked.add(_norm(line.split("==")[0]))
    missing = [w for w in wanted if w not in locked]
    assert not missing, f"pyproject 依赖未入 lock —— 重跑 scripts/gen_lockfile.py: {missing}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_lockfile.py -v -p no:cacheprovider`
Expected: FAIL（requirements.lock 不存在 → FileNotFoundError）。

- [ ] **Step 3: 生成脚本 + 冻结 lock**

```python
# scripts/gen_lockfile.py
"""冻结当前环境为 geo-agent/requirements.lock。
用法: python3.12 scripts/gen_lockfile.py --path /tmp/pylibs312
环境须为刚跑过全量套件的绿环境(锁=该环境的确切版本集)。"""
from __future__ import annotations
import argparse
import importlib.metadata
import time
from pathlib import Path

SKIP = {"pip", "setuptools", "wheel", "pkg-resources"}

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="/tmp/pylibs312", help="site-packages 风格的目标目录")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    pins = sorted(
        (f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions(path=[a.path])
         if d.metadata["Name"] and d.metadata["Name"].lower() not in SKIP),
        key=str.lower)
    out = Path(a.out) if a.out else Path(__file__).resolve().parents[1] / "requirements.lock"
    header = (f"# Frozen {time.strftime('%Y-%m-%d')} from {a.path}"
              f" (env that passed the full test suite)\n"
              f"# Regenerate: python3.12 scripts/gen_lockfile.py --path <env-dir>\n")
    out.write_text(header + "\n".join(pins) + "\n", encoding="utf-8")
    print(f"wrote {len(pins)} pins -> {out}")

if __name__ == "__main__":
    main()
```

Run: `cd geo-agent && python3.12 scripts/gen_lockfile.py --path /tmp/pylibs312`
然后 `head -5 requirements.lock` 人工抽查（应含 dashscope/openai/pytest 等，版本为 == 精确）。

- [ ] **Step 4: CI 切换**

`../.github/workflows/ci.yml` 第 20 行：

```yaml
        run: python -m pip install -r ./geo-agent/requirements.lock
```

（原 `python -m pip install -e "./geo-agent[dev]"`。pytest 由 pyproject `pythonpath=["src"]` 找到包，无需 editable。）

- [ ] **Step 5: 黄金锁 skipif 统一**

`tests/test_v1_semantics.py` 的 skipif 块替换为：

```python
_REQUIRED_LOCAL = [
    REPO / "data" / "raw" / "w1",
    REPO / "data" / "analysis" / "w1" / "eval_report.json",   # 与断言实际读取同源(假信心修复)
]

@pytest.mark.skipif(
    not all(p.exists() for p in _REQUIRED_LOCAL),
    reason="需本地真实 w1 数据(gitignored): data/raw/w1 与 data/analysis/w1/eval_report.json",
)
```

- [ ] **Step 6: 跑测试确认通过 + 全量**

Run: `PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_lockfile.py "tests/test_v1_semantics.py" -v -p no:cacheprovider`，再全量。
Expected: lockfile 测试 PASS；黄金锁在本机 PASS（43.4/49.8）。

- [ ] **Step 7: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git add geo-agent/scripts/gen_lockfile.py geo-agent/requirements.lock geo-agent/tests/test_lockfile.py geo-agent/tests/test_v1_semantics.py .github/workflows/ci.yml && git commit -m "build(deps): requirements.lock 冻结 + CI 切锁安装 + 黄金锁 skipif 路径统一"
```

---

### Task 7: cost_budget_yuan 删除 + run.yaml 一致性锁

**Files:**
- Modify: `src/geo/shared/config.py:15`（删字段）
- Modify: `run.yaml`（删行）
- Test: `tests/test_config.py`（追加）

**Interfaces:**
- Produces: `RunSpec` 无 `cost_budget_yuan` 字段；新测试锁定 `run.yaml 键集 == RunSpec.model_fields 键集`（防未来再积死配置）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py 追加
import yaml
from geo.shared.config import RunSpec, REPO

def test_run_yaml_keys_match_run_spec_fields():
    """run.yaml 与 RunSpec 字段集一致——多余键=死配置,缺失键=靠默认值漂移,都该显式。"""
    data = yaml.safe_load((REPO / "run.yaml").read_text(encoding="utf-8"))
    assert set(data.keys()) == set(RunSpec.model_fields.keys()), \
        f"run.yaml keys={sorted(data)} vs RunSpec fields={sorted(RunSpec.model_fields)}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_config.py -v -p no:cacheprovider`
Expected: 新测试 FAIL（run.yaml 仍含 cost_budget_yuan，RunSpec 已删——先删字段则此测试红；或反之，二取一先改均红）。

- [ ] **Step 3: 实现**

- `config.py:15` 删除 `cost_budget_yuan: float = 100.0`。
- `run.yaml` 删除该行及其注释行（`cost_budget_yuan: 100        # 安全阀熔断（记录呈现、不考核）`）。

- [ ] **Step 4: 跑测试确认通过 + 全量 + 黄金锁**

Run: 全量套件。Expected: 全绿；黄金锁 43.4/49.8（run.yaml 变更不影响评分路径）。

- [ ] **Step 5: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git add geo-agent/src/geo/shared/config.py geo-agent/run.yaml geo-agent/tests/test_config.py && git commit -m "chore(config): 删除 cost_budget_yuan 死配置 + run.yaml/RunSpec 键集一致性锁"
```

---

### Task 8: 收尾——全量验证 + 合并 + 推送 + CI

- [ ] **Step 1: 全量 + 黄金锁终验**

Run: `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
Expected: 全绿（基线 376 + 2 skipped + 新增约 17 条），无 skip 异常增长。

- [ ] **Step 2: 工作树卫生**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git status --short
```
Expected: 仅本计划新增/修改文件已提交；`knowledge/` 无意外改动；gsc_probe* / qwen_B02_postfix.json / .claude/worktrees/ 仍为未跟踪（有意不提交）。

- [ ] **Step 3: 合并推送**

```bash
git checkout main && git merge --no-ff p1-eng-debt -m "merge: P1 工程债修复 —— playbook 保旧+草稿/fetcher 失败不缓存/依赖锁/周编号+快照冻结/cost_budget 删除" && git push origin main
```

- [ ] **Step 4: CI 验证**

```bash
gh run list --branch main --limit 3
```
若 push 事件未触发（既有坑）：`gh workflow run CI --ref main`。Expected: test + site 双绿。

- [ ] **Step 5: 删分支**

```bash
git branch -d p1-eng-debt
```

---

## Self-Review 记录

1. **Spec 覆盖**：spec §2①→Task 2；§3②→Task 3；§4③→Task 6；§5④→Task 4（带子/入口/迁移/清理）+ Task 5（冻结守卫）；§6⑤→Task 7；§7 执行策略→Global Constraints + Task 8。原子写 helper（spec §2 要求三处写入原子化）独立成 Task 1 供 2/5 复用——覆盖完整。
2. **占位符扫描**：无 TBD/TODO；所有代码步骤含完整代码；「若…则修实现而非测试」类指令均给了判据。
3. **类型一致性**：`atomic_write_text(path: Path, text: str)`（Task 1 定义，Task 2/3/5 消费）；`validate_production_week(week: int) -> int`（Task 4）；`FetchError`；`TEST_WEEK` 常量（Task 4 定义，Task 5 消费）；`iso_snapshots` fixture（Task 4 定义，Task 5 消费）；run_research 返回键 `degraded`/`drafts`（Task 2 内自洽）。已核对无误。
