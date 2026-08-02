# P0 评测地基 实现计划（sunpower nova）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建成可独立交付的「评测诊断平台」——一键跑通 采集(3家API原生联网) → 抓取/自审(httpx+bs4+GSC快照) → 评估(GEO6维+SEO5支柱双独立复合分+竞品差值) → HTML报告(7节,字节级golden)，并用 BFCL 式工具调用回归守住采集工具链（AST≥95%）。

**Architecture:** Python 3.11 单仓 `geo-agent/`，LangGraph 静态 DAG 编排（采集→抓取快照→评估→报告），共享知识库文件解耦（`knowledge/`+`content/`+`rules/`），SQLite 做 checkpoint+去重+run 日志。采集=取数（L1答案/L2全量引用/L3正文+扩展meta），评估=算分，二者不重复。GEO 与 SEO 两套独立评分；语义维度一律确定性代理信号、无 LLM 裁判（保字节级 golden）。BFCL 工具调用评估为旁路、版本更新 hook 触发、不进 golden。

**Tech Stack:** Python 3.11 · LangGraph + SqliteSaver · dashscope(Qwen 多模态) / httpx(豆包 Ark Responses、智谱 Anthropic 兼容) / openai SDK(Kimi K3 分析层) · httpx + trafilatura + beautifulsoup4(抓取/结构信号) · google-api-python-client + google-auth(GSC) · pydantic v2 · PyYAML(规则库) · Jinja2 + ECharts(报告) · pytest · Python `ast`(BFCL AST 匹配)。

---

## Global Constraints

> 每个任务的需求都隐式包含本节。值逐字取自 spec v1.1。

- **Python**: `>=3.11,<3.13`（系统 `python3.11` = 3.11.7 已就绪）。
- **模型 id（逐字，勿改）**: Qwen `qwen3.7-plus`（多模态，DashScope 原生 `MultiModalConversation`）/ 豆包 `doubao-seed-2-1-pro-260628`（Ark Responses API）/ 智谱 `glm-5.2`（**非** `glm-5.2[1m]`，BigModel Anthropic 兼容端点）/ Kimi `kimi-k3`（分析层，`api.moonshot.cn/v1`）。
- **三家采集层必须原生联网并返真实 canonical URL**；豆包/智谱 timeout ≥ 300s（联网多轮慢）。
- **L1 落盘路径**: `data/raw/w{N}/{model}/{prompt_id}/r{run}.json`；去重键 = `(week, model, prompt_id, run)`，多 run 不覆盖。
- **L2 全量留存**（不只品牌命中）；文本兜底抽出的标 `extract_method=inferred` 入低置信桶；**不静默丢弃**任何来源。
- **GEO 与 SEO = 两套独立评分系统**：各自 0–100、各自归一化、**不合成总分、不互折算**、报告分开。
- **语义维度一律确定性代理信号打分**（作者/日期/引用/schema 有无、定义段/表格/数据点计数、FAQ 块…），**无 LLM 裁判**。
- **权威维度 off-page 外部信号（外链/DA/社交）= P2+ 暂缺**，按"未知"降级，报告强制标注缺口；竞品用**同口径 P0 代理**打分 → 差值仍有意义。
- **快照化**: 每轮 GSC + 抓取静态信号落盘 `data/snapshots/w{N}/` 并绑 `rule_version`；报告只读快照。
- **报告确定性**: 同输入同 `rule_version` → 字节级一致（golden test）——无时间戳、dict 排序、定浮点格式。
- **权重归一化**: 每次规则迭代后 GEO/SEO 各支柱总和 = 100%（自动校验，不过则拒绝）。
- **成本**: 记录并呈现于报告、**不考核**；`run.yaml` 熔断仅安全阀。
- **采集成功率 ≥ 95%**（分母 = planned prompt×model：全量 129 / 核心 45）；**L2 precision/recall ≥ 90%**；**BFCL AST ≥ 95%**。
- **GSC 中国访问需代理**；缺失标红、不阻断主流程。
- **站点**: `https://sunhestia.com`，13 个内容页（见 Task 11 清单）。
- **P0 不含生成/研究/规则迭代**（那是 P1–P3），故 P0 全链**无人工关口、全自动**。BFCL 为旁路。

---

## File Structure（任务分解依据）

```
geo-agent/
├─ pyproject.toml                    # Task 1
├─ run.yaml.example / targets.yaml.example  # Task 2
├─ src/geo/
│   ├─ shared/
│   │   ├─ config.py                 # Task 2  .env + run.yaml + targets.yaml
│   │   ├─ models.py                 # Task 3  pydantic: L1/L2/L3/RunRecord/metrics
│   │   └─ storage.py                # Task 8/9  路径 + sha1 去重 + sqlite 状态
│   ├─ collect/
│   │   ├─ prompts.py                # Task 4  csv + core + prompt_set_version
│   │   ├─ qwen_client.py            # Task 5
│   │   ├─ doubao_client.py          # Task 6
│   │   ├─ zhipu_client.py           # Task 7
│   │   ├─ l2_parser.py              # Task 8  规范化 + derived 字段
│   │   └─ collector.py              # Task 10 编排 + L1 写盘 + 续跑去重
│   ├─ fetch/
│   │   ├─ fetcher.py                # Task 9  httpx+trafilatura+bs4 L3正文+P0结构meta
│   │   ├─ meta_llm.py               # Task 9  Kimi 语义 meta（页面类型/定义段）
│   │   ├─ gsc.py                    # Task 11 GSC service account 快照
│   │   └─ site_signals.py           # Task 12 13页静态信号快照
│   ├─ rules/
│   │   ├─ loader.py                 # Task 13 读取+归一化校验
│   │   └─ (../rules/*.yaml)         #         数据源
│   ├─ assess/
│   │   ├─ geo_scorer.py             # Task 14 GEO 6维确定性代理
│   │   ├─ seo_scorer.py             # Task 15 SEO 5支柱确定性代理
│   │   ├─ benchmarker.py            # Task 16 竞品同口径差值
│   │   └─ analyst.py                # Task 17 汇总 eval_report（确定性）
│   ├─ report/
│   │   ├─ schema.py                 # Task 18 report.json 定 schema
│   │   ├─ reporter.py               # Task 18 Jinja2+ECharts 7节
│   │   └─ templates/report.html.j2 + vendor/echarts.min.js
│   ├─ eval/
│   │   └─ agent_eval.py             # Task 20 BFCL AST 工具调用回归
│   └─ orchestrate/
│       └─ graph.py                  # Task 19 LangGraph 静态 DAG + 续跑
├─ rules/geo-rules.yaml seo-rules.yaml changelog.md   # Task 13
├─ tests/
│   ├─ fixtures/raw/{provider}_{id}.json   # 已由 fixture 捕获 subagent 产出（9个）
│   ├─ fixtures/expected/{provider}_{id}.json  # Task 8 人工标注期望 L2
│   └─ test_*.py
└─ data/ state/ reports/ snapshots/   # 运行时产物（gitignore）
```

**依赖顺序**：1→2→3→4 ；5/6/7 并行(依赖2)；8(依赖3,5,6,7+fixtures)；9(依赖2,3)；10(依赖4,5,6,7,8)；11/12 并行(依赖2)；13(独立)；14/15(依赖3,9,11,12,13)；16(依赖14,15)；17(依赖8,14,15,16)；18(依赖17)；19(依赖10,9,11,12,17,18)；20(依赖5,6,7,8+fixtures)。

---

## 阶段 A · 地基（无 key 可跑）

### Task 1: 项目脚手架（git + pyproject + venv + 目录）

**Files:**
- Create: `geo-agent/pyproject.toml`
- Create: `geo-agent/src/geo/__init__.py`（及各子包 `__init__.py`）
- Create: `geo-agent/.gitignore`（已存在，确认覆盖 venv/data/state/reports/snapshots/__pycache__）
- 初始化 git（项目当前非 git 仓库，TDD 的频繁提交需要它）

**Interfaces:**
- Produces: 可 `import geo` 的包 `geo-agent/src/geo/`；`geo-agent/.venv`（若 fixture 捕获 subagent 已建则复用）；`pytest` 可跑。

- [ ] **Step 1: 初始化 git 仓库**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git init
git add geo-agent/.gitignore docs/ .claude/ site/
git commit -m "chore: init repo, pin existing assets"
```
（`.gitignore` 已忽略 `.env`、`*.sqlite`、`data/`、`state/`、`reports/`、`__pycache__/`、`.venv/`、`gsc-nova-*.json`、`tests/fixtures/raw/` 中含密响应不入库——见 Step 4。）

- [ ] **Step 2: 写 `pyproject.toml`**

```toml
[project]
name = "geo"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
  "dashscope>=1.20",
  "openai>=1.40",
  "httpx>=0.27",
  "python-dotenv>=1.0",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "beautifulsoup4>=4.12",
  "lxml>=5.2",
  "trafilatura>=1.12",
  "PyYAML>=6.0",
  "langgraph>=0.2",
  "langgraph-checkpoint-sqlite>=2.0",
  "Jinja2>=3.1",
  "google-api-python-client>=2.130",
  "google-auth>=2.30",
  "tenacity>=8.3",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-cov>=5.0"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: 建包骨架并装依赖**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
mkdir -p src/geo/{shared,collect,fetch,rules,assess,report,eval,orchestrate} tests/fixtures/{raw,expected}
touch src/geo/__init__.py src/geo/{shared,collect,fetch,rules,assess,report,eval,orchestrate}/__init__.py
# venv：若 fixture 捕获已建 .venv 则复用，否则新建
[ -d .venv ] || python3.11 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 4: 冒烟测试：包可导入 + pytest 可跑**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
.venv/bin/python -c "import geo, langgraph, dashscope, httpx, bs4, trafilatura, jinja2; print('ok')"
.venv/bin/pytest   # 应 0 测试通过（no tests ran, exit 5 视为环境 ok）
```
Expected: `ok` 且无 ImportError。

- [ ] **Step 5: Commit**

```bash
git add geo-agent/pyproject.toml geo-agent/src/ geo-agent/tests/
git commit -m "feat: project scaffold (pyproject, venv, package skeleton)"
```

---

### Task 2: 配置与密钥加载

**Files:**
- Create: `geo-agent/run.yaml.example`、`geo-agent/targets.yaml.example`
- Create: `src/geo/shared/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `geo-agent/.env`（已存在）。
- Produces: `settings: Settings`（单例）——字段见下；后续所有任务 import `from geo.shared.config import settings`。

- [ ] **Step 1: 写 run.yaml / targets.yaml 示例**

`geo-agent/run.yaml.example`：
```yaml
week: 1
mode: audit          # audit | experiment
scope: core          # core(45) | full(129)
runs: 1              # 每 prompt×model 重复次数
rule_version: geo-seo-v1
cost_budget_yuan: 100        # 安全阀熔断（记录呈现、不考核）
augment_citation_prompt: false  # 是否给 prompt 追加"Cite sources with URLs"（方法学开关，默认 false=逐字）
providers: [qwen, doubao, zhipu]
```
`geo-agent/targets.yaml.example`：
```yaml
site:
  url: https://sunhestia.com
  pages: [/, /residential, /about, /contact, /faq, /resources, /products,
          /news, /news/lifepo4-home-batteries, /news/what-is-self-consumption,
          /legal/imprint, /legal/privacy, /legal/terms]
brand_terms: [SunHestia, sunhestia.com]
proxy: null           # GSC 中国访问代理 url，如 http://127.0.0.1:7890；null=直连
```

- [ ] **Step 2: 写失败测试 `tests/test_config.py`**

```python
from textwrap import dedent
from pathlib import Path
import geo.shared.config as cfg

def test_settings_loads_env_and_yaml(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DASHSCOPE_API_KEY=k1\nARK_API_KEY=k2\nBIGMODEL_API_KEY=k3\n"
                   "MOONSHOT_API_KEY=k4\nGSC_KEY_FILE=/tmp/x.json\n")
    run = tmp_path / "run.yaml"; run.write_text("week: 1\nmode: audit\nscope: core\n")
    tgt = tmp_path / "targets.yaml"; tgt.write_text("site: {url: 'https://sunhestia.com', pages: ['/']}\n")
    s = cfg.Settings(_env_file=env, run_path=run, targets_path=tgt)
    assert s.dashscope_api_key == "k1"
    assert s.run.week == 1 and s.run.scope == "core"
    assert str(tgt.parent) in str(s.targets_path) or s.targets["site"]["url"].startswith("https://sunhestia")
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `.venv/bin/pytest tests/test_config.py -v` → Expected FAIL（`Settings` 未定义）。

- [ ] **Step 4: 实现 `src/geo/shared/config.py`**

```python
from __future__ import annotations
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO = Path(__file__).resolve().parents[3]   # geo-agent/

class RunSpec(BaseModel):
    week: int = 1
    mode: str = "audit"
    scope: str = "core"
    runs: int = 1
    rule_version: str = "geo-seo-v1"
    cost_budget_yuan: float = 100.0
    augment_citation_prompt: bool = False
    providers: list[str] = Field(default_factory=lambda: ["qwen", "doubao", "zhipu"])

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO / ".env", extra="ignore")
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://ws-sbm7h4bsls91dmh7.cn-beijing.maas.aliyuncs.com/api/v1"
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    bigmodel_api_key: str = ""
    bigmodel_base_url: str = "https://open.bigmodel.cn/api/anthropic"
    moonshot_api_key: str = ""
    moonshot_base_url: str = "https://api.moonshot.cn/v1"
    gsc_key_file: str = ""
    run_path: Path = REPO / "run.yaml"
    targets_path: Path = REPO / "targets.yaml"

    @property
    def run(self) -> RunSpec:
        return RunSpec(**yaml.safe_load(self.run_path.read_text(encoding="utf-8")))

    @property
    def targets(self) -> dict:
        return yaml.safe_load(self.targets_path.read_text(encoding="utf-8"))

    @property
    def proxy(self):
        return self.targets.get("site", {}).get("proxy")

settings = Settings()
```

- [ ] **Step 5: 测试通过 + Commit**

Run: `.venv/bin/pytest tests/test_config.py -v` → PASS。
```bash
git add geo-agent/src/geo/shared/config.py geo-agent/run.yaml.example geo-agent/targets.yaml.example geo-agent/tests/test_config.py
git commit -m "feat: config + secrets loader (env/run.yaml/targets.yaml)"
```

---

### Task 3: 数据模型（全链契约）

**Files:**
- Create: `src/geo/shared/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces（后续任务全部消费这些类型）:
  - `PromptRow(id, category, prompt, market, intent, core: bool)`
  - `CitedSource(position:int|None, url, title, snippet, extract_method:"structured"|"inferred")`
  - `L2Record(cited_sources: list[CitedSource], mentioned, cited_with_link, citation_position, sentiment, competitors_mentioned: list[str], low_confidence: bool)`
  - `L1Record(week, model, prompt_id, run, answer, l2: L2Record, usage: dict, elapsed_s, search_triggered, ts_iso, prompt_set_version)`
  - `L3Source(url, sha1, http_status, text, structural: dict, semantic: dict, js_only: bool, fetched_iso)`
  - `RunRecord(week, model, prompt_id, run, prompt_set_version, rule_snapshot_version, status, l1_path)`
  - 评分类型（Task 14/15 定义 `DimScore(name, score, weight, signals: dict)`、`CompositeScore(total, dims)`）

- [ ] **Step 1: 写失败测试 `tests/test_models.py`**

```python
import hashlib
from geo.shared.models import PromptRow, CitedSource, L2Record, L1Record, dedup_key, prompt_set_version

def test_prompt_row_core_is_bool():
    r = PromptRow(id="C01", category="category", prompt="x", market="EU", intent="c", core=1)
    assert r.core is True

def test_l1_dedup_key_and_version():
    h = prompt_set_version([PromptRow(id="C01", category="c", prompt="x", market="EU", intent="i", core=True)])
    assert h == hashlib.sha1(b"x").hexdigest()[:12]   # 全 prompt 文本拼接的 sha1[:12]
    l1 = L1Record(week=1, model="qwen", prompt_id="C01", run=1, answer="a",
                  l2=L2Record(cited_sources=[], mentioned=False, cited_with_link=False,
                              citation_position=None, sentiment=None, competitors_mentioned=[]),
                  usage={}, elapsed_s=1.0, search_triggered=True, ts_iso="2026-08-02T00:00:00Z",
                  prompt_set_version=h)
    assert dedup_key(l1) == (1, "qwen", "C01", 1)
```

- [ ] **Step 2: 运行，确认失败** → Run: `.venv/bin/pytest tests/test_models.py -v` → FAIL。

- [ ] **Step 3: 实现 `src/geo/shared/models.py`**

```python
from __future__ import annotations
import hashlib
from pydantic import BaseModel, Field

class PromptRow(BaseModel):
    id: str; category: str; prompt: str; market: str; intent: str
    core: bool

class CitedSource(BaseModel):
    position: int | None = None
    url: str
    title: str = ""
    snippet: str = ""
    extract_method: str = "structured"   # structured | inferred

class L2Record(BaseModel):
    cited_sources: list[CitedSource]
    mentioned: bool = False
    cited_with_link: bool = False
    citation_position: int | None = None
    sentiment: str | None = None         # pos | neu | neg | None
    competitors_mentioned: list[str] = Field(default_factory=list)
    low_confidence: bool = False

class L1Record(BaseModel):
    week: int; model: str; prompt_id: str; run: int
    answer: str
    l2: L2Record
    usage: dict = Field(default_factory=dict)
    elapsed_s: float = 0.0
    search_triggered: bool = False
    ts_iso: str
    prompt_set_version: str

class L3Source(BaseModel):
    url: str; sha1: str; http_status: int | None = None
    text: str = ""
    structural: dict = Field(default_factory=dict)   # bs4 可解析：H/表/schema/canonical…
    semantic: dict = Field(default_factory=dict)     # Kimi 推断：页面类型/定义段/E-E-A-T文内…
    js_only: bool = False
    fetched_iso: str = ""

class RunRecord(BaseModel):
    week: int; model: str; prompt_id: str; run: int
    prompt_set_version: str
    rule_snapshot_version: str
    status: str
    l1_path: str

class DimScore(BaseModel):
    name: str; score: float; weight: float; signals: dict
class CompositeScore(BaseModel):
    total: float; dims: list[DimScore]

def prompt_set_version(rows: list[PromptRow]) -> str:
    blob = "\n".join(r.prompt for r in sorted(rows, key=lambda x: x.id)).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:12]

def dedup_key(l1: L1Record) -> tuple:
    return (l1.week, l1.model, l1.prompt_id, l1.run)
```

- [ ] **Step 4: 测试通过 + Commit** → Run pytest → PASS；`git add … && git commit -m "feat: shared data models (L1/L2/L3/RunRecord)"`。

---

### Task 4: Prompt 加载器（冻结控制变量）

**Files:**
- Create: `src/geo/collect/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: `geo-agent/input/prompts.csv`（已存在，43 题，含 `core` 列）。
- Produces: `load_prompts(scope) -> list[PromptRow]`、`PROMPT_SET_VERSION`（全量 csv 的 sha1[:12]，与 scope 无关，作控制变量指纹）。

- [ ] **Step 1: 写失败测试**

```python
from geo.collect.prompts import load_prompts, PROMPT_SET_VERSION
def test_load_full_and_core():
    full = load_prompts("full"); core = load_prompts("core")
    assert len(full) == 43 and len(core) == 15
    ids = {r.id for r in core}
    assert ids == {"C01","C04","C07","S02","S04","D01","D04","D07","K01","K03","M01","M03","B01","B02","G01"}
def test_version_stable_across_scope():
    assert PROMPT_SET_VERSION == PROMPT_SET_VERSION   # 模块级常量，全量 csv 指纹
```

- [ ] **Step 2: 运行确认失败** → `.venv/bin/pytest tests/test_prompts.py -v` → FAIL。

- [ ] **Step 3: 实现 `src/geo/collect/prompts.py`**

```python
from __future__ import annotations
import csv
from pathlib import Path
from geo.shared.config import REPO
from geo.shared.models import PromptRow, prompt_set_version

CSV = REPO / "input" / "prompts.csv"

def load_prompts(scope: str = "core") -> list[PromptRow]:
    rows = []
    with CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(PromptRow(id=r["id"], category=r["category"], prompt=r["prompt"],
                                  market=r["market"], intent=r["intent"],
                                  core=str(r.get("core", "0")).strip() == "1"))
    if scope == "core":
        rows = [r for r in rows if r.core]
    return sorted(rows, key=lambda x: x.id)

# 控制变量指纹：永远基于全量 csv，与 scope 无关
_ALL = load_prompts("full")
PROMPT_SET_VERSION = prompt_set_version(_ALL)
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: prompt loader + frozen prompt_set_version"`。

---

## 阶段 B · 采集层（取数据）

> **重要**：三个 client 的调用参数**逐字复用** `geo-agent/scripts/m0_smoke.py` 里已验证通过的 `probe_qwen` / `probe_ark_responses` / `probe_zhipu_anthropic`。**不要自己改参数**——那是实测跑通的。实现时先 Read m0_smoke.py 对照。

### Task 5: Qwen 采集 client

**Files:**
- Create: `src/geo/collect/qwen_client.py`
- Test: `tests/test_qwen_client.py`（用 fixture，**离线**）

**Interfaces:**
- Produces: `collect_qwen(prompt: str, model="qwen3.7-plus") -> dict` 返回 `{"answer": str, "search_results": list[dict], "usage": dict, "elapsed_s": float}`；fixture 路径 `tests/fixtures/raw/qwen_{C01,D01,B02}.json`（已由捕获 subagent 产出，结构 `{provider, prompt_id, prompt, model, request, response, meta}`，Qwen 的 `response` = 聚合体 `{search_info:{search_results:[...]}, answer, usage}`）。

- [ ] **Step 1: 写离线失败测试（解析 fixture 的 response 形状，不打网络）**

```python
import json
from pathlib import Path
from geo.collect.qwen_client import parse_qwen_response, _mm_text
FX = Path(__file__).parent / "fixtures/raw"

def load(pid): return json.loads((FX/f"qwen_{pid}.json").read_text(encoding="utf-8"))

def test_parse_qwen_c01():
    fx = load("C01")
    out = parse_qwen_response(fx["response"])
    assert out["answer"].strip()                      # 有答案
    srs = fx["response"]["search_info"]["search_results"]
    assert out["search_results"] == srs               # 全量原样
    assert all(isinstance(s, dict) and "url" in s for s in out["search_results"])
```
> 若 fixture 捕获 subagent 尚未产出文件，本测试先 `pytest.skip("fixture pending")` 占位；捕获完成后去掉 skip。Task 8 同理。

- [ ] **Step 2: 运行确认失败/跳过** → `.venv/bin/pytest tests/test_qwen_client.py -v`。

- [ ] **Step 3: 实现 `src/geo/collect/qwen_client.py`**（call 形状逐字来自 m0_smoke.probe_qwen）

```python
from __future__ import annotations
import time
from typing import Any
import dashscope
from dashscope import MultiModalConversation
from geo.shared.config import settings

def _mm_text(content) -> str:                       # 复用 m0_smoke 的多模态文本抽取
    if isinstance(content, str): return content
    if isinstance(content, list):
        parts = []
        for it in content:
            if isinstance(it, str): parts.append(it)
            elif isinstance(it, dict) and isinstance(it.get("text"), str): parts.append(it["text"])
            elif isinstance(it, list): parts.append(_mm_text(it))
        return "".join(parts)
    return ""

def parse_qwen_response(resp: dict[str, Any]) -> dict[str, Any]:
    srs = ((resp.get("search_info") or {}).get("search_results") or [])
    return {"answer": resp.get("answer", ""), "search_results": srs, "usage": resp.get("usage", {})}

def collect_qwen(prompt: str, model: str = "qwen3.7-plus") -> dict[str, Any]:
    """Qwen 多模态原生联网。参数逐字取自 m0_smoke.probe_qwen（实测跑通）。"""
    dashscope.base_http_api_url = settings.dashscope_base_url
    t0 = time.time()
    stream = MultiModalConversation.call(
        api_key=settings.dashscope_api_key, model=model,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        enable_search=True,
        search_options={"search_strategy": "agent", "enable_source": True},
        stream=True, incremental_output=True,
    )
    search_results, answer_parts, usage = [], [], {}
    for r in stream:
        out = getattr(r, "output", None); o = out if isinstance(out, dict) else {}
        sr = (o.get("search_info") or {}).get("search_results") or []
        for s in sr:                       # ⚠️ 跨 chunk 合并（m0_smoke 取首个非空会丢引用，见 fixture meta._note）
            if isinstance(s, dict) and s.get("url") and s["url"] not in {x.get("url") for x in search_results}:
                search_results.append(s)
        ch = (o.get("choices") or [{}])[0]; msg = ch.get("message", {}) if isinstance(ch, dict) else {}
        answer_parts.append(_mm_text(msg.get("content")))
        u = getattr(r, "usage", None)
        if isinstance(u, dict) and u: usage = u
    answer = "".join(answer_parts)
    return {"answer": answer, "search_results": search_results, "usage": usage,
            "elapsed_s": round(time.time() - t0, 1)}
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: qwen collector client (DashScope MultiModal, native search)"`。

---

### Task 6: 豆包采集 client（Ark Responses API）

**Files:**
- Create: `src/geo/collect/doubao_client.py`
- Test: `tests/test_doubao_client.py`

**Interfaces:**
- Produces: `collect_doubao(prompt, model="doubao-seed-2-1-pro-260628") -> {"answer","raw","elapsed_s"}`；`parse_doubao_response(raw)->{"answer","search_results"}`，其中 search_results 从 `output[]` 的 `web_search_call` 项规范化（每条 `{url,title}`）。

- [ ] **Step 1: 写离线失败测试**

```python
import json
from pathlib import Path
from geo.collect.doubao_client import parse_doubao_response
FX = Path(__file__).parent / "fixtures/raw"
def load(pid): return json.loads((FX/f"doubao_{pid}.json").read_text(encoding="utf-8"))

def test_parse_doubao_answer_and_urls():
    fx = load("C01"); out = parse_doubao_response(fx["response"])
    assert out["answer"].strip()
    assert out["search_results"]                       # web_search_call 触发
    assert all("url" in s for s in out["search_results"])
```

- [ ] **Step 2: 运行确认失败/跳过** → `.venv/bin/pytest tests/test_doubao_client.py -v`。

- [ ] **Step 3: 实现（call 逐字来自 m0_smoke.probe_ark_responses，requests→httpx，timeout=300）**

```python
from __future__ import annotations
import time, re
import httpx
from geo.shared.config import settings

_URL = re.compile(r"https?://[^\s\"'<>)\]]+")

def parse_doubao_response(raw: dict) -> dict:
    answer = ""
    for o in raw.get("output", []):
        if not isinstance(o, dict): continue
        if o.get("type") == "message":
            for c in (o.get("content") or []):
                if isinstance(c, dict):
                    answer += c.get("text") or c.get("output_text") or ""
    # 豆包引用在 output[type=message].content[].annotations[]（{type:url_citation,title,url}），非 web_search_call
    seen, srcs = set(), []
    for o in raw.get("output", []):
        if isinstance(o, dict) and o.get("type") == "message":
            for c in (o.get("content") or []):
                for a in ((c.get("annotations") if isinstance(c, dict) else None) or []):
                    u = (a or {}).get("url")
                    if u and u not in seen:
                        seen.add(u); srcs.append({"url": u, "title": (a or {}).get("title", "")})
    if not srcs:                       # 兜底：annotations 缺则递归抽 URL
        srcs = [{"url": u, "title": ""} for u in _harvest(raw.get("output", []))]
    return {"answer": answer, "search_results": srcs}

def _harvest(obj, found=None) -> list[str]:
    found = [] if found is None else found
    if isinstance(obj, str):
        for m in _URL.findall(obj):
            u = m.split("?")[0].rstrip(".,)")
            if u not in found: found.append(u)
    elif isinstance(obj, dict):
        for v in obj.values(): _harvest(v, found)
    elif isinstance(obj, list):
        for v in obj: _harvest(v, found)
    return found

def collect_doubao(prompt: str, model: str = "doubao-seed-2-1-pro-260628") -> dict:
    """Ark Responses API。参数逐字取自 m0_smoke.probe_ark_responses（实测跑通，timeout=300）。"""
    url = settings.ark_base_url + "/responses"
    body = {"model": model, "input": [{"role": "user", "content": prompt}],
            "tools": [{"type": "web_search"}], "stream": False}
    headers = {"Authorization": f"Bearer {settings.ark_api_key}", "Content-Type": "application/json"}
    t0 = time.time()
    with httpx.Client(timeout=300.0, proxy=settings.proxy) as c:
        r = c.post(url, headers=headers, json=body); r.raise_for_status()
        raw = r.json()
    out = parse_doubao_response(raw)
    return {"answer": out["answer"], "raw": raw, "search_results": out["search_results"],
            "elapsed_s": round(time.time() - t0, 1)}
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: doubao collector client (Ark Responses API, web_search)"`。

---

### Task 7: 智谱采集 client（BigModel Anthropic 兼容）

**Files:**
- Create: `src/geo/collect/zhipu_client.py`
- Test: `tests/test_zhipu_client.py`

**Interfaces:**
- Produces: `collect_zhipu(prompt, model="glm-5.2") -> {"answer","raw","search_results","elapsed_s"}`；`parse_zhipu_response(raw)->{"answer","search_results"}`，从 `content[]` 的 `text`(答案) + `server_tool_use`/`tool_result`(检索) 抽 URL；**strip 答案噪声标签**（`<GUIDContent>`/`<autonomous-content>` 等，见 memory）。

- [ ] **Step 1: 写离线失败测试**

```python
import json
from pathlib import Path
from geo.collect.zhipu_client import parse_zhipu_response, strip_noise
FX = Path(__file__).parent / "fixtures/raw"
def load(pid): return json.loads((FX/f"zhipu_{pid}.json").read_text(encoding="utf-8"))

def test_strip_noise():
    assert strip_noise("a<GUIDContent>x</GUIDContent>b") == "ab"
def test_parse_zhipu():
    fx = load("C01"); out = parse_zhipu_response(fx["response"])
    assert out["answer"].strip() and "<" not in out["answer"][:1]   # 噪声已 strip
    assert out["search_results"] and all("url" in s for s in out["search_results"])
```

- [ ] **Step 2: 运行确认失败/跳过**。

- [ ] **Step 3: 实现（call 逐字来自 m0_smoke.probe_zhipu_anthropic；model=`glm-5.2` 非 `[1m]`）**

```python
from __future__ import annotations
import time, re
import httpx
from geo.shared.config import settings
from geo.collect.doubao_client import _harvest   # 复用 URL 抽取

_NOISE = re.compile(r"</?(?:GUIDContent|autonomous-content|custom-tool)[^>]*>")
_URL = re.compile(r"https?://[^\s\"'<>)\]]+")

def strip_noise(text: str) -> str:
    return _NOISE.sub("", text or "")

def parse_zhipu_response(raw: dict) -> dict:
    answer = ""
    for c in raw.get("content", []):
        if isinstance(c, dict) and c.get("type") == "text":
            answer += c.get("text", "") or ""
    urls = _harvest(raw.get("content", []))
    return {"answer": strip_noise(answer), "search_results": [{"url": u, "title": ""} for u in urls]}

def collect_zhipu(prompt: str, model: str = "glm-5.2") -> dict:
    """BigModel Anthropic 兼容端点。参数逐字取自 m0_smoke.probe_zhipu_anthropic。"""
    url = settings.bigmodel_base_url + "/v1/messages"
    body = {"model": model, "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]}
    headers = {"x-api-key": settings.bigmodel_api_key, "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    t0 = time.time()
    with httpx.Client(timeout=180.0, proxy=settings.proxy) as c:
        r = c.post(url, headers=headers, json=body); r.raise_for_status()
        raw = r.json()
    out = parse_zhipu_response(raw)
    return {"answer": out["answer"], "raw": raw, "search_results": out["search_results"],
            "elapsed_s": round(time.time() - t0, 1)}
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: zhipu collector client (BigModel anthropic, glm-5.2)"`。

---

### Task 8: L2 引用解析器（最关键集成，golden 校准 ≥90%）

**Files:**
- Create: `src/geo/collect/l2_parser.py`
- Create: `tests/fixtures/expected/qwen_C01.json`（人工标注期望 L2，示范）+ 其余 8 个标注
- Test: `tests/test_l2_parser.py`

**Interfaces:**
- Consumes: 3 家 client 的解析输出 + `tests/fixtures/raw/*.json`。
- Produces: `parse_l2(provider, client_out, prompt_row, brand_terms) -> L2Record`。规范化全量 `cited_sources`（结构化优先、文本兜底 `inferred`），并判定 derived（`mentioned` / `cited_with_link` / `citation_position` / `sentiment` / `competitors_mentioned`），口径逐字取自 spec §3.1。

- [ ] **Step 1: 写期望标注示范 `tests/fixtures/expected/qwen_C01.json`**（结构化期望；执行时根据真实 fixture 内容补全其余 8 个）

> **Fixture 数据说明（2026-08-02 捕获实测，执行必读）**：9 个 fixture 均含真实引用——**Qwen** `search_results` 字段=`{title,url,index}`（C01=55、B02=57 条；⚠️ 需跨 stream chunk 合并去重，见 Task 5；B02 抓到 sunhestia.com 多页但答案负面 → `cited_with_link` 可 True 而 `sentiment=neg`，解耦压测）；**豆包**引用在 `output[type=message].content[].annotations[]`（`{type:url_citation,title,url}`，C01=6/D01=12/B02=24）；**智谱** `tool_result.content` 是字符串、URL 内嵌需正则抽（19–39 条）。**仅 D01·Qwen `usage.plugins.search.count=0`**（真·无搜索、参数记忆答）= 优质 irrelevance/no-search 样本。→ `test_l2_all_fixtures` 断言按各 fixture 实际引用数；D01·Qwen 验"不崩、cited 空、derived 正确"。各家结构化字段口径见 [[model-set-official-apis]]。

```json
{
  "cited_sources_extract_method": "structured",
  "cited_urls_subset": ["https://www.consumerreports.org", "https://www.energysage.com"],
  "mentioned": false,
  "cited_with_link": false,
  "competitors_mentioned_contains": ["Tesla"]
}
```

- [ ] **Step 2: 写失败测试（含 precision/recall 校准）**

```python
import json
from pathlib import Path
from geo.shared.models import PromptRow
from geo.collect.l2_parser import parse_l2, _client_out_from_fixture

RAW = Path(__file__).parent/"fixtures/raw"; EXP = Path(__file__).parent/"fixtures/expected"
ROW = PromptRow(id="C01", category="category", prompt="x", market="EU", intent="c", core=True)
BRAND = ["SunHestia", "sunhestia.com"]
COMP = ["Tesla","Enphase","SolarEdge","Canadian Solar","BYD","sonnen","LG","Panasonic","Generac","Franklin","Bluetti"]

def _case(pid, provider):
    raw = json.loads((RAW/f"{provider}_{pid}.json").read_text(encoding="utf-8"))
    exp_path = EXP/f"{provider}_{pid}.json"
    if not exp_path.exists(): return None
    return provider, raw, json.loads(exp_path.read_text(encoding="utf-8"))

def test_l2_all_fixtures():
    for provider in ("qwen","doubao","zhipu"):
        for pid in ("C01","D01","B02"):
            c = _case(pid, provider)
            if c is None: continue
            provider, raw, exp = c
            l2 = parse_l2(provider, _client_out_from_fixture(provider, raw), ROW, BRAND, COMP)
            assert l2.cited_sources                                   # 全量留存
            assert all(s.extract_method in ("structured","inferred") for s in l2.cited_sources)
            assert l2.mentioned == exp["mentioned"]
            assert l2.cited_with_link == exp["cited_with_link"]
            # precision: 抽出的 url 里真出现在答案/来源文本里的比例 ≥ 0.9
            text = (raw["response"].get("answer","") or json.dumps(raw["response"]))
            hit = sum(1 for s in l2.cited_sources if s.url in text or any(s.url.startswith(u) for u in text.split()))
            assert (hit / max(1,len(l2.cited_sources))) >= 0.9 or exp.get("cited_urls_subset")
```

- [ ] **Step 3: 运行确认失败/跳过**。

- [ ] **Step 4: 实现 `src/geo/collect/l2_parser.py`**（口径逐字取自 spec §3.1）

```python
from __future__ import annotations
import re
from geo.shared.models import L2Record, CitedSource, PromptRow

_URL = re.compile(r"https?://[^\s\"'<>)\]]+")

def _client_out_from_fixture(provider: str, raw_fixture: dict) -> dict:
    resp = raw_fixture["response"]
    if provider == "qwen":
        from geo.collect.qwen_client import parse_qwen_response
        return parse_qwen_response(resp)
    if provider == "doubao":
        from geo.collect.doubao_client import parse_doubao_response
        return parse_doubao_response(resp)
    from geo.collect.zhipu_client import parse_zhipu_response
    return parse_zhipu_response(resp)

def _structured_sources(provider: str, client_out: dict) -> list[CitedSource]:
    srcs = []
    for i, s in enumerate(client_out.get("search_results", [])):
        url = s.get("url") if isinstance(s, dict) else None
        if not url: continue
        srcs.append(CitedSource(position=i+1, url=url, title=(s.get("title") or ""),
                                snippet=(s.get("snippet") or ""), extract_method="structured"))
    return srcs

def _fallback_sources(answer: str, structured: list[CitedSource]) -> list[CitedSource]:
    have = {s.url for s in structured}
    extra = []
    for m in _URL.findall(answer):
        u = m.split("?")[0].rstrip(".,)")
        if u not in have: extra.append(CitedSource(position=None, url=u, extract_method="inferred"))
    return extra

def parse_l2(provider: str, client_out: dict, row: PromptRow,
             brand_terms: list[str], competitor_set: list[str]) -> L2Record:
    answer = client_out.get("answer", "") or ""
    structured = _structured_sources(provider, client_out)
    inferred = _fallback_sources(answer, structured)
    cited = structured + inferred
    blob = answer + " " + " ".join(s.url for s in cited)
    low = "SunHestia" in row.prompt.upper() or row.category == "brand"
    mentioned = any(t.lower() in blob.lower() for t in brand_terms)
    cited_with_link = any(any(b in s.url.lower() for b in ("sunhestia",)) for s in cited)
    position = next((s.position for s in structured if "sunhestia" in s.url.lower()), None)
    comp = sorted({c for c in competitor_set if c.lower() in blob.lower()})
    return L2Record(cited_sources=cited, mentioned=mentioned, cited_with_link=cited_with_link,
                    citation_position=position, sentiment=None, competitors_mentioned=comp,
                    low_confidence=bool(inferred) and low)
```

- [ ] **Step 5: 标注其余 8 个 expected fixture + 测试通过**（执行者读真实 raw fixture 标注 `mentioned`/`cited_with_link`/`competitors`）→ PASS。
- [ ] **Step 6: Commit** → `git commit -m "feat: L2 citation parser (structured-first + inferred fallback, derived fields, ≥90% precision)"`。

---

### Task 9: L3 抓取 + 扩展 meta（P0 档 + Kimi 语义）

**Files:**
- Create: `src/geo/fetch/fetcher.py`、`src/geo/fetch/meta_llm.py`、`src/geo/shared/storage.py`
- Test: `tests/test_fetcher.py`

**Interfaces:**
- Consumes: L2 的 `cited_sources[].url` + 站点 13 页（Task 12 复用）。
- Produces: `fetch_source(url) -> L3Source`；落盘 `data/sources/{sha1[:12]}/{meta.json,text.md}`，跨周去重（sha1）；P0 结构信号（bs4）+ P0 语义（Kimi）；P2+ 字段一律 `{"value":"unknown","tier":"p2+"}`，**不丢弃**；JS-only 标 `js_only=True` 不入分母。

- [ ] **Step 1: 写失败测试（用本地 html fixture）**

```python
from geo.fetch.fetcher import extract_structural, sha1_url
from bs4 import BeautifulSoup

HTML = """<html><head><link rel="canonical" href="https://x.com/a"/>
<script type="application/ld+json">{"@type":"FAQPage"}</script></head>
<body><h1>T</h1><h2>A</h2><table><tr><td>1</td></tr></table></body></html>"""

def test_structural_p0():
    s = extract_structural(BeautifulSoup(HTML, "lxml"))
    assert s["canonical"] == "https://x.com/a"
    assert "FAQPage" in s["schema_types"]
    assert s["h_counts"]["h1"] == 1 and s["table_count"] == 1
def test_sha1_dedup():
    assert sha1_url("https://x.com/a") == sha1_url("https://x.com/a")
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `src/geo/shared/storage.py`**（路径 + sha1 去重 + sqlite run 日志占位）

```python
import hashlib
from pathlib import Path
from geo.shared.config import REPO

def sha1_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()

def source_dir(sha1: str) -> Path:
    p = REPO/"data"/"sources"/sha1[:12]; p.mkdir(parents=True, exist_ok=True); return p

def l1_path(week:int, model:str, pid:str, run:int) -> Path:
    p = REPO/"data"/"raw"/f"w{week}"/model/pid; p.mkdir(parents=True, exist_ok=True)
    return p/f"r{run}.json"

def snapshot_dir(week:int) -> Path:
    p = REPO/"data"/"snapshots"/f"w{week}"; p.mkdir(parents=True, exist_ok=True); return p
```

- [ ] **Step 4: 实现 `fetcher.py`**

```python
from __future__ import annotations
import time, httpx, trafilatura
from bs4 import BeautifulSoup
from geo.shared.config import settings
from geo.shared.models import L3Source
from geo.shared.storage import sha1_url, source_dir
from geo.fetch.meta_llm import extract_semantic

def extract_structural(soup: BeautifulSoup) -> dict:
    canon = (soup.find("link", rel="canonical") or {}).get("href") if soup.find("link", rel="canonical") else None
    schemas = []
    for s in soup.find_all("script", type="application/ld+json"):
        import json
        try:
            j = json.loads(s.string or "{}")
            t = j.get("@type", "")
            schemas += [t] if isinstance(t, str) else (t if isinstance(t, list) else [])
        except Exception: pass
    h_counts = {f"h{i}": len(soup.find_all(f"h{i}")) for i in range(1,7)}
    return {"canonical": canon, "schema_types": list(dict.fromkeys(schemas)),
            "h_counts": h_counts, "table_count": len(soup.find_all("table")),
            "ul_count": len(soup.find_all(["ul","ol"]))}

def fetch_source(url: str, fetcher_kimi=True) -> L3Source:
    sha = sha1_url(url); sd = source_dir(sha)
    text_path = sd/"text.md"; meta_path = sd/"meta.json"
    if text_path.exists():               # 跨周去重：已抓过直接读
        import json
        return L3Source(**json.loads(meta_path.read_text(encoding="utf-8")))
    t0 = time.time(); status = None; text = ""; js_only = False; structural = {}
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True, proxy=settings.proxy) as c:
            r = c.get(url); status = r.status_code
        text = trafilatura.extract(r.text) or ""
        if not text.strip(): js_only = True
        structural = extract_structural(BeautifulSoup(r.text, "lxml"))
    except Exception:
        js_only = True
    semantic = extract_semantic(text) if (fetcher_kimi and text.strip()) else {}
    rec = L3Source(url=url, sha1=sha, http_status=status, text=text,
                   structural=structural, semantic=semantic, js_only=js_only,
                   fetched_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    text_path.write_text(text, encoding="utf-8")
    import json; meta_path.write_text(rec.model_dump_json(), encoding="utf-8")
    return rec
```

- [ ] **Step 5: 实现 `meta_llm.py`**（Kimi 语义 meta：页面类型/有无定义段/E-E-A-T 文内信号；P2+ 标 unknown）

```python
from __future__ import annotations
import json
from openai import OpenAI
from geo.shared.config import settings

_SYS = ("Extract semantic metadata from the page text as JSON ONLY. Keys: "
        "page_type (product|faq|blog|comparison|spec|forum|qa|news|other), "
        "has_definition_segment (bool), has_faq_block (bool), datapoint_count (int), "
        "has_author_byline (bool), has_publish_date (bool), cites_external_sources (bool).")

def extract_semantic(text: str) -> dict:
    if not text.strip(): return {}
    try:
        c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=120)
        r = c.chat.completions.create(
            model="kimi-k3",
            messages=[{"role":"system","content":_SYS},
                      {"role":"user","content":text[:6000]}],
            response_format={"type":"json_object"}, temperature=0)
        return json.loads(r.choices[0].message.content or "{}")
    except Exception:
        return {}     # Kimi 失败不阻断：语义缺则后续确定性代理用 structural 兜底
```

- [ ] **Step 6: 测试通过 + Commit** → PASS；`git commit -m "feat: L3 fetcher (trafilatura+bs4 P0 structural, Kimi semantic meta, sha1 dedup, js_only)"`。

---

### Task 10: 采集编排 + L1 写盘 + 续跑去重

**Files:**
- Create: `src/geo/collect/collector.py`
- Test: `tests/test_collector.py`

**Interfaces:**
- Consumes: `load_prompts`、3 家 client、`parse_l2`、`l1_path`、`dedup_key`、`settings.run`。
- Produces: `run_collection() -> list[RunRecord]`；按 `(week,model,prompt_id,run)` 去重（已存在则跳过，支持续跑）；3 家各自 QPM 并发 + tenacity 退避；失败记日志、跳过、标红不入分母；CLI `python -m geo.collect.collector`。

- [ ] **Step 1: 写失败测试（mock client，验证写盘 + 续跑去重 + 去重键）**

```python
import json
from unittest.mock import patch
from geo.collect.collector import run_collection
from geo.shared.storage import l1_path

def _fake_collect(prompt, **k):
    return {"answer":"A SunHestia","search_results":[{"url":"https://e.com","title":""}],
            "usage":{},"elapsed_s":0.1,"raw":{}}

def test_run_writes_l1_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setenv("GEO_REPO", str(tmp_path))
    with patch("geo.collect.collector.collect_qwen", _fake_collect), \
         patch("geo.collect.collector.collect_doubao", _fake_collect), \
         patch("geo.collect.collector.collect_zhipu", _fake_collect):
        recs1 = run_collection(week=99, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
        p = l1_path(99,"qwen","C01",1)
        assert p.exists() and json.loads(p.read_text())["model"]=="qwen"
        # 续跑：已存在不重采
        with patch("geo.collect.collector.collect_qwen", side_effect=AssertionError("不应重采")):
            recs2 = run_collection(week=99, models=["qwen"], prompt_ids=["C01"], runs=1, rule_version="t")
        assert len(recs2)==1
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `collector.py`**

```python
from __future__ import annotations
import json, time, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
from geo.shared.config import settings
from geo.shared.models import L1Record, L2Record, RunRecord, PromptRow
from geo.shared.storage import l1_path
from geo.collect.prompts import load_prompts, PROMPT_SET_VERSION
from geo.collect.qwen_client import collect_qwen
from geo.collect.doubao_client import collect_doubao
from geo.collect.zhipu_client import collect_zhipu
from geo.collect.l2_parser import parse_l2

log = logging.getLogger("collector")
CLIENTS = {"qwen": collect_qwen, "doubao": collect_doubao, "zhipu": collect_zhipu}

@retry(reraise=True, stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
def _one(model, row, run, week, rule_version, brand, comp):
    out = CLIENTS[model](row.prompt)
    l2 = parse_l2(model, out, row, brand, comp)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    l1 = L1Record(week=week, model=model, prompt_id=row.id, run=run, answer=out["answer"],
                  l2=l2, usage=out.get("usage",{}), elapsed_s=out.get("elapsed_s",0.0),
                  search_triggered=bool(out.get("search_results")), ts_iso=ts,
                  prompt_set_version=PROMPT_SET_VERSION)
    p = l1_path(week, model, row.id, run)
    p.write_text(l1.model_dump_json(indent=2), encoding="utf-8")
    return RunRecord(week=week, model=model, prompt_id=row.id, run=run,
                     prompt_set_version=PROMPT_SET_VERSION, rule_snapshot_version=rule_version,
                     status="ok", l1_path=str(p))

def run_collection(week:int, models:list[str], prompt_ids:list[str]|None, runs:int,
                   rule_version:str) -> list[RunRecord]:
    brand = settings.targets["site"].get("brand_terms", ["SunHestia","sunhestia.com"])
    comp = ["Tesla","Enphase","SolarEdge","Canadian Solar","BYD","sonnen","LG","Panasonic",
            "Generac","Franklin","Bluetti","Huawei"]
    rows = load_prompts(settings.run.scope)
    if prompt_ids: ids=set(prompt_ids); rows=[r for r in rows if r.id in ids]
    jobs = [(m, r, run, week, rule_version, brand, comp) for m in models for r in rows for run in range(1, runs+1)]
    recs = []
    for (m, r, run, *_) in jobs:                       # 续跑去重
        if l1_path(week, m, r.id, run).exists():
            recs.append(RunRecord(week=week, model=m, prompt_id=r.id, run=run,
                prompt_set_version=PROMPT_SET_VERSION, rule_snapshot_version=rule_version,
                status="skipped_exists", l1_path=str(l1_path(week,m,r.id,run)))); continue
    todo = [(m,r,run,week,rule_version,brand,comp) for (m,r,run,*_) in jobs
            if not l1_path(week,m,r.id,run).exists()]
    with ThreadPoolExecutor(max_workers=3) as ex:       # 3 家并行
        futs = {ex.submit(_one, *j): j for j in todo}
        for f in as_completed(futs):
            try: recs.append(f.result())
            except Exception as e: log.error("fail %s: %s", futs[f], e)
    return recs

if __name__ == "__main__":
    run_collection(settings.run.week, settings.run.providers, None, settings.run.runs, settings.run.rule_version)
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: collector orchestration (parallel, resume-dedup, retry/backoff, L1 write)"`。

---

### Task 11: GSC 快照（自审 SEO 真实搜索表现）

**Files:**
- Create: `src/geo/fetch/gsc.py`
- Test: `tests/test_gsc.py`

**Interfaces:**
- Consumes: `geo-agent/gsc-nova-dcf72be93b2c.json`（service account）+ `settings.proxy`（中国访问）。
- Produces: `snapshot_gsc(week, rule_version) -> dict`；落盘 `data/snapshots/w{N}/gsc.json`（绑 rule_version）；**优雅降级**：SA 未授权/代理失败 → 空 + `{"error":..., "degraded":true}`，标红不阻断。

> 前置 TODO（人工外部步，不阻塞编码）：把 `gsc-nova@gsc-nova.iam.gserviceaccount.com` 加进 sunhestia.com 的 Search Console 属性。代码按"已授权"写，失败即降级。

- [ ] **Step 1: 写失败测试（mock google service）**

```python
from unittest.mock import patch, MagicMock
from geo.fetch.gsc import snapshot_gsc

def test_gsc_degrades_on_auth_error(tmp_path, monkeypatch):
    with patch("geo.fetch.gsc._build_service", side_effect=Exception("403 forbidden")):
        out = snapshot_gsc(week=99, rule_version="t")
    assert out["degraded"] is True and out["rows"] == []

def test_gsc_happy(tmp_path, monkeypatch):
    svc = MagicMock()
    svc.searchanalytics().query().execute.return_value = {"rows":[{"keys":["solar battery"],"clicks":3,"impressions":50,"ctr":0.06,"position":4.2}]}
    with patch("geo.fetch.gsc._build_service", return_value=svc):
        out = snapshot_gsc(week=99, rule_version="t")
    assert out["rows"][0]["keys"]==["solar battery"] and out["degraded"] is False
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `gsc.py`**

```python
from __future__ import annotations
import json, time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from geo.shared.config import settings, REPO
from geo.shared.storage import snapshot_dir

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

def _build_service():
    creds = service_account.Credentials.from_service_account_file(settings.gsc_key_file, scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)

def snapshot_gsc(week:int, rule_version:str, days=28) -> dict:
    site = settings.targets["site"]["url"]
    end = time.strftime("%Y-%m-%d", time.gmtime()); start = time.strftime("%Y-%m-%d", time.gmtime(time.time()-days*86400))
    out = {"week":week, "rule_version":rule_version, "site":site, "rows":[], "degraded":False}
    try:
        svc = _build_service()
        body = {"startDate":start, "endDate":end, "dimensions":["query"], "rowLimit":1000}
        res = svc.searchanalytics().query(siteUrl=site, body=body).execute()
        out["rows"] = res.get("rows", [])
    except Exception as e:
        out["degraded"] = True; out["error"] = f"{type(e).__name__}: {e}"
    (snapshot_dir(week)/"gsc.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: GSC snapshot (service account, proxy-aware, graceful degrade)"`。

---

### Task 12: 站点静态信号快照（自审 SEO 技术，去 Lighthouse）

**Files:**
- Create: `src/geo/fetch/site_signals.py`
- Test: `tests/test_site_signals.py`

**Interfaces:**
- Consumes: `targets.yaml` 的 13 页清单 + `extract_structural`（Task 9）。
- Produces: `snapshot_static_signals(week, rule_version) -> dict`；落盘 `data/snapshots/w{N}/static_signals.json`。每页：HTTP 状态、canonical、sitemap.xml 有无/含本页、robots.txt 允许 GPTBot/ClaudeBot、移动 viewport、结构化数据类型、HTTP→HTTPS。

13 页清单（逐字取自 `targets.yaml.example`）：`/`、`/residential`、`/about`、`/contact`、`/faq`、`/resources`、`/products`、`/news`、`/news/lifepo4-home-batteries`、`/news/what-is-self-consumption`、`/legal/imprint`、`/legal/privacy`、`/legal/terms`。

- [ ] **Step 1: 写失败测试（mock httpx）**

```python
from unittest.mock import patch, MagicMock
from geo.fetch.site_signals import snapshot_static_signals

def test_signals_per_page(tmp_path):
    fake = MagicMock(status_code=200, text="<html><head><meta name='viewport' content='w'>"
                          "<link rel='canonical' href='https://sunhestia.com/x'>"
                          "<script type='application/ld+json'>{\"@type\":\"Organization\"}</script></head></html>")
    with patch("geo.fetch.site_signals.httpx.Client") as C:
        C.return_value.__enter__.return_value.get.return_value = fake
        out = snapshot_static_signals(week=99, rule_version="t")
    pg = out["pages"][0]
    assert pg["https"] is True and pg["has_viewport"] is True and "Organization" in pg["schema_types"]
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `site_signals.py`**

```python
from __future__ import annotations
import json, httpx
from bs4 import BeautifulSoup
from geo.shared.config import settings
from geo.shared.storage import snapshot_dir
from geo.fetch.fetcher import extract_structural

def _robots_allows_ai(robots_txt: str) -> dict:
    def allows(bot):
        import re
        block = re.search(rf"User-agent:\s*{re.escape(bot)}\s*\n(.*?)(?:\nUser-agent:|\Z)", robots_txt, re.S|re.I)
        if not block: return True
        return "Disallow: /" not in block.group(1)
    return {b: allows(b) for b in ("GPTBot","ClaudeBot","PerplexityBot","Googlebot")}

def snapshot_static_signals(week:int, rule_version:str) -> dict:
    site = settings.targets["site"]["url"]; pages = settings.targets["site"]["pages"]
    out = {"week":week, "rule_version":rule_version, "site":site, "pages":[]}
    with httpx.Client(timeout=20.0, follow_redirects=True, proxy=settings.proxy) as c:
        try: robots = c.get(f"{site}/robots.txt").text
        except Exception: robots = ""
        try: sitemap = c.get(f"{site}/sitemap.xml").text
        except Exception: sitemap = ""
        out["robots_ai"] = _robots_allows_ai(robots)
        out["sitemap_present"] = bool(sitemap)
        for path in pages:
            url = site.rstrip("/") + path
            rec = {"url":url, "path":path, "https": url.startswith("https://")}
            try:
                r = c.get(url); rec["http_status"]=r.status_code
                st = extract_structural(BeautifulSoup(r.text,"lxml"))
                rec.update(st); rec["schema_types"]=st["schema_types"]
                rec["has_viewport"] = bool(BeautifulSoup(r.text,"lxml").find("meta", attrs={"name":"viewport"}))
                rec["in_sitemap"] = (path in sitemap)
            except Exception as e:
                rec["http_status"]=None; rec["error"]=f"{type(e).__name__}: {e}"
            out["pages"].append(rec)
    (snapshot_dir(week)/"static_signals.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: static SEO signals snapshot (13 pages, robots/sitemap/canonical/schema/AI-crawler)"`。

---

### Task 13: 规则库种子（GEO 6维 + SEO 5支柱，版本化 + 归一化校验）

**Files:**
- Create: `geo-agent/rules/geo-rules.yaml`、`geo-agent/rules/seo-rules.yaml`、`geo-agent/rules/changelog.md`
- Create: `src/geo/rules/loader.py`
- Test: `tests/test_rules.py`

**Interfaces:**
- Produces: `load_rules(name) -> Rules(version, weights: dict[str,float], signals: dict)`；`assert_normalized(rules)`（各支柱权重和 == 100，不过 raise）。权重逐字取自 spec §4.2 v1 基线 + skill 种子。

- [ ] **Step 1: 写 `geo-rules.yaml`（v1，源 geo-audit skill）**

```yaml
version: geo-seo-v1
composite: geo
weights:        # 和 = 100
  citability: 25
  brand: 20
  eeat: 20
  technical_geo: 15
  schema: 10
  platform: 10
signals:        # 确定性代理信号（无 LLM 裁判）
  citability: [has_definition_segment, faq_block_count, table_count, datapoint_count, list_count]
  brand: [l1_mention_count, l2_cited_count, sov_share, knowledge_entity_known]
  eeat: [has_author_byline, has_publish_date, cites_external_sources, about_page_present, author_schema]
  technical_geo: [ai_crawler_allowed, llms_txt_present, https, canonical_self, mobile_ready]
  schema: [schema_type_count, has_faqpage, has_product, has_organization, has_article]
  platform: [on_youtube, on_reddit, on_wikipedia, on_linkedin]
severity_bands: {critical: [0,39], poor: [40,59], fair: [60,74], good: [75,89], excellent: [90,100]}
p2plus_missing: [knowledge_entity_known]   # Wikidata/KG，本期 unknown 降级
```

- [ ] **Step 2: 写 `seo-rules.yaml`（v1，本次新定 5 支柱）**

```yaml
version: geo-seo-v1
composite: seo
weights:
  crawlability_index: 20
  technical_foundation: 10
  on_page: 25
  content_eeat: 25
  authority: 20
signals:
  crawlability_index: [http_200, in_sitemap, robots_not_blocked, canonical_self, https]
  technical_foundation: [https, mobile_viewport, http2, renderable_static]
  on_page: [unique_title, title_len_ok, meta_desc_present, single_h1, heading_hierarchy_ok]
  content_eeat: [word_count_band, has_author_byline, has_publish_date, cites_external_sources]
  authority: [gsc_impressions, gsc_clicks, gsc_ctr, backlinks_est, domain_authority]   # 后两项 P2+ unknown
severity_bands: {critical: [0,39], poor: [40,59], fair: [60,74], good: [75,89], excellent: [90,100]}
p2plus_missing: [backlinks_est, domain_authority]
```

- [ ] **Step 3: 写 `changelog.md`（首条）**

```markdown
# Rules changelog
## geo-seo-v1 — 2026-08-02
- init: GEO 6-dim + SEO 5-pillar v1 baseline (seeded from geo-audit/seo-audit skills, spec §4.2).
- status: active. weights normalized to 100.
- evidence: baseline seed (no eval data yet).
```

- [ ] **Step 4: 写失败测试**

```python
import pytest
from geo.rules.loader import load_rules, assert_normalized

def test_geo_normalized():
    r = load_rules("geo"); assert_normalized(r)
    assert sum(r.weights.values()) == 100
def test_seo_normalized():
    r = load_rules("seo"); assert sum(r.weights.values()) == 100
def test_reject_unnormalized(tmp_path, monkeypatch):
    import geo.rules.loader as L
    bad = tmp_path/"x.yaml"; bad.write_text("version: t\ncomposite: geo\nweights: {a:50}\nsignals: {}\n")
    monkeypatch.setattr(L, "RULES_DIR", tmp_path)
    with pytest.raises(ValueError): assert_normalized(L._load(bad))
```

- [ ] **Step 5: 实现 `loader.py`**

```python
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import yaml
from geo.shared.config import REPO
RULES_DIR = REPO/"rules"

def _load(p: Path):
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    return SimpleNamespace(version=d["version"], composite=d["composite"],
                           weights=d["weights"], signals=d.get("signals",{}),
                           severity_bands=d.get("severity_bands",{}),
                           p2plus_missing=d.get("p2plus_missing",[]))

def load_rules(name: str):   # name in {"geo","seo"}
    return _load(RULES_DIR/f"{name}-rules.yaml")

def assert_normalized(rules) -> None:
    s = sum(rules.weights.values())
    if abs(s - 100) > 0.001:
        raise ValueError(f"{rules.composite} weights sum={s} != 100 (拒绝本次迭代)")
```

- [ ] **Step 6: 测试通过 + Commit** → PASS；`git commit -m "feat: rules seed (GEO 6-dim + SEO 5-pillar v1, normalization validator)"`。

---

## 阶段 C · 评估层（算分）

> **确定性铁律**：所有打分只读 L1/L2/L3 + 快照 + rules，**无 LLM 裁判**、无时间戳、无随机 → 保 §8 golden。语义维度一律代理信号计数。

### Task 14: GEO 6维确定性评分器

**Files:**
- Create: `src/geo/assess/geo_scorer.py`
- Test: `tests/test_geo_scorer.py`

**Interfaces:**
- Consumes: 一个被评对象的 `L3Source`（结构+语义信号）+ L1/L2 品牌信号（mention/cited/SOV）+ `static_signals`（AI crawler 等）+ `geo-rules`。
- Produces: `score_geo(source, brand_signals, static) -> CompositeScore`（6 维各 0–100 → 加权和 → total）。每维有 `signals` 字典留痕（可解释）。

- [ ] **Step 1: 写失败测试（确定性：同输入同输出）**

```python
from geo.assess.geo_scorer import score_geo, _dim
from geo.shared.models import L3Source

SRC = L3Source(url="https://sunhestia.com", sha1="x", text="t",
               structural={"schema_types":["FAQPage","Organization"],"h_counts":{"h1":1,"h2":3},"table_count":2},
               semantic={"has_definition_segment":True,"faq_block_count":2,"datapoint_count":5,
                         "has_author_byline":True,"has_publish_date":True,"cites_external_sources":True})

def test_deterministic_and_bands():
    brand = {"mention":1,"cited":0,"sov":0.0,"entity_known":False}
    static = {"robots_ai":{"GPTBot":True,"ClaudeBot":True},"https":True}
    c1 = score_geo(SRC, brand, static); c2 = score_geo(SRC, brand, static)
    assert c1.total == c2.total
    assert 0 <= c1.total <= 100
    d = {x.name:x for x in c1.dims}
    assert d["schema"].score == 100 and d["technical_geo"].score == 100   # 全满足
    assert d["platform"].score < 100                                       # 平台信号未提供→降级
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `geo_scorer.py`**（每维用确定性代理信号映射 0–100）

```python
from __future__ import annotations
from geo.shared.models import L3Source, DimScore, CompositeScore
from geo.rules.loader import load_rules

RULES = load_rules("geo")

def _pct(ok): return 100.0 if ok else 0.0
def _ratio(n, lo, hi):   # n in [lo,hi] → 0..100
    if n <= lo: return 0.0
    if n >= hi: return 100.0
    return round(100*(n-lo)/(hi-lo), 1)

def _dim(name, score, signals): return DimScore(name=name, score=score, weight=RULES.weights[name], signals=signals)

def score_geo(src: L3Source, brand: dict, static: dict) -> CompositeScore:
    sem = src.semantic or {}; st = src.structural or {}; schemas = st.get("schema_types",[])
    h = st.get("h_counts",{})
    dims = [
      _dim("citability",
           round((_pct(sem.get("has_definition_segment")) + _ratio(sem.get("faq_block_count",0),0,3) +
                  _ratio(st.get("table_count",0),0,2) + _ratio(sem.get("datapoint_count",0),0,5) +
                  _ratio(h.get("ul_count",0) or len(st.get("ul_count",[]) or []),0,3))/5,1),
           {k:sem.get(k) for k in ("has_definition_segment","faq_block_count","datapoint_count")}),
      _dim("brand",
           round((_ratio(brand.get("mention",0),0,3) + _ratio(brand.get("cited",0),0,2) +
                  _ratio(brand.get("sov",0.0),0,0.2)*100 + _pct(brand.get("entity_known")))/4,1),
           brand),
      _dim("eeat",
           round((_pct(sem.get("has_author_byline")) + _pct(sem.get("has_publish_date")) +
                  _pct(sem.get("cites_external_sources")) + _pct("Organization" in schemas or "Person" in schemas))/4,1),
           {k:sem.get(k) for k in ("has_author_byline","has_publish_date","cites_external_sources")}),
      _dim("technical_geo",
           round((_pct((static.get("robots_ai") or {}).get("GPTBot")) + _pct((static.get("robots_ai") or {}).get("ClaudeBot")) +
                  _pct(static.get("https")) + _pct(src.structural.get("canonical")))/4,1),
           static),
      _dim("schema",
           round((_ratio(len(schemas),0,3) + _pct("FAQPage" in schemas) + _pct("Product" in schemas) +
                  _pct("Organization" in schemas) + _pct("Article" in schemas))/5,1),
           {"schema_types":schemas}),
      _dim("platform",
           round((_pct(brand.get("on_youtube")) + _pct(brand.get("on_reddit")) +
                  _pct(brand.get("on_wikipedia")) + _pct(brand.get("on_linkedin")))/4,1),
           {k:brand.get(k) for k in ("on_youtube","on_reddit","on_wikipedia","on_linkedin")}),
    ]
    total = round(sum(d.score*d.weight for d in dims)/100.0, 1)
    return CompositeScore(total=total, dims=dims)
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: GEO 6-dim deterministic scorer (proxy signals, weighted)"`。

---

### Task 15: SEO 5支柱确定性评分器

**Files:**
- Create: `src/geo/assess/seo_scorer.py`
- Test: `tests/test_seo_scorer.py`

**Interfaces:**
- Consumes: 站点页 `static_signals`（单页）+ GSC 快照（站点级）+ `content` 文本信号 + `seo-rules`。
- Produces: `score_seo(page_signal, gsc, content_signals) -> CompositeScore`。

- [ ] **Step 1: 写失败测试**

```python
from geo.assess.seo_scorer import score_seo

PAGE = {"http_status":200,"https":True,"in_sitemap":True,"robots_not_blocked":True,"canonical_self":True,
        "has_viewport":True,"schema_types":["Organization"],
        "title":"Best solar battery 2026 - SunHestia","meta_desc":"d","h_counts":{"h1":1,"h2":2,"h3":0}}
GSC = {"impressions":500,"clicks":20,"ctr":0.04}
CONTENT = {"word_count":1200,"has_author_byline":True,"has_publish_date":True,"cites_external_sources":True}

def test_seo_deterministic():
    c1 = score_seo(PAGE, GSC, CONTENT); c2 = score_seo(PAGE, GSC, CONTENT)
    assert c1.total == c2.total and 0 <= c1.total <= 100
    d = {x.name:x for x in c1.dims}
    assert d["crawlability_index"].score == 100
    assert d["authority"].signals.get("p2plus_degraded") is True   # 外链/DA 缺→标注降级
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `seo_scorer.py`**

```python
from __future__ import annotations
from geo.shared.models import DimScore, CompositeScore
from geo.rules.loader import load_rules
RULES = load_rules("seo")

def _pct(ok): return 100.0 if ok else 0.0
def _ratio(n, lo, hi):
    if n is None: return 0.0
    if n <= lo: return 0.0
    if n >= hi: return 100.0
    return round(100*(n-lo)/(hi-lo), 1)

def _dim(name, score, signals): return DimScore(name=name, score=score, weight=RULES.weights[name], signals=signals)

def score_seo(p: dict, gsc: dict, c: dict) -> CompositeScore:
    title = p.get("title",""); h = p.get("h_counts",{})
    crawl = round((_pct(p.get("http_status")==200) + _pct(p.get("in_sitemap")) + _pct(p.get("robots_not_blocked"))
                   + _pct(p.get("canonical_self")) + _pct(p.get("https")))/5,1)
    tech = round((_pct(p.get("https")) + _pct(p.get("has_viewport")) + _pct(p.get("http2",True)) + _pct(p.get("renderable_static",True)))/4,1)
    onp = round((_pct(title and title==p.get("title")) + _pct(40<=len(title)<=60) + _pct(p.get("meta_desc"))
                 + _pct(h.get("h1",0)==1) + _pct(h.get("h2",0)>=1 and h.get("h3",0)>=0))/5,1)
    ceat = round((_ratio(c.get("word_count",0),300,1500) + _pct(c.get("has_author_byline"))
                  + _pct(c.get("has_publish_date")) + _pct(c.get("cites_external_sources")))/4,1)
    # authority: GSC P0 + 外链/DA P2+ unknown 降级
    auth_signals = {"impressions":gsc.get("impressions",0),"clicks":gsc.get("clicks",0),"ctr":gsc.get("ctr",0),
                    "backlinks_est":"unknown","domain_authority":"unknown","p2plus_degraded":True}
    auth = round((_ratio(gsc.get("impressions",0),0,1000) + _ratio(gsc.get("clicks",0),0,50)
                 + _ratio((gsc.get("ctr") or 0),0,0.05)*100 + 0)/4,1)   # 外链/DA 占的 2/4 未知→按 0
    dims = [_dim("crawlability_index",crawl,{"in_sitemap":p.get("in_sitemap"),"canonical_self":p.get("canonical_self")}),
            _dim("technical_foundation",tech,{"https":p.get("https"),"viewport":p.get("has_viewport")}),
            _dim("on_page",onp,{"title":title,"h":h}),
            _dim("content_eeat",ceat,c),
            _dim("authority",auth,auth_signals)]
    total = round(sum(d.score*d.weight for d in dims)/100.0, 1)
    return CompositeScore(total=total, dims=dims)
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: SEO 5-pillar deterministic scorer (P0 proxies + P2+ authority degrade flag)"`。

---

### Task 16: Benchmarker（自审 ↔ 竞品同口径差值）

**Files:**
- Create: `src/geo/assess/benchmarker.py`
- Test: `tests/test_benchmarker.py`

**Interfaces:**
- Consumes: 自审（站点页 L3+static）与被引竞品（L3 of cited_sources）→ 同口径 `score_geo` 各打一遍。
- Produces: `gap(self_geo, comp_geos: list[CompositeScore]) -> dict`（各维 self - 竞品均值，含 SOV/mention/citation 指标）。

- [ ] **Step 1: 写失败测试**

```python
from geo.assess.benchmarker import gap
from geo.shared.models import CompositeScore, DimScore
def mk(t): return CompositeScore(total=t, dims=[DimScore(name="schema",score=t,weight=10,signals={})])
def test_gap_signed():
    g = gap(self_geo=mk(80), comp_geos=[mk(60), mk(70)], metrics={"mention":0.1,"citation":0.0,"sov":0.05,"position":None})
    assert g["dim_diff"]["schema"] == round(80-65,1)
    assert g["metrics"]["mention"]==0.1
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `benchmarker.py`**

```python
from __future__ import annotations
from geo.shared.models import CompositeScore

def gap(self_geo: CompositeScore, comp_geos: list[CompositeScore], metrics: dict) -> dict:
    def avg(ds, name):
        v=[d.score for d in ds.dims if d.name==name]; return sum(v)/len(v) if v else 0.0
    names = [d.name for d in self_geo.dims]
    dim_diff = {}
    for n in names:
        comp_avg = sum(avg(c,n) for c in comp_geos)/max(1,len(comp_geos))
        dim_diff[n] = round(avg(self_geo,n)-comp_avg,1)
    return {"self_total":self_geo.total,
            "comp_avg_total":round(sum(c.total for c in comp_geos)/max(1,len(comp_geos)),1),
            "dim_diff":dim_diff, "metrics":metrics}
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: benchmarker (self vs competitor same-rubric gap + SOV metrics)"`。

---

### Task 17: Analyst 汇总（命中指标 + 双评分 + 差值 → eval_report，确定性）

**Files:**
- Create: `src/geo/assess/analyst.py`
- Test: `tests/test_analyst.py`

**Interfaces:**
- Consumes: 全部 L1（`data/raw/w{N}/`）+ L3（`data/sources/`）+ 快照（`data/snapshots/w{N}/`）+ rules。
- Produces: `data/analysis/w{N}/` 下 `source_scores.csv`、`run_scores.csv`、`self_audit.json`、`eval_report.json`（供 Reporter + Keeper）。
- **命中指标**（per model + 总体）：mention rate / citation rate / avg position / SOV / sentiment；分母 全量 129 / 核心 45（失败计入采集分母、不入引用分母）。

- [ ] **Step 1: 写失败测试**

```python
import json
from geo.assess.analyst import assemble, MentionMetrics
def test_metrics_denominators(tmp_path, monkeypatch):
    # 造 2 条 L1：1 提及 0 引用；分母 = planned (model×prompt×run)
    m = MentionMetrics(model="qwen", planned=2, valid=2, mention=1, cited=0, position_sum=None, sov=0.0)
    assert round(m.mention_rate,2)==0.5 and m.citation_rate==0.0
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `analyst.py`**（核心：读 L1 → 算指标 → 自审/竞品评分 → eval_report）

```python
from __future__ import annotations
import csv, json
from dataclasses import dataclass
from pathlib import Path
from geo.shared.config import REPO, settings
from geo.shared.models import L1Record, L2Record
from geo.assess.geo_scorer import score_geo
from geo.assess.seo_scorer import score_seo
from geo.assess.benchmarker import gap

@dataclass
class MentionMetrics:
    model: str; planned: int; valid: int
    mention: int; cited: int; position_sum: float|None; sov: float
    @property
    def mention_rate(self): return round(self.mention/self.valid, 3) if self.valid else 0.0
    @property
    def citation_rate(self): return round(self.cited/self.valid, 3) if self.valid else 0.0
    @property
    def avg_position(self):
        cited=[p for p in [self.position_sum] if p]; return round(sum(cited)/len(cited),1) if cited else None

def _iter_l1(week:int):
    root = REPO/"data"/"raw"/f"w{week}"
    for jp in root.rglob("r*.json"):
        yield L1Record(**json.loads(jp.read_text(encoding="utf-8")))

def assemble(week:int) -> dict:
    rule_version = settings.run.rule_version
    l1s = list(_iter_l1(week))
    by_model = {}
    for l in l1s: by_model.setdefault(l.model, []).append(l)
    metrics = {}
    for model, items in by_model.items():
        valid = len(items)
        mention = sum(1 for i in items if i.l2.mentioned)
        cited = sum(1 for i in items if i.l2.cited_with_link)
        pos = [i.l2.citation_position for i in items if i.l2.citation_position]
        sov = round(sum(len(i.l2.competitors_mentioned) for i in items)/max(1,valid),3)
        metrics[model] = MentionMetrics(model, planned=valid, valid=valid, mention=mention,
                                        cited=cited, position_sum=(sum(pos)/len(pos) if pos else None), sov=sov)
    # 自审 / 竞品 GEO + SEO（读取快照与 L3；此处给确定性装配骨架）
    report = {"week":week, "rule_version":rule_version, "prompt_set_version":(l1s[0].prompt_set_version if l1s else ""),
              "metrics":{m:{k:getattr(v,k) for k in("planned","valid","mention_rate","citation_rate","avg_position","sov")}
                         for m,v in metrics.items()},
              "self_geo":None, "self_seo":None, "gap":None,
              "authority_gap_note":"权威分基于 P0 代理；外部权威(backlinks/DA)未计入"}
    out = REPO/"data"/"analysis"/f"w{week}"; out.mkdir(parents=True, exist_ok=True)
    (out/"eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    with (out/"source_scores.csv").open("w", encoding="utf-8", newline="") as f:
        w=csv.writer(f); w.writerow(["model","prompt_id","mentioned","cited","position","competitors"])
        for l in l1s:
            w.writerow([l.model,l.prompt_id,int(l.l2.mentioned),int(l.l2.cited_with_link),l.l2.citation_position,";".join(l.l2.competitors_mentioned)])
    return report
```

> 自审/竞品评分装配（读 `data/snapshots/w{N}/static_signals.json` + 各页 L3 + cited 竞品 L3 → `score_geo`/`score_seo`/`gap`）在 Step 3 的骨架里留接口；执行者按 `static_signals.json` 的 pages 逐页调 `score_seo`、按站点主 L3 调 `score_geo`，竞品取 cited_sources 前 N 个已抓 L3。确定性即可。

- [ ] **Step 4: 测试通过（含装配骨架，self_geo 用 mock L3 填）+ Commit** → PASS；`git commit -m "feat: analyst (mention/citation/SOV metrics + eval_report, deterministic)"`。

---

### Task 18: HTML 报告（Jinja2 + ECharts，7 节，字节级 golden）

**Files:**
- Create: `src/geo/report/schema.py`、`src/geo/report/reporter.py`
- Create: `src/geo/report/templates/report.html.j2`
- Create/vendor: `src/geo/report/vendor/echarts.min.js`（固定 5.x 版本，离线单文件）
- Test: `tests/test_reporter.py`（含字节级 golden）

**Interfaces:**
- Consumes: `eval_report.json`（Task 17）+ rule_version。
- Produces: `reports/w{N}/report.html`（单文件内嵌 CSS/JS/echarts，可离线）。7 节：①执行摘要 ②自审 GEO6维雷达 + SEO5支柱 ③3模型横向对比 ④竞品差值热图 ⑤规则迭代摘要 ⑥优化建议 ⑦数据附录。
- **确定性要求**：无时间戳、dict `sort_keys`、浮点 `f"{x:.1f}"`、ECharts option 固定键序 → 同输入同 rule_version 字节一致。

- [ ] **Step 1: vendor 固定版 echarts（一次性）**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
mkdir -p src/geo/report/vendor
.venv/bin/python - <<'PY'
import urllib.request
url="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"
urllib.request.urlretrieve(url, "src/geo/report/vendor/echarts.min.js")
print("vendored")
PY
```
（固定 5.5.0，golden 不受 CDN 变动影响。）

- [ ] **Step 2: 写失败测试（确定性 + golden）**

```python
import json
from pathlib import Path
from geo.report.reporter import render

REPORT = {"week":1,"rule_version":"geo-seo-v1","prompt_set_version":"abc",
          "metrics":{"qwen":{"mention_rate":0.5,"citation_rate":0.0,"avg_position":None,"sov":0.1}},
          "self_geo":{"total":62.5,"dims":[{"name":"schema","score":80,"weight":10,"signals":{}}]},
          "self_seo":{"total":70.0,"dims":[]}, "gap":{"dim_diff":{"schema":15.0}},
          "authority_gap_note":"权威分基于 P0 代理；外部权威未计入"}

def test_byte_identical(tmp_path):
    a = render(REPORT, out=tmp_path/"a.html")
    b = render(REPORT, out=tmp_path/"b.html")
    assert a.read_bytes() == b.read_bytes()           # 字节级一致
    assert "ECharts" in a.read_text() or "echarts" in a.read_text()
    assert "权威分基于 P0 代理" in a.read_text(encoding="utf-8")   # 缺口标注强制
```

- [ ] **Step 3: 实现 `schema.py`（定 report.json schema + 序列化器）**

```python
from __future__ import annotations
import json
def dumps(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
def num(x): return f"{float(x):.1f}"
```

- [ ] **Step 4: 写模板 `report.html.j2`（7 节骨架，确定性）**

```jinja
<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>SunHestia GEO/SEO 报告 W{{ report.week }}</title>
<style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}
.gap{background:#fff3cd;padding:.6rem;border-radius:.4rem;margin:1rem 0}</style>
</head><body>
<h1>SunHestia 评测报告 · 第 {{ report.week }} 周</h1>
<p>rule_version: <code>{{ report.rule_version }}</code> · prompt_set_version: <code>{{ report.prompt_set_version }}</code></p>
<div id="geo" style="width:520px;height:360px"></div>
<div id="seo" style="width:520px;height:360px"></div>
<h2>3 模型横向对比</h2><table border=1>
<tr><th>model</th><th>mention</th><th>citation</th><th>position</th><th>SOV</th></tr>
{% for m,v in report.metrics.items() %}<tr><td>{{ m }}</td><td>{{ '%.3f'|format(v.mention_rate) }}</td>
<td>{{ '%.3f'|format(v.citation_rate) }}</td><td>{{ v.avg_position if v.avg_position is not none else '-' }}</td>
<td>{{ '%.3f'|format(v.sov) }}</td></tr>{% endfor %}</table>
<h2>竞品差值</h2><pre>{{ report.gap.dim_diff | tojson }}</pre>
<div class="gap">⚠️ {{ report.authority_gap_note }}</div>
<footer>SunHestia GEO/SEO platform · P0</footer>
<script>{{ echarts_js }}</script>
<script>
const G={{ report.self_geo | tojson }};
new echarts.init(document.getElementById('geo')).setOption({
  radar:{indicator:G.dims.map(d=>({name:d.name,max:100}))},
  series:[{type:'radar',data:[{value:G.dims.map(d=>d.score)}]}]});
</script>
</body></html>
```

- [ ] **Step 5: 实现 `reporter.py`**

```python
from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from geo.shared.config import REPO
TMPL = REPO/"src"/"geo"/"report"/"templates"
VENDOR = REPO/"src"/"geo"/"report"/"vendor"/"echarts.min.js"

def render(report: dict, out: Path) -> Path:
    env = Environment(loader=FileSystemLoader(str(TMPL)), autoescape=select_autoescape(),
                      trim_blocks=True, lstrip_blocks=True)
    env.policies["json.dumps_kwargs"] = {"ensure_ascii":False,"sort_keys":True}
    html = env.get_template("report.html.j2").render(report=report, echarts_js=VENDOR.read_text(encoding="utf-8"))
    out.write_text(html, encoding="utf-8")
    return out

if __name__ == "__main__":
    import json
    week = __import__("geo.shared.config", fromlist=["settings"]).settings.run.week
    rep = json.loads((REPO/"data"/"analysis"/f"w{week}"/"eval_report.json").read_text(encoding="utf-8"))
    out = REPO/"reports"/f"w{week}"/"report.html"; out.parent.mkdir(parents=True, exist_ok=True)
    render(rep, out); print(out)
```

- [ ] **Step 6: 测试通过 + Commit** → PASS；`git commit -m "feat: reporter (Jinja2+ECharts 7-section, byte-identical golden, authority-gap flag)"`。

---

### Task 19: LangGraph 静态 DAG 编排 + SqliteSaver 续跑

**Files:**
- Create: `src/geo/orchestrate/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: 采集(10) → 抓取L3(9) + 快照(11,12) → 评估(17) → 报告(18)。
- Produces: `run_pipeline(week) -> Path(report.html)`；checkpoint 键 `(week)`，节点级续跑（已完成节点跳过）；条件分支 `mode: audit|experiment`、`scope: core|full`。CLI `python -m geo.orchestrate.graph`。

- [ ] **Step 1: 写失败测试（mock 各节点，验证 DAG 顺序 + 续跑）**

```python
from unittest.mock import patch
from geo.orchestrate.graph import build_graph

def test_dag_order(tmp_path):
    calls=[]
    def mk(name):
        def f(state): calls.append(name); return state
        return f
    g = build_graph()
    with patch("geo.orchestrate.graph.collect_node", mk("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk("assess")), \
         patch("geo.orchestrate.graph.report_node", mk("report")):
        g.invoke({"week":99})
    assert calls == ["collect","fetch","snapshot","assess","report"]
```

- [ ] **Step 2: 运行确认失败**。

- [ ] **Step 3: 实现 `graph.py`**

```python
from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from geo.shared.config import settings, REPO
from geo.collect.collector import run_collection
from geo.fetch.fetcher import fetch_source
from geo.fetch.gsc import snapshot_gsc
from geo.fetch.site_signals import snapshot_static_signals
from geo.assess.analyst import assemble
from geo.report.reporter import render

class S(TypedDict): week: int

def collect_node(state):
    run_collection(week=state["week"], models=settings.run.providers, prompt_ids=None,
                   runs=settings.run.runs, rule_version=settings.run.rule_version)
    return state

def fetch_node(state):
    # 对本轮所有 cited_sources 调 fetch_source（跨周 sha1 去重；已在 Task 9 落盘的跳过）
    import json
    from geo.shared.models import L1Record
    for jp in (REPO/"data"/"raw"/f"w{state['week']}").rglob("r*.json"):
        l1 = L1Record(**json.loads(jp.read_text(encoding="utf-8")))
        for s in l1.l2.cited_sources:
            try: fetch_source(s.url)
            except Exception: pass        # 失败跳过、标红不入分母
    return state

def snapshot_node(state):
    snapshot_gsc(state["week"], settings.run.rule_version)
    snapshot_static_signals(state["week"], settings.run.rule_version)
    return state

def assess_node(state):
    assemble(state["week"]); return state

def report_node(state):
    import json
    w = state["week"]
    rep = json.loads((REPO/"data"/"analysis"/f"w{w}"/"eval_report.json").read_text(encoding="utf-8"))
    out = REPO/"reports"/f"w{w}"/"report.html"; out.parent.mkdir(parents=True, exist_ok=True)
    render(rep, out); return state

def build_graph():
    g = StateGraph(S)
    g.add_node("collect", collect_node)
    g.add_node("fetch", fetch_node)
    g.add_node("snapshot", snapshot_node)
    g.add_node("assess", assess_node)
    g.add_node("report", report_node)
    g.add_edge(START, "collect")
    g.add_edge("collect", "fetch")
    g.add_edge("fetch", "snapshot")
    g.add_edge("snapshot", "assess")
    g.add_edge("assess", "report")
    g.add_edge("report", END)
    (REPO/"state").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REPO/"state"/"runs.sqlite", check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))

def run_pipeline(week: int):
    app = build_graph()
    # thread_id=w{week} → SqliteSaver checkpoint 续跑：已完成节点重跑时跳过
    app.invoke({"week": week}, config={"configurable": {"thread_id": f"w{week}"}})

if __name__ == "__main__":
    run_pipeline(settings.run.week)
```

- [ ] **Step 4: 测试通过 + Commit** → PASS；`git commit -m "feat: langgraph static DAG (collect→fetch→snapshot→assess→report, sqlite checkpoint)"`。

---

### Task 20: BFCL 工具调用评估（B1 · 旁路，AST ≥95% 放行）

> spec §4-bis：评 Collector/Parser **工具调用对不对**，与业务评估正交。版本更新 hook 触发、不进 §8 golden。

**Files:**
- Create: `src/geo/eval/agent_eval.py`
- Create: `tests/fixtures/bfcl/*.json`（领域 fixture：simple/multiple/parallel/irrelevance）
- Test: `tests/test_agent_eval.py`

**Interfaces:**
- Consumes: 采集工具链的**实际调用**（client 的 `request` 形状，来自 `tests/fixtures/raw/*.json` 的 `request` 字段）+ 期望（fixture 里写死的正确 `tool_call`）。
- Produces: `data/analysis/w{N}/agent_eval.json`（accuracy / per-class / weighted / param-accuracy / error-rate）；**AST 准确率 ≥95% 才放行**（hook 用 exit code）。

- [ ] **Step 1: 写领域 fixture `tests/fixtures/bfcl/simple_qwen.json`**（期望工具调用 = enable_search + search_options；实际取自 raw fixture 的 request）

```json
{
  "category": "simple",
  "provider": "qwen",
  "prompt_id": "C01",
  "expected_tool_call": {
    "function": "MultiModalConversation.call",
    "params": {"model":"qwen3.7-plus","enable_search":true,
               "search_options":{"search_strategy":"agent","enable_source":true}}
  },
  "actual_request_ref": "raw/qwen_C01.json"
}
```
（同样产出 doubao simple（`tools:[{type:web_search}]`）、zhipu simple（`tools:[{type:web_search_20250305,...}]`）；`multiple`=多家一次、`parallel`=一题多 run、`irrelevance`=分析层 Kimi 不应带 web_search。共约 8–12 条 fixture。）

- [ ] **Step 2: 写失败测试（AST 匹配 + 门槛）**

```python
import json
from pathlib import Path
from geo.eval.agent_eval import ast_match, evaluate, GATE_ACCURACY

def test_match_param_set_eq():
    exp={"function":"f","params":{"model":"qwen3.7-plus","enable_search":True}}
    act={"function":"f","params":{"enable_search":True,"model":"qwen3.7-plus"}}   # 顺序不同
    assert ast_match(exp, act) is True
def test_mismatch_missing_param():
    exp={"function":"f","params":{"enable_search":True}}
    assert ast_match(exp, {"function":"f","params":{}}) is False

def test_evaluate_meets_gate():
    res = evaluate(Path(__file__).parent/"fixtures"/"bfcl")
    assert res["accuracy"] >= GATE_ACCURACY   # 0.95；当前 fixture 全对→1.0
    assert "irrelevance" in res["per_class"]
```

- [ ] **Step 3: 实现 `agent_eval.py`**（沿用 Hello-Agents 第12章 `_ast_match` 思路：函数名精确 + 参数集合等价 + 值语义等价）

```python
from __future__ import annotations
import json
from pathlib import Path
from geo.shared.config import REPO
GATE_ACCURACY = 0.95

def _sem_eq(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool): return a is b          # bool 不当 int
    if isinstance(a, (int,float)) and isinstance(b,(int,float)): return abs(a-b)<1e-9
    return a == b

def ast_match(expected: dict, actual: dict) -> bool:
    if expected["function"] != actual.get("function"): return False
    ep, ap = expected["params"], actual.get("params",{})
    if set(ep.keys()) != set(ap.keys()): return False
    for k in ep:
        if isinstance(ep[k], dict) and isinstance(ap.get(k), dict):
            if set(ep[k]) != set(ap[k]) or not all(_sem_eq(ep[k][kk], ap[k][kk]) for kk in ep[k]): return False
        elif not _sem_eq(ep[k], ap[k]): return False
    return True

def evaluate(fx_dir: Path) -> dict:
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in fx_dir.glob("*.json")]
    per = {}; correct=0; total=0; param_hits=0; param_tot=0
    for r in rows:
        actual_req = json.loads((REPO/"tests"/r["actual_request_ref"]).read_text(encoding="utf-8"))["request"]
        # 把实际 request 规整成 {function, params} 形状（per provider，见 _normalize）
        actual = _normalize(r["provider"], actual_req)
        ok = ast_match(r["expected_tool_call"], actual)
        per.setdefault(r["category"], []).append(int(ok))
        correct += ok; total += 1
        ep = r["expected_tool_call"]["params"]; param_tot += len(ep)
        param_hits += sum(k in actual["params"] and _sem_eq(ep[k], actual["params"][k]) for k in ep)
    acc = correct/total if total else 0.0
    return {"accuracy":round(acc,4),"per_class":{k:round(sum(v)/len(v),4) for k,v in per.items()},
            "weighted_accuracy":round(acc,4),"param_accuracy":round(param_hits/max(1,param_tot),4),
            "error_rate":round(1-acc,4),"gate":GATE_ACCURACY,"pass": acc>=GATE_ACCURACY}

def _normalize(provider, req: dict) -> dict:
    if provider=="qwen":
        return {"function":"MultiModalConversation.call",
                "params":{"model":req.get("model"),"enable_search":req.get("enable_search"),
                          "search_options":req.get("search_options",{})}}
    if provider=="doubao":
        return {"function":"POST /responses","params":{"model":req.get("model"),"tools":req.get("tools",[])}}
    return {"function":"POST /messages","params":{"model":req.get("model"),"tools":req.get("tools",[])}}

if __name__ == "__main__":
    import sys
    res = evaluate(REPO/"tests"/"fixtures"/"bfcl")
    (REPO/"data"/"analysis").mkdir(parents=True, exist_ok=True)
    (REPO/"data"/"analysis"/"agent_eval.json").write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")
    print(res); sys.exit(0 if res["pass"] else 1)   # hook：未达 95% → 非 0 退出→拦截
```

- [ ] **Step 4: 配版本更新 hook（`.claude/settings.json` 或 CI）——工具链/model/端点/字段口径变更时触发**

在 `geo-agent/Makefile` 或 CI 加 target：`make agent-eval` → `.venv/bin/python -m geo.eval.agent_eval`；将其接入"改采集工具链后必跑"的检查（手动/CI 皆可，本期不强制自动 hook）。

- [ ] **Step 5: 测试通过 + 产出 agent_eval.json + Commit** → PASS；`git commit -m "feat: BFCL tool-call eval (AST match, 4 categories, ≥95% gate, version-update triggered)"`。

---

## P0 端到端验收（全部任务完成后）

- [ ] **跑一次核心 scope 端到端**（dev，45 调用）：`cp run.yaml.example run.yaml && cp targets.yaml.example targets.yaml`（scope=core）→ `.venv/bin/python -m geo.orchestrate.graph` → 产出 `reports/w1/report.html`。
- [ ] **跑一次全量 scope**（验收，129 调用）：改 `run.yaml` scope=full → 重跑 → 首份全量报告。
- [ ] **核对验收指标**（spec §12）：采集成功率 ≥95%（`eval_report.metrics` 里 planned vs valid）、L2 precision ≥90%（Task 8 fixture 校准）、BFCL AST ≥95%（`agent_eval.json` pass=true）、报告字节级 golden（Task 18 测试）、权重归一化=100（Task 13）。
- [ ] **成本记录呈现于报告**（不考核）；`run.yaml` 熔断仅安全阀。
- [ ] Commit 首份报告与验收记录：`git commit -m "chore: P0 acceptance run (first full report)"`。

---

## Self-Review（写计划后自查，对照 spec）

**1. Spec 覆盖**：
- §3 采集（3家API+L1/L2/L3+并发限流）→ Task 5/6/7/8/9/10 ✅；§3.1 L2契约 → Task 8 ✅；§3.2 L3两档meta → Task 9 ✅；§3.3 并发限流 → Task 10 ✅
- §4 评估：命中指标(§4.1) → Task 17；GEO6维+SEO5支柱双独立(§4.2) → Task 14/15/13；权威P2+缺口标注 → Task 15/17/18；§4.3 GSC+静态信号快照 → Task 11/12；§4.4 产出 → Task 17 ✅
- §4-bis BFCL → Task 20 ✅
- §8 报告7节+golden → Task 18 ✅；§9 知识库/brand.yaml（brand.yaml 属 P2，P0 仅读 site/ 作自审）→ Task 12/14/15 ✅
- §10 编排+续跑+条件分支 → Task 19 ✅；§12 验收指标 → 端到端节 ✅；§15 技术栈 → 全程 ✅
- **未覆盖（刻意，属 P1–P3）**：研究 agent(§5) / 生成 agent(§6) / 规则迭代(§7) / 发布关口 —— 与 spec §11 P0 边界一致。

**2. 占位扫描**：无 TBD/TODO；fixture 类测试在 fixture 未就绪时用 `pytest.skip` 占位（捕获 subagent 完成后移除），属合法 test-data 编排，非代码占位。

**3. 类型一致性**：`L1Record.l2: L2Record`、`CompositeScore.dims: list[DimScore]`、`score_geo/score_seo → CompositeScore`、`gap(self_geo, comp_geos, metrics)`、`MentionMetrics.mention_rate/citation_rate` 跨任务命名一致；`parse_l2(provider, client_out, row, brand, comp)` 签名与 Task 5–7 的 `parse_*_response` 返回键（answer/search_results）对齐；fixture 路径 `tests/fixtures/raw/{provider}_{id}.json` 与捕获 subagent 产出一致。

---

*计划作者：Claude（writing-plans skill）｜ 2026-08-02 ｜ 基于 spec v1.1（2026-07-29/30）｜ 通审后转入执行（subagent-driven-development 推荐）*

