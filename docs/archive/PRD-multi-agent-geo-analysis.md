# SunHestia GEO 多 Agent 分析系统 — PRD v4（MVP）

> 项目代号 **sunpower nova** ｜ 对外品牌 **SunHestia** ｜ PRD 版本 **v4（2026-07-27，MVP 切分）**
> 角色：资深产品经理 + 高级架构师 评审后修订
> 状态：**待用户评审**
> 变更摘要：
> - v3→**v4**：评审发现 v3 范围对 solo + 7 周实验窗口过大、规则迭代会破坏 W1↔W7 可比性。**切 MVP**：
>   ① 范围收紧为「采集→报告」主链路；规则改**静态快照**（保可比）
>   ② 架构降为 **LangGraph + 静态 DAG**（不要动态 Plan-Execute）
>   ③ 砍 model-behavior 规则、砍采纳回写闭环（延后）
>   ④ 新增：平台**验收指标**、**L2 引用解析契约**、**实验/审计双模式**、分析层用**非被测模型**、L3 只存正文、成本/可观测性
> - 延后项集中到 §3.2，不丢失、明确出 MVP 范围

---

## 0. 决策摘要（已锁定）

| 决策点 | 选择 | 工程含义 |
|---|---|---|
| 范围 | **MVP：采集→报告主链路** | 先跑通可用、保住实验窗口；迭代能力延后 |
| 分析目标 | **用户输入 URL**（实验模式锁定 sunhestia.com） | 双模式：实验模式（锁定）/ 临时审计模式（自由） |
| 模型集 | **Qwen / 豆包 / 智谱** | 经 DashScope/Ark/BigModel + 原生联网搜索（国内可达、保真） |
| 规则 | **静态快照**（MVP 不迭代） | 保证 W1↔W7 同口径可比；规则版本随数据快照留存 |
| 架构 | **LangGraph + 静态 DAG** | 流水线步骤固定；重试/续跑用 checkpoint，不要动态 Plan-Execute |
| 报告 | **本地 HTML**（标准化模板） | Jinja2 + ECharts；含简化优化建议（gap→模板建议） |
| 分析层 LLM | **Kimi K3**（非被测模型，用户提供 key） | 避免 Qwen/豆包/智谱自评偏差，与采集层隔离 |
| 技术栈 | **Python + LangGraph** | 与现有 `.py` 同构，可脱离 Claude Code 独立跑 |

---

## 1. 背景与目标

### 1.1 背景
SunHestia 7 周 GEO 实验（W1–W7，2026-07-27 → 2026-09-13，见 §13.1）需自动化测量「各 LLM 联网作答时是否提及/引用 SunHestia」并产出可执行优化建议。窗口紧（7 周），故先交付 **MVP 主链路**，迭代能力延后。

### 1.2 MVP 目标
> 跑通一条**确定性、可复现**的流水线：用户选模型/目标 → 经各厂官方 API **原生联网搜索**采集答案+引用 → 抓取来源正文 → 按静态规则评分（GEO + SEO 定性）→ 3 模型横向对比 + 自审↔竞品差值 → 产出**标准化本地 HTML 报告**（含简化优化建议）。**全程同口径，保证 W1↔W7 可比。**

### 1.3 非目标（本版不做）
- 实时监控/告警；多语种；公开 SaaS；自动改写站点代码
- ChatGPT/Gemini/Grok/DeepSeek（已移除）

---

## 2. 用户与使用场景

| 维度 | 说明 |
|---|---|
| 主要用户 | 项目运营（单人） |
| 触发 | CLI 手动 / 每周日定时（launchd/cron） |
| 典型场景 | 编辑 `input/run.yaml`（选模型/周号/模式）→ 周日自动跑 → 周一开本地 HTML 报告 → 看分数+差值+建议，决定本周杠杆 |
| 频率 | 每周 1 次；全量周（W1/W4/W7）= 43×3=129，核心周 = 15×3=45 |

---

## 3. 范围

### 3.1 MVP In Scope
1. **双模式目标**：实验模式（锁定 sunhestia.com 13 页）/ 临时审计模式（自由输入 URL）
2. 模型可选默认全选（Qwen / 豆包 / 智谱）
3. 各厂官方 API + **原生联网搜索**采集
4. **L2 引用解析契约**（方案①：逐厂结构化 + 文本兜底）+ golden fixture 校准
5. 三层存储：L1 答案 / L2 来源 / **L3 仅正文+meta（不存 raw.html）**
6. **静态规则**评分：GEO 6 维复合分 + SEO 5 支柱定性清单（不产复合分）
7. 3 模型横向对比 + 自审↔竞品差值
8. 标准化本地 HTML 报告 + **简化优化建议**（gap→模板映射，确定性）
9. LangGraph 静态 DAG + checkpoint 续跑 + run 日志
10. 平台**验收指标**埋点（见 §7.4）

### 3.2 延后（Post-MVP，不丢失）
- **规则持续迭代**：采纳回写闭环（RulesKeeper）、`draft→active` 证据门槛、规则 changelog（用户补充 #5 的核心，MVP 用静态快照替代以保证可比）
- **模型行为规则**（model-behavior.yaml，n=3 价值薄）
- **动态 Plan-and-Execute**（Planner/Replanner）
- **SEO 复合分**（权重 TBD，MVP 只定性）
- **LLM 抽引用**（方案③，精度不足时升级）
- Recommender 的 LLM 驱动/模型感知建议（MVP 用确定性 gap→模板）
- **自动提示词生成**：MVP 提示词集由用户提供（`input/prompts.csv`）并冻结——内容指纹记为 `prompt_set_version`，与 `rule_snapshot_version` 同为控制变量、保证 W1↔W7 可比（漂移即变 version、可检测）。**延后项**：站点分析→提示词草稿（仅作初始化种子；须过「意图分布护栏」brand 类 ≤10% + 人工校准 + 冻结为单一 `prompt_set_version`，不参与每周测量）

### 3.3 Out of Scope
站点代码自动改写；公开报告页；非英语市场

---

## 4. 数据模型

### 4.1 输入
```
geo-agent/input/
├─ targets.yaml   # 目标 URL（实验模式锁定 sunhestia.com；审计模式自由）
├─ prompts.csv    # 冻结提示词集（43 题；schema: id,category,prompt,market,intent）→ 内容指纹 prompt_set_version
└─ run.yaml       # week、selected_models、mode(experiment|audit)、scope(full|core)、runs_per_prompt、rule_snapshot_version
```

> **两个控制变量（贯穿全链、保证 W1↔W7 可比）**：
> - `rule_snapshot_version` — 规则快照版本，写在 `run.yaml`（用户指定，默认 `v1`）。
> - `prompt_set_version` — 提示词集内容指纹，由 `load_prompts()` 对 `prompts.csv` 计算（sha1，漂移即变）；**不进 run.yaml**，随每条记录留存。自动生成提示词为 Post-MVP（§3.2）。

### 4.2 三层存储
| 层 | 内容 | MVP 简化 |
|---|---|---|
| L1 答案 | 答案原文 + 元信息（model/model_version/run/ts/是否联网/耗时） | — |
| L2 来源 | 规范化引用列表（见 4.4） | 方案① 解析 |
| L3 快照 | **正文 text.md + meta.json（标题/HTTP/content-type/抓取ts）** | **不存 raw.html**；JS-only 站标「不可分析」不入分母 |

```
geo-agent/
├─ input/
│  ├─ targets.yaml          # 目标 URL（实验锁定 / 审计自由）
│  ├─ prompts.csv           # 冻结提示词集 → prompt_set_version
│  └─ run.yaml              # week/models/mode/scope/runs_per_prompt/rule_snapshot_version
├─ data/
│  ├─ raw/w{N}/{model}/{prompt_id}.json                       # L1 答案+元信息
│  ├─ sources/{sha1[:12]}/{meta.json,text.md}                 # L3 正文+meta，跨周去重
│  └─ analysis/w{N}/{source_scores.csv, run_scores.csv, self_audit.json, report.json}
├─ rules/      geo-rules.yaml  seo-rules.yaml                  # 静态快照，见 §6
├─ fixtures/   {qwen,doubao,zhipu}/{sample}.json               # P3 golden fixtures
├─ state/      runs.sqlite                                     # checkpoint+去重+run日志(失败/429/解析置信度/采纳记录-延后)
└─ reports/    w{N}/report.html
```

### 4.3 与现有实验衔接
- 复用 `geo-measurements/prompts.csv`（43 冻结题）
- 复用 `answers/` 命名规范（`w{N}-{model}-{prompt_id}`），镜像兼容 `fill_row.py`
- **新平台取代旧** `aggregate.py / dashboard.md`（P7）：旧 5 模型数据归档不跑；W1 三家基线**重新采集**
- 模型集 = Qwen/豆包/智谱；分母 129（全量）/ 45（核心）

### 4.4 L2 引用解析契约（P3，方案①）
**规范化记录（每 prompt×model）：**
```
cited_sources: [ {position, url, title, snippet, extract_method: structured|inferred} ]
derived: mentioned(Y/N) · cited_with_link(Y/N) · citation_position · sentiment · competitors_mentioned
```
- **结构化优先**：解析各家原生字段（DashScope `search_results` / Ark `web_search` / BigModel `web_search info`）→ 规范化
- **文本兜底**：结构化空时，正则抽正文 URL，标 `extract_method=inferred`
- **品牌判定**（沿用 `schema.md`）：`mentioned` 认字面 `SunHestia`/`sunhestia.com`；`cited_with_link` 认指向 sunhestia 的可点击链接；品牌类 prompt（B01–B04）复读不算提及
- **校准（P15）**：每家 golden fixture → parser 输出 vs 人工标注，测 precision/recall，低则调阈值；`inferred` 记录入低置信桶

---

## 5. 分析维度（规则库驱动，静态）

> MVP：规则 = **静态快照**，随每次 run 的 `rule_snapshot_version` 留存；重算历史数据时固定版本 → 保 W1↔W7 可比。维度定义与权重存 `rules/*.yaml`，Analyst 运行时读取。每维度 0–100 + 可解释依据；对象分两组：**目标自审** vs **被引用竞品标杆**，输出差值。

### 5.1 维度来源
| 维度组 | 内容 | 规则来源 |
|---|---|---|
| **GEO** | 6 维加权复合分（§6.1） | 移植 `geo-audit` skill |
| **SEO** | 5 支柱**定性清单**（不产复合分，§6.2） | 移植 `seo-audit` skill |
| **来源属性** | 标题关键字命中 / 内容关键字覆盖 / 文案风格 GEO 友好度 / 站点权威性（降级估算）/ 时效性 | 系统自有标尺 |
| ~~模型行为~~ | ~~n=3 价值薄~~ | **延后** |

### 5.2 自审专属
目标 URL 额外做 SEO 技术信号：Lighthouse（CWV）+ 抓取层 canonical/sitemap/移动端/结构化数据（**仅静态 HTML 可见**）。GSC 接入延后（需 service account，§14）。

### 5.3 第三方数据
权威性：免费档不足 → MVP **降级估算**（域名年龄 + 估算），付费接入延后。

---

## 6. 规则系统（MVP：静态快照）

### 6.1 GEO 规则（移植 `geo-audit` skill）
复合 GEO 分 = 6 维加权（0–100）：Citability 25 / Brand 20 / E-E-A-T 20 / Technical GEO 15 / Schema 10 / Platform 10。附评分分级、严重度分级、业务类型调整、质量门。

### 6.2 SEO 规则（移植 `seo-audit` skill，定性）
5 支柱检查清单（可抓取性&索引 / 技术地基 CWV / 页面优化 / 内容质量 E-E-A-T / 权威），每项 `Issue / Impact(H/M/L) / Evidence / Fix`。**MVP 不产 SEO 复合分**（seo-audit 无显式权重，复合分延后定权）。

### 6.3 规则快照与可比性（P2 解决）
- MVP 规则**冻结为快照** `rules/geo-rules.yaml@v1` / `seo-rules.yaml@v1`
- 每次run记录 `rule_snapshot_version`；历史数据可按**固定版本重算** → W1↔W7 同口径
- 规则修订只在**新快照版本**生效，不污染历史得分

### 6.4 延后（Post-MVP，见 §3.2）
规则条目 schema 的 `status/evidence/version` 字段、采纳→回写闭环（§v3 的 6.4/6.5）、model-behavior。

---

## 7. 报告规格

### 7.1 形态
本地 HTML（`reports/w{N}/report.html`），单文件内嵌 CSS/JS/图表，可离线打开；Jinja2 + ECharts。

### 7.2 标准化结构（固定模板，可 diff）
1. **执行摘要**：结论 + 核心数字（提及/引用/SOV/位次）+ `rule_snapshot_version`
2. **目标自审 GEO + SEO**：6 维雷达 + SEO 支柱清单
3. **3 模型横向对比**：提及/引用/位次/SOV 柱状图 + 表
4. **竞品标杆差值**：自审 vs Top 引用竞品的热图
5. **优化建议**：**确定性 gap→模板**（低分维度→对应杠杆建议），按「影响×成本」排序（**MVP 无采纳勾选**，延后）
6. **数据附录**：来源清单、异常 run、模型版本、`inferred` 低置信记录

### 7.3 标准化保证（需求 5）
报告由 `report.json`（固定 Schema）驱动 → 给定数据+规则版本，结构确定；文案用占位符；历史 diff 按规则版本对齐。

### 7.4 平台验收指标（P5）
| 指标 | 目标 |
|---|---|
| 单周全量run耗时 | < 30 min |
| 采集成功率 | ≥ 95%（**分母=计划 prompt×model 数**：全量 129 / 核心 45；失败计入、入日志可重跑） |
| L2 解析与人工一致率 | ≥ 90%（fixture 校准） |
| 单周成本上限 | **¥100**（写入 `run.yaml` 熔断；M0 实测各模型单价后细化分配） |
| 报告确定性 | 同输入同规则版本 → 字节级一致报告（golden test） |

---

## 8. 多 Agent 架构（LangGraph · 静态 DAG）

### 8.1 范式
- **静态 DAG**：节点固定 = Collect → Fetch → Score → Compare → Report；条件分支仅「实验/审计模式」「全量/核心」
- **Checkpoint**：LangGraph `SqliteSaver` → 可中断续跑、幂等（键 `(week,model,prompt_id,run)`）
- **失败处理**：节点级重试 + 退避；失败记日志、跳过、标红不入分母（此"分母"指下游 mention/citation rate 的有效采集数；采集成功率分母另计=计划数，见 §7.4）（**不**做动态重规划）

### 8.2 Agent 拆分（MVP）
```
Coordinator   读 input → 跑静态 DAG（无动态规划）
 ├─ Collector   3家官方API（原生搜索ON,stream=true）→ L1+L2（方案①解析）
 ├─ Fetcher     L2 URL 去重抓取 → L3 正文+meta（JS-only 标记）
 ├─ Analyst×N   读静态 rules → GEO 6维分 + SEO 定性 + 来源属性
 ├─ SEOAuditor  目标 URL 技术信号（Lighthouse，静态HTML）
 ├─ Benchmarker 4模型横向对比 + 自审↔竞品差值（不做模型行为假设）
 ├─ Recommender 确定性 gap→模板建议（不做模型感知/采纳回写）
 └─ Reporter    Jinja2 → 标准化 HTML
```
延后：RulesKeeper、model-behavior 提炼、动态 Planner/Replanner。

### 8.3 并发与限流
3 家官方 API 各自 QPM 限速并行；Fetcher 并发池 + per-domain 礼貌延迟 + 退避。

---

## 9. 技术栈

| 层 | 选型 |
|---|---|
| 语言 | Python 3.11 |
| 编排 | **LangGraph**（+ SqliteSaver，静态 DAG） |
| 采集层（官方API+原生搜索） | Qwen→DashScope 原生 SDK `dashscope.Generation.call`（依赖 `dashscope` 包），model `qwen-plus`，`enable_search=True`（顶层）、`result_format="message"`；豆包→火山方舟 Ark `api/v3`，model `doubao-seed-2-1-pro-260628`（OpenAI 兼容）`tools=[{type:web_search}]`；智谱→BigModel `paas/v4`，model `GLM-5.2`（OpenAI 兼容）`tools=[{type:web_search,web_search:{enable:true,search_result:true}}]` |
| **分析层 LLM** | **Kimi K3**（model `kimi-k3`；非被测模型；Moonshot 官方 `api.moonshot.cn/v1`，用户提供 key）→ 避免 Qwen/豆包/智谱自评偏差，与采集层隔离。**中转站现已全部停用** |
| 抓取 | `httpx` + `trafilatura`（正文）+ `beautifulsoup4`（结构特征） |
| 规则库 | YAML 静态快照（geo/seo） |
| 状态/日志 | SQLite（checkpoint + 去重 + run 日志） |
| 报告 | `Jinja2` + ECharts |
| 配置/密钥 | `.env`：采集 `DASHSCOPE`(Qwen)/`ARK`/`BIGMODEL` + 分析层 `MOONSHOT_API_KEY`（Kimi K3）+ `config.yaml`（model id） |
| 运行 | CLI `python -m geo_agent run --week N [--resume]`；定时 launchd/cron |

> ⚠️ model id 经 M0 冒烟确认（2026-07-27）：Qwen=`qwen-plus`（`qwen3.7-plus` 无效）、豆包=`doubao-seed-2-1-pro-260628`、智谱=`GLM-5.2`、Kimi=`kimi-k3`；豆包/智谱 web_search 调用格式待调研（M0 暴露）。

---

## 10. 与现有实验衔接
- `prompts.csv` 冻结不变
- 模型集 = Qwen/豆包/智谱；版本记 `model_version`
- **新平台取代旧** `aggregate.py/dashboard.md`（旧 5 模型数据归档）
- W1 三家基线**重新采集**（旧数据不再可比）
- 全量 129 / 核心 45

---

## 11. 数据隐私与合规
- 第三方来源正文：仅内部分析，不公开发布；报告只发聚合结论与链接
- API key（三家采集官方 + Moonshot/Kimi）：存 `.env`，`.gitignore` 覆盖，永不入库
- 答案与来源正文：本地存储

---

## 12. 风险与依赖

| 等级 | 风险 | 影响 | 缓解 |
|---|---|---|---|
| 🔴 | **三家官方 key 未到位** | M0 无法动工 | 先提供 key（§14 🔑）；可先写无依赖部分 |
| 🔴 | **L2 解析口径漂移/低精度** | 核心测量信号失真 | 方案① + golden fixture 校准 + precision/recall 门槛 ≥90%；`inferred` 隔离 |
| 🟡 | 官方模型名/参数漂移 | 采集失败 | M0 连通性冒烟 + 记 `model_version` |
| 🟡 | JS-only 来源正文取不到 | L3 不完整 | 标「不可分析」不入分母；明确边界（不上 headless，YAGNI） |
| 🟡 | 3 家 API 计费/限流 | 成本/429 | M0 实测定预算熔断；核心周 45 行；缓存 prompt 级结果 |
| 🟡 | LLM 随机性 | 周间波动 | 每 prompt 多 run 取众数 + 记版本 |
| 🟡 | 来源抓取被限流/403 | L3 缺失 | 退避 + 礼貌延迟；缺失标红 |
| 🟢 | 报告口径漂移 | 不可比 | 固定模板 + JSON Schema + `rule_snapshot_version` 入报告 |
| 🟢 | 分析层 Kimi K3 不稳 | 打分中断 | 失败重试；必要时切另一非被测模型（中转站已全停用） |

> 历史结论（存档）：中转站对任何模型都不提供真实联网 → 采集层走官方 API。v4 起中转站全停用（采集 + 分析均走各厂官方 API，分析层 = Kimi K3）。

---

## 13. 里程碑（MVP）

| M | 交付 | 验收 |
|---|---|---|
| M0 | Collector（3家官方API原生搜索）+ L2 解析（方案①）+ golden fixture + 校准 | 1 prompt×3 模型落 L1+L2，解析一致率 ≥90%，确认 model id |
| M1 | Fetcher（L3 正文+meta，去重）+ JS-only 标记 | 来源正文抽取达标 |
| M2 | 静态规则快照（geo-rules/seo-rules）+ Analyst 评分 | 单来源 GEO/SEO 评分可解释 |
| M3 | Benchmarker + 确定性 Recommender + Reporter（HTML）+ 验收指标埋点 + run 日志 | 本地报告 6 节齐全、确定性 golden test 通过 |
| M4 | LangGraph 静态 DAG 编排 + 续跑 + 端到端 1 周 | 全量 129 一键跑通、可中断恢复、<30min |
| **MVP 完成** | W1 内建完（M0–M4）+ 周末采三家基线（vanilla）→ W2 起杠杆 | 首份基线报告 |

### 13.1 实验日历（自然周 W1–W7，2026-07-27 → 2026-09-13）

> 时间线重定（2026-07-27）：W1 起改为 **7/27（周一）**，自然周（周一–周日），**9/13（周日）= W7 结束**，共 **7 周**（原 8 周压缩）。W1 报告旧 §10 路线图（W1–W8）**作废**，以本表为准。

| 周 | 日期 | 工作 | 测量 |
|---|---|---|---|
| **W1** | 7/27–8/2 | **开发（M0–M4）+ 基线处理**（站点保持 vanilla） | 周末基线 **全量 129** |
| W2 | 8/3–8/9 | 杠杆①：技术 GEO 地基（llms.txt / hreflang / 预渲染核对） | 核心 45 |
| W3 | 8/10–8/16 | 杠杆②：Schema.org 结构化数据 | 核心 45 |
| W4 | 8/17–8/23 | 杠杆③：LLM 内容重构（定义式开头 / H2-H3 / 事实摘要） | **全量 129（中期）** |
| W5 | 8/24–8/30 | 杠杆④：FAQ + 参考资料（对比页 / 术语表） | 核心 45 |
| W6 | 8/31–9/6 | 杠杆⑤：E-E-A-T（作者 / 专家 / 评价 / 认证） | 核心 45 |
| W7 | 9/7–9/13 | 杠杆⑥：站外权威（外链 / 目录 / 社区）+ 收尾（深度/时效并入） | **全量 129（终期）** |

- **全量周**：W1（基线）/ W4（中期）/ W7（终期）；**核心周**：W2/W3/W5/W6
- **周节奏**：周一二实施当周杠杆 / 周三五静默 / 周末测量
- ⚠️ **W1 是关键路径**：M0–M4 须在 W1 内（~8/1 前）完成才能周末采基线。**依赖 4 个 API key 尽早到位**；key 到位前先做不依赖 key 的 M1/M2/M3 骨架。若构建滑期，基线顺延至 W2 初、杠杆周相应压缩。
- **杠杆 7→6**：去掉独立的「时效/深度」周（并入 W7 收尾），保留 6 个高影响杠杆、维持「一周一杠杆」归因。

**Post-MVP（延后，按需）**：规则采纳回写闭环、model-behavior、动态 Plan-Execute、SEO 复合分、LLM 抽引用、GSC 接入、自动提示词生成。

---

## 14. 待确认

> 🔑 **阻塞项（先决）**：4 个 key（3 采集 + 1 分析层）**均已提供 2026-07-27**（存 `geo-agent/.env`）：
> - ✅ `DASHSCOPE_API_KEY`（Qwen `qwen-plus`）
> - ✅ `ARK_API_KEY`（豆包 `doubao-seed-2-1-pro-260628`）
> - ✅ `BIGMODEL_API_KEY`（智谱 `GLM-5.2`，key 已更正 2026-07-27）
> - ✅ `MOONSHOT_API_KEY`（分析层 Kimi `kimi-k3`）
> key 已齐；M0 冒烟已跑 2026-07-27（连通 3/5、搜索 0/4，见 `geo-agent/m0_smoke.py`）；DeepSeek 已砍（DashScope 无原生搜索）。

**v4 已全部确认（2026-07-27）**：纯A MVP；静态 DAG；规则静态快照；P3 方案①；SEO 定性；双模式；**分析层 = Kimi K3**；L3 仅正文；验收指标；新平台取代旧。

1. ✅ 分析层 = **Kimi K3**（非被测模型，用户提供 key）→ `.env` 加 `MOONSHOT_API_KEY`；**中转站全部停用**
2. ✅ 单周成本上限 = **¥100**（写入 `run.yaml` 熔断；M0 实测单价后细化分配）
3. ✅ 目标 URL：实验模式锁定 **sunhestia.com 13 页**
4. ⏸️ GSC service account：**确认延后**（非 MVP 阻塞；需 service account + 代理，详见下方说明）

> **GSC service account 说明**：Google Search Console 的"机器人账号"，程序化读取站点曝光/点击/查询词，免交互 OAuth。获取：① Google Cloud 建项目 → 启用 Search Console API → 建 service account → 下载 JSON；② 把该 service account 邮箱加入 Search Console 的 sunhestia.com 属性用户。⚠️ 中国访问需代理；MVP 的 SEOAuditor 先用 Lighthouse + 抓取层，不依赖 GSC。

---

*v4 草案 2026-07-27（MVP 切分：纯A + 静态DAG + 静态规则 + L2契约 + 验收指标）｜ 待用户评审*
