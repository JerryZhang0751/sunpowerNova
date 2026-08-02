# MVP Foundation (key-free) Implementation Plan — Plan 1 of 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the key-free foundation of the geo-agent platform — project setup, config/secrets loading, canonical data models, the L2 citation parser, and the source fetcher — so W1 work starts immediately without any API keys.

**Architecture:** A Python package `geo-agent/geo_agent/` with focused modules (config, models, collector/l2_parser, fetcher). Pydantic v2 for data contracts, pytest for TDD, httpx+trafilatura for fetching. This plan produces the data-ingestion layer that later plans (Collector, Analyst, Reporter, DAG) build on. Nothing here calls a paid LLM API, so it is fully runnable/testable today.

**Tech Stack:** Python 3.11, pydantic v2, pyyaml, python-dotenv, httpx, trafilatura, beautifulsoup4, pytest.

## Global Constraints

(From PRD v4 — every task implicitly includes these.)
- Python ≥ 3.11.
- Secrets live in `geo-agent/.env` (gitignored) — never hardcode, never commit. `.gitignore` already covers `.env`, `gsc-nova-*.json`, `data/`, `state/`, `reports/`, `*.sqlite`.
- L3 stores **text + meta only** — never raw.html.
- Rules are a **static snapshot**; every stored record carries `rule_snapshot_version` (default `"v1"`) for reproducibility.
- The **prompt set is a frozen control variable** (`input/prompts.csv`); every stored record carries `prompt_set_version` — a content hash computed by `load_prompts()`. Same status as `rule_snapshot_version`: any drift in the prompt set changes the version, so W1↔W7 citation deltas stay attributable to GEO levers, not to "the questions changed." Auto-generation of prompts is Post-MVP (PRD §3.2); MVP loads a user-provided, frozen CSV.
- Brand detection is literal: `mentioned` = "SunHestia"/"sunhestia.com" appears; `cited_with_link` = a source URL matches `sunhestia.(com|pages.dev)`.
- Provider citation field paths below are per official docs; **verified against real responses in Plan 2 (M0)** once keys arrive — the parser exposes them in one place so adjustment is a one-line change.

## Scope of this plan (and what comes after)

- **Plan 1 (this):** setup, config, models, L2 parser, fetcher, **prompt-set loader (frozen input + content version)** — key-free.
- **Plan 2:** Collector (3 official APIs, native search, stream) + L2 calibration on real responses — **needs the 4 keys**.
- **Plan 3:** Analyst (Kimi) + Benchmarker + deterministic Recommender + Reporter template — needs Kimi key.
- **Plan 4:** LangGraph static DAG + checkpoint/resume + acceptance-metric instrumentation + end-to-end.

---

## File Structure

```
geo-agent/
├─ pyproject.toml                      # deps + pytest config (Task 0)
├─ .gitignore                          # exists
├─ .env                                # exists (secrets)
├─ geo_agent/
│  ├─ __init__.py
│  ├─ config.py                        # Task 1: load .env + yaml inputs
│  ├─ models.py                        # Task 2: L1/L2/L3 pydantic models
│  ├─ collector/
│  │  ├─ __init__.py
│  │  └─ l2_parser.py                  # Task 3: citation parsing
│  ├─ fetcher.py                       # Task 4: source → L3 text+meta
│  └─ prompts.py                       # Task 5: load input/prompts.csv + content-version freeze
└─ tests/
   ├─ __init__.py
   ├─ fixtures/                        # Task 3: sample provider responses
   ├─ test_config.py
   ├─ test_models.py
   ├─ test_l2_parser.py
   ├─ test_fetcher.py
   └─ test_prompts.py
```

---

### Task 0: Project setup (git, deps, package skeleton)

**Files:**
- Create: `pyproject.toml`
- Create: `geo_agent/__init__.py`, `geo_agent/collector/__init__.py`, `tests/__init__.py`
- Create: root `.gitignore` (project root, not geo-agent/)

**Interfaces:** Produces an importable `geo_agent` package and a runnable `pytest`.

- [ ] **Step 1: Initialize git at project root**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git init
```

- [ ] **Step 2: Create root `.gitignore`**

```gitignore
# secrets — never commit
geo-agent/.env
geo-agent/gsc-nova-*.json
geo-agent/*-service-account*.json

# geo-agent runtime
geo-agent/data/
geo-agent/state/
geo-agent/reports/
geo-agent/__pycache__/
*.pyc
*.sqlite

# existing project artifacts
site/node_modules/
site/dist/
.idea/
__pycache__/
```

- [ ] **Step 3: Create `geo-agent/pyproject.toml`**

```toml
[project]
name = "geo-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "httpx>=0.27",
  "pydantic>=2.6",
  "pyyaml>=6.0",
  "python-dotenv>=1.0",
  "trafilatura>=1.12",
  "beautifulsoup4>=4.12",
  "jinja2>=3.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 4: Create package markers**

`geo-agent/geo_agent/__init__.py`:
```python
"""SunHestia GEO multi-agent platform."""
```
`geo-agent/geo_agent/collector/__init__.py`: (empty)
`geo-agent/tests/__init__.py`: (empty)

- [ ] **Step 5: Install + verify pytest runs (no tests yet → 0 collected, exit 0)**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
pip install -e ".[dev]"
pytest -q
```
Expected: `no tests ran` (or 0 collected), exit code 0 — no import errors.

- [ ] **Step 6: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add .gitignore geo-agent/pyproject.toml geo-agent/geo_agent geo-agent/tests
git commit -m "chore: scaffold geo-agent package + pytest"
```

---

### Task 1: Config & secrets loader

**Files:**
- Create: `geo_agent/config.py`
- Create: `tests/test_config.py`
- Create: `geo-agent/config.yaml`, `geo-agent/input/run.yaml`, `geo-agent/input/targets.yaml`

**Interfaces:**
- Produces: `Settings` (api keys/base_urls from `.env`), `load_config()`, `load_run(path)`, `load_targets(path)`.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from geo_agent.config import Settings, load_run, load_targets

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-dash")
    monkeypatch.setenv("ARK_API_KEY", "sk-ark")
    monkeypatch.setenv("BIGMODEL_API_KEY", "sk-big")
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-moon")
    s = Settings()
    assert s.dashscope_api_key == "sk-dash"
    assert s.ark_api_key == "sk-ark"
    assert s.bigmodel_api_key == "sk-big"
    assert s.moonshot_api_key == "sk-moon"
    assert "dashscope.aliyuncs.com" in s.dashscope_base_url

def test_load_run_and_targets(tmp_path):
    run = tmp_path / "run.yaml"; run.write_text(
        "week: W1\nmode: experiment\nselected_models: [qwen, doubao, zhipu]\nscope: full\nruns_per_prompt: 1\nrule_snapshot_version: v1\n")
    tgt = tmp_path / "targets.yaml"; tgt.write_text(
        "experiment:\n  self: [https://sunhestia.com/]\n")
    r = load_run(run); t = load_targets(tgt)
    assert r.week == "W1" and r.mode == "experiment" and r.scope == "full"
    assert "https://sunhestia.com/" in t["experiment"]["self"]
```

- [ ] **Step 2: Run test → verify it fails**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
pytest tests/test_config.py -q
```
Expected: FAIL (`ModuleNotFoundError` / `ImportError`).

- [ ] **Step 3: Implement `geo_agent/config.py`**

```python
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / "geo-agent" / ".env"

@dataclass
class Settings:
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    ark_api_key: str = os.getenv("ARK_API_KEY", "")
    ark_base_url: str = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    bigmodel_api_key: str = os.getenv("BIGMODEL_API_KEY", "")
    bigmodel_base_url: str = os.getenv("BIGMODEL_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    moonshot_api_key: str = os.getenv("MOONSHOT_API_KEY", "")
    moonshot_base_url: str = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")

def _load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

@dataclass
class RunConfig:
    week: str
    mode: str  # experiment | audit
    selected_models: list[str]
    scope: str  # full | core
    runs_per_prompt: int
    rule_snapshot_version: str

def load_run(path) -> RunConfig:
    d = _load_yaml(path)
    return RunConfig(**d)

def load_targets(path) -> dict:
    return _load_yaml(path)

def load_config(path=PROJECT_ROOT / "geo-agent" / "config.yaml") -> dict:
    return _load_yaml(path)
```

- [ ] **Step 4: Create the yaml input files**

`geo-agent/input/run.yaml`:
```yaml
week: W1
mode: experiment
selected_models: [qwen, doubao, zhipu]
scope: full
runs_per_prompt: 1
rule_snapshot_version: v1
```
`geo-agent/input/targets.yaml`:
```yaml
experiment:
  self:
    - https://sunhestia.com/
    - https://sunhestia.com/products/
    - https://sunhestia.com/residential/
    - https://sunhestia.com/faq/
audit: {}
```
`geo-agent/config.yaml`:
```yaml
models:
  qwen:    {provider: dashscope, model: qwen-plus,   search: enable_search}
  doubao:  {provider: ark,       model: doubao-pro-32k, search: tool_web_search}
  zhipu:   {provider: bigmodel,  model: glm-4.6,    search: tool_web_search}
full_weeks: [W1, W4, W7]
core_subset_ids: [C01, C04, S01, S02, D01, D04, K01, K03, M01, M03, B01, B02, G01, G02, G05]
```
> Note: exact `model` ids are confirmed in Plan 2 (M0) against real APIs; the config is the single place to change them.

- [ ] **Step 5: Run test → verify pass**

```bash
pytest tests/test_config.py -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add geo-agent/geo_agent/config.py geo-agent/tests/test_config.py geo-agent/input geo-agent/config.yaml
git commit -m "feat(config): settings + run/targets loaders"
```

---

### Task 2: Canonical data models (L1/L2/L3)

**Files:**
- Create: `geo_agent/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `CitedSource`, `RunRecord` (L1+L2), `SourceSnapshot` (L3). Later tasks import these names verbatim.

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from datetime import datetime
from geo_agent.models import CitedSource, RunRecord, SourceSnapshot

def test_cited_source_defaults():
    s = CitedSource(position=1, url="https://x.com")
    assert s.extract_method == "structured"
    assert s.title is None

def test_run_record_roundtrip():
    r = RunRecord(
        week="W1", model="qwen", model_version="qwen-plus", prompt_id="C01", run=1,
        captured_at=datetime(2026,8,2), answer_text="See SunHestia at sunhestia.com",
        searched=True,
        cited_sources=[CitedSource(position=1, url="https://sunhestia.com/")],
    )
    r.mentioned = True
    r.cited_with_link = True
    r.citation_position = 1
    js = r.model_dump_json()
    r2 = RunRecord.model_validate_json(js)
    assert r2.mentioned is True and r2.cited_with_link is True
    assert r2.rule_snapshot_version == "v1"
    assert r2.prompt_set_version == "unversioned"  # default until load_prompts() stamps a real hash

def test_source_snapshot_no_raw_html():
    snap = SourceSnapshot(url="https://x.com", url_hash="abc123",
        title="t", text="body", http_status=200, content_type="text/html",
        fetched_at=datetime(2026,8,2))
    assert "raw_html" not in snap.model_fields
```

- [ ] **Step 2: Run → verify fail**

```bash
pytest tests/test_models.py -q
```
Expected: FAIL (import).

- [ ] **Step 3: Implement `geo_agent/models.py`**

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

class CitedSource(BaseModel):
    position: int
    url: str
    title: Optional[str] = None
    snippet: Optional[str] = None
    extract_method: Literal["structured", "inferred"] = "structured"

class RunRecord(BaseModel):
    # identity
    week: str
    model: Literal["qwen", "doubao", "zhipu"]
    model_version: str
    prompt_id: str
    run: int = 1
    captured_at: datetime
    # L1
    answer_text: str
    searched: bool
    # L2
    cited_sources: list[CitedSource] = Field(default_factory=list)
    mentioned: bool = False
    cited_with_link: bool = False
    citation_position: Optional[int] = None
    sentiment: Optional[Literal["pos", "neu", "neg"]] = None
    competitors_mentioned: list[str] = Field(default_factory=list)
    # provenance
    rule_snapshot_version: str = "v1"
    prompt_set_version: str = "unversioned"  # content hash from load_prompts(); "unversioned" until a real prompt set is loaded

class SourceSnapshot(BaseModel):
    url: str
    url_hash: str            # sha1[:12]
    title: Optional[str] = None
    text: Optional[str] = None   # trafilatura main text; raw.html intentionally NOT stored
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    fetched_at: datetime
    js_only: bool = False    # text empty / script-heavy → flagged, not scored
```

- [ ] **Step 4: Run → verify pass**

```bash
pytest tests/test_models.py -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add geo-agent/geo_agent/models.py geo-agent/tests/test_models.py
git commit -m "feat(models): L1/L2/L3 pydantic contracts"
```

---

### Task 3: L2 citation parser (per-provider + text fallback)

**Files:**
- Create: `geo_agent/collector/l2_parser.py`
- Create: `tests/fixtures/qwen_sample.json`, `tests/fixtures/doubao_sample.json`, `tests/fixtures/zhipu_sample.json`, `tests/fixtures/text_only.json`
- Create: `tests/test_l2_parser.py`

**Interfaces:**
- Produces: `parse_citations(provider, raw_response: dict, answer_text: str) -> ParseResult`, where `ParseResult` has `cited_sources: list[CitedSource]`, `mentioned: bool`, `cited_with_link: bool`.
- Consumes: `CitedSource` from Task 2.

- [ ] **Step 1: Create fixtures (sample provider responses, per docs)**

`tests/fixtures/qwen_sample.json` (DashScope `search_results`):
```json
{"choices":[{"message":{"content":"SunHestia offers LFP batteries. See sunhestia.com."}}],
 "search_results":[{"title":"SunHestia","url":"https://sunhestia.com/","snippet":"LFP home battery"}]}
```
`tests/fixtures/doubao_sample.json` (Ark web_search tool result):
```json
{"choices":[{"message":{"content":"Tesla Powerwall and sunhestia.com are options."}}],
 "search_results":[{"url":"https://www.tesla.com/powerwall","title":"Powerwall"}]}
```
`tests/fixtures/zhipu_sample.json` (BigModel web_search info):
```json
{"choices":[{"message":{"content":"sonnen and SunHestia serve Europe."}}],
 "web_search":[{"url":"https://sonnen.de","title":"sonnen"}]}
```
`tests/fixtures/text_only.json` (no structured citations → fallback):
```json
{"choices":[{"message":{"content":"Visit https://sunhestia.com/products/ today."}}]}
```

- [ ] **Step 2: Write the failing test**

`tests/test_l2_parser.py`:
```python
import json
from pathlib import Path
from geo_agent.collector.l2_parser import parse_citations

FIX = Path(__file__).parent / "fixtures"

def _load(name): return json.loads((FIX / name).read_text())

def test_qwen_structured_and_brand():
    r = parse_citations("qwen", _load("qwen_sample.json"),
                        "SunHestia offers LFP batteries. See sunhestia.com.")
    assert r.cited_sources[0].url == "https://sunhestia.com/"
    assert r.cited_sources[0].extract_method == "structured"
    assert r.mentioned is True and r.cited_with_link is True

def test_text_fallback_when_no_structured():
    r = parse_citations("qwen", _load("text_only.json"),
                        "Visit https://sunhestia.com/products/ today.")
    assert r.cited_sources[0].extract_method == "inferred"
    assert r.cited_with_link is True

def test_doubao_and_zhipu_parse():
    d = parse_citations("doubao", _load("doubao_sample.json"), "Tesla and sunhestia.com.")
    assert d.cited_sources[0].url == "https://www.tesla.com/powerwall"
    z = parse_citations("zhipu", _load("zhipu_sample.json"), "sonnen and SunHestia.")
    assert z.cited_sources[0].url == "https://sonnen.de"
    assert z.mentioned is True

def test_no_mention_when_absent():
    r = parse_citations("qwen", {"search_results": []}, "Tesla makes the Powerwall.")
    assert r.mentioned is False and r.cited_with_link is False and r.cited_sources == []
```

- [ ] **Step 3: Run → verify fail**

```bash
pytest tests/test_l2_parser.py -q
```
Expected: FAIL (import).

- [ ] **Step 4: Implement `geo_agent/collector/l2_parser.py`**

```python
from __future__ import annotations
import re
from dataclasses import dataclass
from ..models import CitedSource

URL_RE = re.compile(r"https?://[^\s\"'<>)\],]+")
BRAND_RE = re.compile(r"sunhestia", re.IGNORECASE)
BRAND_DOMAIN_RE = re.compile(r"sunhestia\.(com|pages\.dev)", re.IGNORECASE)

@dataclass
class ParseResult:
    cited_sources: list[CitedSource]
    mentioned: bool
    cited_with_link: bool

def _extract_urls(text: str) -> list[str]:
    seen, out = set(), []
    for m in URL_RE.findall(text):
        u = m.rstrip(".,);]").split("#")[0].split("?")[0]
        if u not in seen:
            seen.add(u); out.append(u)
    return out

def _structured(provider: str, data: dict) -> list[dict]:
    # One place to adjust field paths after seeing real responses (Plan 2 calibration).
    if provider == "qwen":
        return [{"url": r.get("url"), "title": r.get("title"), "snippet": r.get("snippet")}
                for r in (data.get("search_results") or [])]
    if provider == "doubao":
        return [{"url": r.get("url"), "title": r.get("title"), "snippet": r.get("snippet")}
                for r in (data.get("search_results") or [])]
    if provider == "zhipu":
        return [{"url": r.get("url"), "title": r.get("title"), "snippet": r.get("snippet")}
                for r in (data.get("web_search") or [])]
    return []

def parse_citations(provider: str, raw_response: dict, answer_text: str) -> ParseResult:
    raw = [r for r in _structured(provider, raw_response) if r.get("url")]
    if raw:
        sources = [CitedSource(position=i + 1, url=r["url"], title=r.get("title"),
                               snippet=r.get("snippet"), extract_method="structured")
                   for i, r in enumerate(raw)]
    else:
        sources = [CitedSource(position=i + 1, url=u, extract_method="inferred")
                   for i, u in enumerate(_extract_urls(answer_text))]
    mentioned = bool(BRAND_RE.search(answer_text))
    cited_with_link = any(BRAND_DOMAIN_RE.search(s.url) for s in sources)
    return ParseResult(cited_sources=sources, mentioned=mentioned, cited_with_link=cited_with_link)
```

- [ ] **Step 5: Run → verify pass**

```bash
pytest tests/test_l2_parser.py -q
```
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add geo-agent/geo_agent/collector geo-agent/tests/fixtures geo-agent/tests/test_l2_parser.py
git commit -m "feat(l2): per-provider citation parser + text fallback"
```

---

### Task 4: Source fetcher (URL → L3 text + meta)

**Files:**
- Create: `geo_agent/fetcher.py`
- Create: `tests/test_fetcher.py`

**Interfaces:**
- Produces: `fetch_url(url, http_client=None) -> SourceSnapshot`; `hash_url(url) -> str`.
- Consumes: `SourceSnapshot` from Task 2.

- [ ] **Step 1: Write the failing test** (mock httpx so no network)

`tests/test_fetcher.py`:
```python
from geo_agent.fetcher import fetch_url, hash_url

class FakeResp:
    status_code = 200
    headers = {"content-type": "text/html"}
    text = """<html><head><title>SunHestia</title></head>
      <body><article><h1>Your roof. Your power.</h1><p>LFP home batteries.</p></article></body></html>"""

class FakeClient:
    def get(self, url, **kw): return FakeResp()
    def close(self): pass

def test_hash_url_stable():
    assert hash_url("https://x.com/a") == hash_url("https://x.com/a")
    assert len(hash_url("https://x.com/a")) == 12

def test_fetch_extracts_text_and_meta():
    snap = fetch_url("https://sunhestia.com/", http_client=FakeClient())
    assert snap.http_status == 200
    assert "Your roof" in (snap.text or "")
    assert snap.js_only is False
    assert snap.url_hash == hash_url("https://sunhestia.com/")

def test_js_only_flagged_when_no_text():
    class JSOnly(FakeResp):
        text = "<html><body><div id='app'></div><script>render()</script></body></html>"
    class C(FakeClient):
        def get(self, url, **kw): return JSOnly()
    snap = fetch_url("https://app.example/", http_client=C())
    assert snap.js_only is True
```

- [ ] **Step 2: Run → verify fail**

```bash
pytest tests/test_fetcher.py -q
```
Expected: FAIL (import).

- [ ] **Step 3: Implement `geo_agent/fetcher.py`**

```python
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
import trafilatura
from .models import SourceSnapshot

def hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]

def _is_js_only(html: str, text: str) -> bool:
    if text and len(text.strip()) >= 80:
        return False
    # script-heavy + little extractable text => likely client-rendered
    low = html.lower()
    return ("<script" in low) and (low.count("<p") < 2)

def fetch_url(url: str, http_client=None, timeout: float = 30.0) -> SourceSnapshot:
    own = http_client is None
    client = http_client or __import__("httpx").Client(timeout=timeout, follow_redirects=True)
    try:
        resp = client.get(url)
        html = getattr(resp, "text", "") or ""
        text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
        return SourceSnapshot(
            url=url,
            url_hash=hash_url(url),
            title=trafilatura.extract(html, output_format="txt", with_metadata=True) or None,
            text=text or None,
            http_status=getattr(resp, "status_code", None),
            content_type=resp.headers.get("content-type") if hasattr(resp, "headers") else None,
            fetched_at=datetime.now(timezone.utc),
            js_only=_is_js_only(html, text),
        )
    finally:
        if own:
            client.close()
```
> Note: `title` extraction via `with_metadata=True` is a simplification; Plan 3 tunes it. The contract (text + meta, no raw.html, js_only flag) is what matters here.

- [ ] **Step 4: Run → verify pass**

```bash
pytest tests/test_fetcher.py -q
```
Expected: PASS (3 tests).

- [ ] **Step 5: Full suite green**

```bash
pytest -q
```
Expected: all tests PASS (config, models, l2_parser, fetcher).

- [ ] **Step 6: Commit**

```bash
git add geo-agent/geo_agent/fetcher.py geo-agent/tests/test_fetcher.py
git commit -m "feat(fetcher): URL → L3 text+meta, js_only flag, sha1 dedup key"
```

---

### Task 5: Prompt-set loader (frozen input + content-versioned freeze)

**Why this task:** The prompt set is a control variable as critical as the rules
snapshot — if the questions drift week to week, citation-rate deltas stop being
attributable to GEO levers. This task loads the user-provided `input/prompts.csv`
and exposes a content hash (`prompt_set_version`) so any drift is detectable. It
also carries the full/core scope selection so the DAG (Plan 4) can ask "which
prompts run this week?" in one call. Nothing here calls a paid API.

**Files:**
- Create: `geo_agent/prompts.py`
- Create: `tests/test_prompts.py`
- Create: `geo-agent/input/prompts.csv` (copy of `geo-measurements/prompts.csv`, the frozen 43-prompt set)
- Consumes: `RunRecord.prompt_set_version` from Task 2 (this task stamps the value via the Collector in Plan 2; it does **not** edit `models.py`).

**Interfaces:**
- Produces: `load_prompts(path=None) -> PromptSet`; `Prompt` (dataclass: `id, category, prompt, market, intent`); `PromptSet.prompts: list[Prompt]`, `PromptSet.version: str` (sha1[:12] of the canonical set), `PromptSet.select(*, week, full_weeks, core_ids) -> list[Prompt]`.
- Consumes: `RunRecord.prompt_set_version` (Task 2). **Contract for Plan 2 (Collector):** call `ps = load_prompts(...)`, then set `record.prompt_set_version = ps.version` on every `RunRecord` it emits.

- [ ] **Step 1: Write the failing tests**

`tests/test_prompts.py`:
```python
from geo_agent.prompts import load_prompts, PromptSet, Prompt

def _write(p, rows):
    p.write_text("id,category,prompt,market,intent\n" + "\n".join(rows) + "\n",
                 encoding="utf-8")

def test_load_parses_fields_and_types(tmp_path):
    f = tmp_path / "p.csv"
    _write(f, ["C01,category,What is the best home solar?,EU,product-category",
               "B01,brand,SunHestia solar reviews,EU,brand"])
    ps = load_prompts(f)
    assert len(ps.prompts) == 2
    assert isinstance(ps.prompts[0], Prompt)
    assert ps.prompts[0].id == "C01"
    assert ps.prompts[0].prompt == "What is the best home solar?"
    assert ps.prompts[0].market == "EU"

def test_version_is_stable_for_same_content(tmp_path):
    f1, f2 = tmp_path / "a.csv", tmp_path / "b.csv"
    _write(f1, ["C01,category,Q1,EU,x", "B01,brand,Q2,EU,y"])
    _write(f2, ["B01,brand,Q2,EU,y", "C01,category,Q1,EU,x"])  # row order swapped
    assert load_prompts(f1).version == load_prompts(f2).version
    assert len(load_prompts(f1).version) == 12

def test_version_changes_on_drift(tmp_path):
    base = tmp_path / "base.csv"; _write(base, ["C01,category,Q1,EU,x"])
    drift = tmp_path / "drift.csv"; _write(drift, ["C01,category,Q1 CHANGED,EU,x"])
    added = tmp_path / "added.csv"; _write(added, ["C01,category,Q1,EU,x", "C02,category,Q2,EU,x"])
    v = load_prompts(base).version
    assert load_prompts(drift).version != v   # text changed -> drift detected
    assert load_prompts(added).version != v   # prompt added  -> drift detected

def test_select_full_vs_core(tmp_path):
    f = tmp_path / "p.csv"
    _write(f, [f"{pid},cat,p{pid},EU,x" for pid in ["C01","C04","S01","M01","B01"]])
    ps = load_prompts(f)
    full = ps.select(week="W1", full_weeks=["W1","W4","W7"], core_ids=["C01","S01"])
    core = ps.select(week="W2", full_weeks=["W1","W4","W7"], core_ids=["C01","S01"])
    assert {p.id for p in full} == {"C01","C04","S01","M01","B01"}  # W1 is full
    assert {p.id for p in core} == {"C01","S01"}                    # W2 is core
```

- [ ] **Step 2: Run → verify fail**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
pytest tests/test_prompts.py -q
```
Expected: FAIL (`ModuleNotFoundError` / `ImportError`).

- [ ] **Step 3: Implement `geo_agent/prompts.py`**

```python
from __future__ import annotations
import csv, hashlib, json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPTS = PROJECT_ROOT / "geo-agent" / "input" / "prompts.csv"


@dataclass
class Prompt:
    id: str
    category: str
    prompt: str
    market: str
    intent: str


@dataclass
class PromptSet:
    prompts: list[Prompt]
    version: str

    def select(self, *, week: str, full_weeks: list[str],
               core_ids: list[str]) -> list[Prompt]:
        if week in full_weeks:
            return list(self.prompts)
        core = set(core_ids)
        return [p for p in self.prompts if p.id in core]


def _version(prompts: list[Prompt]) -> str:
    # Canonical: sorted by id, whole-row serialized. Any edit / add / remove
    # changes the hash, so prompt-set drift is always detectable.
    payload = [{"id": p.id, "category": p.category, "prompt": p.prompt,
                "market": p.market, "intent": p.intent}
               for p in sorted(prompts, key=lambda x: x.id)]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False,
                                   sort_keys=True).encode("utf-8")).hexdigest()[:12]


def load_prompts(path=None) -> PromptSet:
    p = Path(path) if path else DEFAULT_PROMPTS
    with p.open(newline="", encoding="utf-8") as f:
        prompts = [Prompt(id=r["id"], category=r["category"], prompt=r["prompt"],
                          market=r["market"], intent=r["intent"])
                   for r in csv.DictReader(f)]
    return PromptSet(prompts=prompts, version=_version(prompts))
```

- [ ] **Step 4: Verify the RunRecord handshake (no code change)**

`RunRecord.prompt_set_version` is declared in Task 2 (`= "unversioned"`). This
task does **not** edit `models.py`; it confirms the field exists and records the
Plan-2 contract:

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
python -c "from geo_agent.models import RunRecord as R; assert 'prompt_set_version' in R.model_fields and R.model_fields['prompt_set_version'].default=='unversioned'"
```
Expected: no output, exit 0. (If this fails, Task 2 has not run yet — run Task 2 first.)

- [ ] **Step 5: Create the frozen input `geo-agent/input/prompts.csv`**

Copy the existing experiment prompt set (43 prompts, schema `id,category,prompt,market,intent`):

```bash
cd "/Users/jerry/AiProject/sunpower nova"
mkdir -p geo-agent/input
cp geo-measurements/prompts.csv geo-agent/input/prompts.csv
```

Sanity-check the loader against the real file:

```bash
cd geo-agent
python -c "from geo_agent.prompts import load_prompts; ps=load_prompts(); print(len(ps.prompts), ps.version)"
```
Expected: `43 <12-char-hash>`.

- [ ] **Step 6: Run → verify pass**

```bash
pytest tests/test_prompts.py -q
```
Expected: PASS (4 tests).

- [ ] **Step 7: Full suite green**

```bash
pytest -q
```
Expected: all tests PASS (config, models, l2_parser, fetcher, prompts).

- [ ] **Step 8: Commit**

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git add geo-agent/geo_agent/prompts.py geo-agent/tests/test_prompts.py geo-agent/input/prompts.csv
git commit -m "feat(prompts): frozen prompt-set loader + content-versioned freeze"
```

---

## Self-Review (run after writing)

- **Spec coverage:** PRD §4.2 (L1/L2/L3) → Task 2; §4.4 (L2 contract, brand detection, structured+fallback) → Task 3; §4.2 L3 text-only + JS-only flag → Task 4; §4.1 inputs → Task 1; §3.2 prompt-set-as-control-variable → Task 5 (frozen CSV input + `prompt_set_version` content hash; auto-generation deferred). ✅ The acceptance criterion "parse-vs-human ≥90%" needs real fixtures → wired in Plan 2 (calibration); the parser interface and synthetic-fixture tests are in place here.
- **Placeholder scan:** provider field paths are documented-format assumptions with a single-point-of-change + a Plan 2 calibration task — not placeholders. Model ids are in `config.yaml` (one place). No TBD/TODO. ✅
- **Type consistency:** `CitedSource` / `RunRecord` / `SourceSnapshot` / `ParseResult` / `hash_url` / `fetch_url` / `parse_citations` / `load_run` / `load_targets` / `Settings` / `load_prompts` / `PromptSet` / `Prompt` — names match across tasks. `RunRecord.prompt_set_version` (Task 2) is the field `load_prompts().version` (Task 5) stamps via the Collector in Plan 2. ✅
