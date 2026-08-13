# P1 研究 Agent 设计（Research Agent）

- **日期**：2026-08-13
- **状态**：已 brainstorm 定稿，待实现计划
- **分支**：`p1-research-agent`（off `main`/`p0-eval-foundation` @ `d1573fb`）
- **权威依据**：整合 spec §5（研究 agent）、§3.2（L3 来源特征维度）、§11 P1 行（`docs/superpowers/specs/2026-07-29-sunpower-nova-integration-design.md`）。本文件细化 P1 的实现口径，冲突以整合 spec 为准。
- **前置**：✅ P0 评测地基已交付；✅ w1 基线 100% 完整（三家各 15 / 核心 45/45；self_geo 47.6 / self_seo 49.8）。

---

## 1. 目标与范围

P1 在 6 环节闭环中落地「研究」环节：**从已采集的真实回答（L1+L2）+ 被引页正文与结构（L3）+ GSC 真实查询词，归纳「什么样的内容/来源更易被 LLM 引用」，产出可复用的 GEO 行动手册与平台画像**。

**本轮交付（方案 1：独立研究模块 + 务实首版）：**

1. 新建 `src/geo/research/` 包，独立可跑（`python -m geo.research.run --week N`）。
2. **分层采样**补抓 Top-N 最高频被引、未抓过的外部源（复用 `fetcher.fetch_source` + `meta_llm`），不做全量 cited_sources 抓取。
3. 确定性特征聚合（4 桶）+ Kimi K3 综合（4 任务，每条结论带样本量标签）。
4. **有界 Kimi web_search「联网查证」**（Tier1+2，约 6–10 次调用）。
5. 产出 `knowledge/playbook.md`（混合结构）+ `knowledge/platform-profiles.md`。

**本轮不做（延后）：**
- LangGraph DAG 节点接入（`research_node` 是薄包装，模块稳定后再加，本期不动 graph 早退/续跑逻辑）。
- 全量 cited_sources 穷尽抓取（用分层采样替代，以样本量纪律约束）。
- P2+ 权威信号（backlinks/DA，需付费源，标「未知」降级）。
- `brand.yaml` 抽取（属 P2 生成 agent；P1 读取 `targets.yaml` 的 `brand_terms` 作为品牌词）。

---

## 2. 输入与产出

**输入**（读取，不改）：
- `data/raw/w{N}/{model}/{pid}/r{run}.json` — L1Record（内嵌 L2，含**全量 cited_sources**）。
- `data/sources/{sha1[:12]}/{text.md,meta.json}` — L3Source（structural + semantic）。
- `data/snapshots/w{N}/gsc.json` — `rows[].keys` = GSC 真实查询词。
- `input/prompts.csv` — PromptRow（category/intent/market/core）。
- `targets.yaml` — `site.brand_terms`。

**产出**（新建文件）：
- `knowledge/playbook.md`
- `knowledge/platform-profiles.md`
- `data/analysis/w{N}/research_aggregates.json` — 确定性 `FeatureAggregates` 快照（golden + 供 P3/RulesKeeper 读）。

---

## 3. 模块架构

`src/geo/research/`，6 个单元各司一职、可独立测试：

| 文件 | 职责 | 接口要点 |
|---|---|---|
| `corpus.py` | 组装研究语料：L1+L2 与 L3 join + GSC 查询词 + prompts | `build_corpus(week) -> ResearchCorpus` |
| `sample.py` | 分层采样：Top-N 最高频被引、未抓外部源 → fetch+Kimi 语义解析 | `fetch_topn(corpus, n) -> FetchStats`（复用 `fetcher.fetch_source`）|
| `features.py` | ★确定性特征聚合（4 桶 + 样本量计数） | `aggregate(corpus) -> FeatureAggregates` |
| `kimi.py` | Kimi K3 层：综合（4 任务）+ web_search 查证（Tier1+2） | `synthesize(aggregates, examples) -> list[PlaybookConclusion]`；`web_search_verify(items) -> dict` |
| `render.py` | 渲染 playbook.md（混合）+ platform-profiles.md | `render_playbook(conclusions, aggregates, week) -> str`；`render_profiles(...)` |
| `run.py` | CLI（`--week N`）编排 | `corpus → sample → features → (kimi.synthesis ∥ kimi.web_search) → render` |

**数据流**：
```
data/raw(L1+L2) · data/sources(L3) · data/snapshots/gsc.json · input/prompts.csv · targets.yaml
   │ corpus.py (join)
   ▼
ResearchCorpus ──sample.py(补抓Top-N)──▶ 扩充 data/sources
   │ features.py (确定性聚合)
   ▼
FeatureAggregates ──┬─ kimi.synthesis(Kimi K3, 4任务) ──▶ PlaybookConclusion[](带sample_n)
                    └─ kimi.web_search(Kimi K3+联网, Tier1+2) ──▶ 平台外部事实
   │ render.py
   ▼
knowledge/playbook.md + knowledge/platform-profiles.md   (+ data/analysis/wN/research_aggregates.json)
```

**复用现有 infra**：`fetcher.fetch_source` / `meta_llm.extract_semantic` 的 Kimi 调用模式（client、`temperature=1`、`json_object`、非阻塞）/ `storage.sha1_url,source_dir` / `analyst._iter_l1` 与 `_load_l3_source` 模式（复制，不 import 其 `_` 私有）/ `settings.moonshot_*`。

---

## 4. 确定性骨架（可单测 / golden）

### 4.1 corpus.py — ResearchCorpus
- 复制 `_iter_l1(week)`（`rglob("r*.json")` → L1Record）与按 URL 取 L3 的模式。
- `ResearchItem = {l1: L1Record, prompt: PromptRow, sources: list[(CitedSource, L3Source|None)]}`。
- `coverage = {total_l1, total_cited_sources, l3_resolved, l3_missing, l3_js_only}`（供诚实标注 + sample_n）。

### 4.2 sample.py — 分层采样补抓
- 跨语料统计每个**去重外部 URL** 的被引频次（排除品牌站、已知 js_only）。
- 按频次降序取 Top-N（默认 N=30–50，可配），跳过已抓（`data/sources` 已存在）。
- 对每个：`fetch_source(url)`（抓正文 + 跑 `meta_llm` 语义 → 落 `data/sources/{sha1}/`）。
- 产出 `FetchStats = {requested, fetched, failed, js_only}`。**N 封顶 → 成本/时间有界**。

### 4.3 features.py — FeatureAggregates（4 桶）
按 spec §5 四任务，跨语料聚合 L3 的 structural+semantic：

| 桶 | 聚合 |
|---|---|
| **格式特征** | 对比表(`table_count>0`)/Q&A(`has_faq_block`)/清单(`ul_count>0`)/定义段(`has_definition_segment`)/规格卡(`page_type=product` 或 `datapoint_count`高) → 各在被引源中的出现数 + 比例 + per平台 |
| **来源特征** | §3.2 维度：域名类型(厂商/评测/论坛/wiki/news)、page_type、内容长度、H结构、列表/表格密度、schema_types 分布、freshness(`has_publish_date`)、UGC vs 一手官方（权威=P2+ →「未知」降级）|
| **分平台差异** | qwen/doubao/zhipu 交叉表：各 mention/citation/sov、偏好的源类型（如 doubao citation=0、qwen/zhipu 13.3%）|
| **问题空间** | GSC 6 查询词 + prompts 的 category/intent → 意图簇（comparison/scenario/definition/brand）命中；标 GSC 有但 prompts 未覆盖的选题缺口 |

**每桶字段**：`cited_n`（被引源中具备数）/ `sample_n`（该桶总分析源数）/ `platforms` / `low_confidence`（`sample_n < 5`）。

⚠️ **诚实性边界**：格式/来源特征只报「被引源中 X% 具备此特征」（观察性相关），**不得表述为"因此更易被引"**（无反事实基线）。归因留给 Kimi+人审，sample 标签防过度结论。

### 4.4 样本量纪律（横切）
- 每个聚合桶带 `cited_n / sample_n / platforms / low_confidence`。
- 这些数值**原样透传**给 Kimi；Kimi 被 system prompt 限定只能引用、不得改写或杜撰。
- `sample_n` 不足（<5）自动标「低置信」。

---

## 5. Kimi 层（kimi.py，非确定 / 人审）

### 5.1 synthesize — 综合（4 任务）
- Kimi K3 吃 `FeatureAggregates` JSON + 少量真实 L1 片段，按 4 任务输出结构化结论。
- `temperature=1`（kimi-k3 强制）、`response_format={"type":"json_object"}`、timeout≥120s。
- 输出 `PlaybookConclusion = {id, category, conclusion, sample_n, platforms, confidence, action, examples[]}`。
- **反幻觉**：system prompt 限定「只能用所给 aggregates；原样保留 sample_n；不得杜撰 URL 或数据」。

### 5.2 web_search_verify — 联网查证（Tier1+2，**新集成**）
- 开启 Moonshot web_search 工具查证外部事实，返接地答案 + 来源 URL + 置信度。
- **Tier1（必查，高价值/可行动）**：
  1. 三家被测平台（Qwen/Doubao/Zhipu）的网页检索**爬虫名 + robots `User-agent`**；
  2. 三家**收录/被引机制**（爬公开网 / 私有索引 / 训练数据 → 决定站点内容能否影响被引）。
- **Tier2（查，有用上下文）**：
  3. 主流 AI 平台爬虫名**对照表**（ChatGPT/GPTBot、Gemini/Google-Extended、Perplexity/PerplexityBot、Claude/ClaudeBot + 中文三家）；
  4. 各平台**引用行为外部佐证**（如 doubao 不引链接的公开说法）。
- **成本边界 ~6–10 次调用**；查不到→诚实标「外部未验证/低置信」，不杜撰。
- ⚠️ 实现期需核实 Moonshot web_search 工具 schema（spec 已确认 kimi-k3 具联网能力；meta_llm 现未接 web_search）。

---

## 6. 产物结构

### 6.1 `knowledge/playbook.md`（混合：结构化字段 + prose）
```
# SunHestia GEO Playbook · w{N}
> 生成自 w{N} | rule_version | prompt_set_version | L1=45(qwen15/doubao15/zhipu15)
> 被引源分析 N / L3已解析M/缺失K | ⚠️ 观察性相关非因果, 低置信项已标

## 1. 被引格式特征     F0x 每条: 结论 / cited_n·sample_n·confidence / 示例 / 行动
## 2. 被引来源特征     域名类型/page_type/schema/freshness/UGC 分布 + 样本
## 3. 分平台差异       如 doubao citation=0 → 侧品牌词不求链接
## 4. 问题空间与选题   意图簇命中 + 选题缺口候选（用户决定是否纳入, 不动冻结基线）
## 5. 可复用内容模板   据高被引特征给 1-3 个骨架(对比表/定义段/规格卡)
```
结构化字段（cited_n/sample_n/confidence）= P2/P3 可确定解析；prose = 可 Kimi 读。

### 6.2 `knowledge/platform-profiles.md`
```
# 平台引用画像 · w{N}
## Qwen · qwen3.7-plus (阿里 DashScope)
- 引用偏好(数据,n=15): mention/citation/avg_pos/sov
- 爬虫名(联网查证): [结果+来源URL+置信度]
- 收录机制(联网查证): 爬公开网→SEO/内容可影响 [置信度]
- 被引内容特征: 偏好[…]
## Doubao · doubao-seed-2-1-pro (字节 Ark)  (citation0%→侧品牌词)
## Zhipu · glm-5.2 (BigModel)
## 附录: 主流AI平台爬虫名对照表(Tier2联网查证)  ChatGPT/Gemini/Perplexity/Claude + 中文三家
```

---

## 7. 错误处理（全非阻塞 + 日志，沿用 meta_llm 哲学）

| 失败 | 处理 |
|---|---|
| Kimi synthesis 抛错/空/非法 JSON | 降级渲染**确定性 FeatureAggregates 原样** + 标「Kimi综合不可用」；记日志 |
| web_search 查无/失败 | 标「外部未验证/低置信」，不杜撰 |
| 采样 URL fetch 失败 / js_only | 跳过，计入 coverage 未抓数，反映到 sample_n |
| L3 缺失 | 容忍（analyst 同款），排除出特征 n |

P1 的**主产出就是 Kimi 综合**，故不像 meta_llm 那样静默返 `{}`，而需显式日志 + 降级渲染（保证总有可用产物）。

---

## 8. 测试策略（确定性 / Kimi 切分）

- **单测（确定性）**：corpus join / sample 的 Top-N 选取+去重 / features 聚合 / `low_confidence` 阈值 / render（给定结论→精确 markdown）。用**小型合成 fixture**（几条 L1+L3，checked into `tests/fixtures/`）。
- **Golden**：冻结合成语料 → `FeatureAggregates` 字节稳定；render 路径（喂固定 `PlaybookConclusion` fixture）字节稳定。
- **Kimi 层（mock，不入 CI）**：好 JSON→正确解析；坏/空 JSON→优雅降级；web_search 空返→「未验证」标签。
- **Live smoke（`@pytest.mark.live`，手动跑）**：真调 Kimi 跑 w1，校验 prompt+解析通；**不校验文本质量**。
- **人审验收（spec §11）**：抽样 5–10 条 playbook 结论核事实准确性+可行动性；达标线=无杜撰、sample_n 诚实、结论有聚合支撑。

> 测试性切分原则：`corpus/sample/features/render` 确定性 → golden；`kimi` 非确定 → mock 解析+降级，质量走人审。**不追求 Kimi 文本的字节 golden**（P0 全字节 golden 是因为全确定性，P1 不同）。

---

## 9. 验收标准（spec §11 + §5）

- ✅ 能从真实回答+全量引用列出**被引用特征清单 + 内容模板**（playbook §1/§2/§5）。
- ✅ platform-profiles 含**数据派生引用偏好** + **联网查证的爬虫名/收录机制**（带来源与置信度）。
- ✅ 每条结论带**样本量标签**，不足标「低置信」。
- ✅ 外部事实由 Kimi 联网查证、不靠模型记忆凭空生成（反幻觉）。
- ✅ **抽样人审质量合格**（不以硬性字段清单验收）。
- ✅ 确定性部分测试全绿；Kimi 降级路径被测。

---

## 10. 与下游衔接（P2/P3 契约）

- **P2 生成 agent**：读 `playbook.md`（内容模板 + 高被引特征）+ 未来的 `brand.yaml` → 草稿。
- **P3 RulesKeeper**：读 `playbook.md` + `eval_report.json` → 规则迭代（§7）。
- 本期 playbook 的**结构化字段**保证两者可确定解析关键数值；prose 部分可由 Kimi 读。
- `research_aggregates.json` 作为确定性中间产物供 P3 复算/回溯。

---

## 11. 实现期待核实项

1. Moonshot web_search 工具 schema（`tools` 字段格式）—— spec 确认 kimi-k3 具联网能力，需实测调通。
2. Top-N 默认值（30/40/50）的取舍——依首轮 w1 去重后外部源数量定。
3. Kimi 综合「单次大调用 vs 分桶多次调用」——依 token 上限与稳定性定。
