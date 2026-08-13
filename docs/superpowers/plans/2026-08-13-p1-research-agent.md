# P1 Research Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone research agent (`src/geo/research/`) that turns w1's collected L1/L2/L3 + GSC queries into `knowledge/playbook.md` + `knowledge/platform-profiles.md` via a deterministic feature-aggregation backbone and a bounded Kimi K3 synthesis + web-search verification layer.

**Architecture:** Six modules under `src/geo/research/` (corpus → sample → features → [kimi.synthesis ∥ kimi.web_search] → render), orchestrated by a CLI (`run.py`). The deterministic backbone (corpus/sample-selection/features/render) is golden-tested; the Kimi layer is mock-tested for prompt/parse/fallback and human-audited for text quality. DAG integration is deferred (module is standalone-invocable now).

**Tech Stack:** Python 3.11 · OpenAI SDK → Moonshot `kimi-k3` (analysis layer) · reuse `fetcher.fetch_source` + `meta_llm` pattern · Jinja2-free plain-string rendering · pytest (system `python3.11`).

## Global Constraints

- **Python/runtime**: system `python3.11` (editable `geo` importable from project root; `geo-agent/.venv` is path-restricted for the main agent — never invoke `.venv/bin/python`). Run tests with `cd geo-agent && python3.11 -m pytest <path> -v`.
- **Network**: Kimi API calls + URL fetches need `dangerouslyDisableSandbox`; Clash proxy `127.0.0.1:7890` must be up.
- **Kimi K3 invariants**: model id literal `"kimi-k3"`; `temperature=1` MANDATORY (kimi-k3 rejects 0 → 400); `response_format={"type":"json_object"}` for synthesis; client = `OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url)`.
- **Non-blocking Kimi**: synthesize/web_search failures must fall back to deterministic aggregates, never crash the pipeline.
- **Test split**: deterministic modules → unit + golden; Kimi modules → mock (injectable call seam) + `@pytest.mark.live` smoke that is SKIPPED in CI.
- **git**: branch `p1-research-agent`; NEVER `git add -A` (root `.venv/` is untracked & not gitignored — would commit 49MB); always `git add <explicit path>`. Every commit message ends with:
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```
- **Honesty**: feature aggregates report observational prevalence only, never causal claims; every conclusion carries `sample_n`; insufficient samples (`<5`) flagged `low_confidence`; unverifiable external facts marked `外部未验证`, never fabricated.

---

## File Structure

**Create** (all under `geo-agent/src/geo/research/`):
| File | Responsibility |
|---|---|
| `__init__.py` | package marker |
| `models.py` | research-only dataclasses: `ResearchItem`, `Coverage`, `ResearchCorpus`, `FeatureBucket`, `FeatureAggregates`, `PlaybookConclusion`, `FetchStats` |
| `corpus.py` | `build_corpus(week, repo=REPO) -> ResearchCorpus` — join L1(+L2)+L3+GSC+prompts |
| `sample.py` | `select_topn(corpus, n, brand_host) -> list[str]` (deterministic) + `fetch_topn(urls) -> FetchStats` |
| `features.py` | `aggregate(corpus) -> FeatureAggregates` — 4 buckets + sample tags |
| `kimi.py` | `_kimi_chat(messages, tools=None)` seam + `synthesize(...)` + `web_search_verify(...)` |
| `render.py` | `render_playbook(...)` + `render_profiles(...)` → markdown str |
| `run.py` | `run_research(week, kimi_enabled=True)` + `__main__` CLI |

**Create tests** (under `geo-agent/tests/`):
- `test_research_models.py`, `test_corpus.py`, `test_sample.py`, `test_features.py`, `test_kimi.py`, `test_render.py`, `test_run.py`
- `fixtures/research/` — small synthetic L1 JSONs + L3 meta.json + gsc.json + prompts.csv

**Read-only reuse** (do not modify): `shared/models.py` (L1Record/L2Record/CitedSource/L3Source/PromptRow), `shared/storage.py` (`sha1_url`, `source_dir`, `l1_path`, `snapshot_dir`, `REPO`), `shared/config.py` (`settings`), `fetch/fetcher.py` (`fetch_source`), `fetch/meta_llm.py` (pattern only).

---

## Task 1: Scaffold research package + data models

**Files:**
- Create: `geo-agent/src/geo/research/__init__.py`, `geo-agent/src/geo/research/models.py`
- Test: `geo-agent/tests/test_research_models.py`

**Interfaces:**
- Produces: `ResearchItem`, `Coverage`, `ResearchCorpus`, `FeatureBucket`, `FeatureAggregates`, `PlaybookConclusion`, `FetchStats` (dataclasses). These names/types are consumed by every later task.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_research_models.py
from geo.research.models import (ResearchItem, Coverage, ResearchCorpus, FeatureBucket,
    FeatureAggregates, PlaybookConclusion, FetchStats)
from geo.shared.models import L1Record, L2Record, CitedSource, PromptRow

def test_researchcorpus_roundtrip():
    l1 = L1Record(week=1, model="qwen", prompt_id="C01", run=1, answer="x",
                  l2=L2Record(cited_sources=[CitedSource(position=1, url="https://a.com")]),
                  ts_iso="2026-08-13T00:00:00Z", prompt_set_version="abc")
    prompt = PromptRow(id="C01", category="comparison", prompt="q", market="EU", intent="comparison", core=True)
    item = ResearchItem(l1=l1, prompt=prompt, sources=[(l1.l2.cited_sources[0], None)])
    cov = Coverage(total_l1=1, total_cited_sources=1, l3_resolved=0, l3_missing=1, l3_js_only=0)
    corpus = ResearchCorpus(week=1, items=[item], gsc_queries=["hestia solar"], coverage=cov)
    assert corpus.coverage.total_cited_sources == 1

def test_featurebucket_low_confidence_flag():
    b = FeatureBucket(key="comparison_table", cited_n=2, sample_n=3, platforms=["qwen"], low_confidence=True)
    assert b.low_confidence is True

def test_playbookconclusion_fields():
    c = PlaybookConclusion(id="F01", category="format", conclusion="对比表常见", sample_n=45,
                           cited_n=12, platforms=["qwen","zhipu"], confidence="high",
                           action="多用对比表", examples=["https://a.com"])
    assert c.category == "format" and c.confidence == "high"

def test_fetchstats():
    f = FetchStats(requested=40, fetched=35, failed=3, js_only=2)
    assert f.fetched == 35
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd geo-agent && python3.11 -m pytest tests/test_research_models.py -v`
Expected: FAIL — `ModuleNotFoundError: geo.research.models`

- [ ] **Step 3: Write minimal implementation**

```python
# src/geo/research/__init__.py
```

```python
# src/geo/research/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from geo.shared.models import L1Record, PromptRow, CitedSource, L3Source

@dataclass
class ResearchItem:
    l1: L1Record
    prompt: PromptRow
    sources: list[tuple[CitedSource, L3Source | None]]

@dataclass
class Coverage:
    total_l1: int
    total_cited_sources: int
    l3_resolved: int
    l3_missing: int
    l3_js_only: int

@dataclass
class ResearchCorpus:
    week: int
    items: list[ResearchItem]
    gsc_queries: list[str]
    coverage: Coverage

@dataclass
class FeatureBucket:
    key: str
    cited_n: int
    sample_n: int
    platforms: list[str]
    low_confidence: bool

@dataclass
class FeatureAggregates:
    week: int
    coverage: Coverage
    formats: list[FeatureBucket]                 # 对比表/Q&A/清单/定义段/规格卡
    sources: dict                                # §3.2 distribution: {domain_type:{...}, page_type:{...}, ...}
    platforms: dict                              # per-platform: {model:{mention,citation,sov,...}}
    problem_space: dict                          # {intent_clusters:[...], topic_gaps:[...]}

@dataclass
class PlaybookConclusion:
    id: str
    category: str        # format|source|platform|problem_space
    conclusion: str
    sample_n: int
    cited_n: int | None
    platforms: list[str]
    confidence: str      # high|mid|low
    action: str
    examples: list[str]

@dataclass
class FetchStats:
    requested: int
    fetched: int
    failed: int
    js_only: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd geo-agent && python3.11 -m pytest tests/test_research_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/research/__init__.py geo-agent/src/geo/research/models.py geo-agent/tests/test_research_models.py
git commit -m "feat(research): scaffold package + data models"
```

---

## Task 2: Test fixtures + corpus.build_corpus

**Files:**
- Create: `geo-agent/tests/fixtures/research/input/prompts.csv`, `geo-agent/tests/fixtures/research/data/raw/w1/qwen/C01/r1.json`, `geo-agent/tests/fixtures/research/data/sources/<sha1>/meta.json`, `geo-agent/tests/fixtures/research/data/snapshots/w1/gsc.json`
- Create: `geo-agent/src/geo/research/corpus.py`
- Test: `geo-agent/tests/test_corpus.py`

**Interfaces:**
- Consumes: `shared.storage.sha1_url`, `REPO`; `shared.models` records. `build_corpus` reads `repo/data/raw/w{N}/**/r*.json`, `repo/data/sources/<sha1[:12]>/meta.json`, `repo/data/snapshots/w{N}/gsc.json`, `repo/input/prompts.csv`.
- Produces: `build_corpus(week: int, repo: Path = REPO) -> ResearchCorpus`.

> **Fixture layout rule**: the fixture dir IS a mini-repo — paths mirror a real `geo-agent/` (`data/raw/...`, `data/sources/...`, `data/snapshots/...`, `input/...`). All `build_corpus`/`select_topn`/`run_research` tests pass `repo=<FIX or tmp>` explicitly; never monkeypatch module-level `REPO`.

- [ ] **Step 1: Create fixtures**

`tests/fixtures/research/input/prompts.csv`:
```csv
id,category,prompt,market,intent,core
C01,comparison,Top residential solar companies in Europe 2026,EU,comparison,1
M03,comparison,Alternatives to Tesla Powerwall for home storage,EU,comparison,1
```

`tests/fixtures/research/data/raw/w1/qwen/C01/r1.json` (an L1Record with embedded L2; cited url `https://www.cnet.com/x`):
```json
{"week":1,"model":"qwen","prompt_id":"C01","run":1,"answer":"Brand X leads...","l2":{"cited_sources":[{"position":1,"url":"https://www.cnet.com/x","title":"Best Solar","extract_method":"structured"}],"mentioned":false,"cited_with_link":false,"citation_position":null,"sentiment":"neu","competitors_mentioned":["Tesla"],"low_confidence":false},"usage":{},"elapsed_s":1.0,"search_triggered":true,"ts_iso":"2026-08-13T00:00:00Z","prompt_set_version":"abc"}
```

Compute the sha1[:12] of `https://www.cnet.com/x` (deterministic: `hashlib.sha1(url.encode()).hexdigest()[:12]`). Create `tests/fixtures/research/data/sources/<that_sha1>/meta.json`:
```json
{"url":"https://www.cnet.com/x","sha1":"<full>","http_status":200,"text":"...","structural":{"canonical":"https://www.cnet.com/x","title":"Best Solar","meta_desc":"d","schema_types":["Article"],"h_counts":{"h1":1,"h2":2,"h3":0,"h4":0,"h5":0,"h6":0},"table_count":1,"ul_count":0},"semantic":{"page_type":"review","has_definition_segment":false,"has_faq_block":false,"datapoint_count":5,"has_author_byline":true,"has_publish_date":true,"cites_external_sources":true},"js_only":false,"fetched_iso":"2026-08-13T00:00:00Z"}
```

`tests/fixtures/research/data/snapshots/w1/gsc.json`:
```json
{"week":1,"rule_version":"geo-seo-v1","site":"sc-domain:sunhestia.com","rows":[{"keys":["hestia solar"],"clicks":0,"impressions":1,"ctr":0,"position":47}],"degraded":false}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_corpus.py
from pathlib import Path
from geo.research.corpus import build_corpus
import json, hashlib

FIX = Path(__file__).parent / "fixtures" / "research"

def test_build_corpus_joins_and_counts():
    corpus = build_corpus(1, repo=FIX)
    assert corpus.week == 1
    assert len(corpus.items) == 1
    it = corpus.items[0]
    assert it.l1.prompt_id == "C01"
    assert it.prompt.category == "comparison"
    assert len(it.sources) == 1
    cited, l3 = it.sources[0]
    assert cited.url == "https://www.cnet.com/x"
    assert l3 is not None and l3.structural["table_count"] == 1   # L3 resolved
    assert corpus.coverage.total_l1 == 1
    assert corpus.coverage.total_cited_sources == 1
    assert corpus.coverage.l3_resolved == 1
    assert corpus.gsc_queries == ["hestia solar"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd geo-agent && python3.11 -m pytest tests/test_corpus.py -v`
Expected: FAIL — `build_corpus` not defined / import error.

- [ ] **Step 4: Write minimal implementation**

```python
# src/geo/research/corpus.py
from __future__ import annotations
import json
from pathlib import Path
from geo.shared.config import REPO
from geo.shared.models import L1Record, L2Record, CitedSource, L3Source, PromptRow
from geo.shared.storage import sha1_url
from geo.research.models import ResearchItem, ResearchCorpus, Coverage

def _iter_l1(week: int, repo: Path) -> list[L1Record]:
    base = repo / "data" / "raw" / f"w{week}"
    out = []
    if not base.exists(): return out
    for p in sorted(base.rglob("r*.json")):
        out.append(L1Record(**json.loads(p.read_text(encoding="utf-8"))))
    return out

def _load_prompts(repo: Path) -> dict[str, PromptRow]:
    import csv
    rows = {}
    with (repo / "input" / "prompts.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["id"]] = PromptRow(id=r["id"], category=r["category"], prompt=r["prompt"],
                                      market=r["market"], intent=r["intent"], core=r["core"]=="1" or r["core"].lower()=="true")
    return rows

def _load_l3(url: str, repo: Path) -> L3Source | None:
    d = repo / "data" / "sources" / sha1_url(url)[:12]
    mp = d / "meta.json"
    if not mp.exists(): return None
    l3 = L3Source(**json.loads(mp.read_text(encoding="utf-8")))
    return None if l3.js_only else l3

def _load_gsc_queries(week: int, repo: Path) -> list[str]:
    gp = repo / "data" / "snapshots" / f"w{week}" / "gsc.json"
    if not gp.exists(): return []
    data = json.loads(gp.read_text(encoding="utf-8"))
    return [k for row in data.get("rows", []) for k in row.get("keys", [])]

def build_corpus(week: int, repo: Path = REPO) -> ResearchCorpus:
    prompts = _load_prompts(repo)
    l1s = _iter_l1(week, repo)
    items, resolved, missing, js, total_cited = [], 0, 0, 0, 0
    for l1 in l1s:
        src_pairs = []
        for cited in l1.l2.cited_sources:
            total_cited += 1
            l3 = _load_l3(cited.url, repo)
            if l3 is None:
                missing += 1
            elif l3.js_only:
                js += 1
            else:
                resolved += 1
            src_pairs.append((cited, l3))
        p = prompts.get(l1.prompt_id, PromptRow(id=l1.prompt_id, category="?", prompt="", market="", intent="?", core=False))
        items.append(ResearchItem(l1=l1, prompt=p, sources=src_pairs))
    cov = Coverage(total_l1=len(l1s), total_cited_sources=total_cited,
                   l3_resolved=resolved, l3_missing=missing, l3_js_only=js)
    return ResearchCorpus(week=week, items=items, gsc_queries=_load_gsc_queries(week, repo), coverage=cov)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd geo-agent && python3.11 -m pytest tests/test_corpus.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add geo-agent/src/geo/research/corpus.py geo-agent/tests/test_corpus.py geo-agent/tests/fixtures/research/
git commit -m "feat(research): corpus builder joining L1/L2/L3/GSC/prompts"
```

---

## Task 3: sample.select_topn + fetch_topn

**Files:**
- Create: `geo-agent/src/geo/research/sample.py`
- Test: `geo-agent/tests/test_sample.py`

**Interfaces:**
- Consumes: `ResearchCorpus`, `fetcher.fetch_source`, `storage.source_dir`.
- Produces: `select_topn(corpus, n=40, brand_host="sunhestia.com", repo=REPO) -> list[str]`; `fetch_topn(urls) -> FetchStats`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sample.py
from geo.research.sample import select_topn
from geo.research.corpus import build_corpus
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "research"

def _corpus():
    return build_corpus(1, repo=FIX)

def test_select_topn_ranks_external_excludes_brand(tmp_path):
    # tmp_path has no sources dir → url not yet fetched → returned
    urls = select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=tmp_path)
    assert urls == ["https://www.cnet.com/x"]

def test_select_topn_caps_at_n(tmp_path):
    assert len(select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=tmp_path)) <= 40

def test_select_topn_excludes_already_fetched():
    # FIX has the source meta.json → already fetched → excluded
    assert select_topn(_corpus(), n=40, brand_host="sunhestia.com", repo=FIX) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd geo-agent && python3.11 -m pytest tests/test_sample.py -v`
Expected: FAIL — `select_topn` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/geo/research/sample.py
from __future__ import annotations
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from geo.shared.config import REPO
from geo.shared.storage import sha1_url
from geo.research.models import ResearchCorpus, FetchStats

def _already_fetched(url: str, repo: Path) -> bool:
    return (repo / "data" / "sources" / sha1_url(url)[:12] / "meta.json").exists()

def select_topn(corpus: ResearchCorpus, n: int = 40, brand_host: str = "sunhestia.com", repo: Path = REPO) -> list[str]:
    freq = Counter()
    for it in corpus.items:
        for cited, _ in it.sources:
            host = urlparse(cited.url).hostname or ""
            if not host or host.endswith(brand_host):
                continue
            freq[cited.url] += 1
    ranked = [u for u, _ in freq.most_common()]
    return [u for u in ranked[:n] if not _already_fetched(u, repo)]

def fetch_topn(urls: list[str]) -> FetchStats:
    from geo.fetch.fetcher import fetch_source
    fetched = failed = js = 0
    for u in urls:
        try:
            fetch_source(u)
            fetched += 1
        except Exception:
            failed += 1
    return FetchStats(requested=len(urls), fetched=fetched, failed=failed, js_only=js)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd geo-agent && python3.11 -m pytest tests/test_sample.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/research/sample.py geo-agent/tests/test_sample.py
git commit -m "feat(research): tiered-sample URL selection + fetch wrapper"
```

---

## Task 4: features.aggregate (4 buckets + sample tags, golden)

**Files:**
- Create: `geo-agent/src/geo/research/features.py`
- Test: `geo-agent/tests/test_features.py`

**Interfaces:**
- Consumes: `ResearchCorpus`, `L3Source` field names (`structural.table_count/ul_count/schema_types/h_counts`, `semantic.has_faq_block/has_definition_segment/page_type/datapoint_count`).
- Produces: `aggregate(corpus) -> FeatureAggregates`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features.py
from geo.research.corpus import build_corpus
from geo.research.features import aggregate, LOW_CONF_THRESHOLD
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "research"

def _corpus():
    return build_corpus(1, repo=FIX)

def test_aggregate_formats_bucket_counts():
    agg = aggregate(_corpus())
    keys = {b.key for b in agg.formats}
    assert {"comparison_table","qa","list","definition","spec_card"} <= keys
    tbl = next(b for b in agg.formats if b.key == "comparison_table")
    assert tbl.cited_n == 1 and tbl.sample_n == 1          # fixture: 1 cited source w/ table
    assert tbl.low_confidence is True                       # sample_n=1 < threshold(5)

def test_aggregate_platforms_metrics():
    agg = aggregate(_corpus())
    assert "qwen" in agg.platforms
    assert agg.platforms["qwen"]["n"] == 1

def test_aggregate_problem_space_has_intents():
    agg = aggregate(_corpus())
    assert any(c["intent"] == "comparison" for c in agg.problem_space["intent_clusters"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd geo-agent && python3.11 -m pytest tests/test_features.py -v`
Expected: FAIL — `aggregate` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/geo/research/features.py
from __future__ import annotations
from collections import Counter, defaultdict
from geo.research.models import ResearchCorpus, FeatureAggregates, FeatureBucket

LOW_CONF_THRESHOLD = 5

def _low(n: int) -> bool:
    return n < LOW_CONF_THRESHOLD

def _domain_type(host: str) -> str:
    # coarse classifier; P2+ authority deferred → 'unknown'
    h = (host or "").lower()
    if any(w in h for w in ("wikipedia.","wikimedia.")): return "wiki"
    if any(w in h for w in ("reddit.","forum.","community.")): return "ugc_forum"
    if any(w in h for w in ("news.","cnet.","techcrunch.","theverge.")): return "news_review"
    if any(w in h for w in ("tesla.","enphase.","solaredge.","byd.","sonnen.","lg.","bluetti.")): return "manufacturer"
    return "other"

def aggregate(corpus: ResearchCorpus) -> FeatureAggregates:
    platforms = defaultdict(lambda: {"n":0,"mention":0,"cited":0})
    intent_hits = Counter()
    fmt = {k: {"cited":0,"plats":set()} for k in
           ["comparison_table","qa","list","definition","spec_card"]}
    src_dim = {"domain_type":Counter(),"page_type":Counter(),"schema":Counter(),
               "has_publish_date":0,"ugc":0,"resolved":0}
    resolved_n = 0

    for it in corpus.items:
        m = it.l1.model
        platforms[m]["n"] += 1
        if it.l1.l2.mentioned: platforms[m]["mention"] += 1
        if it.l1.l2.cited_with_link: platforms[m]["cited"] += 1
        intent_hits[it.prompt.intent] += 1
        for cited, l3 in it.sources:
            if l3 is None: continue
            resolved_n += 1
            st, se = l3.structural or {}, l3.semantic or {}
            if st.get("table_count",0)>0: fmt["comparison_table"]["cited"]+=1; fmt["comparison_table"]["plats"].add(m)
            if se.get("has_faq_block"): fmt["qa"]["cited"]+=1; fmt["qa"]["plats"].add(m)
            if st.get("ul_count",0)>0: fmt["list"]["cited"]+=1; fmt["list"]["plats"].add(m)
            if se.get("has_definition_segment"): fmt["definition"]["cited"]+=1; fmt["definition"]["plats"].add(m)
            if se.get("page_type")=="product" or se.get("datapoint_count",0)>=8:
                fmt["spec_card"]["cited"]+=1; fmt["spec_card"]["plats"].add(m)
            from urllib.parse import urlparse
            src_dim["domain_type"][_domain_type(urlparse(cited.url).hostname)] += 1
            src_dim["page_type"][se.get("page_type","unknown")] += 1
            for s in st.get("schema_types",[]): src_dim["schema"][s] += 1
            if se.get("has_publish_date"): src_dim["has_publish_date"] += 1

    formats = [FeatureBucket(k, v["cited"], resolved_n, sorted(v["plats"]), _low(resolved_n))
               for k,v in fmt.items()]
    # convert Counters to plain dict for JSON stability
    src_dim = {k:(dict(v) if isinstance(v,Counter) else v) for k,v in src_dim.items()}
    plats = {m:{"n":d["n"],"mention_rate":round(d["mention"]/d["n"],3) if d["n"] else 0.0,
                "citation_rate":round(d["cited"]/d["n"],3) if d["n"] else 0.0} for m,d in platforms.items()}
    covered_intents = {it.prompt.intent for it in corpus.items}
    topic_gaps = [q for q in corpus.gsc_queries if q not in covered_intents]  # coarse gap heuristic
    return FeatureAggregates(week=corpus.week, coverage=corpus.coverage, formats=formats,
        sources=src_dim, platforms=plats,
        problem_space={"intent_clusters":[{"intent":k,"n":v} for k,v in intent_hits.items()],
                       "topic_gaps":topic_gaps})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd geo-agent && python3.11 -m pytest tests/test_features.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/research/features.py geo-agent/tests/test_features.py
git commit -m "feat(research): deterministic feature aggregation (4 buckets + sample tags)"
```

---

## Task 5: kimi._kimi_chat seam + synthesize (mock-tested)

**Files:**
- Create: `geo-agent/src/geo/research/kimi.py`
- Test: `geo-agent/tests/test_kimi.py`

**Interfaces:**
- Consumes: `settings.moonshot_*`, `FeatureAggregates`.
- Produces: `_kimi_chat(messages, tools=None, timeout=120) -> str`; `synthesize(aggregates, examples, *, chat_fn=_kimi_chat) -> list[PlaybookConclusion]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kimi.py
import json
from geo.research.kimi import synthesize
from geo.research.models import FeatureAggregates, Coverage, FeatureBucket

def _agg():
    return FeatureAggregates(week=1, coverage=Coverage(1,1,1,0,0),
        formats=[FeatureBucket("comparison_table",1,1,["qwen"],True)],
        sources={"domain_type":{"manufacturer":1},"page_type":{"review":1},"schema":{"Article":1},
                 "has_publish_date":1,"ugc":0,"resolved":1},
        platforms={"qwen":{"n":1,"mention_rate":0.0,"citation_rate":0.0}},
        problem_space={"intent_clusters":[{"intent":"comparison","n":1}],"topic_gaps":[]})

def test_synthesize_parses_good_json():
    good = json.dumps({"conclusions":[
        {"id":"F01","category":"format","conclusion":"对比表常见","sample_n":1,"cited_n":1,
         "platforms":["qwen"],"confidence":"low","action":"多用对比表","examples":["https://a.com"]}]})
    fake = lambda messages, tools=None, timeout=120: good
    out = synthesize(_agg(), examples=[], chat_fn=fake)
    assert len(out)==1 and out[0].id=="F01" and out[0].confidence=="low"

def test_synthesize_bad_json_returns_empty():
    fake = lambda messages, tools=None, timeout=120: "not json{"
    assert synthesize(_agg(), examples=[], chat_fn=fake) == []

def test_synthesize_preserves_sample_n_no_invent():
    # conclusion sample_n must come from aggregates (1), not invented
    good = json.dumps({"conclusions":[{"id":"F01","category":"format","conclusion":"x",
        "sample_n":999,"cited_n":1,"platforms":[],"confidence":"low","action":"y","examples":[]}]})
    fake = lambda messages, tools=None, timeout=120: good
    out = synthesize(_agg(), examples=[], chat_fn=fake)
    # synthesize MUST clamp sample_n to the aggregate's resolved sample_n, refusing invented 999
    assert out[0].sample_n == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd geo-agent && python3.11 -m pytest tests/test_kimi.py -v`
Expected: FAIL — `synthesize` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/geo/research/kimi.py
from __future__ import annotations
import json, logging
from geo.shared.config import settings
from geo.research.models import FeatureAggregates, PlaybookConclusion

log = logging.getLogger("research.kimi")
_SYS_SYNTH = (
    "你是 GEO 研究 agent。只能依据所给的 FeatureAggregates（JSON）与少量真实回答片段归纳结论。"
    "输出 JSON {conclusions:[{id,category(format|source|platform|problem_space),conclusion,"
    "sample_n,cited_n,platforms,confidence(high|mid|low),action,examples[]}]}。"
    "纪律：sample_n 必须等于所给数据，不得改写或杜撰；不得编造 URL；低样本标 low。"
)

def _kimi_chat(messages: list[dict], tools: list | None = None, timeout: int = 120) -> str:
    from openai import OpenAI
    c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=timeout)
    kwargs = dict(model="kimi-k3", messages=messages, temperature=1)  # kimi-k3 强制 temp=1
    if tools: kwargs["tools"] = tools
    if not tools: kwargs["response_format"] = {"type": "json_object"}
    r = c.chat.completions.create(**kwargs)
    return r.choices[0].message.content or ""

def synthesize(aggregates: FeatureAggregates, examples: list[dict], *, chat_fn=_kimi_chat) -> list[PlaybookConclusion]:
    user = "AGGREGATES:\n" + json.dumps(_agg_to_dict(aggregates), ensure_ascii=False) + \
           "\nEXAMPLES:\n" + json.dumps(examples[:5], ensure_ascii=False)
    try:
        raw = chat_fn([{"role":"system","content":_SYS_SYNTH},{"role":"user","content":user}])
        data = json.loads(raw)
    except Exception as e:
        log.warning("synthesize failed (%s); returning []", e)
        return []
    sample_bound = aggregates.coverage.l3_resolved or 0
    out = []
    for c in data.get("conclusions", []):
        try:
            sn = int(c.get("sample_n", 0))
            if sn > sample_bound: sn = sample_bound      # refuse invented sample_n
            out.append(PlaybookConclusion(
                id=c["id"], category=c.get("category",""), conclusion=c.get("conclusion",""),
                sample_n=sn, cited_n=c.get("cited_n"), platforms=c.get("platforms",[]),
                confidence=c.get("confidence","low"), action=c.get("action",""),
                examples=c.get("examples",[])))
        except Exception as e:
            log.warning("skip malformed conclusion %r: %s", c, e)
    return out

def _agg_to_dict(a: FeatureAggregates) -> dict:
    return {"week":a.week,"coverage":a.coverage.__dict__,
            "formats":[b.__dict__ for b in a.formats],"sources":a.sources,
            "platforms":a.platforms,"problem_space":a.problem_space}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd geo-agent && python3.11 -m pytest tests/test_kimi.py -v`
Expected: PASS (3 tests). Note: `FeatureBucket`/`Coverage` are dataclasses — `.__dict__` works; if not, the test still passes because `_agg_to_dict` is only exercised via the fake chat_fn (we assert on parsed output, not the dict).

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/research/kimi.py geo-agent/tests/test_kimi.py
git commit -m "feat(research): Kimi synthesis seam + sample-n clamp (mock-tested)"
```

---

## Task 6: kimi.web_search_verify (Moonshot web_search, Tier1+2)

**Files:**
- Modify: `geo-agent/src/geo/research/kimi.py` (add `web_search_verify`)
- Test: `geo-agent/tests/test_kimi.py` (append)

**Interfaces:**
- Produces: `web_search_verify(items: list[dict], *, chat_fn=_kimi_chat) -> dict` where items e.g. `[{"platform":"Qwen","fact":"crawler_user_agent"}, ...]`; returns `{platform:{fact:value, sources:[...], confidence:"..."}}`.

> **Impl-time verify (spec §11):** Moonshot web_search tool schema. Expected shape (verify against https://platform.moonshot.cn/docs): `tools=[{"type":"builtin_tools","tools":[{"type":"web_search"}]}]`. If the API rejects, fall back to the documented `$web_search` function-call tool. Keep `_kimi_chat`'s `tools` param as the single seam so the schema lives in one place.

- [ ] **Step 1: Write the failing test** (append to test_kimi.py)

```python
from geo.research.kimi import web_search_verify

def test_web_search_verify_parses_answer_block():
    raw = ("根据联网搜索，Qwen 的网页检索后端为阿里云搜索，公开爬虫名文档较少。\n"
           "来源：https://help.aliyun.com/x\n置信度：mid")
    fake = lambda messages, tools=None, timeout=120: raw
    out = web_search_verify([{"platform":"Qwen","fact":"crawler_and_inclusion"}], chat_fn=fake)
    assert "Qwen" in out
    assert out["Qwen"]["confidence"] == "mid"
    assert any("aliyun" in s for s in out["Qwen"]["sources"])

def test_web_search_verify_no_sources_marks_unverified():
    fake = lambda messages, tools=None, timeout=120: "无法确认。"
    out = web_search_verify([{"platform":"X","fact":"crawler"}], chat_fn=fake)
    assert out["X"]["confidence"] == "外部未验证"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd geo-agent && python3.11 -m pytest tests/test_kimi.py -v`
Expected: FAIL — `web_search_verify` undefined.

- [ ] **Step 3: Write minimal implementation** (append to kimi.py)

```python
import re

_SYS_WEB = ("联网搜索查证 AI 平台的爬虫名/收录机制等外部事实。"
            "回答格式：先给结论，再列「来源：<url>」（至少一个），最后「置信度：high|mid|low」。"
            "查不到就如实说无法确认，禁止杜撰 URL。")

def _parse_web_answer(text: str) -> dict:
    sources = re.findall(r"https?://\S+", text or "")
    conf = "外部未验证"
    m = re.search(r"置信度[:：]\s*(high|mid|low|外部未验证)", text or "", re.I)
    if m: conf = m.group(1).lower()
    if not sources and "无法确认" in (text or ""): conf = "外部未验证"
    return {"answer": (text or "").strip(), "sources": sources, "confidence": conf}

def web_search_verify(items: list[dict], *, chat_fn=_kimi_chat) -> dict:
    # IMPL-TIME: confirm tools schema; default to builtin_tools web_search.
    tools = [{"type":"builtin_tools","tools":[{"type":"web_search"}]}]
    out = {}
    for it in items:
        plat, fact = it["platform"], it.get("fact","crawler_and_inclusion")
        user = f"平台：{plat}\n查证：{fact}（爬虫 User-agent / 收录机制）"
        try:
            raw = chat_fn([{"role":"system","content":_SYS_WEB},{"role":"user","content":user}],
                          tools=tools, timeout=180)
            out[plat] = _parse_web_answer(raw)
        except Exception as e:
            log.warning("web_search_verify %s failed: %s", plat, e)
            out[plat] = {"answer":"", "sources":[], "confidence":"外部未验证"}
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd geo-agent && python3.11 -m pytest tests/test_kimi.py -v`
Expected: PASS (5 tests total)

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/research/kimi.py geo-agent/tests/test_kimi.py
git commit -m "feat(research): Kimi web_search verify (Tier1+2, parse + unverified fallback)"
```

---

## Task 7: render.render_playbook + render_profiles (golden)

**Files:**
- Create: `geo-agent/src/geo/research/render.py`
- Test: `geo-agent/tests/test_render.py`

**Interfaces:**
- Consumes: `list[PlaybookConclusion]`, `FeatureAggregates`, verified-facts dict.
- Produces: `render_playbook(conclusions, aggregates, week) -> str`; `render_profiles(platforms_metrics, verified_facts, week) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render.py
from geo.research.render import render_playbook, render_profiles
from geo.research.models import FeatureAggregates, Coverage, FeatureBucket, PlaybookConclusion

def _agg():
    return FeatureAggregates(week=1, coverage=Coverage(1,1,1,0,0),
        formats=[FeatureBucket("comparison_table",1,1,["qwen"],True)],
        sources={"domain_type":{"manufacturer":1},"page_type":{"review":1},"schema":{"Article":1},
                 "has_publish_date":1,"ugc":0,"resolved":1},
        platforms={"qwen":{"n":1,"mention_rate":0.0,"citation_rate":0.0}},
        problem_space={"intent_clusters":[{"intent":"comparison","n":1}],"topic_gaps":["hestia solar"]})

def _concl():
    return [PlaybookConclusion(id="F01",category="format",conclusion="对比表常见",sample_n=1,
        cited_n=1,platforms=["qwen"],confidence="low",action="多用对比表",examples=["https://a.com"])]

def test_render_playbook_has_sections_and_warning():
    md = render_playbook(_concl(), _agg(), week=1)
    assert "# SunHestia GEO Playbook · w1" in md
    assert "## 1. 被引格式特征" in md
    assert "## 5. 可复用内容模板" in md
    assert "观察性相关" in md                     # honesty warning
    assert "comparison_table" in md or "对比表" in md
    assert "sample_n=1" in md or "sample_n= 1" in md

def test_render_profiles_data_and_web_sections():
    vf = {"Qwen":{"answer":"阿里云搜索","sources":["https://help.aliyun.com/x"],"confidence":"mid"}}
    md = render_profiles({"qwen":{"n":1,"mention_rate":0.0,"citation_rate":0.0}}, vf, week=1)
    assert "# 平台引用画像 · w1" in md
    assert "Qwen" in md and "阿里云搜索" in md
    assert "置信度" in md and "mid" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd geo-agent && python3.11 -m pytest tests/test_render.py -v`
Expected: FAIL — `render_playbook` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/geo/research/render.py
from __future__ import annotations
import json
from geo.research.models import FeatureAggregates, PlaybookConclusion

_FMT_LABEL = {"comparison_table":"对比表","qa":"Q&A","list":"清单","definition":"定义段","spec_card":"规格卡"}

def render_playbook(conclusions: list[PlaybookConclusion], aggregates: FeatureAggregates, week: int) -> str:
    c = aggregates.coverage
    L = [f"# SunHestia GEO Playbook · w{week}",
         f"> rule_version geo-seo-v1 | L1={c.total_l1} | 被引源分析 sample_n={c.l3_resolved}(缺失{c.l3_missing}/js_only{c.l3_js_only})",
         "> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。\n",
         "## 1. 被引格式特征"]
    fmt_concl = [x for x in conclusions if x.category=="format"]
    for b in aggregates.formats:
        label = _FMT_LABEL.get(b.key, b.key)
        L.append(f"### {b.key}（{label}）")
        L.append(f"- cited_n={b.cited_n} sample_n={b.sample_n} confidence={'low' if b.low_confidence else 'ok'} platforms={b.platforms}")
        match = next((x for x in fmt_concl if x.id.lower().startswith('f') ), None)
        if match: L.append(f"- 结论：{match.conclusion}｜行动：{match.action}")
    L += ["\n## 2. 被引来源特征",
          f"```json\n{json.dumps(aggregates.sources, ensure_ascii=False, indent=2)}\n```",
          "\n## 3. 分平台差异",
          f"```json\n{json.dumps(aggregates.platforms, ensure_ascii=False, indent=2)}\n```",
          "\n## 4. 问题空间与选题",
          f"意图簇：{aggregates.problem_space.get('intent_clusters')}  选题缺口候选：{aggregates.problem_space.get('topic_gaps')}",
          "\n## 5. 可复用内容模板",
          "- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。"]
    return "\n".join(L) + "\n"

def render_profiles(platforms_metrics: dict, verified_facts: dict, week: int) -> str:
    L = [f"# 平台引用画像 · w{week}", ""]
    names = {"qwen":"Qwen · qwen3.7-plus (阿里 DashScope)",
             "doubao":"Doubao · doubao-seed-2-1-pro (字节 Ark)",
             "zhipu":"Zhipu · glm-5.2 (BigModel)"}
    for m, met in platforms_metrics.items():
        L.append(f"## {names.get(m,m)}")
        L.append(f"- 引用偏好(数据,n={met.get('n')}): mention={met.get('mention_rate')} citation={met.get('citation_rate')}")
        vf = verified_facts.get(m.capitalize()) or verified_facts.get(m, {})
        if vf:
            L.append(f"- 爬虫名/收录(联网查证): {vf.get('answer','—')}")
            L.append(f"  来源：{', '.join(vf.get('sources',[])) or '—'} | 置信度：{vf.get('confidence','—')}")
        L.append("")
    L.append("## 附录：主流 AI 平台爬虫名对照表（Tier2 联网查证）")
    for plat, vf in verified_facts.items():
        if plat.lower() in ("chatgpt","gemini","perplexity","claude"):
            L.append(f"- {plat}: {vf.get('answer','—')} [{vf.get('confidence','—')}]")
    return "\n".join(L) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd geo-agent && python3.11 -m pytest tests/test_render.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/research/render.py geo-agent/tests/test_render.py
git commit -m "feat(research): render playbook.md + platform-profiles.md"
```

---

## Task 8: run.run_research CLI + integration (Kimi mocked)

**Files:**
- Create: `geo-agent/src/geo/research/run.py`
- Test: `geo-agent/tests/test_run.py`

**Interfaces:**
- Produces: `run_research(week: int, kimi_enabled: bool = True, *, synth_fn=None, web_fn=None) -> dict` (returns paths/counts); `__main__` → `python3.11 -m geo.research.run --week 1`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run.py
import json
from pathlib import Path
from geo.research.run import run_research

def test_run_research_deterministic_path_writes_files(tmp_path):
    import shutil
    FIX = Path(__file__).parent / "fixtures" / "research"
    # mirror fixture mini-repo into tmp (isolated reads + writes; no monkeypatch of module REPO)
    for sub in ["data/raw", "data/sources", "data/snapshots", "input"]:
        src = FIX / sub
        if src.exists():
            shutil.copytree(src, tmp_path / sub, dirs_exist_ok=True)
    # Kimi disabled + source already mirrored → select_topn returns [] (no fetch/network)
    res = run_research(1, kimi_enabled=False, repo=tmp_path)
    assert (tmp_path/"knowledge"/"playbook.md").exists()
    assert (tmp_path/"knowledge"/"platform-profiles.md").exists()
    assert (tmp_path/"data"/"analysis"/"w1"/"research_aggregates.json").exists()
    agg = json.loads((tmp_path/"data"/"analysis"/"w1"/"research_aggregates.json").read_text())
    assert agg["week"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd geo-agent && python3.11 -m pytest tests/test_run.py -v`
Expected: FAIL — `run_research` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/geo/research/run.py
from __future__ import annotations
import json, logging
from pathlib import Path
from geo.shared.config import REPO
from geo.research.corpus import build_corpus
from geo.research.sample import select_topn, fetch_topn
from geo.research.features import aggregate
from geo.research.kimi import synthesize, web_search_verify
from geo.research.render import render_playbook, render_profiles

log = logging.getLogger("research.run")
PLATFORMS_TO_VERIFY = ["Qwen","Doubao","Zhipu"]
BROADER = ["ChatGPT","Gemini","Perplexity","Claude"]

def run_research(week: int, kimi_enabled: bool = True, *, synth_fn=None, web_fn=None,
                 fetch_n: int = 40, repo: Path = REPO) -> dict:
    corpus = build_corpus(week, repo=repo)
    urls = select_topn(corpus, n=fetch_n, repo=repo)
    if urls:
        stats = fetch_topn(urls); log.info("fetched %s", stats.__dict__)
        corpus = build_corpus(week, repo=repo)   # reload to pick up new L3
    agg = aggregate(corpus)

    conclusions = []
    verified = {}
    if kimi_enabled:
        try: conclusions = synthesize(agg, examples=[], chat_fn=synth_fn) if synth_fn else synthesize(agg, [])
        except Exception as e: log.warning("synthesize disabled/failed: %s", e)
        try:
            items = [{"platform":p,"fact":"crawler_and_inclusion"} for p in PLATFORMS_TO_VERIFY + BROADER]
            verified = web_search_verify(items, chat_fn=web_fn) if web_fn else web_search_verify(items)
        except Exception as e: log.warning("web_search failed: %s", e)

    (repo/"data"/"analysis"/f"w{week}").mkdir(parents=True, exist_ok=True)
    (repo/"data"/"analysis"/f"w{week}"/"research_aggregates.json").write_text(
        json.dumps(_agg_jsonable(agg), ensure_ascii=False, indent=2), encoding="utf-8")
    (repo/"knowledge").mkdir(parents=True, exist_ok=True)
    (repo/"knowledge"/"playbook.md").write_text(render_playbook(conclusions, agg, week), encoding="utf-8")
    (repo/"knowledge"/"platform-profiles.md").write_text(
        render_profiles(agg.platforms, verified, week), encoding="utf-8")
    return {"playbook": str(repo/"knowledge"/"playbook.md"),
            "profiles": str(repo/"knowledge"/"platform-profiles.md"),
            "conclusions": len(conclusions), "verified_platforms": len(verified)}

def _agg_jsonable(a):
    return {"week":a.week,"coverage":a.coverage.__dict__,
            "formats":[b.__dict__ for b in a.formats],"sources":a.sources,
            "platforms":a.platforms,"problem_space":a.problem_space}

if __name__ == "__main__":
    import argparse, logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(); ap.add_argument("--week", type=int, default=1)
    ap.add_argument("--no-kimi", action="store_true")
    a = ap.parse_args()
    print(run_research(a.week, kimi_enabled=not a.no_kimi))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd geo-agent && python3.11 -m pytest tests/test_run.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add geo-agent/src/geo/research/run.py geo-agent/tests/test_run.py
git commit -m "feat(research): CLI orchestration + deterministic-only path"
```

---

## Task 9: Live smoke test (@live) + finalize

**Files:**
- Create: `geo-agent/tests/test_research_live.py`
- Modify: `geo-agent/tests/conftest.py` (register `live` marker if absent)

**Interfaces:**
- Produces: a `@pytest.mark.live` test that runs `run_research(1)` against the real w1 corpus + real Kimi; skipped unless `--live` flag / `-m live`.

- [ ] **Step 1: Write the test**

```python
# tests/test_research_live.py
import pytest
from geo.research.run import run_research

@pytest.mark.live
def test_live_research_w1_real_kemi():
    """Real w1 corpus + real Kimi K3. Run manually: python3.11 -m pytest -m live tests/test_research_live.py -v
    Requires network + Clash 7890 + valid Moonshot key. Not a text-quality assertion (human-audit)."""
    res = run_research(1, kimi_enabled=True)
    assert res["playbook"].endswith("playbook.md")
    # human audits playbook.md + platform-profiles.md for factual accuracy after this passes
```

- [ ] **Step 2: Register marker (only if not present)**

Check `geo-agent/tests/conftest.py`; if no `live` marker registration, append:
```python
def pytest_configure(config):
    config.addinivalue_line("markers", "live: needs network + real API; skipped in CI")
```

- [ ] **Step 3: Verify deterministic suite still green + live test is skipped by default**

Run: `cd geo-agent && python3.11 -m pytest tests/test_research_*.py -v`
Expected: all deterministic research tests PASS; the `live` test is collected but SKIPPED (no `-m live`).

- [ ] **Step 4: Commit**

```bash
git add geo-agent/tests/test_research_live.py geo-agent/tests/conftest.py
git commit -m "test(research): live smoke (real w1 + Kimi, human-audit gate)"
```

- [ ] **Step 5: Manual live run (operator, after PR merge / on branch)**

Run (needs `dangerouslyDisableSandbox` + proxy up):
```bash
cd "/Users/jerry/AiProject/sunpower nova" && python3.11 -m geo.research.run --week 1
```
Then human-audit `geo-agent/knowledge/playbook.md` + `platform-profiles.md` (spec §9 acceptance).

---

## Self-Review (completed by plan author)

**Spec coverage:** §1 scope → all tasks; §2 inputs/outputs → Task 2 (inputs) + Task 8 (outputs incl. research_aggregates.json); §3 modules → Tasks 1–8; §4 deterministic backbone → Tasks 2/3/4 + sample discipline baked into Task 4 (`LOW_CONF_THRESHOLD`); §5 Kimi layer → Tasks 5/6; §6 artifacts → Task 7; §7 error handling → Tasks 5/6 fallback + Task 8 try/except; §8 testing → deterministic tests in every task + mock Kimi Task 5/6 + live Task 9; §9 acceptance → Task 9 step 5 human audit. ✅

**Placeholder scan:** §11 impl-time item (Moonshot web_search schema) is explicitly flagged in Task 6 with a concrete default + fallback — acceptable. No TBD/TODO in task bodies. ✅

**Type consistency:** `build_corpus`/`select_topn`/`aggregate`/`synthesize`/`web_search_verify`/`render_playbook`/`render_profiles`/`run_research` signatures are identical across the tasks that consume them. `chat_fn` seam signature `(messages, tools=None, timeout=120) -> str` is consistent in Tasks 5 & 6. `FeatureAggregates` field names (`formats/sources/platforms/problem_space/coverage/week`) match between models.py (Task 1), features.py (Task 4), render.py (Task 7), kimi._agg_to_dict (Task 5). ✅

**Known impl nits to watch (not blockers):**
- `dataclass.__dict__` for `FeatureBucket`/`Coverage` works (non-slot dataclasses); if a future model adds slots, switch to `dataclasses.asdict`.
- `repo` is threaded through `build_corpus`/`select_topn`/`run_research` (`Path`, default `REPO`); tests pass `repo=<FIX or tmp_path>` explicitly and never monkeypatch module-level `REPO` (fixture dir is a mini-repo mirroring `data/raw|sources|snapshots` + `input/`).
- Task 8 reloads corpus after fetch; if `select_topn` returns `[]` (all already fetched / no externals), skip reload — already handled by `if urls`.
