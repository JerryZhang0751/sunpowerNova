# P2 生成 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地闭环「生成」环节——brand.yaml 单一事实源 + Kimi K3 生成带 Schema JSON-LD 建议的官网内容草稿（确定性事实核验 + 人审三档 + 发布归档），全流程不自动发布。

**Architecture:** 对称 P1 `research/` 模式的新包 `src/geo/generate/`（brand/topics/kimi/validate/run 五模块）；确定性/LLM 切分——数字归属核验、playbook 解析、选题建议全确定性（golden 可测），Kimi 调用走可注入 `chat_fn` seam（mock 测试 + live 人审）；CLI `python3.11 -m geo.generate.run`。

**Tech Stack:** Python 3.11 / pytest（沿现有 `geo-agent/pyproject.toml` 依赖，无新增）/ Kimi K3（OpenAI 兼容 `settings.moonshot_*`）/ PyYAML。

**Spec:** `docs/superpowers/specs/2026-08-16-p2-generate-agent-design.md`（冲突以 spec 为准）

## Global Constraints

- 分支 `p2-generate-agent`（off `main`）；测试从 `geo-agent/` 目录用 `python3.11 -m pytest tests/<file> -v` 跑。
- Kimi 调用一律：`model="kimi-k3"`、`temperature=1`（强制）、`response_format={"type":"json_object"}`、`chat_fn(messages, tools=None, timeout=120) -> str` seam 可注入（照 `src/geo/research/kimi.py` 的 `_kimi_chat`）。
- 确定性纪律：本计划所有核验（数字归属/JSON-LD/banned/frontmatter）不得调 LLM。
- 生成绝不自动发布、绝不写 `site/`；只产 `content/drafts/`，归档到 `content/published/`。
- `knowledge/` 与 `content/` 不在 .gitignore——`knowledge/brand.yaml` 人审定稿后须 git commit（单一事实源入库）；`content/` 产物（drafts/published/reviews.jsonl）作为 ledger 也 commit。
- 所有用户可见输出/日志沿项目惯例：中文、诚实标注、不静默编造。
- 每个任务 TDD：先写失败测试→跑确认失败→最小实现→跑通过→commit。

---

### Task 1: 包脚手架 + brand 加载器 + slugify

**Files:**
- Create: `geo-agent/src/geo/generate/__init__.py`（空）
- Create: `geo-agent/src/geo/generate/brand.py`
- Create: `geo-agent/tests/fixtures/generate/knowledge/brand.yaml`
- Test: `geo-agent/tests/test_generate_brand.py`

**Interfaces:**
- Consumes: 无（首任务）
- Produces:
  - `load_brand(path: Path) -> dict` —— 解析 YAML，校验 `version: int >= 1` 且顶层键 `entity/products/faqs/glossary/banned` 齐全；不合法 raise `BrandError(msg)`
  - `class BrandError(Exception)`
  - `slugify(topic: str) -> str` —— 小写、非字母数字连字符折叠、去首尾连字符
  - fixture `tests/fixtures/generate/knowledge/brand.yaml`（后续 Task 2/7 复用）

- [ ] **Step 1: 写 fixture `tests/fixtures/generate/knowledge/brand.yaml`**

```yaml
version: 1
updated: 2026-08-16
entity:
  brand: SunHestia
  domain: sunhestia.com
  positioning: "Residential solar and storage for European homes"
products:
  - id: home-battery
    name: SunHestia Home Battery
    specs:
      chemistry: LiFePO4
      capacity_kwh: "5–15"
      warranty_years: 10
  - id: pv-module
    name: SunHestia Solar PV Modules
    specs:
      cell_type: monocrystalline
      power_w: "400–450"
      performance_guarantee_years: 25
faqs:
  - q: "What does a residential solar and storage system include?"
    a: "Typically rooftop solar panels, a hybrid inverter, and a home battery."
glossary:
  - term: self-consumption
    definition: "The share of your electricity use that is covered by solar produced on your own property."
  - term: LiFePO4
    definition: "Lithium iron phosphate battery chemistry — stable, long-lasting, cobalt-free."
banned: [no_pricing, no_savings_percentages]
competitors: [Tesla, Enphase, SolarEdge]
i18n: {}
```

- [ ] **Step 2: 写失败测试 `tests/test_generate_brand.py`**

```python
# tests/test_generate_brand.py
from pathlib import Path
import pytest
from geo.generate.brand import load_brand, BrandError, slugify

FIX = Path(__file__).parent / "fixtures" / "generate"
BRAND = FIX / "knowledge" / "brand.yaml"

def test_load_brand_valid():
    brand = load_brand(BRAND)
    assert brand["version"] == 1
    assert brand["products"][0]["id"] == "home-battery"
    assert "no_pricing" in brand["banned"]

def test_load_brand_missing_file():
    with pytest.raises(BrandError, match="brand.yaml 不存在"):
        load_brand(FIX / "knowledge" / "nope.yaml")

def test_load_brand_missing_top_keys(tmp_path):
    p = tmp_path / "brand.yaml"
    p.write_text("version: 1\nentity: {brand: SunHestia}\n", encoding="utf-8")
    with pytest.raises(BrandError, match="缺少顶层键"):
        load_brand(p)

def test_load_brand_bad_version(tmp_path):
    p = tmp_path / "brand.yaml"
    p.write_text("version: 0\nentity: {}\nproducts: []\nfaqs: []\nglossary: []\nbanned: []\n", encoding="utf-8")
    with pytest.raises(BrandError, match="version"):
        load_brand(p)

def test_slugify():
    assert slugify("How to Size a Home Battery?") == "how-to-size-a-home-battery"
    assert slugify("  LiFePO4  vs  NMC ") == "lifepo4-vs-nmc"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_brand.py -v`
Expected: FAIL（`ModuleNotFoundError: geo.generate`）

- [ ] **Step 4: 最小实现**

```python
# src/geo/generate/brand.py
from __future__ import annotations
import re
import yaml
from pathlib import Path

REQUIRED_KEYS = ("entity", "products", "faqs", "glossary", "banned")

class BrandError(Exception):
    pass

def load_brand(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise BrandError(f"brand.yaml 不存在: {path}；先运行 --bootstrap-brand")
    brand = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(brand.get("version"), int) or brand["version"] < 1:
        raise BrandError(f"brand.yaml version 非法: {brand.get('version')!r}")
    missing = [k for k in REQUIRED_KEYS if k not in brand]
    if missing:
        raise BrandError(f"brand.yaml 缺少顶层键: {missing}")
    return brand

def slugify(topic: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return s or "untitled"
```

`src/geo/generate/__init__.py` 建空文件。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_brand.py -v`
Expected: 5 PASS

- [ ] **Step 6: Commit**

```bash
git add geo-agent/src/geo/generate/ geo-agent/tests/test_generate_brand.py geo-agent/tests/fixtures/generate/
git commit -m "feat(generate): package scaffold + brand loader + slugify"
```

---

### Task 2: 数字 claim 提取 + validate_brand 校验器

**Files:**
- Create: `geo-agent/tests/fixtures/generate/site/src/pages/products.astro`（迷你抽取源）
- Create: `geo-agent/tests/fixtures/generate/site/src/pages/faq.astro`
- Modify: `geo-agent/src/geo/generate/brand.py`（追加）
- Test: `geo-agent/tests/test_generate_brand.py`（追加）

**Interfaces:**
- Consumes: Task 1 `load_brand`/fixture brand.yaml
- Produces（Task 3/7 依赖，签名精确）:
  - `parse_claims(text: str) -> list[tuple[frozenset[str], str]]` —— 从文本提取数字 claim `(数字集合, 单位)`；单位统一小写归一（years→year、watts→w）；范围 "5–15 kWh" → `({"5","15"}, "kwh")`
  - `brand_claims(brand: dict) -> list[tuple[frozenset[str], str]]` —— 遍历 entity/products[].specs/faqs/glossary 叶子的 `键: 值` 文本提取（键名含单位：`capacity_kwh`/`warranty_years`）
  - `claims_match(claim, inventory) -> bool` —— 子集语义：`claim.nums ⊆ inv.nums 且单位相等`
  - `validate_brand(brand: dict, sources_text: str) -> list[str]` —— 返回违规清单（空=通过）；查数字 claim 未在源页出现 + 产品名/术语未字面出现

- [ ] **Step 1: 写 site fixture 页面（迷你抽取源，含 brand.yaml 全部事实字面量）**

```astro
---
// tests/fixtures/generate/site/src/pages/products.astro（迷你；仅作抽取源，非真站点文件）
const products = ["SunHestia Home Battery", "SunHestia Solar PV Modules"];
---
<p>
  The SunHestia Home Battery is a LiFePO4 wall-mounted battery, modular from
  5–15 kWh, with a 10-year warranty. SunHestia Solar PV Modules are
  monocrystalline, 400–450 W black panels with a 25-year performance guarantee.
</p>
```

```astro
---
// tests/fixtures/generate/site/src/pages/faq.astro
---
<p>
  A residential system includes rooftop solar panels, a hybrid inverter, and a
  home battery. Self-consumption is the share of your electricity use covered
  by solar produced on your own property. LiFePO4 means lithium iron
  phosphate — stable, long-lasting, cobalt-free.
</p>
```

- [ ] **Step 2: 写失败测试（追加到 `tests/test_generate_brand.py`）**

```python
from geo.generate.brand import parse_claims, brand_claims, claims_match, validate_brand
import yaml

SITE = FIX / "site" / "src" / "pages"

def _sources_text():
    return "\n\n".join(p.read_text(encoding="utf-8") for p in SITE.rglob("*.astro"))

def test_parse_claims_prose():
    claims = parse_claims("modular from 5–15 kWh with a 10-year warranty, 400–450 W panels")
    assert (frozenset({"5", "15"}), "kwh") in claims
    assert (frozenset({"10"}), "year") in claims
    assert (frozenset({"400", "450"}), "w") in claims

def test_parse_claims_ignores_ordinals_and_years():
    claims = parse_claims("1. first step in 2026, item 3, and 40 pages")
    assert claims == []

def test_brand_claims_from_key_names():
    brand = yaml.safe_load(BRAND.read_text(encoding="utf-8"))
    inv = brand_claims(brand)
    assert (frozenset({"5", "15"}), "kwh") in inv
    assert (frozenset({"10"}), "year") in inv          # warranty_years: 10
    assert (frozenset({"25"}), "year") in inv          # performance_guarantee_years: 25
    assert (frozenset({"400", "450"}), "w") in inv

def test_claims_match_subset_semantics():
    inv = [(frozenset({"5", "15"}), "kwh")]
    assert claims_match((frozenset({"15"}), "kwh"), inv)      # 单值是范围的子集
    assert claims_match((frozenset({"5", "15"}), "kwh"), inv)
    assert not claims_match((frozenset({"20"}), "kwh"), inv)  # 编造的 20 kWh
    assert not claims_match((frozenset({"10"}), "kwh"), inv)  # 单位不符

def test_validate_brand_pass():
    brand = yaml.safe_load(BRAND.read_text(encoding="utf-8"))
    assert validate_brand(brand, _sources_text()) == []

def test_validate_brand_flags_invented_number_and_name():
    brand = yaml.safe_load(BRAND.read_text(encoding="utf-8"))
    brand["products"][0]["specs"]["capacity_kwh"] = "5–20"        # 源页没有 20
    brand["products"].append({"id": "ev-charger", "name": "SunHestia EV Charger",
                              "specs": {"power_kw": "22"}})        # 源页没有该产品
    violations = validate_brand(brand, _sources_text())
    assert any("20" in v and "kwh" in v for v in violations)
    assert any("EV Charger" in v for v in violations)
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_brand.py -v -k "claims or validate_brand"`
Expected: FAIL（`ImportError: parse_claims`）

- [ ] **Step 4: 实现（追加到 `brand.py`）**

```python
# --- 数字 claim 提取（brand 抽取校验与草稿核验共用脊柱）---
_UNITS = r"(kwh|kw|wh|watts|watt|w|years|year|percent|volts|volt|v|%|°c|°f)"
_UNIT_NORM = {"watts": "w", "watt": "w", "years": "year", "percent": "%", "volts": "v", "volt": "v"}
_NUM = r"(\d+(?:\s*[-–—]\s*\d+)?)"
# 文本体：数字在前，单位紧随（含 "10-year" 连字符形）
_CLAIM_RE = re.compile(rf"{_NUM}\s*[-\s]*{_UNITS}\b", re.I)
# 键值体：键名含单位在前、值在后（"capacity kwh: 5–15"；下划线先归一为空格）
_KEYVAL_RE = re.compile(rf"\b{_UNITS}\b[^0-9\n]{{0,25}}{_NUM}", re.I)

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("_", " ").replace("–", "-").replace("—", "-")).strip().lower()

def _norm_unit(u: str) -> str:
    u = u.lower()
    return _UNIT_NORM.get(u, "%" if u == "percent" else u)

def _norm_nums(raw: str) -> frozenset[str]:
    return frozenset(p.strip() for p in re.split(r"[-]+", raw) if p.strip())

def parse_claims(text: str) -> list[tuple[frozenset[str], str]]:
    t = _norm(text)
    out = []
    for nums_raw, unit in _CLAIM_RE.findall(t):
        out.append((_norm_nums(nums_raw), _norm_unit(unit)))
    return out

def _iter_fact_leaves(brand: dict):
    def scalars(d: dict, prefix=""):
        for k, v in d.items():
            if isinstance(v, (str, int, float)):
                yield f"{k}: {v}"
            elif isinstance(v, dict):
                yield from scalars(v, f"{prefix}{k}.")
    yield from scalars(brand.get("entity", {}))
    for p in brand.get("products", []):
        yield from scalars(p)
    for f in brand.get("faqs", []):
        yield from scalars(f)
    for g in brand.get("glossary", []):
        yield from scalars(g)

def brand_claims(brand: dict) -> list[tuple[frozenset[str], str]]:
    out = []
    for leaf in _iter_fact_leaves(brand):
        t = _norm(leaf)
        for nums_raw, unit in _KEYVAL_RE.findall(t):
            out.append((_norm_nums(nums_raw), _norm_unit(unit)))
    return out

def claims_match(claim: tuple[frozenset[str], str],
                 inventory: list[tuple[frozenset[str], str]]) -> bool:
    nums, unit = claim
    return any(unit == u2 and nums <= n2 for n2, u2 in inventory)

def validate_brand(brand: dict, sources_text: str) -> list[str]:
    src_claims = parse_claims(sources_text)
    violations = []
    for leaf in _iter_fact_leaves(brand):
        for claim in parse_claims(leaf) or _leaf_keyval_claims(leaf):
            if not claims_match(claim, src_claims):
                nums, unit = claim
                violations.append(f"数字 claim {sorted(nums)} {unit} 未在源页出现（来自: {leaf[:60]}）")
    for p in brand.get("products", []):
        if p.get("name") and p["name"] not in sources_text:
            violations.append(f"产品名未在源页字面出现: {p['name']}")
    for g in brand.get("glossary", []):
        if g.get("term") and g["term"] not in sources_text:
            violations.append(f"术语未在源页字面出现: {g['term']}")
    return violations

def _leaf_keyval_claims(leaf: str) -> list[tuple[frozenset[str], str]]:
    # 键名含单位、值为裸数字的叶子（parse_claims 文本体正则吃不到，用键值正则）
    t = _norm(leaf)
    return [(_norm_nums(n), _norm_unit(u)) for u, n in _KEYVAL_RE.findall(t)]
```

> 注意：`validate_brand` 里 `parse_claims(leaf) or _leaf_keyval_claims(leaf)`——叶子文本两套正则都试，去重不必做（重复违规信息无害，宁多标红不漏检）。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_brand.py -v`
Expected: 全部 PASS（11 tests）

- [ ] **Step 6: Commit**

```bash
git add geo-agent/src/geo/generate/brand.py geo-agent/tests/test_generate_brand.py geo-agent/tests/fixtures/generate/site/
git commit -m "feat(generate): numeric claim extraction + validate_brand (anti-hallucination spine)"
```

---

### Task 3: bootstrap —— Kimi 抽取 + L2 竞品聚合 + 组装 + run_bootstrap

**Files:**
- Create: `geo-agent/tests/fixtures/generate/data/raw/w1/qwen/C01/r1.json`（迷你 L1，含 competitors）
- Modify: `geo-agent/src/geo/generate/brand.py`（追加 bootstrap 部分）
- Test: `geo-agent/tests/test_generate_bootstrap.py`

**Interfaces:**
- Consumes: Task 2 `validate_brand`；`settings.moonshot_api_key/base_url`（照 research/kimi.py 的 `_kimi_chat` 模式）
- Produces:
  - `read_site_pages(site_root: Path) -> dict[str, str]` —— `{相对路径: 页面原文}`，rglob `*.astro`
  - `bootstrap_draft(pages: dict[str, str], *, chat_fn=None) -> dict` —— Kimi 抽 entity/products/faqs/glossary（JSON）；`chat_fn=None` 用真 Kimi；非法 JSON 抛 `BrandError`
  - `competitors_from_raw(repo: Path) -> list[str]` —— 聚合 `data/raw/*/*/*/r*.json` 的 `l2.competitors_mentioned`，按频次降序
  - `assemble_brand(draft: dict, competitors: list[str]) -> dict` —— 组装完整 brand dict（补 `version:1/updated/banned 默认/i18n:{}`）
  - `run_bootstrap(*, repo: Path, chat_fn=None) -> dict` —— 编排：读 site → 抽取 → 组装 → `validate_brand` → 零违规写 `knowledge/brand.yaml`，有违规写 `knowledge/brand.yaml.draft` 并在返回值 `violations` 里列出（不静默）

- [ ] **Step 1: 写 L1 fixture `tests/fixtures/generate/data/raw/w1/qwen/C01/r1.json`**

```json
{
  "week": 1, "model": "qwen", "prompt_id": "C01", "run": 1,
  "answer": "Tesla and Enphase make home batteries.",
  "l2": {
    "cited_sources": [{"position": 1, "url": "https://example.com/a", "title": "A", "snippet": "", "extract_method": "structured"}],
    "mentioned": false, "cited_with_link": false, "citation_position": null,
    "sentiment": null, "competitors_mentioned": ["Tesla", "Enphase", "Tesla"], "low_confidence": false
  },
  "usage": {}, "elapsed_s": 1.0, "search_triggered": true,
  "ts_iso": "2026-08-13T00:00:00Z", "prompt_set_version": "prompts-v1"
}
```

- [ ] **Step 2: 写失败测试 `tests/test_generate_bootstrap.py`**

```python
# tests/test_generate_bootstrap.py
import json
from pathlib import Path
import pytest
import yaml
from geo.generate.brand import (
    read_site_pages, bootstrap_draft, competitors_from_raw, assemble_brand, run_bootstrap, BrandError)

FIX = Path(__file__).parent / "fixtures" / "generate"

def _mock_chat(payload: dict):
    def chat_fn(messages, tools=None, timeout=120) -> str:
        return json.dumps(payload, ensure_ascii=False)
    return chat_fn

_GOOD = {
    "entity": {"brand": "SunHestia", "domain": "sunhestia.com",
               "positioning": "Residential solar and storage for European homes"},
    "products": [{"id": "home-battery", "name": "SunHestia Home Battery",
                  "specs": {"chemistry": "LiFePO4", "capacity_kwh": "5–15", "warranty_years": 10}},
                 {"id": "pv-module", "name": "SunHestia Solar PV Modules",
                  "specs": {"cell_type": "monocrystalline", "power_w": "400–450",
                            "performance_guarantee_years": 25}}],
    "faqs": [{"q": "What does a residential solar and storage system include?",
              "a": "Typically rooftop solar panels, a hybrid inverter, and a home battery."}],
    "glossary": [{"term": "self-consumption",
                  "definition": "The share of your electricity use covered by solar produced on your own property."},
                 {"term": "LiFePO4", "definition": "Lithium iron phosphate battery chemistry."}],
}

def test_read_site_pages():
    pages = read_site_pages(FIX / "site" / "src" / "pages")
    assert set(pages) == {"products.astro", "faq.astro"}
    assert "LiFePO4" in pages["products.astro"]

def test_bootstrap_draft_ok():
    draft = bootstrap_draft({"products.astro": "LiFePO4 5–15 kWh 10-year warranty"},
                            chat_fn=_mock_chat(_GOOD))
    assert draft["products"][0]["id"] == "home-battery"

def test_bootstrap_draft_bad_json():
    def bad(messages, tools=None, timeout=120):
        return "not json"
    with pytest.raises(BrandError, match="Kimi 抽取失败"):
        bootstrap_draft({"p": "x"}, chat_fn=bad)

def test_competitors_from_raw():
    comps = competitors_from_raw(FIX / "data" / "raw")   # 注意传 raw 根
    assert comps[0] == "Tesla"                            # 出现 2 次居首
    assert "Enphase" in comps

def test_assemble_brand():
    brand = assemble_brand(_GOOD, ["Tesla"])
    assert brand["version"] == 1 and brand["banned"] == ["no_pricing", "no_savings_percentages"]
    assert brand["competitors"] == ["Tesla"] and brand["i18n"] == {}

def test_run_bootstrap_clean_writes_brand(tmp_path):
    res = run_bootstrap(repo=FIX, chat_fn=_mock_chat(_GOOD))
    # FIX 本身当 repo：site 在 FIX/site —— 见 Step 4 对 site_root 的解析约定
    assert res["violations"] == []
    out = FIX / "knowledge" / "brand.yaml"
    assert out.exists() and yaml.safe_load(out.read_text(encoding="utf-8"))["version"] == 1

def test_run_bootstrap_violations_write_draft_only(tmp_path):
    bad_payload = json.loads(json.dumps(_GOOD))
    bad_payload["products"][0]["specs"]["capacity_kwh"] = "5–20"   # 源页无 20
    res = run_bootstrap(repo=FIX, chat_fn=_mock_chat(bad_payload))
    assert res["violations"] and "20" in res["violations"][0]
    assert res["wrote"] == str(FIX / "knowledge" / "brand.yaml.draft")
```

> ⚠️ `test_run_bootstrap_clean_writes_brand` 会覆写 fixture `knowledge/brand.yaml`——**测试结束需还原**：测试开头 `orig = out.read_text()`，teardown 写回；或用 `tmp_path` 组 mini-repo（复制 FIX 的 site/knowledge/data 到 tmp_path 后传 repo=tmp_path）。**采用 tmp_path 方案**（不动共享 fixture），断言路径改 `tmp_path/...`。

- [ ] **Step 3: 跑测试确认失败**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_bootstrap.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 4: 实现（追加到 `brand.py`）**

```python
# --- bootstrap（一次性引导，低频重跑保险）---
import logging
from collections import Counter
from geo.shared.config import settings, REPO

log = logging.getLogger("generate.brand")

_SYS_BOOT = (
    "你是品牌事实抽取器。只准从所给的站点页面文本抽取事实，禁止推断或编造。"
    "输出 JSON：{entity:{brand,domain,positioning,legal_name?,locations?},"
    "products:[{id,name,specs:{...}}],faqs:[{q,a}],glossary:[{term,definition}]}。"
    "specs 的键名带单位（如 capacity_kwh/warranty_years/power_w）；抽不到的键省略，不要编。"
)

def _kimi_chat(messages: list[dict], tools=None, timeout: int = 120) -> str:
    from openai import OpenAI
    c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=timeout)
    r = c.chat.completions.create(model="kimi-k3", messages=messages, temperature=1,
                                  response_format={"type": "json_object"})
    return r.choices[0].message.content or ""

def read_site_pages(site_root: Path) -> dict[str, str]:
    site_root = Path(site_root)
    return {str(p.relative_to(site_root)): p.read_text(encoding="utf-8")
            for p in sorted(site_root.rglob("*.astro"))}

def bootstrap_draft(pages: dict[str, str], *, chat_fn=None) -> dict:
    chat = chat_fn or _kimi_chat
    user = "\n\n".join(f"=== 页面 {name} ===\n{text}" for name, text in pages.items())
    try:
        data = json.loads(chat([{"role": "system", "content": _SYS_BOOT},
                                {"role": "user", "content": user}]))
    except Exception as e:
        raise BrandError(f"Kimi 抽取失败（非法 JSON）: {e}") from e
    for k in ("entity", "products", "faqs", "glossary"):
        if k not in data:
            raise BrandError(f"Kimi 抽取结果缺键: {k}")
    return data

def competitors_from_raw(raw_root: Path) -> list[str]:
    raw_root = Path(raw_root)
    counter: Counter[str] = Counter()
    for f in raw_root.rglob("r*.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
            counter.update((rec.get("l2") or {}).get("competitors_mentioned", []))
        except Exception as e:
            log.warning("skip unreadable raw %s: %s", f, e)
    return [name for name, _ in counter.most_common()]

DEFAULT_BANNED = ["no_pricing", "no_savings_percentages"]

def assemble_brand(draft: dict, competitors: list[str], *, updated: str = "1970-01-01") -> dict:
    return {"version": 1, "updated": updated,
            "entity": draft.get("entity", {}), "products": draft.get("products", []),
            "faqs": draft.get("faqs", []), "glossary": draft.get("glossary", []),
            "banned": list(DEFAULT_BANNED), "competitors": competitors, "i18n": {}}

def run_bootstrap(*, repo: Path = REPO, chat_fn=None, updated: str = None) -> dict:
    from datetime import date
    repo = Path(repo)
    site_root = repo / "site" / "src" / "pages"          # mini-repo 约定：repo 下有 site/
    if not site_root.exists():                            # 真仓库：site/ 是 geo-agent 的兄弟
        site_root = repo.parent / "site" / "src" / "pages"
    pages = read_site_pages(site_root)
    draft = bootstrap_draft(pages, chat_fn=chat_fn)
    competitors = competitors_from_raw(repo / "data" / "raw")
    brand = assemble_brand(draft, competitors, updated=updated or date.today().isoformat())
    sources_text = "\n\n".join(pages.values())
    violations = validate_brand(brand, sources_text)
    (repo / "knowledge").mkdir(parents=True, exist_ok=True)
    if violations:
        out = repo / "knowledge" / "brand.yaml.draft"
        out.write_text(yaml.safe_dump(brand, allow_unicode=True, sort_keys=False), encoding="utf-8")
        log.warning("brand 校验 %d 项违规，写入 %s（人修/删后重跑）", len(violations), out)
    else:
        out = repo / "knowledge" / "brand.yaml"
        out.write_text(yaml.safe_dump(brand, allow_unicode=True, sort_keys=False), encoding="utf-8")
        log.info("brand.yaml 写入 %s（待人审定稿）", out)
    return {"wrote": str(out), "violations": violations,
            "hint": "人审定稿后 git commit knowledge/brand.yaml"}
```

> `brand.py` 顶部需补 `import json`（若 Task 2 未引）。

- [ ] **Step 5: 跑测试确认通过（含 tmp_path mini-repo 版 run_bootstrap 测试）**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_bootstrap.py tests/test_generate_brand.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add geo-agent/src/geo/generate/brand.py geo-agent/tests/test_generate_bootstrap.py geo-agent/tests/fixtures/generate/data/
git commit -m "feat(generate): brand bootstrap (Kimi extract + L2 competitors + deterministic validation)"
```

---

### Task 4: topics.py —— --suggest 确定性选题建议

**Files:**
- Create: `geo-agent/tests/fixtures/generate/data/analysis/w1/eval_report.json`
- Create: `geo-agent/tests/fixtures/generate/data/snapshots/w1/gsc.json`
- Create: `geo-agent/src/geo/generate/topics.py`
- Test: `geo-agent/tests/test_generate_topics.py`

**Interfaces:**
- Consumes: 无（读 repo 下 `data/analysis/w{N}/eval_report.json` + `data/snapshots/w{N}/gsc.json`）
- Produces: `suggest_topics(week: int, *, repo: Path) -> tuple[list[dict], list[str]]` —— `([建议], [缺失源])`；建议 dict `{source: "eval_gap"|"gsc", detail: str, topic: str, page_type: str}`；eval_gap 只取 score<50 的维度升序、每维一条模板建议；gsc 按曝光降序取前 8

- [ ] **Step 1: 写 fixtures**

`tests/fixtures/generate/data/analysis/w1/eval_report.json`（迷你，含低分维度）：

```json
{
  "week": 1, "rule_version": "geo-seo-v1",
  "self_geo": {"dims": [
    {"name": "citability", "score": 32.0, "weight": 25.0},
    {"name": "brand", "score": 100.0, "weight": 20.0},
    {"name": "eeat", "score": 25.0, "weight": 20.0}]},
  "self_seo": {"dims": [
    {"name": "crawlability_index", "score": 100.0, "weight": 20.0},
    {"name": "content_eeat", "score": 1.4, "weight": 25.0}]}
}
```

`tests/fixtures/generate/data/snapshots/w1/gsc.json`：

```json
{
  "week": 1, "rule_version": "geo-seo-v1", "site": "https://sunhestia.com", "degraded": false,
  "rows": [
    {"keys": ["hestia solar"], "clicks": 0, "impressions": 3, "ctr": 0, "position": 47},
    {"keys": ["photovoltaic self consumption"], "clicks": 0, "impressions": 5, "ctr": 0, "position": 77},
    {"keys": ["lifepo4 battery"], "clicks": 1, "impressions": 9, "ctr": 0.1, "position": 21}
  ]
}
```

- [ ] **Step 2: 写失败测试 `tests/test_generate_topics.py`**

```python
# tests/test_generate_topics.py
import json, shutil
from pathlib import Path
from geo.generate.topics import suggest_topics

FIX = Path(__file__).parent / "fixtures" / "generate"

def test_suggest_topics_eval_gaps_first():
    out, missing = suggest_topics(1, repo=FIX)
    assert missing == []
    gaps = [s for s in out if s["source"] == "eval_gap"]
    # score<50 的三个维度：content_eeat(1.4) < eeat(25) < citability(32)，升序
    assert [g["detail"] for g in gaps] == ["content_eeat=1.4", "eeat=25.0", "citability=32.0"]
    assert gaps[0]["page_type"] in ("faq", "spec", "comparison", "guide")
    assert all(g["topic"] for g in gaps)

def test_suggest_topics_gsc_by_impressions():
    out, _ = suggest_topics(1, repo=FIX)
    gsc = [s for s in out if s["source"] == "gsc"]
    assert [s["topic"] for s in gsc] == ["lifepo4 battery", "photovoltaic self consumption", "hestia solar"]
    assert gsc[0]["detail"] == "impressions=9"

def test_suggest_topics_missing_sources_reported(tmp_path):
    out, missing = suggest_topics(2, repo=tmp_path)   # 空 repo
    assert out == []
    assert len(missing) == 2 and any("eval_report" in m for m in missing)
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_topics.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 4: 实现 `src/geo/generate/topics.py`**

```python
# src/geo/generate/topics.py
from __future__ import annotations
import json
from pathlib import Path

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

def suggest_topics(week: int, *, repo: Path) -> tuple[list[dict], list[str]]:
    repo = Path(repo)
    out: list[dict] = []
    missing: list[str] = []
    er = repo / "data" / "analysis" / f"w{week}" / "eval_report.json"
    if er.exists():
        rep = json.loads(er.read_text(encoding="utf-8"))
        dims = [d for sec in ("self_geo", "self_seo") for d in rep.get(sec, {}).get("dims", [])
                if d.get("score", 100) < 50]
        for d in sorted(dims, key=lambda x: x["score"]):
            topic, ptype = GAP_TEMPLATES.get(d["name"], _DEFAULT_TEMPLATE)
            out.append({"source": "eval_gap", "detail": f"{d['name']}={d['score']}", "topic": topic, "page_type": ptype})
    else:
        missing.append(str(er))
    gsc = repo / "data" / "snapshots" / f"w{week}" / "gsc.json"
    if gsc.exists():
        snap = json.loads(gsc.read_text(encoding="utf-8"))
        for row in sorted(snap.get("rows", []), key=lambda r: -r.get("impressions", 0))[:8]:
            q = " ".join(row.get("keys", [])).strip()
            if q:
                out.append({"source": "gsc", "detail": f"impressions={row.get('impressions', 0)}",
                            "topic": q, "page_type": "guide"})
    else:
        missing.append(str(gsc))
    return out, missing
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_topics.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add geo-agent/src/geo/generate/topics.py geo-agent/tests/test_generate_topics.py geo-agent/tests/fixtures/generate/data/
git commit -m "feat(generate): deterministic topic suggestions (eval gaps + GSC queries)"
```

---

### Task 5: kimi.py —— playbook_digest 确定性解析

**Files:**
- Create: `geo-agent/tests/fixtures/generate/knowledge/playbook.md`（P1 render 格式迷你版）
- Create: `geo-agent/src/geo/generate/kimi.py`
- Test: `geo-agent/tests/test_generate_kimi.py`

**Interfaces:**
- Consumes: P1 `render_playbook` 输出格式（`# SunHestia GEO Playbook · w{N}` 标题行 + `### {key}（label）` 节 + `- cited_n=N sample_n=N confidence=...` 行）
- Produces: `playbook_digest(playbook_text: str) -> dict` —— `{"week": int|None, "formats": [{"key": str, "cited_n": int, "sample_n": int, "confidence": str}], "templates_note": str}`；空文本/解析不到 → week=None、formats=[]（不抛错）

- [ ] **Step 1: 写 fixture `tests/fixtures/generate/knowledge/playbook.md`**

```markdown
# SunHestia GEO Playbook · w1
> rule_version geo-seo-v1 | L1=45 | 被引源分析 sample_n=6(缺失1/js_only0)
> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。

## 1. 被引格式特征
### comparison_table（对比表）
- cited_n=4 sample_n=6 confidence=ok platforms=['qwen', 'zhipu']
- 结论：被引源多含对比表｜行动：优先对比表骨架
### definition（定义段）
- cited_n=2 sample_n=6 confidence=low platforms=['qwen']

## 2. 被引来源特征
```json
{}
```

## 3. 分平台差异
```json
{}
```

## 4. 问题空间与选题
意图簇：comparison  选题缺口候选：['sizing']

## 5. 可复用内容模板
- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。
```

- [ ] **Step 2: 写失败测试（`tests/test_generate_kimi.py` 先只测 digest）**

```python
# tests/test_generate_kimi.py
from pathlib import Path
from geo.generate.kimi import playbook_digest

FIX = Path(__file__).parent / "fixtures" / "generate"

def test_playbook_digest_parses_week_and_formats():
    d = playbook_digest((FIX / "knowledge" / "playbook.md").read_text(encoding="utf-8"))
    assert d["week"] == 1
    by_key = {f["key"]: f for f in d["formats"]}
    assert by_key["comparison_table"] == {"key": "comparison_table", "cited_n": 4, "sample_n": 6, "confidence": "ok"}
    assert by_key["definition"]["confidence"] == "low"

def test_playbook_digest_empty_text():
    d = playbook_digest("")
    assert d["week"] is None and d["formats"] == []

def test_playbook_digest_unrelated_text():
    d = playbook_digest("# 别的文档\nnothing here")
    assert d["week"] is None and d["formats"] == []
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_kimi.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 4: 实现 `src/geo/generate/kimi.py`**

```python
# src/geo/generate/kimi.py
from __future__ import annotations
import re

_WEEK_RE = re.compile(r"Playbook · w(\d+)")
_FMT_HDR_RE = re.compile(r"^### (\w+)（.+?）", re.M)
_FMT_LINE_RE = re.compile(r"- cited_n=(\d+) sample_n=(\d+) confidence=(\w+)")

def playbook_digest(playbook_text: str) -> dict:
    text = playbook_text or ""
    m = _WEEK_RE.search(text)
    formats: list[dict] = []
    lines = text.splitlines()
    current_key = None
    for line in lines:
        h = _FMT_HDR_RE.match(line)
        if h:
            current_key = h.group(1)
            continue
        if current_key:
            fm = _FMT_LINE_RE.search(line)
            if fm:
                formats.append({"key": current_key, "cited_n": int(fm.group(1)),
                                "sample_n": int(fm.group(2)), "confidence": fm.group(3)})
                current_key = None
    return {"week": int(m.group(1)) if m else None, "formats": formats,
            "templates_note": "高被引骨架：对比表 / 定义段 / 规格卡（见 playbook §5）"}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_kimi.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add geo-agent/src/geo/generate/kimi.py geo-agent/tests/test_generate_kimi.py geo-agent/tests/fixtures/generate/knowledge/playbook.md
git commit -m "feat(generate): deterministic playbook digest parser"
```

---

### Task 6: kimi.py —— generate_draft（Kimi seam + 重试 + --no-kimi 骨架）

**Files:**
- Modify: `geo-agent/src/geo/generate/kimi.py`（追加）
- Test: `geo-agent/tests/test_generate_kimi.py`（追加）

**Interfaces:**
- Consumes: Task 5 `playbook_digest`；`brand` dict（Task 1 load_brand 产物）
- Produces:
  - `generate_draft(topic: str, page_type: str, brand: dict, digest: dict, *, chat_fn=None) -> dict` —— 返回 `{frontmatter: {topic, page_type, slug}, title: str, body_md: str, json_ld: list[dict], fact_anchors: [{"claim","path","value"}]}`；Kimi 两次失败抛 `GenerateError`
  - `class GenerateError(Exception)`
  - `skeleton_draft(topic: str, page_type: str, brand: dict) -> dict` —— 确定性 `--no-kimi` 路径：page_type 模板 + brand 事实表（无 prose、无 fact_anchors → 核验会标 flagged，可接受）
  - `_kimi_chat(messages, tools=None, timeout=120) -> str`（同 research 模式）

- [ ] **Step 1: 写失败测试（追加）**

```python
import pytest
from geo.generate.kimi import generate_draft, skeleton_draft, GenerateError

_BRAND = yaml.safe_load((FIX / "knowledge" / "brand.yaml").read_text(encoding="utf-8"))
_DIGEST = {"week": 1, "formats": [{"key": "comparison_table", "cited_n": 4, "sample_n": 6, "confidence": "ok"}],
           "templates_note": "对比表优先"}

_GOOD_KIMI = {
    "frontmatter": {"topic": "How to size a home battery", "page_type": "guide", "slug": "how-to-size-a-home-battery"},
    "title": "How to size a home battery",
    "body_md": "# How to size a home battery\n\nA common starting point is 5–15 kWh; the battery carries a 10-year warranty.",
    "json_ld": [{"@context": "https://schema.org", "@type": "Article", "headline": "How to size a home battery"}],
    "fact_anchors": [{"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
                     {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}],
}

def _ok_chat(payload):
    def chat_fn(messages, tools=None, timeout=120):
        assert "BRAND FACTS" in messages[1]["content"]
        return json.dumps(payload, ensure_ascii=False)
    return chat_fn

def test_generate_draft_ok():
    d = generate_draft("How to size a home battery", "guide", _BRAND, _DIGEST,
                       chat_fn=_ok_chat(_GOOD_KIMI))
    assert d["frontmatter"]["slug"] == "how-to-size-a-home-battery"
    assert d["fact_anchors"][0]["path"] == "products[home-battery].specs.capacity_kwh"

def test_generate_draft_retries_once_then_raises():
    calls = {"n": 0}
    def flaky(messages, tools=None, timeout=120):
        calls["n"] += 1
        return "not json"
    with pytest.raises(GenerateError, match="两次失败"):
        generate_draft("t", "guide", _BRAND, _DIGEST, chat_fn=flaky)
    assert calls["n"] == 2

def test_skeleton_draft_deterministic():
    d1 = skeleton_draft("t", "spec", _BRAND)
    d2 = skeleton_draft("t", "spec", _BRAND)
    assert d1 == d2
    assert "LiFePO4" in d1["body_md"]
    assert d1["frontmatter"]["page_type"] == "spec"
```

> 文件顶部补 `import json, yaml`。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_kimi.py -v -k "generate_draft or skeleton"`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现（追加到 `kimi.py`）**

```python
import json, logging
import yaml
from geo.shared.config import settings

log = logging.getLogger("generate.kimi")

PAGE_TYPES = ("faq", "spec", "comparison", "guide")
_SKELETONS = {
    "faq":        "## {topic}\n\n（FAQ 块：每小节一问一答）\n\n## Q1 …",
    "spec":       "## {topic}\n\n（规格卡：表格列产品事实，数据只取 BRAND FACTS）",
    "comparison": "## {topic}\n\n（对比表：列 = 维度，行 = 选项；数据只取 BRAND FACTS）",
    "guide":      "## {topic}\n\n（指南：定义段开头 + 步骤清单 + 数据点）",
}

class GenerateError(Exception):
    pass

def _kimi_chat(messages: list[dict], tools=None, timeout: int = 180) -> str:
    from openai import OpenAI
    c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=timeout)
    r = c.chat.completions.create(model="kimi-k3", messages=messages, temperature=1,
                                  response_format={"type": "json_object"})
    return r.choices[0].message.content or ""

_SYS_GEN = (
    "你是 SunHestia 官网内容写手。只能使用 BRAND FACTS 中的数字与规格，不得编造任何数字、"
    "型号或承诺；写不出的事实就略过。输出 JSON："
    "{frontmatter:{topic,page_type,slug},title,body_md,json_ld:[schema.org 对象],"
    "fact_anchors:[{claim,path,value}]}。"
    "纪律：body_md 里每个数字都必须有一条 fact_anchors，path 用 id 式"
    "（如 products[home-battery].specs.warranty_years）；json_ld 至少一个对象且与页面类型匹配"
    "（guide→Article、faq→FAQPage、spec→Product、comparison→Article）；body_md 用英文写、"
    "markdown 结构（H1/H2/表格/FAQ 块按 PLAYBOOK DIGEST 的高被引格式优先）。"
)

def generate_draft(topic: str, page_type: str, brand: dict, digest: dict, *, chat_fn=None) -> dict:
    chat = chat_fn or _kimi_chat
    facts = yaml.safe_dump({k: brand.get(k) for k in ("entity", "products", "faqs", "glossary")},
                           allow_unicode=True, sort_keys=False)
    user = (f"TOPIC: {topic}\nPAGE_TYPE: {page_type}\n\nBRAND FACTS:\n{facts}\n\n"
            f"PLAYBOOK DIGEST:\n{json.dumps(digest, ensure_ascii=False)}")
    last: Exception | None = None
    for attempt in (1, 2):
        try:
            data = json.loads(chat([{"role": "system", "content": _SYS_GEN},
                                    {"role": "user", "content": user}]))
            for k in ("frontmatter", "title", "body_md", "json_ld", "fact_anchors"):
                if k not in data:
                    raise ValueError(f"输出缺键 {k}")
            return data
        except Exception as e:
            last = e
            log.warning("generate_draft 第 %d 次失败: %s", attempt, e)
    raise GenerateError(f"Kimi 生成两次失败: {last}")

def skeleton_draft(topic: str, page_type: str, brand: dict) -> dict:
    body = _SKELETONS.get(page_type, _SKELETONS["guide"]).format(topic=topic)
    facts_tbl = ["| 产品 | 规格 |", "|---|---|"]
    for p in brand.get("products", []):
        specs = "；".join(f"{k}={v}" for k, v in p.get("specs", {}).items())
        facts_tbl.append(f"| {p.get('name','')} | {specs} |")
    body_md = f"{body}\n\n" + "\n".join(facts_tbl)
    return {"frontmatter": {"topic": topic, "page_type": page_type, "slug": ""},
            "title": topic, "body_md": body_md, "json_ld": [], "fact_anchors": []}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_kimi.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/generate/kimi.py geo-agent/tests/test_generate_kimi.py
git commit -m "feat(generate): Kimi generate_draft seam (retry + fact_anchors) + deterministic skeleton"
```

---

### Task 7: validate.py —— 草稿四项核验 + 核对清单附录

**Files:**
- Create: `geo-agent/src/geo/generate/validate.py`
- Test: `geo-agent/tests/test_generate_validate.py`

**Interfaces:**
- Consumes: Task 2 `parse_claims/brand_claims/claims_match`；Task 6 draft dict 形状
- Produces:
  - `@dataclass ValidationResult: ok: bool; issues: list[str]; appendix_md: str`
  - `validate_draft(draft: dict, brand: dict) -> ValidationResult` —— 四项：①frontmatter 完整（topic/page_type/slug/created/brand_version 必填 + page_type 枚举）②数字归属（body 的 claims ⊆ brand_claims 且每个 claim 有吻合的 fact_anchor：路径可解析 + 值吻合）③JSON-LD 结构（合法 JSON dict、`@type` 合法、类型必填键）④banned 口径
  - `resolve_path(brand: dict, path: str)` —— id 式路径解析（`products[home-battery].specs.capacity_kwh`）；不可解析返回 `_MISSING` 哨兵
  - `appendix_md`：`| claim | anchor | 校验 |` 表格（每条数字 claim 一行 ✅/❌）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_generate_validate.py
import yaml
from pathlib import Path
from geo.generate.validate import validate_draft, resolve_path, _MISSING

FIX = Path(__file__).parent / "fixtures" / "generate"
BRAND = yaml.safe_load((FIX / "knowledge" / "brand.yaml").read_text(encoding="utf-8"))

def _draft(**over):
    d = {
        "frontmatter": {"topic": "How to size a home battery", "page_type": "guide",
                        "slug": "how-to-size-a-home-battery", "created": "2026-08-16",
                        "brand_version": 1},
        "title": "How to size a home battery",
        "body_md": "# How to size a home battery\n\nStart at 5–15 kWh; the battery carries a 10-year warranty.",
        "json_ld": [{"@context": "https://schema.org", "@type": "Article",
                     "headline": "How to size a home battery"}],
        "fact_anchors": [
            {"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
            {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}],
    }
    d.update(over)
    return d

def test_resolve_path():
    assert resolve_path(BRAND, "products[home-battery].specs.warranty_years") == 10
    assert resolve_path(BRAND, "products[nope].specs.x") is _MISSING

def test_validate_ok():
    r = validate_draft(_draft(), BRAND)
    assert r.ok, r.issues
    assert "| 5–15 kWh | products[home-battery].specs.capacity_kwh | ✅ |" in r.appendix_md

def test_validate_flags_invented_number():
    d = _draft(body_md="# t\n\nA 20 kWh battery is big.")
    r = validate_draft(d, BRAND)
    assert not r.ok and any("20" in i for i in r.issues)

def test_validate_flags_missing_anchor():
    d = _draft(fact_anchors=[{"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"}])
    r = validate_draft(d, BRAND)     # 10-year 无 anchor
    assert not r.ok and any("anchor" in i for i in r.issues)

def test_validate_flags_bad_anchor_path():
    d = _draft(fact_anchors=[
        {"claim": "5–15 kWh", "path": "products[home-battery].specs.nonexistent", "value": "5–15"},
        {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}])
    r = validate_draft(d, BRAND)
    assert not r.ok and any("nonexistent" in i for i in r.issues)

def test_validate_flags_bad_jsonld():
    d = _draft(json_ld=[{"@type": "FAQPage"}])          # 缺 mainEntity
    r = validate_draft(d, BRAND)
    assert not r.ok and any("FAQPage" in i for i in r.issues)

def test_validate_flags_pricing():
    d = _draft(body_md="# t\n\nThe system costs $9999.")
    r = validate_draft(d, BRAND)
    assert not r.ok and any("no_pricing" in i for i in r.issues)

def test_validate_flags_savings_percent():
    d = _draft(body_md="# t\n\nSave 40% on your bills.")
    r = validate_draft(d, BRAND)
    assert not r.ok and any("no_savings_percentages" in i for i in r.issues)

def test_validate_flags_frontmatter():
    d = _draft()
    d["frontmatter"] = {"topic": "x"}                    # 缺 page_type/slug/created/brand_version
    r = validate_draft(d, BRAND)
    assert not r.ok and any("frontmatter" in i for i in r.issues)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_validate.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 `src/geo/generate/validate.py`**

```python
# src/geo/generate/validate.py
from __future__ import annotations
import re
from dataclasses import dataclass, field
from geo.generate.brand import parse_claims, brand_claims, claims_match

_MISSING = object()
JSONLD_REQUIRED = {"FAQPage": ["mainEntity"], "Article": ["headline"],
                   "HowTo": ["name", "step"], "Product": ["name", "brand"]}
FRONTMATTER_REQUIRED = ("topic", "page_type", "slug", "created", "brand_version")
PAGE_TYPES = ("faq", "spec", "comparison", "guide")
BANNED_PATTERNS = {
    "no_pricing": re.compile(r"[$€£¥]\s*\d|\b\d+\s*(yuan|eur|usd|dollars?|euros?)\b|price[:\s$€£¥]*\d", re.I),
    "no_savings_percentages": re.compile(
        r"(save|saving|savings|off|cheaper|节省)[^.\n]{0,25}\d+\s*%|\d+\s*%\s*(off|savings?|cheaper|节省)", re.I),
}

@dataclass
class ValidationResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    appendix_md: str = ""

def resolve_path(brand: dict, path: str):
    cur = brand
    for seg in path.split("."):
        m = re.match(r"^(\w+)\[(.+)\]$", seg)
        if m:
            key, ident = m.group(1), m.group(2)
            cur = cur.get(key) if isinstance(cur, dict) else None
            if not isinstance(cur, list):
                return _MISSING
            cur = next((it for it in cur if isinstance(it, dict) and it.get("id") == ident), None)
            if cur is None:
                return _MISSING
        elif isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return _MISSING
    return cur

def _claim_key(claim) -> tuple:
    return frozenset(n for n in claim[0]), claim[1]

def validate_draft(draft: dict, brand: dict) -> ValidationResult:
    issues: list[str] = []
    rows: list[tuple[str, str, bool]] = []      # (claim 文本, anchor 展示, ok)
    fm = draft.get("frontmatter", {})
    missing_fm = [k for k in FRONTMATTER_REQUIRED if not fm.get(k)]
    if missing_fm:
        issues.append(f"frontmatter 缺字段: {missing_fm}")
    if fm.get("page_type") not in PAGE_TYPES:
        issues.append(f"frontmatter.page_type 非法: {fm.get('page_type')!r}")

    inventory = brand_claims(brand)
    body_claims = parse_claims(draft.get("body_md", ""))
    anchors = draft.get("fact_anchors", []) or []
    for claim in body_claims:
        nums, unit = claim
        claim_txt = f"{'–'.join(sorted(nums))} {unit}"
        anchor = next((a for a in anchors
                       if set(parse_nums_from(a.get("claim", ""))) <= nums or
                          set(parse_nums_from(str(a.get("value", "")))) == nums), None)
        anchored = False
        if anchor is not None:
            resolved = resolve_path(brand, anchor.get("path", ""))
            if resolved is _MISSING:
                issues.append(f"anchor 路径不可解析: {anchor.get('path')!r}（claim {claim_txt}）")
                rows.append((claim_txt, anchor.get("path", ""), False))
            elif not claims_match(claim, inventory):
                issues.append(f"数字 claim 未归属 brand.yaml: {claim_txt}")
                rows.append((claim_txt, anchor.get("path", ""), False))
            else:
                anchored = True
                rows.append((claim_txt, anchor.get("path", ""), True))
        else:
            if claims_match(claim, inventory):
                issues.append(f"数字 claim 缺 anchor: {claim_txt}")
                rows.append((claim_txt, "—(缺)", False))
            else:
                issues.append(f"数字 claim 未归属 brand.yaml: {claim_txt}")
                rows.append((claim_txt, "—(编造)", False))
        _ = anchored

    for i, obj in enumerate(draft.get("json_ld", []) or []):
        t = obj.get("@type", "") if isinstance(obj, dict) else ""
        if t not in JSONLD_REQUIRED:
            issues.append(f"json_ld[{i}] @type 非法: {t!r}")
            continue
        for k in JSONLD_REQUIRED[t]:
            if not obj.get(k):
                issues.append(f"json_ld[{i}] {t} 缺必填键: {k}")

    body = draft.get("body_md", "")
    for name, pat in BANNED_PATTERNS.items():
        if name in (brand.get("banned") or []) and pat.search(body):
            issues.append(f"口径禁项命中: {name}")

    lines = ["| claim | anchor | 校验 |", "|---|---|---|"]
    for claim_txt, path, ok in rows:
        lines.append(f"| {claim_txt} | {path} | {'✅' if ok else '❌'} |")
    return ValidationResult(ok=not issues, issues=issues, appendix_md="\n".join(lines))

def parse_nums_from(s: str) -> list[str]:
    return re.findall(r"\d+", str(s))
```

> 实现注意：`test_validate_ok` 断言附录行 `| 5–15 kWh | products[home-battery].specs.capacity_kwh | ✅ |`——`claim_txt` 由 `sorted(nums)` 拼成 `5–15`（字典序 "15"<"5"，所以 `sorted(['5','15'])==['15','5']` 会产出 "15–5"！）。**修正 `_claim_key`/`claim_txt` 构造**：`nums_sorted = sorted(nums, key=float)`，`claim_txt = f"{'–'.join(nums_sorted)} {unit}"`（`5–15 kWh` ✓）。测试里两个 fixture 数字均为单值或顺序无关场景，按数值排序即符合直觉。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_validate.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/generate/validate.py geo-agent/tests/test_generate_validate.py
git commit -m "feat(generate): draft validation (frontmatter/claims-anchors/JSON-LD/banned) + checklist appendix"
```

---

### Task 8: run.py —— CLI 编排（生成/建议/人审/归档/bootstrap）

**Files:**
- Create: `geo-agent/src/geo/generate/run.py`
- Test: `geo-agent/tests/test_generate_run.py`

**Interfaces:**
- Consumes: Task 1-7 全部（`load_brand/slugify/playbook_digest/generate_draft/skeleton_draft/validate_draft/suggest_topics/run_bootstrap`）
- Produces（CLI 入口 `python3.11 -m geo.generate.run`）:
  - `run_generate(topic, page_type="guide", week=1, allow_no_playbook=False, kimi=True, chat_fn=None, repo=REPO, today=None) -> dict` —— 返回 `{"path": str, "validation": "passed"|"flagged", "issues": [...], "playbook_week": int|None}`；写 `content/drafts/{slug}.md`（yaml frontmatter + 可选警告横幅 + body + `## Suggested JSON-LD` + 附录）
  - `run_review(slug, verdict, notes="", repo=REPO, now=None) -> dict` —— 追加 `content/reviews.jsonl`；verdict=reject 时草稿 frontmatter `status: rejected`；slug 不存在 raise `SystemExit`（列出现有 slug）
  - `run_mark_published(slug, repo=REPO) -> dict` —— `drafts/{slug}.md` → `published/{slug}.md` + `status: published`
  - `run_suggest(week, repo) -> dict` —— 打印建议（`suggest_topics` 直通）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_generate_run.py
import json, shutil, yaml
from pathlib import Path
import pytest
from geo.generate.run import run_generate, run_review, run_mark_published

FIX = Path(__file__).parent / "fixtures" / "generate"

def _mini_repo(tmp_path: Path) -> Path:
    """复制 fixture 的 knowledge+data 到 tmp mini-repo（site/bootstrap 已在 Task 3 测过）。"""
    for sub in ("knowledge", "data"):
        src = FIX / sub
        if src.exists():
            shutil.copytree(src, tmp_path / sub)
    return tmp_path

def _chat_ok(messages, tools=None, timeout=120):
    return json.dumps({
        "frontmatter": {"topic": "battery sizing", "page_type": "guide", "slug": "battery-sizing"},
        "title": "battery sizing",
        "body_md": "# Battery sizing\n\nStart at 5–15 kWh with a 10-year warranty.",
        "json_ld": [{"@context": "https://schema.org", "@type": "Article", "headline": "battery sizing"}],
        "fact_anchors": [
            {"claim": "5–15 kWh", "path": "products[home-battery].specs.capacity_kwh", "value": "5–15"},
            {"claim": "10-year warranty", "path": "products[home-battery].specs.warranty_years", "value": "10"}],
    }, ensure_ascii=False)

def test_run_generate_writes_valid_draft(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    p = Path(res["path"])
    assert p == repo / "content" / "drafts" / "battery-sizing.md"
    text = p.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["status"] == "draft" and fm["validation"] == "passed"
    assert fm["playbook_week"] == 1 and fm["brand_version"] == 1 and fm["created"] == "2026-08-16"
    assert "未经研究校准" not in text and "## Suggested JSON-LD" in text
    assert res["validation"] == "passed"

def test_run_generate_requires_playbook(tmp_path):
    repo = _mini_repo(tmp_path)
    (repo / "knowledge" / "playbook.md").unlink()
    with pytest.raises(SystemExit, match="playbook"):
        run_generate("t", chat_fn=_chat_ok, repo=repo)

def test_run_generate_allow_no_playbook_marks_draft(tmp_path):
    repo = _mini_repo(tmp_path)
    (repo / "knowledge" / "playbook.md").unlink()
    res = run_generate("battery sizing", allow_no_playbook=True, chat_fn=_chat_ok,
                       repo=repo, today="2026-08-16")
    text = Path(res["path"]).read_text(encoding="utf-8")
    assert "未经研究校准" in text
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["playbook_week"] is None

def test_run_generate_no_kimi_skeleton(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_generate("battery sizing", kimi=False, repo=repo, today="2026-08-16")
    assert Path(res["path"]).exists() and res["validation"] == "flagged"   # 骨架无 anchors → flagged

def test_run_review_and_publish(tmp_path):
    repo = _mini_repo(tmp_path)
    res = run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    slug = "battery-sizing"
    out = run_review(slug, "pass", notes="事实核对通过", repo=repo, now="2026-08-16T12:00:00")
    reviews = [json.loads(l) for l in (repo / "content" / "reviews.jsonl").read_text(encoding="utf-8").splitlines()]
    assert reviews[-1] == {"slug": slug, "verdict": "pass", "notes": "事实核对通过",
                           "ts": "2026-08-16T12:00:00", "brand_version": 1, "playbook_week": 1}
    run_mark_published(slug, repo=repo)
    assert (repo / "content" / "published" / f"{slug}.md").exists()
    assert not (repo / "content" / "drafts" / f"{slug}.md").exists()
    fm = yaml.safe_load((repo / "content" / "published" / slug).with_suffix(".md").read_text(encoding="utf-8").split("---")[1])
    assert fm["status"] == "published"

def test_run_review_reject_marks_status(tmp_path):
    repo = _mini_repo(tmp_path)
    run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    run_review("battery-sizing", "reject", repo=repo, now="2026-08-16T12:00:00")
    fm = yaml.safe_load((repo / "content" / "drafts" / "battery-sizing.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["status"] == "rejected"

def test_run_review_unknown_slug_lists_existing(tmp_path, capsys):
    repo = _mini_repo(tmp_path)
    run_generate("battery sizing", chat_fn=_chat_ok, repo=repo, today="2026-08-16")
    with pytest.raises(SystemExit):
        run_review("nope", "pass", repo=repo, now="2026-08-16T12:00:00")
    assert "battery-sizing" in capsys.readouterr().out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_run.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 `src/geo/generate/run.py`**

```python
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
        print(f"草稿不存在: {slug}；现有: {existing}", file=sys.stderr)
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
    pub_dir = repo / "content" / "published"
    pub_dir.mkdir(parents=True, exist_ok=True)
    text = draft.read_text(encoding="utf-8")
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
```

> 注意 `run_generate` 里 `validate_draft({**draft, "frontmatter": {**fm}}, brand)`——把机器 frontmatter 并进 draft 后整体核验（frontmatter 检查项因此测得到 created/brand_version）。
> `--no-kimi` 时 `skeleton_draft` 的 `fact_anchors=[]` 且 body 含规格表数字 → 数字归属可过、anchor 缺 → flagged（exit 2）符合设计（骨架仅用于链路烟雾）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_run.py -v`
Expected: 7 PASS

- [ ] **Step 5: 全量回归**

Run: `cd geo-agent && python3.11 -m pytest tests/ -q`
Expected: 既有 186+ 全绿 + 新增 ~30 全绿

- [ ] **Step 6: Commit**

```bash
git add geo-agent/src/geo/generate/run.py geo-agent/tests/test_generate_run.py
git commit -m "feat(generate): CLI orchestration (topic/suggest/review/publish-archive/bootstrap)"
```

---

### Task 9: live smoke + 真跑准备（P1 live 补跑由操作者执行）

**Files:**
- Create: `geo-agent/tests/test_generate_live.py`

**Interfaces:**
- Consumes: `run_generate`（真 Kimi）+ fixture mini-repo
- Produces: `@pytest.mark.live` 冒烟（真 Kimi + fixture playbook + 真 `knowledge/brand.yaml` 若存在则用之、否则 fixture brand）

- [ ] **Step 1: 写 live 测试**

```python
# tests/test_generate_live.py
import json, shutil
from pathlib import Path
import pytest
from geo.generate.run import run_generate

FIX = Path(__file__).parent / "fixtures" / "generate"

@pytest.mark.live
def test_live_generate_real_kimi(tmp_path):
    """真 Kimi K3 生成一篇。手动跑: python3.11 -m pytest -m live tests/test_generate_live.py -v
    需网络 + 有效 Moonshot key。只验链路通，不判文本质量（人审验收另做）。"""
    repo = tmp_path
    shutil.copytree(FIX / "knowledge", repo / "knowledge")
    res = run_generate("How to size a home battery", "guide", chat_fn=None, repo=repo,
                       today="2026-08-16")
    text = Path(res["path"]).read_text(encoding="utf-8")
    assert "## Suggested JSON-LD" in text and "事实核对清单" in text
    assert res["validation"] in ("passed", "flagged")   # flagged 也算链路通
```

- [ ] **Step 2: 验证默认收集但跳过**

Run: `cd geo-agent && python3.11 -m pytest tests/test_generate_live.py -v`
Expected: SKIPPED（live requires -m live）

- [ ] **Step 3: 确定性全量回归 + 确认 live 默认跳过**

Run: `cd geo-agent && python3.11 -m pytest tests/ -q`
Expected: 全绿，live 测试 skipped

- [ ] **Step 4: Commit**

```bash
git add geo-agent/tests/test_generate_live.py
git commit -m "test(generate): live smoke (real Kimi, human-audit gate)"
```

- [ ] **Step 5: 真跑验收（操作者，合并后）——spec §8.2 顺序**

1. 补跑 P1 live：`python3.11 -m geo.research.run --week 1`（需代理+Moonshot key；产真 playbook + 人审 P1 验收）
2. `python3.11 -m geo.generate.run --bootstrap-brand` → 校验 0 违规 → **人审定稿** → `git add geo-agent/knowledge/brand.yaml && git commit`
3. `python3.11 -m geo.generate.run --week 1 --suggest` 挑题
4. `python3.11 -m geo.generate.run --week 1 --topic "..." --page-type guide`（真 playbook + 真 brand）
5. 人审三档：`--review <slug> --verdict pass|minor|reject --notes "..."`；pass/minor → 人手动发 site/ → `--mark-published <slug>`
6. 达标线：至少一篇 pass 且 `validation: passed`

---

## Self-Review (completed by plan author)

**Spec coverage:** §2 brand.yaml（Task 1 加载/Task 2 校验/Task 3 bootstrap）✓；§3 五模块（brand=1-3、topics=4、kimi=5-6、validate=7、run=8）✓；§4 生成流程（playbook 摘要=Task 5、fact_anchors=Task 6、降级=Task 8）✓；§5 草稿契约+四项核验（Task 7+8）✓；§6 人审/CLI/bootstrap 命令（Task 8）✓；§7 错误处理（playbook 拒跑=Task 8、Kimi 两次失败=Task 6、flagged 标红=Task 7/8、suggest 缺源=Task 4、slug 不存在=Task 8）✓；§8 测试策略（确定性/mock/live/人审路径=Task 9 Step 5）✓。
**Placeholder scan:** 无 TBD/TODO；Task 3 Step 2 的 fixture 覆写风险已给出 tmp_path 解决方案并写成硬要求；Task 7 的 sorted 陷阱已给修正代码。✓
**Type consistency:** `parse_claims -> list[tuple[frozenset,str]]`（Task 2 定义，Task 7 消费）✓；`validate_brand(brand, sources_text) -> list[str]`（Task 2 定义，Task 3 消费）✓；draft dict 键 `frontmatter/title/body_md/json_ld/fact_anchors`（Task 6 产、Task 7/8 消费）✓；`ValidationResult.ok/issues/appendix_md`（Task 7 产、Task 8 消费）✓；`run_generate` 返回键 Task 8 内自洽 ✓。
**已知实现期注意项（非阻塞）:** ① Task 2 `_KEYVAL_RE` 的 `{0,25}` 跨距需对真 brand.yaml 调（en-dash 值 "5–15" 已在 _norm 归一为 "-"）；② Task 8 `_fm_update` 假设草稿形如 `---\nyaml\n---\n正文`（split("---") 三段），附录注释内若出现 "---" 会破坏重解析——附录用 `<!-- ... -->` 包裹且内容为表格，无 "---"，安全；③ reviews.jsonl 无锁并发写不在范围（单人 CLI 场景）。
