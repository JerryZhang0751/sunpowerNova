# SunPower Nova 多智能体 GEO 系统 · 整合设计（v1.1）

> 日期：2026-07-29（v1.1 修订 2026-07-30）｜ 状态：**已通审（2026-07-30）；P0 实现计划已生成（2026-08-02）** ｜ 项目代号 sunpower nova ｜ 对外品牌 SunHestia
> 融合来源：①《GEO战略方案_SunPowerNova.md》（方法论）②《多智能体GEO系统设计方案.md》（闭环架构）③《PRD-multi-agent-geo-analysis.md》v4（采集/规则/报告工程化）
> 本文是以上三份的**整合定稿**，取代三者中冲突的部分；冲突以本文为准。
>
> **v1.1 变更（2026-07-30）**：全流程自动化，**唯一阻塞式人工关口 = 内容发布**（研究/规则迭代改自动）；GSC + 抓取静态信号**快照化**为版本化输入；GEO/SEO 改为**两套独立评分**；L3 扩展 meta 拆 **P0 / P2+ 两档**并改**强提示词驱动 LLM 解析**（不设硬性字段清单）；`qwen-plus → qwen3.7-plus`；成本改为**记录呈现、不考核**；核心 **15 题**固化到 `prompts.csv`（`core` 列）。
> **✅ 点 1 已定（2026-07-30 补）**：新增 **§4-bis 智能体性能评估（B）**，与 §4 业务评估正交；**本期仅「工具调用评估（BFCL 式 AST 匹配）」**，评 Collector/Parser 工具调用正确性；LLM Judge / Win Rate / GAIA 均不做。§4 的语义维度（E-E-A-T/文案友好度）改**确定性代理**打分（不引入 LLM 裁判，保 golden test）。源：Datawhale Hello-Agents 第 12 章（原文未存档，BFCL 要点已完整并入 §4-bis；2026-08-17 自洽检查确认 `docs/refs_ch12.txt` 从未入库）。

---

## 0. TL;DR 与已锁定决策

用一套**以共享知识库为中心的 6 环节闭环系统**，把 GEO 从"凭感觉写内容"变成"**调目标模型 API 拿真实引用 → 反推被引用特征 → 按特征产内容 → 再评测验证 → 迭代规则**"的可度量循环。eval（采集+评估）是整个系统的**数据中枢**。

**6 环节闭环**：采集 → 研究 → 生成 → 评估 → 规则迭代 → HTML 报告 →（人决策）→ 下一轮

| # | 决策点 | 锁定选择 |
|---|---|---|
| 1 | 系统范围 | **全闭环**（P0–P3 全做） |
| 2 | eval 模型集 | **仅 3 家官方 API**（Qwen / 豆包 / 智谱）；手动 5 家线归档 |
| 3 | 时间线 | **暂停 7 周 GEO 实验，集中建系统**；站点继续被索引自然沉淀；建好（到 P2/P3）再恢复实验 |
| 4 | 内容去向 | 生成 agent **先只发官网 site/**；第三方渠道延后 |
| 5 | 架构骨架 | **闭环主轴 + 吸收 PRD v4 资产**（采集/规则/报告保留，统一在 `geo-agent/` 下） |
| 6 | 规则 | **可迭代、版本化**（不再静态快照）；含权重迭代，每次归一化到 100% |
| 7 | 分析层 LLM | **Kimi K3**（非被测模型，与采集层隔离），用于研究/生成/L3 语义解析；**本期无 LLM 裁判**（§4 语义维度改确定性代理，B 仅 BFCL）|
| 8 | SEO 复合分 | 新增（PRD v4 原只定性）；5 支柱加权 |
| 9 | 自审 SEO 信号 | **去 Lighthouse**，改 **GSC service account + 抓取层静态信号**（均**快照化**为版本化输入）|
| 10 | 人工关口 | **全流程自动，唯一阻塞关口 = 内容发布**；研究/规则迭代自动执行（规则靠证据门槛+可回滚）|
| 11 | GEO vs SEO 评分 | **两套独立评分系统**，不合成总分、不互相折算 |
| 12 | L3 扩展 meta | **不设硬性必抽字段清单**，改**强提示词驱动 Kimi K3 解析**；字段拆 P0（可解析）/ P2+（需外部源，暂缺）|
| 13 | 成本 | **记录并呈现于报告，不作考核**；`run.yaml` 熔断仅作安全阀 |
| 14 | 智能体性能评估(B) | **新增独立节 §4-bis**，与业务评估(A/§4)正交；**仅工具调用评估(BFCL 式 AST)**，LLM Judge/Win Rate/GAIA 不做；§4 语义维度改**确定性代理**；**版本更新 hook 触发**（非每轮） |

---

## 1. 背景与现状

### 1.1 现状是三套并行

| 现有部分 | 实质 | 产物 | 模型集 | 状态（2026-07-29） |
|---|---|---|---|---|
| `geo-measurements/` + `answers/` | **手动**评测（人跑外部 LLM、助手解析） | dashboard 指标 | 5 家（ChatGPT/Gemini/Grok/DeepSeek/Qwen） | W1 进行中 47/215，全 N → **本次归档** |
| `geo-agent/`（PRD v4 MVP） | **自动**采集→评分→报告平台 | HTML 报告 + 建议 | 3 家 + Kimi | M0 完成，M1–M4 未做 → **本次扩展为闭环** |
| `site/` | Astro 官网 sunhestia.com | 站点本身 | — | 已上线，W1 vanilla → **生成内容的发布阵地 + brand.yaml 抽取源** |

### 1.2 整合后
三套合一为 `geo-agent/` 下的 6 环节闭环系统；`site/` 作为官网阵地保留；`geo-measurements/` 归档（其 `prompts.csv` 迁入 `geo-agent/input/`，命名规范沿用）。

### 1.3 硬约束（来自此前决定性实测）
- 能通过**官方 API 自动跑"原生联网搜索 + 返回引用来源"**的，目前只有 **Qwen(DashScope)/ 豆包(Ark)/ 智谱(BigModel)** 三家。ChatGPT/Gemini/Grok 国内不可达或无返回 source 的联网 API → 只能人工跑（本次归档停用）。
- **中转站对任何模型都不提供真实联网**，已全停用。
- GSC 中国访问需代理（实现时处理）。

---

## 2. 总体架构

### 2.1 闭环数据流（自动流水线，唯一人工关口 = 发布）

```
1. 采集 Collector   读 prompts.csv → 调 Qwen/豆包/智谱 原生联网
                   → 产 L1(答案) + L2(全量引用来源) + L3(被引用页正文+扩展meta)   ← 数据源头
2. 研究 Research    读 L1+L2+L3 + GSC查询词 → 归纳"谁被引用、什么格式/特征被采用"
                   → 产 playbook.md + platform-profiles.md                     ← 弹药
3. 生成 Generate    读 playbook + brand.yaml + 选题 → 产 content/drafts/*
                   → 🔴 人确认事实后决定是否发布 → site/(自有站点)               ← 产出
4. 评估 Assess      读 L1/L2/L3 + 已发布内容 + rules
                   → 命中/引用/SOV/位次 + GEO/SEO诊断分 + 自审↔竞品差值           ← 度量
                   → 产 eval_report
5. 规则迭代 Keeper  读 eval_report + playbook
                   → 规则条目 draft→active(自动·证据门槛) + 权重迭代(归一化100%) + version   ← 进化
                   → 更新 rules/ + changelog.md
6. HTML 报告        读 eval_report + rule_version → 标准化 report.html           ← 呈现
```
→ 人看报告 → 决策 → 触发下一轮（跑新 prompt / 挖新数据 / 生成新内容）

> **自动化边界（v1.1）**：采集→研究→生成→评估→规则→报告 **全部自动串跑**；**唯一阻塞式人工关口 = 内容发布确认**（站点自有，人核对 `brand.yaml` 事实后决定是否触发发页）。规则 `draft→active` 由证据门槛自动判定、可经 `changelog` 回滚，不设人工关口。评估读"已发布内容"，故发布确认是链路上的必经停等点（详见 §10）。

> **B · 智能体性能评估（旁路，版本更新 hook）**：与上面业务闭环**正交**。采集/解析工具链或 model/端点/字段口径**版本更新时**，由 hook 触发一次 BFCL 式 fixture 回归（AST 准确率 **≥95% 才放行新版本**，否则拦截修复）；**不在每轮采集前跑**，业务闭环始终用"上次通过 B 的版本"运行。结果只进报告"系统质量"观察项，不进字节级 golden test。详见 §4-bis。

**采集 vs 评估分工（不重复）**：采集 = 取数据（调 API 拿 L1/L2/L3）；评估 = 算指标 + 打分（基于采集结果算命中/引用、用规则打诊断分）。命中率/引用率属"评估"产出。

### 2.2 目录骨架（统一 `geo-agent/`）

```
geo-agent/
├─ input/        prompts.csv(冻结43题，自 geo-measurements 迁入) · targets.yaml · run.yaml
├─ knowledge/    brand.yaml(单一事实源，从 site/ 抽) · playbook.md · platform-profiles.md
├─ content/      drafts/ · published/
├─ rules/        geo-rules.yaml · seo-rules.yaml · changelog.md   ← 版本化、可迭代
├─ data/         raw/(L1答案) · sources/(L2引用+L3正文+扩展meta,去重) · analysis/(评分+eval_report) · snapshots/(GSC+抓取静态信号快照,版本化)
├─ state/        runs.sqlite   (checkpoint + 去重 + run 日志)
├─ reports/      w{N}/report.html   (Jinja2 + ECharts)
├─ src/          collect/ · research/ · generate/ · assess/ · rules/ · report/ · shared/
├─ scripts/      m0_smoke · probe_* · verify_*（现有探针归档）
└─ .env          DASHSCOPE · ARK · BIGMODEL · MOONSHOT
```

---

## 3. 采集层 Collector（取数据）

**输入**：`prompts.csv`（**由用户提供**，43 题冻结为可比基线；含 `core` 列标记核心 15 题，见 §4.1）+ `run.yaml`（week/models/mode/scope/runs/rule_version）+ `targets.yaml`

**调用（3 家官方 API 原生联网，stream）**：

| 模型 | 端点 | model | 联网开关 | 引用字段路径 |
|---|---|---|---|---|
| Qwen | DashScope 原生 `MultiModalConversation.call`（专属 MaaS `/api/v1`，**多模态·必须流式**；`Generation` 对它返 400）| `qwen3.7-plus` | `enable_search=True` + `search_options={search_strategy:"agent", enable_source:True}` | `output.search_info.search_results[]`（title/url/site_name）|
| 豆包 | Ark **Responses API** `/api/v3/responses`（chat/completions 不认 web_search）| `doubao-seed-2-1-pro-260628` | `tools=[{type:web_search}]` | `output[]`：`web_search_call`(检索)+`message`(答案) |
| 智谱 | BigModel **Anthropic 兼容** `/api/anthropic/v1/messages`（`x-api-key`+`anthropic-version`）| `glm-5.2`（非 `glm-5.2[1m]`）| `tools=[{type:web_search_20250305, name:web_search, max_uses:5}]` | `content[]`：`server_tool_use`+`tool_result`(检索)+`text`(答案) |

> **M0 探针实测口径（2026-07-28，已验证 3/3 原生联网返真实 URL）**：豆包/智谱多轮检索 **timeout ≥ 300s**；模型 id 已核验 `qwen3.7-plus`/`doubao-seed-2-1-pro-260628`/`glm-5.2`。详见项目 memory `model-set-official-apis`。

**三层产出**：
- **L1 答案** `data/raw/w{N}/{model}/{prompt_id}/r{run}.json`：答案原文 + 元信息（model/version/run/ts/联网/耗时/原生 search_results 全量）——**路径含 run 维度**，与去重键 `(week,model,prompt_id,run)` 对齐，多 run 不覆盖
- **L2 引用来源**（规范化）：`cited_sources:[{position,url,title,snippet,extract_method}]` + derived（mentioned/cited_with_link/citation_position/sentiment/competitors）
- **L3 正文** `data/sources/{sha1[:12]}/{meta.json, text.md}`：被引用页正文 + **扩展 meta**（见 3.2），跨周去重；JS-only 标"不可分析"不入分母

### 3.1 L2 引用解析契约（方案①）
- **结构化优先**：解析各家原生字段（DashScope `output.search_info.search_results` / Ark Responses `output[].web_search_call` / BigModel Anthropic `content[].tool_result`）→ 规范化
- **文本兜底**：结构化空时，正则抽正文 URL，标 `extract_method=inferred`
- **derived 字段判定**（口径源自原 `geo-measurements/schema.md`，已并入本节，原文件已清理）：
  - `mentioned`：答案正文或来源出现字面 "SunHestia" / "sunhestia.com"；泛指"很多太阳能公司…"不点名 = N
  - `cited_with_link`：有指向 sunhestia(.com) 的可点击来源链接；编号标记 [1][2] 仅当解析到 sunhestia 才算
  - `citation_position`：1-based 被引用排名，被引时填、否则空
  - `sentiment`：pos/neu/neg，未提及时空
  - `competitors_mentioned`：光储**产品品牌**（Tesla;Enphase;SolarEdge;Canadian Solar…）分号分隔；**排除**评测平台/数据源（EnergySage/Consumer Reports）；即使 SunHestia 未被提也填（喂养 SOV）
  - 品牌类 prompt（B01–B04）：模型复读 "SunHestia" 不算真提及；notes 标"查无/编造/有实料"
- **全量留存**：`cited_sources` 存**全量**（不只品牌命中），供研究 agent 挖特征
- **校准**：每家 golden fixture → parser vs 人工 precision/recall ≥ 90%；`inferred` 入低置信桶

### 3.2 L3 扩展 meta（为穷尽来源特征服务，分两档）
为支撑研究 agent 的"穷尽式来源特征"，L3 `meta.json` 尽量多抽元数据；**不设硬性必抽字段清单**，改用**强提示词驱动 Kimi K3 解析**正文尽量抽全，抓不到的标"未知"也记录、**不静默丢弃**。字段分两档：

**P0 档（`bs4` 可直接解析 / Kimi 可从正文推断，本期做）**：
- 域名层：domain、TLD、域名类型（官方/媒体/社区/百科/评测/政府/学术）、子域
- 页面层：URL 结构、页面类型（产品/FAQ/博客/对比/规格/论坛/问答/新闻）、目录深度、canonical
- 内容层：内容长度、H 结构、列表/表格/图表密度、定义段、FAQ 块、数据密度、媒体类型（文/图/视频）、多语言
- 结构化层：schema.org 类型（Product/FAQPage/HowTo/Article/Review/Organization…）、完整度
- 时效：发布/更新时间、freshness
- 行为/UGC：UGC 标记、是否一手官方

**P2+ 档（需外部付费数据源，本期暂缺、标"未知"降级）**：
- 权威/信任：外链估算、社交信号、域名权威估算、作者/专家/认证、E-E-A-T 外部信号、互动量
> 说明：这些字段 `httpx+bs4` 拿不到（需 Ahrefs/Moz 等付费源），本期不接入、评分时按"未知"降级，避免"权威"维度虚设。

> **提取方式**：结构信号走 `bs4`（H/表格/schema/canonical…）；语义信号（页面类型/定义段/E-E-A-T 文内信号/数据密度…）走 **Kimi K3 提示词解析**；每页解析一次后**快照冻结**入 `data/sources/`，作为下游确定性输入（保 §8 golden test）。

### 3.3 并发与限流
3 家各自 QPM 限速并行；Fetcher 并发池 + per-domain 礼貌延迟 + 退避；失败记日志、跳过、标红不入分母。

---

## 4. 评估层 Assess（算指标 + 打分）

### 4.1 命中指标（基于 L1/L2，每模型 + 总体）
Mention rate / Citation rate / Avg position / Share of Voice / Sentiment；分母 全量 129(43×3) / 核心 45(15×3)。
> **核心 15 题**（`prompts.csv` `core` 列标记，按类别比例抽样 + 品牌/自消费加权，覆盖全 7 类）：`C01·C04·C07 / M01·M03 / D01·D04·D07 / K01·K03 / S02·S04 / B01·B02 / G01`。

### 4.2 诊断分（基于 L3 正文/已发布页，读 `rules/`）

> **GEO 与 SEO 是两套独立评分系统**：各自 0–100、各自权重、各自归一化，**不合成总分、不互相折算**；报告分开呈现、优化建议分开出（见 §8）。

**GEO 6 维复合分（0–100）**——v1 基线权重（源自 geo-audit skill）：
| 维度 | 权重 |
|---|---|
| Citability（可引用性） | 25 |
| Brand（品牌信号） | 20 |
| E-E-A-T | 20 |
| Technical GEO | 15 |
| Schema | 10 |
| Platform（分发） | 10 |

**SEO 5 支柱复合分（0–100）**——v1 基线权重（本次新定）：
| 支柱 | 权重 | 依据 |
|---|---|---|
| 可抓取性 & 索引 | 20 | AI 爬虫抓不到一切免谈，GEO 前提 |
| 技术地基（性能/可渲染） | 10 | 去 Lighthouse 后仅靠静态信号(HTTP/可渲染/移动端)+GSC 索引覆盖，数据有限且对“被引用”影响小 |
| 页面优化（标题/H/结构化/结构） | 25 | 直接决定模型能否解析摘取 |
| 内容质量 E-E-A-T | 25 | 模型信不信你的根 |
| 权威（外链/品牌/真实搜索表现） | 20 | 模型当可信源的程度，含 GSC 真实曝光 |

> 两套权重均为 **v1 基线**，随规则迭代按研究结论调整，每次归一化到 100%（见 §7）。
> **语义维度确定性化（点 1 决策）**：`E-E-A-T`、`文案 GEO 友好度` 等语义维度**一律以确定性代理信号打分**（作者/日期/引用/schema 有无、定义段/表格/数据点计数、FAQ 块…），**不使用 LLM 裁判** → §4 全确定性，保 §8/§12 字节级 golden test。（B 仅做 BFCL 工具调用评估、无 LLM Judge；LLM 判分方案本期不引入。）

**来源属性**：标题关键字命中 / 内容关键字覆盖 / 文案 GEO 友好度 / 权威性(降级) / 时效性。

**权威维度信号清单**（GEO E-E-A-T/Brand + SEO 权威支柱共用；本质=被世界认可的程度的代理）：

| 档 | 信号 | 数据源 | 状态 |
|---|---|---|---|
| **P0 可得** | 页面内 E-E-A-T：作者署名+资质、发布/更新日期、参考文献/引用外链、about/contact/作者页、`schema.org` Organization/Person/author、编辑政策 | `bs4`+Kimi 解析 | ✅ 本期 |
| **P0 可得** | GSC 真实搜索表现：曝光/点击/CTR/平均位次/查询词 | GSC 快照 | ✅ 本期 |
| **P0 可得** | 自有语料品牌信号：SOV、L1/L2 被提及/被引用频次 | 采集结果 | ✅ 本期 |
| **P0 可得** | 站内技术信任（弱）：HTTPS/canonical/sitemap/robots | 抓取静态信号 | ✅ 本期 |
| **P2+ 缺** | 反向链接 / 引荐域（off-page 最核心）| Ahrefs/Majestic/Moz/SEMrush（付费）| ⛔ 未知降级 |
| **P2+ 缺** | 域名权威度 DR/DA/TF-CF | 同上（付费）| ⛔ 未知降级 |
| **P2+ 缺** | 社交信号、第三方口碑（Trustpilot/Reviews）| 各平台/第三方 API | ⛔ 未知降级 |
| **P2+ 缺（低成本优先补）** | 知识图谱/实体存在性 | Wikidata / Google Knowledge Graph API | ⛔ 未知降级 |

> **报告缺口标注（强制）**：权威维度**含 off-page 外部数据缺口**，P2+ 信号按"未知"降级；报告须显式标注"权威分基于 P0 代理、外部权威未计入"，避免读数误导。竞品标杆用**同口径 P0 代理**打分 → 自审↔竞品**差值仍有参考意义**（§4.2 差值口径）。日后补外部源优先级：① Wikidata/KG 实体存在性（免费/低价、对 LLM 引用直接相关）② 1 个反链源（DR + 引荐域）。

**对象两组 → 差值**：目标自审（sunhestia.com）vs 被引用竞品标杆。

### 4.3 自审 SEO 技术信号（去 Lighthouse，换 GSC）
- ❌ 去掉 Lighthouse CWV（重、需 headless chrome）
- ✅ **GSC service account**（`geo-agent/gsc-nova-dcf72be93b2c.json` 已就位）：曝光/点击/CTR/position/查询词/页面 → 真实搜索表现，喂"权威/可发现性"维度
- ✅ **抓取层静态信号**（httpx + bs4，无需 headless）：canonical/sitemap/robots/移动端/结构化数据/HTTP 状态 → 支柱 1 & 3 评分依据
- ⚠️ GSC 中国访问需代理
- 🔒 **快照化输入**：每轮 GSC 拉取结果 + 抓取静态信号**落盘 `data/snapshots/w{N}/` 并绑定 `rule_version`**；报告只读快照 → GSC/页面本身随时间变，不快照就无法复现，快照后 §8/§12 的字节级 golden test 与"历史按版本重算"才成立。

> GSC 查询词同时反哺研究 agent 的问题空间（见 §5）。

### 4.4 产出
`data/analysis/w{N}/`：`source_scores.csv` + `run_scores.csv` + `self_audit.json` + `eval_report.json`（供 Reporter + Keeper 读）。

---

## 4-bis. 智能体性能评估（B · 系统质量 QA，与 §4 业务评估正交）

评的是**多智能体系统本身是否可靠**（工具调用对不对），**不是**网站被引用得怎样（那是 §4/A）。方法源自 Datawhale Hello-Agents 第 12 章。**本期仅采用「工具调用评估（BFCL 式）」**；该章的 LLM Judge / Win Rate / GAIA **暂不做**（无 LLM 裁判，故 B 结果确定、可回归）。

**评估对象**：Collector / Fetcher / Parser 的工具调用与解析正确性——
- 是否为每家**正确构造 API 调用**（`enable_search`/`tools=web_search` 等联网开关、model 名、参数结构）
- 是否**正确解析各家原生引用字段**（DashScope `output.search_info.search_results` / Ark Responses `output[].web_search_call` / BigModel Anthropic `content[].tool_result`）→ 规范化 L2
- **irrelevance 场景**：不需要联网/调用时不误调

**方法（BFCL 式，AST/签名匹配）**：
- 自建**领域 fixture**：`{输入 → 期望的工具调用(函数名+参数) / 期望解析输出}`；**不套用 BFCL 通用数据集**，测我们真实的采集工具链
- **AST 匹配**判对错：函数名精确、参数集合等价（忽略顺序）、值语义等价（沿用第 12 章 `_ast_match`）
- 四类难度沿用 BFCL：**simple**（单调用）/ **multiple** / **parallel** / **irrelevance**（该不调用时不调用）

**指标（沿用第 12 章）**：Accuracy、分类准确率（simple/multiple/parallel/irrelevance）、加权准确率（Σw=1）、参数准确率、Error Rate。

**产出**：`data/analysis/w{N}/agent_eval.json` + 报告"系统质量"小节（回归看板）。

**定位与触发**：属**测试/回归**侧、与业务闭环**旁路正交**。**由版本更新 hook 触发**——采集/解析工具链、或 model/端点/引用字段口径**版本更新时**跑一次 fixture 回归；**不在每轮采集前跑**（业务闭环始终用"上次通过 B 的版本"运行）。AST 准确率 **≥95% 才放行新版本**，不过则拦截修复重跑。结果写入报告"系统质量"观察项；**不进 §8 字节级 golden test**。**P0 落地**。

> 未来若要评"产出质量"（研究/生成 agent），可再引入第 12 章的 LLM Judge + Win Rate（Win Rate 天然对应 §4.2 自审↔竞品差值）；本期明确不做。

---

## 5. 研究 agent Research

**LLM**：Kimi K3（非被测模型，与采集层隔离）。

**输入**：L1 + L2（真实回答 + 全量引用来源）+ L3（被引用页正文 + 扩展 meta）+ brand.yaml + **GSC 查询词**（真实问题空间）。

**处理（Kimi K3）**：
- **格式特征**：对比表 / Q&A / 清单 / 定义段 / 规格卡，哪种更常被引用
- **来源特征**：按 §3.2 的穷尽维度清单归纳——**宁全勿缺，1% 可能性也记**（域名/页面/内容/结构化/权威/时效/行为-UGC/模型引用行为/地理-语言）
- **分平台差异**：Qwen vs 豆包 vs 智谱 偏好不同则**分开记**（不求统一）
- **问题空间**：GSC 查询词 + prompt 集 → 归纳真实意图簇；**向用户建议新增 prompt/选题候选**（`prompts.csv` 由用户提供，是否纳入由用户决定，冻结基线不动）

**产出**：`knowledge/playbook.md`（被引用特征清单 + 可复用内容模板）+ `knowledge/platform-profiles.md`（各平台爬虫名/收录要求/引用偏好）。其中**爬虫名/收录要求等外部事实字段由 Kimi K3 联网搜索查证**（kimi-k3 具联网能力），不靠模型记忆凭空生成，防幻觉。

**样本量纪律（自动，无阻塞关口）**：playbook 每条结论**自动标注样本量**，样本不足者标"低置信"；v1.1 全流程自动，本环不设阻塞式人工关口，人可随时在文件层复核。

**核心纪律**："高质" ≠ "高引用"，GEO 只认后者。让 eval 数据说话，不主观定义高质文章。

---

## 6. 生成 agent Generate

**LLM**：Kimi K3。

**输入**：`playbook.md` + `brand.yaml` + **选题**（来源：GSC 查询词 / 研究结论 / 评估低分维度 gap / 人指定）。

**处理（Kimi K3）**：按 playbook 的被引用特征，产出结构化、带 **Schema JSON-LD 建议**的官网内容（FAQ / 规格 / 对比 / 指南页）。

**产出**：`content/drafts/*.md`（**仅草稿**）。

**🔴 人工关口（全系统唯一阻塞关口）**：站点 `sunhestia.com` 为自有；人审"**品牌事实正确性 + 口径一致**"后，**由人判断是否触发发布**到 `site/`。机器绝不自动发（能源产品说错规格比不提更糟）。发布后 `content/published/` 留档，供 eval 对照。

> 人审三档（供"生成人审通过率"观察项统计）：✅ 直接通过 / 🟡 小改通过 / 🔴 打回重写。

---

## 7. 规则迭代 RulesKeeper（独立第 5 环）

把 PRD v4 原 Post-MVP 的"规则采纳回写闭环"提上来，且**版本化**（保未来恢复实验可比）。

**输入**：`eval_report`（命中/引用/诊断分/差值）+ `playbook`（研究结论）。

**P3 落地**：v1 成员已与代码实际计算集对齐（语义无操作，changelog 2026-08-19）；条目/权重迭代详见 2026-08-19 P3 spec。

**两层迭代（都版本化）**：
1. **规则条目迭代**：从 eval 数据 + 研究结论提炼**规则候选(draft)** → 够证据门槛才 **draft→active**
2. **权重迭代**：按研究结论调 GEO/SEO 各支柱占比——影响被引用大的维度权重↑、小的↓——**每次调整归一化到总和 100%**（自动校验，不通过则拒绝该次迭代）

**产出**：更新 `rules/{geo,seo}-rules.yaml` + `changelog.md`（status/evidence/version）+ 新 `rule_snapshot_version` 写入 `run.yaml`。

**升级门槛（自动，无人工关口）**：draft→active 由**证据门槛自动判定**（样本量/一致性达标才升级）以挡噪音规则；v1.1 全流程自动，本环不设阻塞式人工关口，人可在 `changelog.md` 事后复核并回滚。

**可追溯**：规则可迭代，但每次改动产新 version；历史 data 可按**固定 version 重算** → 未来恢复实验时按版本对齐，保 W1↔W7 可比。

---

## 8. HTML 报告 Reporter

`reports/w{N}/report.html`（Jinja2 + ECharts，单文件内嵌 CSS/JS/图表，可离线），由固定 Schema 的 `report.json` 驱动（同输入同规则版本 → 字节级一致，golden test）。

**7 节标准结构**：
1. 执行摘要（核心数字 + `rule_version`）
2. 目标自审 **GEO 6 维雷达 与 SEO 5 支柱复合分**（**两套独立评分，分开呈现，不合成总分**）
3. 3 模型横向对比（提及/引用/位次/SOV）
4. 竞品标杆差值热图
5. **规则迭代摘要**（本期 draft/active 变更 + 权重调整 + 证据）← 新增
6. 优化建议（确定性 gap→模板，按影响×成本排序）
7. 数据附录（来源清单、异常 run、模型版本、inferred 低置信）

**报告观察项**（展示不验收）：单周耗时、**单周成本（¥，各环节 API 分项，记录呈现、不考核）**、生成人审通过率、研究来源特征维度数、**工具调用 AST 准确率（系统质量 B）**、模型版本。

---

## 9. 共享知识库与 brand.yaml

### 9.1 共享知识库（系统的"记忆"）
`knowledge/` + `content/` + `rules/`：各 agent 不直接对话，只读写这些文件 → 可单独跑/测/换模型，人可在任意两步之间检查、叫停。

### 9.2 brand.yaml —— 单一事实源
从 **site/ 现有 13 页 + 竞品分析**抽取：实体定义 / 规格库 / FAQ 库 / 术语表 / 多语言映射（多语言预留）。所有内容派生自此 → 全网口径一致、显著降幻觉。

---

## 10. 编排与人工关口

- **全流程自动化（v1.1）**：采集→研究→生成→评估→规则→报告 由 **LangGraph 状态图**自动串跑；checkpoint 续跑，键 `(week,model,prompt_id,run)`；条件分支仅"实验/审计模式""全量/核心"。
- **唯一阻塞式人工关口 = 内容发布**：生成产草稿后，人核对品牌事实 → 决定是否发布到 `site/`；其余环节（研究 playbook、规则 draft→active）自动执行，仅事后可在文件层复核/回滚。
- **发布不阻断评估/报告（不变式）**：评估+报告**不 data-依赖本轮发布决策**——① 命中/引用/SOV/位次来自 L1/L2（模型当前实际引用，与我们是否发布无关，且新内容有收录延迟、当轮不生效）；② 自审 GEO/SEO 与竞品差值基于**当前线上 `site/`**，**草稿从不进评分**（§6 只评已发布）。故不发布时，全链**照常跑完、报告正常产出**，仅不含未上线的草稿；发布与否只改变"自审当轮测到的线上快照"，两者都是有效 run。一轮时序：采集→研究→生成→〔🔴发布确认〕→评估→规则→报告。
- **触发**：第一版一键跑通全链（发布处停等人确认）；跑顺后定时复跑（launchd/cron）→ 手动随时复跑（P3 落地为手动随时复跑，决策 2026-08-19，定时器不接），发布处仍停等。

| 节点 | 关口 | 把关内容 |
|---|---|---|
| 研究 → playbook | 自动（标注样本量）| 低样本结论标低置信，人可事后复核 |
| 生成 → 草稿 | 自动 | 仅产草稿，不外发 |
| **草稿 → 发布** | **🔴 人确认（唯一阻塞关口）** | 品牌事实正确性、口径一致；人决定是否触发发布 |
| 规则 draft → active | 自动（证据门槛）| 门槛达标才升级，`changelog` 可回滚 |

**不做**：机器自动发布（发布永远人确认）；常驻自主运行（定时复跑但发布处停等）。

---

## 11. 分期 P0–P3（不绑 7 周实验，集中建系统）

| 期 | 交付（6 环节落地） | 验收 |
|---|---|---|
| **P0 评测地基** | 采集（Collector：3家API+L2全量引用+L3扩展meta 两档）→ 评估（Analyst：GEO6维+SEO5支柱**两套独立**复合分+穷尽特征；Benchmarker 差值；GSC 快照自审）→ HTML报告 7节 + LangGraph DAG 编排 + 续跑 + **智能体性能评估 B1（BFCL 式工具调用回归，版本更新 hook 触发）** | 全量 129 一键跑通、产首份报告、**成本记录呈现于报告**（不设阈值考核）；**工具调用 fixture AST 准确率 ≥ 95%** |
| **P1 研究 agent** | 研究 agent：读 L1/L2/L3 + GSC查询词 → playbook.md + platform-profiles.md（穷尽来源特征；外部事实字段 Kimi 联网查证）+ 自动标注样本量 | 能从真实回答+全量引用列出被引用特征清单+内容模板；**抽样人审质量合格**（不以硬性字段清单验收）|
| **P2 生成 agent** | brand.yaml（从 site/13页抽取）+ 生成 agent：读 playbook+brand+选题 → drafts/*（官网内容+Schema）→ 🔴人审→手动发 site/ | 产出一篇通过人审、事实无误的可发布官网内容 |
| **P3 闭环** | RulesKeeper（规则条目 draft→active **自动证据门槛** + 权重迭代归一化100% + changelog + version）+ eval反哺 playbook + 定时复跑 → 手动随时复跑（P3 落地为手动随时复跑，决策 2026-08-19，定时器不接） | 复跑报告能对齐动作看到指标变化；规则版本可追溯、历史可重算 |

> P0 ≈ PRD v4 的 M0–M4 全完成（含 SEO 复合分 + GSC 升级），是可独立交付的"评测诊断平台"；P1–P3 逐环叠加成闭环。**复用已完成的 M0 连通成果**，不重做。

---

## 12. 验收指标（客观、可机器校验）

| 指标 | 目标 |
|---|---|
| 采集成功率 | ≥ 95%（分母=计划 prompt×model：全量 129 / 核心 45） |
| L2 解析与人工一致率 | ≥ 90%（fixture 校准，precision/recall） |
| 工具调用评估（BFCL式·B1）| 领域 fixture **AST 准确率 ≥ 95%**（版本更新时回归）；irrelevance 类不误调 |
| 单周成本 | **记录并呈现于报告，不作考核**；`run.yaml` 熔断仅作安全阀（防失控）|
| 报告确定性 | 同输入同规则版本 → 字节级一致（golden test） |
| **权重归一化** | 每次规则迭代后 GEO/SEO 各支柱总和 = 100%（**自动校验，不过则拒绝该次迭代**） |
| 规则版本可追溯 | 历史 data 可按 `rule_snapshot_version` 重算 |

---

## 13. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 样本太少就下结论 | playbook/规则不可靠 | 研究 agent 标注样本量；人审关口；数据攒够再定论 |
| 联网端点不返回引用 | 拿不到一手矿 | 已验证 3 家原生联网返回 source；fixture 校准 |
| 生成内容说错品牌事实 | 比不提更糟 | brand.yaml 单一事实源 + 🔴 强制人审正确性 |
| 机器自动发布 | 对外不可逆 | 发布永远人工手动，机器只产草稿 |
| 权重迭代破坏归一化 | 复合分失真 | 自动校验总和=100%，不过则拒绝该次迭代 |
| 各平台偏好混为一谈 | 策略失焦 | platform-profiles.md 分平台记录 |
| GSC 中国访问受阻 | 自审信号缺失 | 代理；缺失标红，不阻断主流程 |
| 实验暂停期站点无杠杆 | 错过窗口 | 站点继续被索引自然沉淀；系统就绪后恢复实验 |
| 采集工具链回归（API 参数/字段变更）| 静默采错数据 | 版本更新 hook 触发 B1 BFCL 式工具调用回归，AST 准确率门槛拦截放行 |

---

## 14. 与现有资产的衔接（迁移映射）

| 现有 | 整合后处理 |
|---|---|
| `geo-measurements/prompts.csv`（43 题） | 迁入 `geo-agent/input/prompts.csv`（**用户提供并冻结为可比基线**；新增 `core` 列标记 15 题）|
| `geo-measurements/{generate_week,fill_row,aggregate,parse_to_commands}.py` + `dashboard.md` + `week-01.csv` | 归档于 `docs/archive/`（新平台取代；旧 5 模型数据不跑） |
| `geo-measurements/schema.md` | 解析口径已并入 spec §3.1；原文件已清理 |
| `answers/w1-*`（47 条） | 归档为历史基线（旧 5 模型，不再可比） |
| `geo-agent/{m0_smoke,probe_*,verify_*}.py` | 归入 `geo-agent/scripts/`（探针留存） |
| `geo-agent/.env`（4 key） | 保留，新增 GSC 代理配置 |
| `geo-agent/gsc-nova-*.json` | 用于 §4.3 GSC 自审 |
| PRD v4 的 M0–M4 设计 | 落入 P0（采集/评估/报告/DAG），规则迭代从延后提至 P3 |
| `site/`（13 页） | brand.yaml 抽取源 + 生成内容发布阵地 |
| `docs/diagrams/` | 本设计落地后更新（新增 6 环节闭环图） |

---

## 15. 技术栈（沿用 PRD v4）

| 层 | 选型 |
|---|---|
| 语言 | Python 3.11 |
| 编排 | LangGraph（+ SqliteSaver，静态 DAG，仅采集→评估） |
| 采集 | DashScope 原生 `MultiModalConversation`(qwen3.7-plus 多模态) / Ark **Responses API**(豆包) / BigModel **Anthropic 端点**(glm-5.2)，均原生联网 |
| 分析层 LLM | Kimi K3（Moonshot `api.moonshot.cn/v1`，`kimi-k3`） |
| 抓取/解析 | httpx + trafilatura（正文）+ beautifulsoup4（结构特征）+ **Kimi K3 提示词解析（L3 语义 meta）** |
| 规则库 | YAML（版本化、可迭代） |
| GSC | Search Console API（service account，结果**快照化**入 `data/snapshots/`）|
| 状态/日志 | SQLite（checkpoint + 去重 + run 日志） |
| 报告 | Jinja2 + ECharts |
| 系统评估(B) | BFCL 式 AST/签名匹配（Python `ast`）+ 领域 fixture |
| 运行 | CLI 一键跑通全链（发布处停等人确认）；定时复跑延后 |

---

*整合设计 v1.1，2026-07-29（修订 2026-07-30）｜ 已通审 2026-07-30（点 1 已补入 §4-bis：智能体性能评估 = BFCL 式工具调用）｜ P0 实现计划已生成 2026-08-02：`docs/superpowers/plans/2026-08-02-p0-evaluation-foundation.md`*
*分期进度（2026-08-18 更新）：P0 ✅ 交付 2026-08-02（165 tests，w1 基线 self_geo 47.6 / self_seo 49.8）；P1 ✅ 合入 main 2026-08-13 @4fa000f（186 tests；live run 已于 08-18 补齐）；P2 ✅ 合入 main 2026-08-16/17（PR #1 `a84ada3` + spec-sync `129ead2`，237 tests）；**真跑六步 ✅ 2026-08-18 完成（P2 验收闭环）**——P1 live 产 playbook（6/7 平台联网查证）+ brand.yaml 人审定稿 + self-consumption guide 生成 validation=passed + 人审 pass + 部署 https://sunhestia.com/news/self-consumption-guide/ + 归档；live 校准 6 修复（Moonshot $web_search 协议 ×2 / 校验器假阳性 ×2 / brand ids + JSON-LD 白名单），247 tests，main@09e22bd。**P3 ✅ 2026-08-19 完成（signal registry + RulesKeeper + 全链 DAG + 反哺；w1 首轮迭代 geo-seo-v1→v2 via has_breadcrumblist promotion 7/34=20.6% 3 平台，faq draft，权重不变（2 周持续性），recalc v1 = 47.6/49.8 零漂移，rollback 创建 v3 恢复 v1）**。*
