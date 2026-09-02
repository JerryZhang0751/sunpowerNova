# Backlog 全量清仓实现计划（19 项，14 任务）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清空 2026-08-24 审计 P2/P3 余项 + 09-01/09-02 新增 backlog 全部 19 项，零污染进入 w4 周迭代。

**Architecture:** 两阶段单分支：阶段一（T1-T8）纯工程卫生（零评分语义影响）；阶段二（T9-T13）数据与评分语义变更（L3 周目录隔离、static 快照 degraded、robots fail-closed、SEO dims 全页均值、research 墙钟预算、静默降级可见化），w1-w3 冻结产物零改动。T14 终局边界验证。

**Tech Stack:** Python 3.11（pydantic v2 / langgraph SqliteSaver / pytest），YAML 配置，Jinja2 报告模板。

**Spec:** `docs/superpowers/specs/2026-09-02-backlog-cleanup-design.md`（§0 决策 D1-D8 已锁定）

## Global Constraints

- **测试环境**（.venv 沙箱封锁既定替代；/tmp 失守先 `cd geo-agent && python3.12 -m pip install --target /tmp/pylibs312 --upgrade -r requirements.lock`）：
  `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
  以 **EXIT=0** 为准（summary 行可能被吞）；目标测试单跑加 `-k`/路径。
- **边界验证协议（用户令：项目已完工、每周固定对照——周可比性是生命线。每任务收尾必跑，顺序执行）**：
  1. `git status --porcelain` → 只出现本任务预期文件（data/state/reports 为 gitignored，不在此列）；
  2. 黄金锁：`PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_v1_semantics.py -p no:cacheprovider -v` → PASS（43.4/49.8）；
  3. 冻结产物零改动：开工先落基线
     `cd geo-agent && shasum data/analysis/w1/eval_report.json data/analysis/w2/eval_report.json data/analysis/w2/eval_report.gap-null-archived.json data/analysis/w3/eval_report.json data/snapshots/w*/*.json data/raw/w*/runs.jsonl > /tmp/frozen_baseline.txt`
     每任务后 `shasum -c /tmp/frozen_baseline.txt`（静默 OK）。**例外（已知且仅此两类）**：T3 可能使 `data/analysis/w1/source_scores.csv` 行序重排（rglob→sorted，行集不变——基线不含此文件）；T9 迁移 `data/sources/`（迁移后重录 sources 基线）。
  4. 全量套件 EXIT=0（基线 458 passed + 2 skipped，只增不减；`-q` 不可信，落盘 `/tmp/pytest.log` 后核对尾部计数）。
- **禁改**：`rules/*.yaml` 评分权重/门槛语义（升版走 w4 正常迭代）、`RunRecord`/runs.jsonl 契约、research 单次超时值（120/180s，codex 明令）、git 历史（不 rewrite）、真实采集/Kimi/发布（一律 mock/tmp）。
- **commit 风格**：沿用仓库惯例（`fix:`/`feat:`/`docs:`/`test:` + 中文主题）；**禁 `git add -A`**，显式路径。
- 生产周号 1-3 已用、测试带 900-999（`geo.shared.weeks.TEST_WEEK=901`）；新测试的 tmp 数据一律 901。

---

## 阶段一：工程卫生（T1-T8）

### Task 1: io_utils fsync + run.yaml 三处原子写

**Files:**
- Modify: `geo-agent/src/geo/shared/io_utils.py`
- Modify: `geo-agent/src/geo/orchestrate/graph.py:145-151`、`geo-agent/src/geo/rules/run.py:63-66`、`geo-agent/src/geo/rules/keeper.py:170-173`
- Test: `geo-agent/tests/test_io_utils.py`（扩展）

**Interfaces:**
- Produces: `atomic_write_text(path: Path, text: str) -> None`（语义不变，新增 fsync 耐久性）；三处 run.yaml 写入改走它（spec §0 裁量：不保注释）。

- [ ] **Step 1: 红测——原子写后文件完整且 tmp 不残留 + run.yaml 写入走 atomic**

```python
# tests/test_io_utils.py 追加
def test_atomic_write_fsync_and_no_tmp_left(tmp_path, monkeypatch):
    import os
    from geo.shared.io_utils import atomic_write_text
    target = tmp_path / "run.yaml"
    seen = {}
    real_fsync = os.fsync
    def spy(fd):
        seen["fsync"] = True
        return real_fsync(fd)
    monkeypatch.setattr(os, "fsync", spy)
    atomic_write_text(target, "week: 3\n")
    assert target.read_text(encoding="utf-8") == "week: 3\n"
    assert not (tmp_path / "run.yaml.tmp").exists()
    assert seen.get("fsync") is True          # fsync 真被调用(耐久性)

def test_graph_next_week_writes_run_yaml_atomically(tmp_path, monkeypatch):
    # graph --next-week 分支的 run.yaml 写入必须走 atomic_write_text
    import geo.orchestrate.graph as G
    from geo.shared import io_utils
    calls = []
    monkeypatch.setattr(io_utils, "atomic_write_text",
                        lambda p, t: calls.append((p, t)))
    monkeypatch.setattr(G, "atomic_write_text", lambda p, t: calls.append((p, t))) \
        if hasattr(G, "atomic_write_text") else None
    # run_pipeline 的 next_week 段不易直调 → 抽函数后直测(见 Step 3)
```

（第二测依赖 Step 3 抽出的 `_bump_run_yaml_week`——先写第一测跑红，第二测在 Step 3 前补。）

- [ ] **Step 2: 跑红**：`python3.12 -m pytest tests/test_io_utils.py -k fsync -p no:cacheprovider` → FAIL（现实现无 fsync）

- [ ] **Step 3: 实现**

```python
# geo-agent/src/geo/shared/io_utils.py 整体替换
# src/geo/shared/io_utils.py
from __future__ import annotations
import os
from pathlib import Path

def atomic_write_text(path: Path, text: str) -> None:
    """tmp + fsync + os.replace 原子写:读方要么看到完整旧文件、要么看到完整新文件。
    2026-09-02:补 fsync(断电场景 replace 后内容已落盘)。"""
    tmp = path.parent / (path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
```

三处 run.yaml 写入统一抽辅助（graph.py 内定义、另两处各自 import 或复制同款三行——三处分属三模块，各自就地替换最小）：

```python
# graph.py:145-151 替换为
    if next_week:
        import yaml as _y
        from geo.shared.io_utils import atomic_write_text
        run_raw = _y.safe_load((REPO / "run.yaml").read_text(encoding="utf-8"))
        run_raw["week"] = week + 1
        atomic_write_text(REPO / "run.yaml",
                          _y.safe_dump(run_raw, allow_unicode=True, sort_keys=False))
        print(f"run.yaml week → {week + 1}")
```

```python
# rules/keeper.py:170-173 中 run.yaml 段替换
        from geo.shared.io_utils import atomic_write_text
        run_raw = yaml.safe_load((repo / "run.yaml").read_text(encoding="utf-8"))
        run_raw["rule_version"] = to_v
        atomic_write_text(repo / "run.yaml",
                          yaml.safe_dump(run_raw, allow_unicode=True, sort_keys=False))
```

```python
# rules/run.py:63-66 中 run.yaml 段替换(do_rollback 内)
    from geo.shared.io_utils import atomic_write_text
    run_raw = yaml.safe_load((repo / "run.yaml").read_text(encoding="utf-8"))
    run_raw["rule_version"] = new_v
    atomic_write_text(repo / "run.yaml",
                      yaml.safe_dump(run_raw, allow_unicode=True, sort_keys=False))
```

补 Step 1 的第二测：graph 抽 `_bump_run_yaml_week(week)`（next_week 段体），直测它调用 atomic_write_text（monkeypatch 后断言 calls 非空且内容 week+1）。

- [ ] **Step 4: 绿**：`pytest tests/test_io_utils.py -p no:cacheprovider -v` → PASS
- [ ] **Step 5: 边界验证协议 1-4**（黄金锁此刻仍会重写 w1 eval_report 为字节相同内容——shasum 不变，预期 OK）
- [ ] **Step 6: Commit** `fix(shared): run.yaml 三处原子写 + atomic_write_text 补 fsync`

### Task 2: MODELS 集中 + settings mtime 缓存

**Files:**
- Modify: `geo-agent/src/geo/shared/config.py`
- Modify: `geo-agent/src/geo/collect/qwen_client.py:67`、`doubao_client.py:74,82`、`zhipu_client.py:46,54`、`geo-agent/src/geo/fetch/meta_llm.py:16`、`geo-agent/src/geo/research/kimi.py:19,80`、`geo-agent/src/geo/research/render.py:89-91`、`geo-agent/src/geo/generate/kimi.py:64`、`geo-agent/src/geo/generate/brand.py:170`
- Test: `geo-agent/tests/test_config_models.py`（新建）

**Interfaces:**
- Produces: `settings.MODELS: dict[str, dict]`，键 `qwen|doubao|zhipu|kimi`，值 `{"api_code": str, "display": str}`；`settings.run`/`settings.targets` 带 mtime 缓存（改写文件后自动失效）。
- Consumes: 后续 T4（kimi_client 用 `MODELS["kimi"]["api_code"]`）。

- [ ] **Step 1: 红测**

```python
# tests/test_config_models.py 新建
import time
def test_models_registry_values():
    from geo.shared.config import settings
    assert settings.MODELS["qwen"]["api_code"] == "qwen3.7-plus"
    assert settings.MODELS["doubao"]["api_code"] == "doubao-seed-2-1-pro-260628"
    assert settings.MODELS["zhipu"]["api_code"] == "glm-5.2"
    assert settings.MODELS["kimi"]["api_code"] == "kimi-k3"
    for v in settings.MODELS.values():
        assert v["display"]

def test_settings_run_cached_until_mtime_changes(tmp_path):
    from geo.shared.config import Settings
    s = Settings(run_path=tmp_path / "run.yaml", targets_path=tmp_path / "t.yaml")
    (tmp_path / "run.yaml").write_text("week: 3\n", encoding="utf-8")
    (tmp_path / "t.yaml").write_text("site: {url: 'https://x.com'}\n", encoding="utf-8")
    a = s.run
    assert s.run is a                       # mtime 未变 → 同一对象(缓存)
    (tmp_path / "run.yaml").write_text("week: 4\n", encoding="utf-8")
    assert s.run.week == 4                  # mtime 变 → 重新读盘
```

注意 mtime 粒度：同秒内两次 write_text mtime 可能不变——测试里若 flaky，第二次写入前 `os.utime` 显式拨后 mtime。

- [ ] **Step 2: 跑红** → FAIL（无 MODELS；run 无缓存）

- [ ] **Step 3: 实现（config.py）**

```python
# config.py:Settings 类体内追加(PrivateAttr)与属性替换
from pydantic import PrivateAttr

MODELS: dict[str, dict] = {   # 2026-09-02 §3:模型名单一事实源(此前 12 处硬编码)
    "qwen":   {"api_code": "qwen3.7-plus",               "display": "Qwen"},
    "doubao": {"api_code": "doubao-seed-2-1-pro-260628", "display": "Doubao"},
    "zhipu":  {"api_code": "glm-5.2",                    "display": "Zhipu"},
    "kimi":   {"api_code": "kimi-k3",                    "display": "Kimi"},
}

class Settings(BaseSettings):
    ...既有字段...
    _run_cache: tuple[float, RunSpec] | None = PrivateAttr(default=None)
    _targets_cache: tuple[float, dict] | None = PrivateAttr(default=None)

    @property
    def run(self) -> RunSpec:
        mtime = self.run_path.stat().st_mtime
        if self._run_cache and self._run_cache[0] == mtime:
            return self._run_cache[1]
        spec = RunSpec(**yaml.safe_load(self.run_path.read_text(encoding="utf-8")))
        self._run_cache = (mtime, spec)
        return spec

    @property
    def targets(self) -> dict:
        mtime = self.targets_path.stat().st_mtime
        if self._targets_cache and self._targets_cache[0] == mtime:
            return self._targets_cache[1]
        t = yaml.safe_load(self.targets_path.read_text(encoding="utf-8"))
        self._targets_cache = (mtime, t)
        return t
```

模块级 `MODELS` 常量 + 各引用点改读：`from geo.shared.config import settings, MODELS`（或 `settings.MODELS` 不存在——直接模块级 `MODELS`，因为静态无需 per-instance）。测试相应用 `from geo.shared.config import MODELS`（Step 1 里两写法取一，实现后统一为 `MODELS`）。

12 处替换（每处把字面量换 `MODELS[...]["api_code"]`；render.py 的展示名映射换 `MODELS[...]["display"]`——先 `grep -rn "qwen3.7-plus\|doubao-seed\|glm-5.2\|kimi-k3" geo-agent/src/` 确认全部命中后逐一替换，替换完同 grep 应零命中（config.py 自身除外））。

- [ ] **Step 4: 绿 + 边界协议 + Commit** `refactor(config): 模型名集中 MODELS + settings.run/targets mtime 缓存`

### Task 3: `_iter_l1` 合一 + 逐条容错

**Files:**
- Create: `geo-agent/src/geo/shared/l1.py`
- Modify: `geo-agent/src/geo/assess/analyst.py:58-62`（删本地 `_iter_l1`）、`geo-agent/src/geo/research/corpus.py:10-16`（同）
- Test: `geo-agent/tests/test_l1_iter.py`（新建）

**Interfaces:**
- Produces: `geo.shared.l1.iter_l1(week: int, repo: Path = REPO) -> Iterator[L1Record]`——目录不存在返回空；坏 JSON/坏 schema 跳过 + `log.warning`（含文件名）；`sorted()` 保证确定性。

- [ ] **Step 1: 红测**

```python
# tests/test_l1_iter.py 新建
import json
def test_iter_l1_skips_corrupt_and_sorted(tmp_path):
    from geo.shared.l1 import iter_l1
    from geo.shared.models import L1Record
    d = tmp_path / "data" / "raw" / "w901" / "qwen" / "C01"; d.mkdir(parents=True)
    good = L1Record(week=901, model="qwen", prompt_id="C01", run=1, answer="a",
                    l2={"cited_sources": [], "mentioned": False}, ts_iso="t",
                    prompt_set_version="v")
    (d / "r2.json").write_text(json.dumps({**good.model_dump(), "run": 2}), encoding="utf-8")
    (d / "r1.json").write_text("{broken", encoding="utf-8")            # 坏 JSON
    (d / "r0.json").write_text(json.dumps({"no": "schema"}), encoding="utf-8")  # 坏 schema
    recs = list(iter_l1(901, repo=tmp_path))
    assert [r.run for r in recs] == [2]      # 坏行跳过、好行保留
def test_iter_l1_missing_dir_empty(tmp_path):
    from geo.shared.l1 import iter_l1
    assert list(iter_l1(999, repo=tmp_path)) == []
```

- [ ] **Step 2: 跑红**（模块不存在）→ FAIL
- [ ] **Step 3: 实现**

```python
# geo-agent/src/geo/shared/l1.py 新建
"""L1 记录迭代(2026-09-02 §4:analyst/corpus 两份实现合一 + 逐条容错)。
单条坏 JSON/坏 schema 跳过并告警,不再炸掉整个 assemble/build_corpus;
sorted 保证跨运行确定性(旧 rglob 顺序依赖文件系统)。"""
from __future__ import annotations
import json, logging
from pathlib import Path
from typing import Iterator
from geo.shared.config import REPO
from geo.shared.models import L1Record

log = logging.getLogger("shared.l1")

def iter_l1(week: int, repo: Path = REPO) -> Iterator[L1Record]:
    root = repo / "data" / "raw" / f"w{week}"
    if not root.exists():
        return
    for jp in sorted(root.rglob("r*.json")):
        try:
            yield L1Record(**json.loads(jp.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            log.warning("w%s L1 残缺跳过 %s: %s", week, jp.name, e)
```

analyst.py：删 `_iter_l1`（:58-62），`from geo.shared.l1 import iter_l1`，全文件 `_iter_l1(` → `iter_l1(`（4 处调用点）。corpus.py 同（先读文件确认其 `_iter_l1`/目录检查逻辑后替换，保留其调用方签名）。
注意：analyst `competitor_domains_by_count` 与 `assemble` 的迭代顺序变 sorted——`source_scores.csv` 行序可能重排（Global Constraints 已声明例外）；`metrics` dict 键序随之，但 eval_report 用 `sort_keys=True` 序列化 → 字节不变。

- [ ] **Step 4: 绿 + 边界协议（黄金锁必须仍 43.4/49.8；`shasum -c` 中 eval_report.json 必 OK）+ Commit** `refactor(shared): _iter_l1 合一至 shared/l1 + 逐条容错 + 确定性排序`

### Task 4: `_kimi_chat` 合一 → shared/kimi_client

**Files:**
- Create: `geo-agent/src/geo/shared/kimi_client.py`
- Modify: `geo-agent/src/geo/research/kimi.py:16-23`、`geo-agent/src/geo/generate/kimi.py`（client 构造行）、`geo-agent/src/geo/generate/brand.py:167-172`、`geo-agent/src/geo/fetch/meta_llm.py:14`
- Test: `geo-agent/tests/test_kimi_client.py`（新建）

**Interfaces:**
- Produces: `make_kimi_client(*, timeout: float, max_retries: int = 2) -> OpenAI`；`kimi_chat(messages, *, timeout=120.0, max_retries=2, tools=None) -> str`（response_format=json_object 在无 tools 时自动带，temperature=1 内建——kimi-k3 强制）。
- 各层**现值保留**：research synthesize 120s（默认 retries）、research web_search 180s（retries=0 由 T12 加，本任务不动）、generate 300s+retries=0（其总预算逻辑不动）、brand 120s、meta_llm 120s。

- [ ] **Step 1: 红测**

```python
# tests/test_kimi_client.py 新建
def test_kimi_chat_no_tools_sets_json_format(monkeypatch):
    import geo.shared.kimi_client as K
    created = {}
    class FakeResp:
        class choices:  # noqa
            class message: content = "{\"ok\":1}"  # noqa
    def fake_create(**kwargs):
        created.update(kwargs)
        return FakeResp
    class FakeCompletions:
        create = staticmethod(fake_create)
    class FakeClient:
        chat = type("C", (), {"completions": FakeCompletions})()
    monkeypatch.setattr(K, "make_kimi_client", lambda **kw: FakeClient())
    assert K.kimi_chat([{"role": "user", "content": "x"}]) == "{\"ok\":1}"
    assert created["response_format"] == {"type": "json_object"}
    assert "tools" not in created and created["temperature"] == 1
def test_kimi_chat_with_tools_no_json_format(monkeypatch):
    ...同上 but tools=[{"type": "builtin_function"}] → "tools" in created and "response_format" not in created
```

- [ ] **Step 2: 跑红** → FAIL
- [ ] **Step 3: 实现**

```python
# geo-agent/src/geo/shared/kimi_client.py 新建
"""Kimi K3 客户端单一实现(2026-09-02 §4:三份 _kimi_chat 合一,超时/重试参数化)。
各层语义保留: research synthesize 120s / web_search 180s(retries 由调用方定) /
generate 300s+max_retries=0 / brand 120s / meta_llm 120s。kimi-k3 强制 temperature=1。"""
from __future__ import annotations
from geo.shared.config import settings, MODELS

def make_kimi_client(*, timeout: float, max_retries: int = 2):
    from openai import OpenAI
    return OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url,
                  timeout=timeout, max_retries=max_retries)

def kimi_chat(messages: list[dict], *, timeout: float = 120.0, max_retries: int = 2,
              tools: list | None = None) -> str:
    c = make_kimi_client(timeout=timeout, max_retries=max_retries)
    kwargs = dict(model=MODELS["kimi"]["api_code"], messages=messages, temperature=1)
    if tools:
        kwargs["tools"] = tools
    else:
        kwargs["response_format"] = {"type": "json_object"}
    r = c.chat.completions.create(**kwargs)
    return r.choices[0].message.content or ""
```

四处替换（只换 client 构造与调用，周围业务逻辑/deadline/预算代码不动）：
- research/kimi.py `_kimi_chat` 函数体 → `from geo.shared.kimi_client import kimi_chat as _shared_chat` + `return _shared_chat(messages, tools=tools, timeout=timeout)`（保留本模块 `_kimi_chat` 名，synthesize 的 `chat_fn=_kimi_chat` 默认参数不受影响）。
- generate/kimi.py：其 `_kimi_chat`/client 构造行改用 `make_kimi_client(timeout=GENERATE_REQUEST_TIMEOUT_S, max_retries=0)`（先读文件，保持函数签名与返回值不变）。
- generate/brand.py:167-172 同（timeout=120 默认 retries）。
- meta_llm.py:14 → `c = make_kimi_client(timeout=120)`，model 参数用 `MODELS["kimi"]["api_code"]`（T2 已改则此处只剩 client 行）。

- [ ] **Step 4: 绿 + 边界协议 + Commit** `refactor(shared): 三份 _kimi_chat 合一至 kimi_client(各层超时值保留)`

### Task 5: 死代码/死分支/恒真测试清理

**Files:**
- Delete: `geo-agent/src/geo/report/schema.py`
- Modify: `geo-agent/src/geo/eval/agent_eval.py:110-117`（删 kimi 分支）
- Modify: `geo-agent/tests/test_prompts.py:10`、`geo-agent/tests/test_fetcher.py:33-35`
- Test: `geo-agent/tests/test_agent_eval.py`（扩展——若无则新建，先 ls tests/ 确认）

**Interfaces:**
- Produces: BFCL provider 覆盖集 = {qwen, doubao, zhipu}（kimi 死分支删除，spec §0 裁量）。

- [ ] **Step 1: 红测**——test_prompts.py:10 改真断言（先跑一次确认现状 PASS=恒真假绿，改后跑应仍 PASS 但有判别力）：

```python
# test_prompts.py:10 替换
def test_prompt_set_version_format():
    import re
    from geo.input.prompts import PROMPT_SET_VERSION   # 按实际 import 路径(读文件头部确认)
    assert re.fullmatch(r"[0-9a-f]{12}", PROMPT_SET_VERSION), \
        "prompt_set_version 应为 prompt blob 的 sha1[:12] 十六进制"
```

```python
# test_fetcher.py:33-35 test_sha1_dedup 替换
def test_sha1_dedup():
    from geo.shared.storage import sha1_url
    u = "https://x.com/a"
    assert sha1_url(u) == sha1_url(u)              # 确定性
    assert sha1_url(u) != sha1_url("https://x.com/b")  # 不同 URL 不同键
```

agent_eval 锁（新测试）：

```python
def test_bfcl_provider_scope_collection_only():
    # 2026-09-02 §4:BFCL(§4-bis)只评采集层三客户端;kimi 分析层不属(死分支已删)
    from geo.eval.agent_eval import evaluate
    rep = evaluate()          # 读 tests/fixtures/bfcl/(离线)
    assert set(rep["by_provider"]) <= {"qwen", "doubao", "zhipu"}
```

（evaluate 返回结构以读文件为准，断言键名相应调整。）

- [ ] **Step 2: 跑**——先全量（现状基线绿），再实施删除：
- `git rm geo-agent/src/geo/report/schema.py`
- agent_eval.py 删 kimi 分支 dict 项（读 :100-125 后删除 kimi entry）
- [ ] **Step 3: 绿**：全量 EXIT=0（新测试 PASS、无 import 报错——grep `from geo.report.schema import\|report.schema` 应零命中）
- [ ] **Step 4: 边界协议 + Commit** `chore: 删 report/schema.py 死代码与 agent_eval kimi 死分支; 恒真测试改真断言`

### Task 6: sqlite WAL/close + test_graph 隔离 + 生产库清洗

**Files:**
- Modify: `geo-agent/src/geo/orchestrate/graph.py:90-111,113-151`、`geo-agent/tests/test_graph.py:24`
- Test: `geo-agent/tests/test_graph.py`（扩展）

**Interfaces:**
- Produces: `build_graph(conn: sqlite3.Connection | None = None)`——None 时自建生产连接（WAL+busy_timeout）；调用方传 conn 则所有权归调用方。`run_pipeline` 自建连接 `finally: conn.close()`。

- [ ] **Step 1: 红测**

```python
# tests/test_graph.py 追加
def test_build_graph_uses_passed_conn_isolated(tmp_path):
    """测试不得触碰生产 state/runs.sqlite(2026-09-02 §2:污染实锤修复)。"""
    import sqlite3
    from geo.orchestrate.graph import build_graph
    conn = sqlite3.connect(tmp_path / "t.sqlite", check_same_thread=False)
    app = build_graph(conn)
    assert app is not None
    conn.close()

def test_run_pipeline_closes_conn(tmp_path, monkeypatch):
    import sqlite3
    import geo.orchestrate.graph as G
    conns = []
    class ConnSpy(sqlite3.Connection): pass
    real_connect = sqlite3.connect
    def spy(*a, **kw):
        c = real_connect(*a, **kw); conns.append(c); return c
    monkeypatch.setattr(sqlite3, "connect", spy)
    monkeypatch.setattr(G, "build_graph", lambda conn=None: _FakeApp())
    ...run_pipeline 走完 finally...
    # 直测更简单:monkeypatch build_graph 返回 fake,断言 conns[0].close 被调
```

（ConnSpy 方案复杂——简化：monkeypatch `sqlite3.connect` 返回包装对象记录 close 调用。实现时以最简可断言方式落地，核心断言 = run_pipeline 返回后连接已 close。）

- [ ] **Step 2: 跑红** → FAIL（build_graph 无 conn 参数）

- [ ] **Step 3: 实现（graph.py）**

```python
def _new_run_conn():
    (REPO / "state").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REPO / "state" / "runs.sqlite", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")        # 崩溃不损 checkpoint(2026-09-02 §2)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def build_graph(conn: sqlite3.Connection | None = None):
    ...nodes/edges 不变...
    conn = conn or _new_run_conn()
    return g.compile(checkpointer=SqliteSaver(conn))
```

`run_pipeline`：`app = build_graph()` 改为：

```python
    conn = _new_run_conn()
    try:
        app = build_graph(conn)
        ...既有 invoke 逻辑...
        ...next_week 段...
    finally:
        conn.close()
```

test_graph.py:24 附近：全部 `build_graph()` 调用改为 tmp conn（`sqlite3.connect(tmp_path/"t.sqlite")` + teardown close）。

- [ ] **Step 4: 生产库清洗（先备份后删除，可回滚）**

```bash
sqlite3 geo-agent/state/runs.sqlite ".tables"                      # 认表名
sqlite3 geo-agent/state/runs.sqlite "SELECT DISTINCT thread_id FROM checkpoints;"
cp geo-agent/state/runs.sqlite geo-agent/state/runs.sqlite.bak-20260902
sqlite3 geo-agent/state/runs.sqlite "DELETE FROM checkpoints WHERE thread_id LIKE 'test%';
 DELETE FROM checkpoint_writes WHERE thread_id LIKE 'test%';
 DELETE FROM checkpoint_blobs WHERE thread_id LIKE 'test%';"
sqlite3 geo-agent/state/runs.sqlite "VACUUM;"
sqlite3 geo-agent/state/runs.sqlite "SELECT DISTINCT thread_id FROM checkpoints;"   # 应只剩 w1/w2/w3(+时间戳线程)
```

（表名以 `.tables` 实测为准逐表清理；runs.sqlite.bak-* 加进 geo-agent/.gitignore 的 `state/` 已覆盖。）

- [ ] **Step 5: 绿 + 边界协议（全量套件跑完后 `shasum geo-agent/state/runs.sqlite` 与跑前一致=测试隔离生效）+ Commit** `fix(orchestrate): sqlite WAL+busy_timeout+run_pipeline 关连接; test_graph 不再写生产库`

### Task 7: 守卫补强（黄金锁只读 / suggest 周校验 / gsc mismatch 测试 / example 锁 / 同 slug 守卫）

**Files:**
- Modify: `geo-agent/src/geo/assess/analyst.py`（assemble 加 `write: bool = True` 与 `seo_dims_aggregation: str = "mean"`——后者本任务只加参数+校验、不接线，T11 接线）
- Modify: `geo-agent/tests/test_v1_semantics.py`（write=False + seo_dims_aggregation="first_page"）
- Modify: `geo-agent/src/geo/generate/run.py`（suggest 周校验 :222-223；run_generate 同 slug 守卫 :109-112；run_mark_published 覆写守卫 :176-178；CLI `--allow-published-overwrite`）
- Test: `geo-agent/tests/test_generate_run.py`（扩展）、`geo-agent/tests/test_gsc.py`（扩展）、`geo-agent/tests/test_run_yaml_example.py`（新建）

**Interfaces:**
- Produces: `assemble(week, *, rules_geo=None, rules_seo=None, out_name="eval_report.json", rule_version=None, write=True, seo_dims_aggregation="mean")`——write=False 时不写 eval_report.json/source_scores.csv（只返回 dict）；seo_dims_aggregation ∈ {"mean","first_page"} 非法值 ValueError（"mean" 分支 T11 才实现，本任务先接受两值并沿用 first_page 逻辑当默认路径未变——**注意**：为保本任务黄金锁绿，本任务把**默认实现仍为 first_page 旧逻辑**，T11 切默认为 mean；参数本任务就位并锁 first_page 路径）。

> 实现注意：为让任务独立可评审，本任务 assemble 的 dims 行为零变化（继续 `seo_scores[0].dims`），只加参数与 write 开关；T11 改默认行为。

- [ ] **Step 1: 红测**

```python
# tests/test_run_yaml_example.py 新建
def test_example_rule_version_matches_current():
    import yaml
    from geo.shared.config import REPO
    ex = yaml.safe_load((REPO / "run.yaml.example").read_text(encoding="utf-8"))
    cur = yaml.safe_load((REPO / "run.yaml").read_text(encoding="utf-8"))
    assert ex["rule_version"] == cur["rule_version"], \
        "run.yaml.example 版本滞后——升版时同步 example(防 v1 滞后复发)"
```

```python
# tests/test_gsc.py 追加
def test_gsc_freeze_warns_on_rule_version_mismatch(tmp_path, monkeypatch, caplog):
    # 2026-08-27 快照冻结守卫的 mismatch 告警分支(此前零覆盖)
    ...(按既有冻结测试的 tmp repo/iso_snapshots fixture 模式)...
    快照写入 rule_version="geo-seo-v2" → 以 "geo-seo-v3" 再调 snapshot_gsc
    → 返回冻结内容(不重取) + caplog 含 warning
```

```python
# tests/test_generate_run.py 追加
def test_generate_refuses_published_slug(tmp_path, monkeypatch):
    # 同 slug 已发布 → 拒写影子草稿;--allow-published-overwrite 才放行
    repo = tmp_path
    (repo/"content"/"published").mkdir(parents=True)
    (repo/"content"/"published"/"my-topic.md").write_text("---\nslug: my-topic\n---\n", encoding="utf-8")
    ...monkeypatch load_brand/playbook_digest/generate_draft 按既有 generate 测试模式...
    with pytest.raises(SystemExit, match="已有发布文"):
        run_generate("my topic", "guide", 901, repo=repo)
    run_generate("my topic", "guide", 901, repo=repo, allow_published_overwrite=True)  # 放行
def test_mark_published_refuses_existing_published(tmp_path):
    ...published/my-topic.md 已存在 + drafts/my-topic.md 存在 + reviews pass
    → SystemExit("已存在") ;override=True 放行...
```

黄金锁（test_v1_semantics.py:49）改：`rep = assemble(1, rules_geo=rg, rules_seo=rs, rule_version="geo-seo-v2", write=False, seo_dims_aggregation="first_page")`；docstring 更新（"不再覆写盘上参照"）。

- [ ] **Step 2: 跑红**（example 滞后 v2≠v4；generate 无守卫；assemble 无 write 参数）
- [ ] **Step 3: 实现**

analyst.py assemble 签名加两参数；文件尾两段写盘包 `if write:`；`if seo_dims_aggregation not in ("mean", "first_page"): raise ValueError(...)`（dims 计算行本任务不动）。

generate/run.py：

```python
def run_generate(topic, page_type="guide", week=1, allow_no_playbook=False, kimi=True,
                 chat_fn=None, repo=REPO, today=None, allow_published_overwrite=False) -> dict:
    ...
    out = out_dir / f"{fm['slug']}.md"
    pub_existing = repo / "content" / "published" / f"{fm['slug']}.md"
    if pub_existing.exists() and not allow_published_overwrite:
        raise SystemExit(f"slug {fm['slug']!r} 已有发布文 {pub_existing}——拒绝生成影子草稿"
                         "(确认换题,或 --allow-published-overwrite 显式放行)")
    out.write_text(...)
```

run_mark_published（draft.unlink() 前归档写入处）：

```python
    pub_file = pub_dir / f"{slug}.md"
    if pub_file.exists() and not override:
        raise SystemExit(f"{pub_file} 已存在——归档将覆写已发布文;确需覆写用 --override --reason")
```

main()：`ap.add_argument("--allow-published-overwrite", action="store_true")` + suggest 分支 `run_suggest(validate_production_week(a.week))` + topic 分支透传新参。

run.yaml.example：rule_version 改 `geo-seo-v4`（与 run.yaml 一致）。

- [ ] **Step 4: 绿 + 边界协议（重点：黄金锁 PASS 且跑完后 `data/analysis/w1/eval_report.json` mtime 不变——只读化生效）+ Commit** `fix(assess,generate): 黄金锁只读化+同slug覆写守卫+suggest周校验+example版本锁+gsc mismatch测试`

### Task 8: P3 文件处置（⚠️ Step 1 前向用户做一次不可逆确认）

**Files:**
- Delete: `geo-agent/scripts/m0_report.json`、`geo-agent/tests/fixtures/raw/qwen_B02_postfix.json`（均未跟踪/已跟踪确认后执行——m0_report.json 是 tracked 用 git rm；postfix 未跟踪直接 rm）
- Modify: `geo-agent/scripts/verify_gemini36.py:25,36`（URL 泛化）、根 `.gitignore`、`site/DEPLOY.md:28` 附近
- Create: `README.md`（仓库根）

- [ ] **Step 1: 向用户确认**：删除 `m0_report.json`（git 历史可寻）与 `qwen_B02_postfix.json`（未跟踪，删即消失）——等用户明示"确认删除"再动（spec §13 承诺）。
- [ ] **Step 2: 执行删除**：`git rm geo-agent/scripts/m0_report.json`；`rm geo-agent/tests/fixtures/raw/qwen_B02_postfix.json`
- [ ] **Step 3: verify_gemini36.py 泛化**：`https://live-turing.cn.llm.tcljd.com/api/v1` → `os.environ.get("RELAY_BASE_URL", "<RELAY_BASE_URL>")` + docstring 注明"relay 已退役；URL 走环境变量，key 不入文件"。
- [ ] **Step 4: 根 .gitignore 追加**：

```
# 残留 worktree(已合并)与含私钥路径的本地探针——有意不入库
.claude/worktrees/
geo-agent/scripts/gsc_probe*.py
```

- [ ] **Step 5: DEPLOY.md 部署节重写**（wrangler login → token 流程）：

```markdown
### 部署(无需 wrangler login——代理后 OAuth CSRF 已知不可用)

```bash
cd site && npm run check && npm run build     # check 必须 0 errors/0 warnings/0 hints
CLOUDFLARE_API_TOKEN=$(cat .cf_token) \
CLOUDFLARE_ACCOUNT_ID=<CLOUDFLARE_ACCOUNT_ID> \
npx wrangler pages deploy dist --project-name sunhestia --branch main
```

- `.cf_token`(本地文件,gitignored)与 ACCOUNT_ID 不入仓库;npx 首跑现场下载 wrangler >300s,后台跑、勿接 tail 管道;direct-upload 原子,杀掉重跑无损。
- 验证:apex 与 pages.dev 双 200 + sitemap-0.xml 含新页 + schema/canonical。
```

- [ ] **Step 6: README.md（根）**——骨架（正文按此扩写，无密钥/项目号）：

```markdown
# SunPower Nova

SunHestia GEO 实验 + 多 Agent GEO/SEO 平台(双线一体)。

## 这是什么
- **实验**:GEO 方法能否可复现地提升光储站点 sunhestia.com 在 LLM 答案中的被引率(周迭代 w1..wN,固定 15 核心 prompt × 3 模型)
- **平台**:6 环节闭环 采集(3 家官方 API 原生联网)→研究(Kimi)→生成(Kimi+人审)→评估(GEO/SEO 双确定性评分)→规则迭代(RulesKeeper)→HTML 报告;LangGraph 静态 DAG
- 权威 spec:`docs/superpowers/specs/`(当前=2026-07-29 整合设计 v1.1);周迭代操作知识见项目记忆 runbook

## 快速上手
...(python3.11 -m pip install -r geo-agent/requirements.lock / 测试命令 / 跑周迭代 python3.11 -m geo.orchestrate graph 入口 / site 构建)...

## 新机器迁移清单(仓库不含的部分)
1. `geo-agent/.env`(4 个 API key) + GSC 服务账号私钥 JSON
2. `geo-agent/data/`(实验数据) + `geo-agent/state/runs.sqlite`(DAG checkpoint) + `geo-agent/reports/`
3. `site/.cf_token`(部署)
4. 代理 `127.0.0.1:10808`(GSC/外站抓取硬依赖) + Python 3.11 + Node
5. git 推送凭据(HTTPS + gh)

## 目录
geo-agent/(平台) · site/(Astro 站点) · docs/(spec/plan/归档) · docs/superpowers/specs/(权威)
```

- [ ] **Step 7: 验证**：`git status --porcelain` 未跟踪项清零（worktrees/gsc_probe 被 ignore）；`grep -rn "296415631960\|sk-\|live-turing" README.md site/DEPLOY.md` 零命中；全量套件 EXIT=0。
- [ ] **Step 8: Commit** `docs: README+DEPLOY 真实流程; 清理 m0_report/orphan fixture; gitignore worktrees+gsc_probe`

---

**Gate A（阶段一收口）**：全量绿 + 黄金锁 43.4/49.8 + `shasum -c /tmp/frozen_baseline.txt` 全 OK + `git status` 干净。任何一项不过→修复后重跑。

---

## 阶段二：数据与评分语义（T9-T13，w4 起生效）

### Task 9: L3 缓存周目录隔离 + 存量迁移

**Files:**
- Modify: `geo-agent/src/geo/shared/storage.py:15-16`、`geo-agent/src/geo/fetch/fetcher.py:87-117`、`geo-agent/src/geo/assess/analyst.py:65-81`、`geo-agent/src/geo/research/sample.py:10-34`、`geo-agent/src/geo/orchestrate/graph.py:38-41`（fetch_node 传 week）、`geo-agent/src/geo/research/run.py:49`（fetch_topn 传 week）
- Test: `geo-agent/tests/test_fetcher.py`（扩展+既有用例更新）、`geo-agent/tests/test_l3_weekly.py`（新建）

**Interfaces:**
- Produces:
  - `storage.source_dir(week: int, sha1: str) -> Path` → `data/sources/w{week}/{sha1[:12]}`（mkdir 保留）
  - `storage.legacy_source_dirs(week: int, repo) -> list[Path]`——周 L3 查找回退链：`[w{week}] + ([w3] if week <= 3 else [])`（w1-w3 的历史评估消费的是迁移前共享缓存=迁移后 w3/ 态；w4+ 只读本周，miss=诚实缺失）
  - `fetch_source(url: str, week: int, fetcher_kimi=True, transport=None) -> L3Source`（week 必填，位置参数后移）；读命中=text.md **与** meta.json 齐备且非毒化；写序 meta→text（text=完整对标志）
  - `analyst._load_l3_source(week: int, url: str) -> L3Source | None`（回退链查找，meta+text 齐才算）
  - `sample._already_fetched(week, url, repo)`、`sample.select_topn(..., week)`、`sample.fetch_topn(urls, week)`

- [ ] **Step 1: 红测（新语义）**

```python
# tests/test_l3_weekly.py 新建
def test_source_dir_is_week_scoped(tmp_path, monkeypatch):
    from geo.shared import storage
    monkeypatch.setattr(storage, "REPO", tmp_path)
    d = storage.source_dir(4, "a" * 40)
    assert d == tmp_path / "data" / "sources" / "w4" / "a" * 12 and d.exists()

def test_fetch_source_meta_only_orphan_is_miss(tmp_path, monkeypatch):
    # 孤儿 meta(写序先 text 后 meta 的反例)→ miss → 重抓(TDD: 崩溃残留可自愈)
    ...patch REPO/transport 按 tests/test_fetcher.py 既有模式;预置 meta.json 无 text.md
    → fetch_source(u, week=901) 走网络 mock 成功 → 两文件齐备...

def test_fetch_source_w4_does_not_read_w3(tmp_path, monkeypatch):
    # w4 只读本周目录:上周缓存不算命中(D1 跨周真重抓)
    ...w3 目录预置完整对;fetch_source(u, week=4) 应发起抓取(mock 计数=1)并写 w4/...

def test_load_l3_source_legacy_fallback_w3(tmp_path):
    from geo.assess.analyst import _load_l3_source
    # w1 重算回退链: w1/ 缺 → w3/ 命中(黄金锁 43.4 的数据通路)
    ...tmp repo 布置 data/sources/w3/<sha1[:12]>/{meta.json,text.md}
    assert _load_l3_source(1, url, repo=tmp_path) is not None
    # w4 无回退: data/sources/w4/ 缺 → None
    assert _load_l3_source(4, url, repo=tmp_path) is None
```

（`_load_l3_source` 需加 `repo` 参数或在测试 monkeypatch REPO——取后者，函数签名 `(week, url)`；红测相应 monkeypatch `geo.assess.analyst.REPO`。既有 test_fetcher 全部用例补 `week=901` 参数。）

- [ ] **Step 2: 跑红** → FAIL
- [ ] **Step 3: 实现**

storage.py：

```python
def source_dir(week: int, sha1: str) -> Path:
    """2026-09-02 D1:周目录隔离——每周独立快照自洽,历史 SEO 重算可复现(w3 起)。"""
    p = REPO / "data" / "sources" / f"w{week}" / sha1[:12]
    p.mkdir(parents=True, exist_ok=True); return p

def legacy_source_dirs(week: int, repo: Path = REPO) -> list[Path]:
    """周 L3 查找链:w{week} + (week<=3 时回退 w3=迁移前共享缓存的终态)。
    w1/w2/w3 的历史评估消费的就是这份态(黄金锁通路);w4+ 不回退——miss=诚实缺失。"""
    dirs = [repo / "data" / "sources" / f"w{week}"]
    if week <= 3:
        dirs.append(repo / "data" / "sources" / "w3")
    return dirs
```

fetcher.py fetch_source 改造（签名+读写序）：

```python
def fetch_source(url: str, week: int, fetcher_kimi=True, transport=None) -> L3Source:
    sha = sha1_url(url); sd = source_dir(week, sha)
    text_path = sd / "text.md"; meta_path = sd / "meta.json"
    if text_path.exists() and meta_path.exists():          # 完整对才算命中(text=标志)
        import json
        cached = L3Source(**json.loads(meta_path.read_text(encoding="utf-8")))
        if not (cached.js_only and cached.http_status is None):   # 存量毒化→miss 重抓
            return cached
    ...抓取段不变...
    # 写序反转: meta 先、text 后——崩溃残留只可能是"孤儿 meta"(判 miss 重抓),
    # 不再产生旧序的孤儿 text.md(旧读路径见到 text 就读 meta → FileNotFoundError
    # 被 research 吞成永久 failed 的路径由此消灭)
    import json; atomic_write_text(meta_path, rec.model_dump_json())
    atomic_write_text(sd / "text.md", text)
    return rec
```

analyst `_load_l3_source`：

```python
def _load_l3_source(week: int, url: str) -> L3Source | None:
    """2026-09-02 D1:周目录+legacy 回退链;meta+text 齐备才算完整。"""
    from geo.shared.storage import legacy_source_dirs
    url_hash = sha1_url(url)[:12]
    for base in legacy_source_dirs(week):
        meta_path = base / url_hash / "meta.json"
        if not (meta_path.exists() and (base / url_hash / "text.md").exists()):
            continue
        try:
            return L3Source(**json.loads(meta_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None
```

调用点：assemble 内 `_load_l3_source(static_signals.get("site",...))` → `(week, ...)`；page 循环同；`_score_competitors` 内 → `(week, comp_url)`。sample.py：`_already_fetched(week, url, repo)` 查 `data/sources/w{week}/{sha1}/meta.json`（**无** legacy 回退——research top-N 每周重选重抓）；`select_topn(corpus, n=40, brand_host=..., repo=..., week=...)`；`fetch_topn(urls, week)`。graph.py fetch_node：`fetch_source(u, week=w)`。research/run.py:47-49：`select_topn(corpus, n=fetch_n, repo=repo, week=week)` + `fetch_topn(urls, week=week)`。

- [ ] **Step 4: 存量迁移（先改码后迁移——回退链保证过渡期读路径不断）**

```bash
cd "geo-agent/data/sources"
mkdir -p w3
for d in */; do [ "$d" = "w3/" ] && continue; mv "$d" w3/; done
ls -d */                      # 只剩 w3/
find . -type f | wc -l        # 文件总数不变(text.md+meta.json 对)
```

幂等（重跑跳过 w3）。迁移后重录 sources 基线：`find . -type f -exec shasum {} \; | sort -k2 > /tmp/sources_baseline.txt`。

- [ ] **Step 5: 绿 + 边界协议**（黄金锁 43.4/49.8 必须仍 PASS——w1 回退链通路；frozen_baseline 全 OK）
- [ ] **Step 6: Commit** `feat(storage): L3 缓存周目录隔离(D1)——历史重算可复现+成对原子+毒化/孤儿自愈; 存量迁移 w3`

### Task 10: static 快照 degraded + robots 解析修正 + fail-closed

**Files:**
- Modify: `geo-agent/src/geo/fetch/site_signals.py:11-17,62-96`
- Modify: `geo-agent/src/geo/assess/registry.py:43-44`（robots None→False 由 `_pct` 自然处理——`(None)` → falsy → 0.0，确认无需改；若 `robots_ai` 整体 None 则 `(st.get("robots_ai") or {})` 已兜——核对后大概率 registry 零改动，仅 site_signals+analyst 侧）
- Test: `geo-agent/tests/test_site_signals.py`（重写 fail-open 用例 + 新增 degraded 用例）

**Interfaces:**
- Produces: 快照 dict 增 `degraded: bool`（robots 拉取失败 或 任一页 error/http_status≠200 → true）；`_robots_allows_ai(robots_txt) -> dict`（支持 `User-agent: *` 组、精确路径规则匹配；空/无组 → True）；守卫"存在且非 degraded → 冻结，degraded → 重取"。

- [ ] **Step 1: 红测（重写旧断言=bug 固化 + 新增）**

```python
# tests/test_site_signals.py 新增/重写
def test_robots_wildcard_group_respected():
    from geo.fetch.site_signals import _robots_allows_ai
    txt = "User-agent: *\nDisallow: /\n"
    assert _robots_allows_ai(txt) == {"GPTBot": False, "ClaudeBot": False,
                                      "PerplexityBot": False, "Googlebot": False}

def test_robots_specific_group_overrides_wildcard():
    txt = "User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nAllow: /\n"
    r = _robots_allows_ai(txt)
    assert r["GPTBot"] is True and r["ClaudeBot"] is False

def test_robots_substring_not_overreach():
    # Disallow: /private 不等于全站封禁(旧子串匹配误伤)
    txt = "User-agent: GPTBot\nDisallow: /private\n"
    assert _robots_allows_ai(txt)["GPTBot"] is True

def test_robots_empty_txt_allows():
    assert all(_robots_allows_ai("").values()) is True

def test_snapshot_error_page_marks_degraded_and_refetchable(...):
    # error 页(http_status=None)落快照 → degraded=true → 二次调用重取(mock 第二次成功) → degraded=false 冻结
def test_snapshot_robots_fetch_fail_marks_degraded(...):
    # robots 请求异常(mock) → robots_ai=None + degraded=true;修复后重取 robots_ai 恢复 dict
def test_snapshot_clean_still_frozen(...):
    # 干净快照二次调用返回原内容零网络(既有语义保留,断言 mock 零调用)
```

（既有 `:42-91` fail-open 断言、`:302-313` 任意内容冻结断言按新语义重写——旧断言即 bug 固化。）

- [ ] **Step 2: 跑红** → FAIL
- [ ] **Step 3: 实现（site_signals.py）**

```python
def _parse_robots_groups(robots_txt: str) -> dict[str, list[tuple[str, str]]]:
    """按 User-agent 分组收集 (kind, path) 规则;组边界=下一个 User-agent 行(REP 惯例)。"""
    groups: dict[str, list[tuple[str, str]]] = {}
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    def flush():
        for a in agents:
            groups.setdefault(a, []).extend(rules)
    for line in robots_txt.splitlines():
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        key, _, val = s.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent" and val:
            if rules:
                flush(); agents, rules = [val], []
            else:
                agents.append(val)          # 连续多 UA 行=同组
        elif key in ("disallow", "allow") and agents:
            rules.append((key, val))
    flush()
    return groups

def _group_allows(rules: list[tuple[str, str]]) -> bool:
    """站点根路径 "/" 的允许判定:最长路径规则优先,等长时 Disallow 胜;
    无任何以 / 开头的规则 → True(该组未封禁)。"""
    best_path, best_allow = "", None
    for kind, p in rules:
        if not p or not p.startswith("/"):
            continue
        if len(p) > len(best_path):
            best_path, best_allow = p, (kind == "allow")
        elif len(p) == len(best_path) and kind == "disallow":
            best_allow = False
    return True if best_allow is None else best_allow

def _robots_allows_ai(robots_txt: str) -> dict:
    groups = _parse_robots_groups(robots_txt)
    out = {}
    for b in ("GPTBot", "ClaudeBot", "PerplexityBot", "Googlebot"):
        rules = next((groups[k] for k in (b, "*") if k in groups), None)
        out[b] = True if rules is None else _group_allows(rules)
    return out
```

（bot 专属组优先于 `*` 组；`import re` 若不再被用则移除原正则块。）

snapshot 主体：

```python
    robots_failed = False
    with httpx.Client(...) as c:
        try:
            robots = c.get(f"{site}/robots.txt").text
        except Exception:
            robots = None; robots_failed = True          # D3:未知≠允许
        out["robots_ai"] = None if robots_failed else _robots_allows_ai(robots)
        ...pages 循环不变...
    degraded = robots_failed or any(
        p.get("error") or p.get("http_status") != 200 for p in out["pages"])
    out["degraded"] = degraded                           # D2:degraded 快照可重取
    atomic_write_text(out_path, json.dumps(out, ensure_ascii=False, indent=2))
```

守卫段（:64-71）替换：

```python
    if out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("w%s static_signals 快照损坏,视为缺失重取", week); prev = None
        if prev is not None and not prev.get("degraded"):   # 干净才冻结(D2)
            log.info("w%s static_signals 快照已存在,跳过重取(冻结)", week)
            return prev
        if prev is not None:
            log.warning("w%s static_signals 快照 degraded,重取(robots 失败或 error 页)", week)
```

analyst 侧：`_load_static_signals` 不变（degraded 快照照读——评估照跑，robots None→0 分 fail-closed）；如模板有 robots 呈现位，加"未知(degraded)"显示（`grep -n robots report/templates/report.html.j2` 定位，若有则最小改动 + 更新 reporter golden fixture；若无呈现位则零模板改动）。

- [ ] **Step 4: 绿 + 边界协议（⚠️ 黄金锁:w1 快照是旧格式无 degraded 键——`prev.get("degraded")`=None=falsy → 冻结语义不变,锁必须仍绿;frozen_baseline 里 snapshots 不变=测试未重写盘上快照）+ Commit** `fix(fetch): static 快照 degraded 可重取(D2)+robots 通配组/精确路径/fail-closed(D3)`

### Task 11: SEO dims 全页平均(D4) + avg_position 接入 + 成本呈现

**Files:**
- Modify: `geo-agent/src/geo/assess/analyst.py`（dims 聚合接 `seo_dims_aggregation` 参数、gap avg_position、cost 节）
- Modify: `geo-agent/src/geo/report/templates/report.html.j2`（SEO 区口径注记 + 成本小节）
- Test: `geo-agent/tests/test_analyst_aggregation.py`（新建或并入既有 analyst 测试）、`geo-agent/tests/test_v1_semantics.py`（新增 mean 口径测试）、reporter golden fixture 更新

**Interfaces:**
- Consumes: T7 的 `seo_dims_aggregation` 参数（"mean" 本任务成为默认行为）。
- Produces: eval_report 增 `cost: {note, by_model: {model: {records_with_usage, input_tokens, output_tokens, total_tokens}}}`；`gap.metrics.avg_position` = 各模型 avg_position 的均值（None 当缺失跳过，全缺=None）。

- [ ] **Step 1: 红测**

```python
# 新测试(并入合适文件)
def test_seo_dims_mean_aggregation(tmp_path, monkeypatch):
    # 两页 fixture:dim A 页1=40 页2=60 → mean=50;total=两页 total 均值
    ...(按既有 assemble 测试的 tmp repo 布局:snapshots/static 2 页+gsc+raw L1)...
    rep = assemble(901, repo=..., seo_dims_aggregation="mean")
    dim = next(d for d in rep["self_seo"]["dims"] if d["name"] == "<目标维>")
    assert dim["score"] == 50.0

def test_seo_dims_first_page_legacy(tmp_path, ...):
    rep = assemble(901, ..., seo_dims_aggregation="first_page")
    assert dim["score"] == 40.0                       # 旧口径=第 1 页

def test_gap_avg_position_real_value(...):
    # metrics 某模型 avg_position=5.5 → gap.metrics.avg_position == 5.5(不再恒 None)
def test_cost_section_from_l1_usage(...):
    # L1 usage={"input_tokens":100,"output_tokens":50,"total_tokens":150} ×2 条同模型
    assert rep["cost"]["by_model"]["qwen"]["total_tokens"] == 300
```

test_v1_semantics.py 追加（真实 w1 上锁新口径总量不变）：

```python
def test_v1_semantics_mean_dims_total_unchanged():
    ...skipif 同主测...
    rg, rs = ...(v2 fixture)...
    rep = assemble(1, rules_geo=rg, rules_seo=rs, rule_version="geo-seo-v2",
                   write=False, seo_dims_aggregation="mean")
    assert rep["self_seo"]["total"] == 49.8           # total 本就是页均值,口径切换不动 total
    assert rep["self_geo"]["total"] == 43.4
```

- [ ] **Step 2: 跑红** → FAIL（mean 未实现/avg_position None/cost 无）
- [ ] **Step 3: 实现（analyst.py）**

dims 聚合（:321-330 替换）：

```python
    self_seo_score = None
    if seo_scores:
        avg_total = round(sum(s.total for s in seo_scores) / len(seo_scores), 1)
        from geo.shared.models import DimScore
        if seo_dims_aggregation == "mean":
            # 2026-09-02 D4:维度=全页均值,与 total 同源(w4 起口径;w1-w3 归档=代表页)
            template = seo_scores[0].dims
            dims = []
            for td in template:
                vals = [d.score for s in seo_scores for d in s.dims if d.name == td.name]
                dims.append(DimScore(name=td.name, weight=td.weight,
                                     score=round(sum(vals) / len(vals), 1) if vals else 0.0,
                                     signals={"aggregation": "mean_across_pages",
                                              "n_pages": len(seo_scores)}))
        else:                                            # first_page = w1-w3 旧口径(黄金锁通路)
            dims = seo_scores[0].dims
        self_seo_score = CompositeScore(total=avg_total, dims=dims)
```

gap avg_position（:342 替换）：

```python
        pos = [m.avg_position for m in metrics.values() if m.avg_position is not None]
        gap_metrics = {
            "mention_rate": ...,
            "citation_rate": ...,
            # 2026-09-02 §10:接入 per-model 已算值(旧恒 None 占位消灭;记忆"勿消费"注记作废)
            "avg_position": round(sum(pos) / len(pos), 1) if pos else None,
            "sov": ...
        }
```

cost 节（report dict 组装处追加）：

```python
    usage_by_model: dict[str, dict] = {}
    for l in l1s:
        u = l.usage or {}
        if not u:
            continue
        agg = usage_by_model.setdefault(
            l.model, {"records_with_usage": 0, "input_tokens": 0, "output_tokens": 0,
                      "total_tokens": 0})
        agg["records_with_usage"] += 1
        it = u.get("input_tokens", u.get("prompt_tokens", 0)) or 0
        ot = u.get("output_tokens", u.get("completion_tokens", 0)) or 0
        agg["input_tokens"] += it; agg["output_tokens"] += ot
        agg["total_tokens"] += u.get("total_tokens") or (it + ot)
    report["cost"] = {"note": "token 用量(L1 usage 汇总;记录呈现、不折价不考核——spec v1.1)",
                      "by_model": usage_by_model}
```

模板（report.html.j2）：SEO 区标题旁加注 `<span class="note">w4+ 维度=全页平均(w1–w3 为代表页口径,跨周维度对比有断点)</span>`；质量/采集门附近加：

```jinja
{% if rep.cost and rep.cost.by_model %}
<div class="cost-row">成本(token,不折价):{% for m, c in rep.cost.by_model.items() %}{{ m }} {{ c.total_tokens }}{% if not loop.last %} · {% endif %}{% endfor %}</div>
{% endif %}
```

（样式贴合现有 dashboard 类名;reporter golden fixture 相应更新——`grep -rn "expected" geo-agent/tests/test_reporter*.py` 找到字节级参照后重生成。）

- [ ] **Step 4: 绿 + 边界协议**（黄金锁 first_page 注入路径 43.4/49.8 + dims==archived 逐维 PASS；新 mean 测试 PASS；frozen 全 OK——write=False 不落盘）
- [ ] **Step 5: Commit** `feat(assess,report): SEO dims 全页平均(D4)+gap avg_position 真值+成本 token 呈现`

### Task 12: research 墙钟预算（D5）

**Files:**
- Modify: `geo-agent/src/geo/research/kimi.py:73-121`、`geo-agent/src/geo/research/run.py:59-62,83-85`
- Test: `geo-agent/tests/test_research_kimi.py`（扩展或新建）

**Interfaces:**
- Consumes: T4 `make_kimi_client`。
- Produces: `web_search_verify(items, *, chat_fn=None, platform_budget_s=600, global_budget_s=3600) -> dict`——耗尽平台 `{"answer":"", "sources":[], "confidence":"外部未验证", "budget_exhausted":"platform"|"global"}`；`run_research` 返回增 `budget_exhausted: list[str]`。

- [ ] **Step 1: 红测**

```python
def test_web_search_verify_global_budget_exhaustion(monkeypatch):
    from geo.research import kimi as K
    calls = []
    def slow_chat(messages, tools=None, timeout=180, **kw):
        calls.append(messages[1]["content"])           # 记录查证的平台
        return "结论 来源:https://x.com/a 置信度:high"
    items = [{"platform": p} for p in ["A", "B", "C"]]
    out = K.web_search_verify(items, chat_fn=slow_chat, platform_budget_s=600,
                              global_budget_s=0)        # 全局预算=0 → 全部跳过
    assert all(v["confidence"] == "外部未验证" and v["budget_exhausted"] == "global"
               for v in out.values()) and calls == []

def test_web_search_verify_platform_deadline_stops_loop(monkeypatch):
    # 默认路径:deadline 到点后 _drive_web_search 不再发起下一轮 create
    ...monkeypatch time.monotonic 序列(第一次=0,之后>deadline)+fake create 计数
    → _drive_web_search(create, msgs, deadline=已过期) 返回 "" 且 create 未被调...

def test_web_search_chat_no_sdk_retries():
    # max_retries=0(SDK 层重试关闭,单轮 ≤timeout)
    import inspect
    src = inspect.getsource(__import__("geo.research.kimi", fromlist=["_web_search_chat"]))
    assert "max_retries=0" in src
```

- [ ] **Step 2: 跑红** → FAIL
- [ ] **Step 3: 实现（kimi.py）**

```python
import time
PLATFORM_BUDGET_S = 600      # D5:每平台墙钟预算(2026-09-02)
GLOBAL_BUDGET_S = 3600       # D5:全局墙钟预算(7 平台查证总量上限)

def _drive_web_search(create, messages, *, max_rounds=10, deadline: float | None = None) -> str:
    msgs = list(messages)
    for _ in range(max_rounds):
        if deadline is not None and time.monotonic() > deadline:
            log.warning("web_search 平台预算耗尽,提前放弃(余轮 %d)", max_rounds - _)
            return ""
        ...既有循环体不变...

def _web_search_chat(messages, tools=None, timeout: int = 180,
                     deadline: float | None = None) -> str:
    from geo.shared.kimi_client import make_kimi_client
    c = make_kimi_client(timeout=timeout, max_retries=0)   # SDK 重试关(单轮≤180s)
    return _drive_web_search(c.chat.completions.create, messages, deadline=deadline)

def web_search_verify(items, *, chat_fn=None,
                      platform_budget_s: int = PLATFORM_BUDGET_S,
                      global_budget_s: int = GLOBAL_BUDGET_S) -> dict:
    tools = _WEB_TOOLS
    out = {}
    t0 = time.monotonic()
    for it in items:
        plat, fact = it["platform"], it.get("fact", "crawler_and_inclusion")
        user = f"平台:{plat}\n查证:{fact}(爬虫 User-agent / 收录机制)"
        if time.monotonic() - t0 >= global_budget_s:
            out[plat] = {"answer": "", "sources": [], "confidence": "外部未验证",
                         "budget_exhausted": "global"}
            continue
        deadline = min(t0 + global_budget_s, time.monotonic() + platform_budget_s)
        try:
            if chat_fn is None:
                raw = _web_search_chat([{"role": "system", "content": _SYS_WEB},
                                        {"role": "user", "content": user}],
                                       tools=tools, timeout=180, deadline=deadline)
            else:
                raw = chat_fn([{"role": "system", "content": _SYS_WEB},
                               {"role": "user", "content": user}], tools=tools, timeout=180)
            parsed = _parse_web_answer(raw)
            if time.monotonic() > deadline:
                parsed["budget_exhausted"] = "platform"   # 单轮超预算(后验标记)
            out[plat] = parsed
        except Exception as e:
            log.warning("web_search_verify %s failed: %s", plat, e)
            out[plat] = {"answer": "", "sources": [], "confidence": "外部未验证"}
    exhausted = sorted(p for p, v in out.items() if v.get("budget_exhausted"))
    if exhausted:
        log.warning("平台查证预算耗尽(降级'外部未验证'):%s", exhausted)
    return out
```

run.py（:59-62 后追加 + 返回 dict 增键）：

```python
        exhausted = sorted(p for p, v in (verified or {}).items() if v.get("budget_exhausted"))
    ...(exhausted 提到 verified 赋值后统一算,含 kimi_enabled=False 的空态)...
    return {..., "budget_exhausted": exhausted}
```

（注意 `_web_search_chat` 的 user prompt 文案保持原样（原文含全角标点）——上面示意以文件现状为准逐字保留。）

- [ ] **Step 4: 绿 + 边界协议 + Commit** `feat(research): 平台查证墙钟预算 600s/平台+3600s 全局(D5),耗尽诚实降级不崩`

### Task 13: 静默降级可见化（评分数值零变化）

**Files:**
- Modify: `geo-agent/src/geo/shared/models.py:36-42`（L3Source 加 `semantic_degraded: bool = False`）
- Modify: `geo-agent/src/geo/fetch/meta_llm.py`（返回 `tuple[dict, bool]` + warning）
- Modify: `geo-agent/src/geo/fetch/fetcher.py:111`（解包 + 传 rec）
- Modify: `geo-agent/src/geo/assess/analyst.py`（logging + 4 处 warning + degraded_events 节 + p0_content_degraded 纳入语义降级）
- Modify: `geo-agent/src/geo/report/templates/report.html.j2`（degraded_events 非零提示行 + fixture 更新）
- Test: `geo-agent/tests/test_meta_llm_degraded.py`（新建）、analyst 测试扩展

**Interfaces:**
- Produces: `extract_semantic(text) -> tuple[dict, bool]`（语义 dict + degraded 标志）；eval_report 增 `degraded_events: {self_geo_score_skipped, page_seo_skipped, gap_skipped, competitor_skipped, l3_semantic_degraded}`（全零=健康）。
- **不变**：所有评分数值路径（黄金锁证明）。

- [ ] **Step 1: 红测**

```python
def test_extract_semantic_failure_returns_degraded_flag(monkeypatch, caplog):
    from geo.fetch import meta_llm
    def boom(*a, **kw): raise RuntimeError("kimi down")
    monkeypatch.setattr(meta_llm, "make_kimi_client", boom)   # T4 后的注入点
    sem, degraded = meta_llm.extract_semantic("some page text")
    assert sem == {} and degraded is True
    sem2, degraded2 = meta_llm.extract_semantic("")           # 空文本=未降级(无从提取)
    assert sem2 == {} and degraded2 is False

def test_analyst_degraded_events_counted(...):
    # 坏 page 输入触发 page_seo_skipped 计数 + warning;报告含 degraded_events 键
def test_analyst_semantic_degraded_feeds_p0_flag(...):
    # page_l3.semantic_degraded=True → content_signals["p0_content_degraded"] True
```

- [ ] **Step 2: 跑红** → FAIL
- [ ] **Step 3: 实现**

meta_llm.py：

```python
import logging
log = logging.getLogger("fetch.meta_llm")

def extract_semantic(text: str) -> tuple[dict, bool]:
    """返回 (semantic, degraded)。degraded=True = Kimi 失败/解析失败——
    semantic 为空但非静默:落 L3Source.semantic_degraded,评估与报告可见(§12)。"""
    if not text.strip():
        return {}, False
    try:
        ...
        parsed = json.loads(r.choices[0].message.content or "{}")
        return (parsed if isinstance(parsed, dict) else {}), False
    except Exception as e:
        log.warning("meta_llm Kimi 失败,semantic 降级(structural 兜底): %s: %s",
                    type(e).__name__, e)
        return {}, True
```

fetcher.py:111：

```python
    if fetcher_kimi and text.strip():
        semantic, sem_degraded = extract_semantic(text)
    else:
        semantic, sem_degraded = {}, False
    rec = L3Source(..., semantic=semantic, semantic_degraded=sem_degraded, ...)
```

analyst.py：`import logging; log = logging.getLogger("assess.analyst")`；开头 `degraded_events = {"self_geo_score_skipped": 0, "page_seo_skipped": 0, "gap_skipped": 0, "competitor_skipped": 0, "l3_semantic_degraded": 0}`；四处 except 体加 `degraded_events["<键>"] += 1; log.warning("w%s ...: %s", week, e)`；页循环内 `if page_l3 and page_l3.semantic_degraded: degraded_events["l3_semantic_degraded"] += 1`；`"p0_content_degraded": page_l3 is None or not page_l3.text or bool(page_l3.semantic_degraded)`；report dict 增 `"degraded_events": degraded_events`。

模板：质量门行旁 `{% if rep.degraded_events and rep.degraded_events.values() | sum %}` 黄色提示 `数据降级事件:{{ ... }}`（fixture 更新）。

- [ ] **Step 4: 绿 + 边界协议（核心证明:黄金锁 43.4/49.8 逐维 PASS——纯可见性零分值漂移;w1 重算 degraded_events 应全 0）+ Commit** `feat(assess,fetch): 静默降级可见化——semantic_degraded 标记+analyst 降级事件计数(评分数值零变化)`

---

### Task 14: 终局边界验证 + 收尾

**Files:**
- 无新代码；产出验证记录 + 记忆更新。

- [ ] **Step 1: 全量套件** EXIT=0（预期 ≥498 passed + 2 skipped；落盘核对尾部计数）。
- [ ] **Step 2: 黄金锁三连**：`pytest tests/test_v1_semantics.py -v` 全 PASS（first_page 注入零漂移 + mean 口径 total 不变 + SOV 反回归）。
- [ ] **Step 3: 冻结产物终验**：`shasum -c /tmp/frozen_baseline.txt` 全 OK（例外仅 Global Constraints 声明两类）；`shasum -c /tmp/sources_baseline.txt`（T9 迁移后基线）OK。
- [ ] **Step 4: 迁移正确性抽验**：`ls geo-agent/data/sources/` 只剩 `w3/`；`find geo-agent/data/sources -type f | wc -l` 与迁移时一致；黄金锁已证 w1 通路。
- [ ] **Step 5: w4 演练（干跑语义，不跑真实网络）**：tmp repo 下 mini fixture 走 `assemble(901, ...)` 默认参数——断言 dims=mean、cost 键、degraded_events 键齐备（=w4 首跑时的报告新面）。
- [ ] **Step 6: 合入**：`git checkout -b backlog-cleanup` 若尚未建分支则从本任务前所有 commit 已在分支（执行期从 main 切出）→ `git checkout main && git merge --no-ff backlog-cleanup` → 合并树全量 EXIT=0 → push（HTTPS 通道：`git -c http.https://github.com.proxy=http://127.0.0.1:10808 -c credential.helper='!gh auth git-credential' push https://github.com/JerryZhang0751/sunpowerNova.git main:main` + 手动 update-ref）→ CI 双绿（`https_proxy=http://127.0.0.1:10808 gh run list --limit 3`；push 事件丢失时 `gh workflow run CI --ref main`）→ 删分支。
- [ ] **Step 7: 记忆更新**：current-status-and-blockers 顶部节 + weekly-iteration-runbook「w4 起生效」段追加（L3 周目录/robots fail-closed/SEO dims 新口径断点/degraded 可重取/预算降级标记/research top-N 每周重选）。

---

## Self-Review 记录

- **Spec 覆盖**：§2→T6｜§3→T2｜§4→T3/T4/T5｜§5→T1｜§6→T7｜§7→T8｜§8→T9｜§9→T10｜§10→T11｜§11→T12｜§12→T13｜§13/§14→Gate A/T14。19 项全覆盖。
- **计划期发现的两个 spec 未言明冲突及解法**（已按 spec §14"发现语义不符→回补"精神在任务内解决）：① 黄金锁逐维断言 SEO dims ↔ D4 全页平均 → `seo_dims_aggregation` 参数（锁注入 first_page，T7 就位/T11 切默认 mean），归档零改动；② 黄金锁 w1 重算依赖 L3 现路径 ↔ T9 迁移 → `legacy_source_dirs` 回退链（w1-w3→w3 终态，w4+ 不回退）。
- **类型一致性**：`source_dir(week, sha1)`/`fetch_source(url, week, ...)`/`_load_l3_source(week, url)`/`iter_l1(week, repo)`/`kimi_chat(...)`/`assemble(..., write, seo_dims_aggregation)` 各任务 Interfaces 与调用点改写一致。
- **已知偏差（记 spec 修订）**：changelog.md 不追加非版本条目（规则版本账本纯净性优先），口径断点注记落在报告模板 + spec/plan；source_scores.csv 行序可能重排（确定性化）。
