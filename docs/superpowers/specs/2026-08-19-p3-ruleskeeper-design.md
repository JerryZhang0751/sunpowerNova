# P3 RulesKeeper · 规则迭代环设计

> 状态:设计定稿 2026-08-19(brainstorming 通审,四节逐节确认);**v1.1 修订 2026-08-19**(外部评审 8 条逐条核实后修订,处置记录见 §10)
> 上游权威:`docs/superpowers/specs/2026-07-29-sunpower-nova-integration-design.md` v1.1 §7/§10/§11(P3 行)
> 输入就绪:`data/analysis/w1/eval_report.json` + `data/analysis/w1/research_aggregates.json` + `knowledge/playbook.md` + `content/reviews.jsonl`

## 0. 目标与已锁定决策

P3 = 整合设计的最后一个里程碑:RulesKeeper(规则条目 draft→active 自动证据门槛 + 权重迭代归一化 + changelog/version)+ eval 反哺 playbook + 全链 DAG。验收(整合 spec §11 P3 行):**复跑报告能对齐动作看到指标变化;规则版本可追溯、历史可重算**。

Brainstorming 锁定决策(2026-08-19):

| # | 决策 |
|---|---|
| 1 | 规则条目 = **评分层实体**:active 后真实改变 GEO/SEO 评分的 signals 成员与维度构成;权重迭代另走 weights |
| 2 | 候选产生 = **纯确定性提取**(零 LLM,从 research_aggregates 桶 + eval_report),全链可 golden test |
| 3 | 权重迭代 = **证据强度公式**(确定性、步长上限、夹值、归一化 100%) |
| 4 | 编排 = **全链入图**(research/generate/rules 三节点进 LangGraph DAG,闭环合成) |
| 5 | 定时复跑 = **不接定时器**,用户随时手动复跑(见 §9 偏差记录) |
| 6 | eval 反哺 = playbook 增**确定性渲染**的「上期动作→指标对照」节;Kimi prompt 不动 |
| 7 | 总体方案 = **信号注册表 + 数据驱动成员关系**(方案 A;公式留代码、成员进数据) |
| 8 | 证据口径 = **唯一 URL(页-周)计数**(v1.1;外部评审证实 134 出现次数仅 34 唯一 URL、youtube 退化 URL 重复 14 次) |
| 9 | 权重迭代加 **2 周同向持续性门槛**(v1.1;观察性证据无未检索对照组,首周只记录不调权) |

**探索期关键发现(承重)**:当前 YAML `signals:` 是文档注释,真实公式硬编码在 scorer;且已漂移——GEO eeat 的 YAML 列有 `about_page_present`/`author_schema`,代码从未计算(实际算 byline/date/cites/Org-or-Person 四项)。P3 必须先让成员关系从代码搬进数据,条目才有生效路径。

## 1. 评分引擎数据驱动化(信号注册表)

新模块 `geo/assess/registry.py`:

- 每个信号 = `(signal_id → checker)` 纯函数,签名 `(src: L3Source, brand: dict, static: dict) → float(0..100)`;实现从现 scorer **逐字搬迁**(含 `_ratio` 的 lo/hi 区间,如 `faq_block_count: (0,3)`)。GEO + SEO 全部现存信号入册。
- scorer 重写为薄解释器:维度分 = `round(mean([REG[id](...) for id in rules.signals[dim]]), 1)`,权重读 `rules.weights`。今天的公式即 N 项均值,数学同构。
- **去掉模块级 `RULES = load_rules(...)` 单例**,改为显式传参/惰性加载——否则按版本重算(§4)无法注入历史规则。
- 对外签名不变:`score_geo(src, brand, static, rules=None)` / `score_seo(...)`——可选 `rules` 参数缺省加载当前版本,重算路径注入历史版本;247 存量测试不破坏。

**v1 语义校正(一次性,changelog 记录)**:`signals:` 成员改为**代码实际计算集**。完整映射(旧 YAML 文档注释 → 旧硬编码实际计算 → 校正后成员):

| 维度 | 旧 YAML(纯文档,已漂移) | 代码实际计算 | 校正后成员(= 注册表 id) |
|---|---|---|---|
| GEO eeat | byline/date/cites/**about_page_present/author_schema**(5 名,后 2 名从未计算) | byline/date/cites/**org-or-person-schema**(4 项) | `[has_author_byline, has_publish_date, cites_external_sources, org_or_person_schema]` |
| GEO technical_geo | ai_crawler_allowed/llms_txt_present/https/canonical_self/mobile_ready(5 名,后 2 名从未计算) | GPTBot/ClaudeBot/https/canonical(4 项,crawler 实为两独立检查) | `[robots_gptbot, robots_claudebot, https, canonical_present]` |
| GEO brand | l1_mention_count/l2_cited_count/sov_share/knowledge_entity_known | 同 4 项(仅名不符) | `[mention_count, cited_count, sov_share, entity_known]` |
| GEO citability / schema / platform | 名义相近 | 同项数 | id 对齐(见 plan Task 1/3) |
| SEO 全维度 | (SEO YAML 同样漂移) | 各维度实际项 | plan Task 3 Step 5 全列 |

⚠️ 两点澄清(v1.1,外部评审 item 3):
1. **eeat 第 4 项必须保留**:w1 归档报告 eeat=25.0 且 byline/date/cites 三项实测全 false——25 分**全部**来自 org/person schema(站点含 Organization JSON-LD)。校正后成员若丢了它,eeat 25→0、GEO 47.6→42.6,黄金锁必炸。撤下的 about_page_present/author_schema 本就不计分,撤除才是"语义无操作"。
2. **已知死路径(保持零漂移,记录不改)**:citability 的 list_count 读 `structural.h_counts.ul_count`,而 meta.json 的 `ul_count` 在 structural 顶层、h_counts 内无此键 → 该信号恒 0(features.py 读顶层路径是通的)。v1 逐字搬迁保留死路径(黄金锁优先);修复属评分语义变更,留待后续版本单独决策,changelog 记录。

**候选池 checker(P3 新实现,不在 v1 成员,恰好 3 个)**:`about_page_present`(13 页清单含 /about)、`author_schema`(L3 schema_types 含 Person/author 属性)、`has_breadcrumblist`(L3 schema_types 含 BreadcrumbList)。全部由已采集数据可算,**不做新抓取、不扩 `extract_structural` 字段**(曾考虑 `video_embed_present`,经核实 L3 structural 无 iframe/video 计数,弃);它们是 draft 条目未来激活的对象。

**护栏**:`test_v1_semantics_unchanged`——新引擎跑 w1 真实 fixture → 与已归档 w1 报告分数完全一致;不过则禁合入。

## 2. 规则条目模型与证据门槛

`{geo,seo}-rules.yaml` 新增 `entries:` 列表:

```yaml
entries:
  - id: schema-add-breadcrumblist
    type: signal_add            # signal_add | signal_remove
    target: schema              # 目标维度
    signal: has_breadcrumblist  # 硬校验:必须存在于信号注册表
    status: active              # draft | active | rejected | retired
    statement: "BreadcrumbList 为被检索源 schema 第一名 (唯一页 7/34 = 20.6%)"
    evidence: {key: "schema.BreadcrumbList", share: 0.206, unique_n: 34, with_n: 7,
               platforms: 3, weeks: [1]}
    since_version: geo-seo-v2
```

**证据口径 = 唯一 URL(页-周)计数**(v1.1,决策 #8):w1 实测 134 条解析记录仅为 **34 个唯一 URL** 的重复出现(youtube.com/watch 退化 URL 重复 14 次;总检索记录 1469)——出现次数口径通胀样本量、令 `sample_n≥100` 形同虚设。全部证据计数(分子/分母/平台归因)一律在**去重 URL** 上进行;`features.py` 扩展聚合输出 unique 桶:`sources.unique_n`、`sources.schema_unique`(每 schema 类型的唯一页数)、`sources.schema_unique_platforms`(携带该类型页的平台并集)、formats 桶增 `unique_cited_n/unique_n/unique_platforms`。w1 唯一口径实测:BreadcrumbList **7/34 = 20.6%、平台并集 [doubao,qwen,zhipu]**;qa/faq **0/34**。

**语义诚实化**(v1.1):L1 `cited_sources` 实为各平台**检索池**(retrieved)——Qwen 答案正文不含内链,search_results 即检索池;智谱 tool_result 同为检索结果;豆包 annotations 为附着正文的真引用(唯一例外,实现注记)。`retrieved_sources / answer_citations` 契约拆分仅豆包可行、三家无法统一,**不做**;全链(spec/changelog/playbook/报告/条目 statement)统一表述「被检索源特征」,不称「被引」。

**候选提取(纯确定性)**:读 `data/analysis/w{N}/research_aggregates.json` 机器可读桶(不解析 playbook.md)。注册表候选信号 → 证据桶的映射是一张**声明式小表**(如 `has_breadcrumblist → schema.BreadcrumbList`);不在映射表的 checker 无证据源、不会被提名。eval_report 的 gap/差值作为辅助证据字段记录,不单独触发条目。证据元素字段:`{signal, kind, bucket, with_n, unique_n, platforms, share}`(with_n = 具备特征的唯一页数,share = with_n/unique_n;出现次数仅留在 aggregates 供 P1 展示)。

**生命周期与门槛**(常数集中 keeper 模块,可调;全部唯一 URL 口径):

| 转换 | 门槛(累积证据) |
|---|---|
| draft → **active**(signal_add) | `unique_n ≥ 30` 且 `share ≥ 0.15` 且 `platforms ≥ 2`(w1:34 / 0.206 / 3 → 过门) |
| draft → **rejected** | 桶存在且 `share = 0`、`unique_n ≥ 30`、持续 ≥ 2 周(如 w1 qa 0/34) |
| active → **retired** | 证据跌破激活门槛连续 2 周 |
| 任何 → **signal_remove 生效** | 需连续 2 周负证据(移除比添加保守,防抖动) |

(unique_n=30 依据:研究抽样 top-N≈30–50/周,30 ≈ 满额周样本;过不了就诚实停 draft,正是门槛本意。)

## 3. 权重迭代公式

每维度证据强度 `S_i ∈ [0,1]`,只有定义了证据流的维度参与调整(**同样唯一 URL 口径**;下表 w1 列为出现口径历史参考,unique 口径以重生成 aggregates 实测为准):

| 维度 | 证据流 | w1 参考 |
|---|---|---|
| GEO citability | `max(格式桶 unique share)` | list 88/134 = 0.657(出现口径) |
| GEO schema | `max(schema 桶 unique share)` | BreadcrumbList 7/34 = 0.206 |
| GEO brand | `(mention率 + citation率) / 2`(eval_report;答案级品牌指标,非检索池) | (0.133+0.089)/2 = 0.111 |
| GEO eeat / technical_geo / platform | 暂无证据流 → 中性,不参与 | — |
| SEO 全部 5 支柱 | 暂无(GSC 28d≈7 曝光太薄)→ 休眠,changelog 记观察项 | — |

- 调整:`delta_i = round(STEP × (S_i − S̄))`,`STEP = 3`(步长上限 ±3);权重夹在 `[5, 35]`;整数化后**最大余数法**归一到恰好 100,过 `assert_normalized`(复用 loader 现有校验)。
- **2 周同向持续性门槛**(v1.1,决策 #9):观察性证据无未检索对照组——特征在被检索源中常见可能仅因全网普遍(基率混杂)。权重调整需**本期与上期 delta 同号**才 apply;每期 `dimension_strengths` 存入 `rules_iteration.json`(供次周对照),首周只记录不动权重。changelog/报告明示「观察性相关、无对照基线」。
- **w1 预期(v1.1)**:无权重变更(首周无持续性);出现口径方向参考 S̄=0.321 → citability +1、brand −1 仅作记录。
- 全部 delta 为 0 且无条目变更 → **不升版本**,changelog 记"无变更"。
- 条目变更与权重变更同轮发生 → 合并一次升版,changelog 分项列出。

## 4. 版本化、changelog、历史重算、回滚

- 版本号沿用单序号 `geo-seo-v{N}`(两文件共享),**有变更才升版**。
- 升版流程:先把**旧文件整体归档**到 `rules/history/geo-seo-v{N}/{geo,seo}-rules.yaml`(不可变快照,entries 随文件归档)→ 再写新文件 → 更新 `run.yaml` 的 `rule_version`(keeper 自动,v1.1 全自动原则;人可在文件层事后回滚)→ 追加 changelog。
- **归档绑定代码**(v1.1):升版归档时写 `rules/history/{v}/manifest.json`(`code_commit`=git HEAD、`week`、`archived_at`)——「公式留代码」的方案 A 下,历史重算的精确性 = 版本↔commit 绑定 + v1 黄金锁共同保证(后续版本如需同等锁,可按需补 recalc 黄金)。
- `changelog.md` 由 keeper **唯一写入**、追加式、确定性渲染:版本头(周次/日期)→ 条目状态转换(带证据数字)→ 权重 old→new 表 → 观察项(SEO 休眠等)→ 回滚提示行。
- **历史重算**:`python3.11 -m geo.rules.run recalc --week 1 --rule-version geo-seo-v1`——`load_rules(name, version=None)` 读 `rules/history/` 快照,重算 `assemble(week)`,写 `data/analysis/w1/eval_report.recalc-{version}.json`(**永不覆盖原件**),可 `--render` 出报告变体。纯磁盘重算、零网络。
- **回滚(v1.1 修订)**:`python3.11 -m geo.rules.run rollback --to geo-seo-v1`——**创建新单调版本**,不倒退版本号:当前版本先归档(若未归档)→ 取 to_version 快照内容写入新版本号 `v{max(所有已知版本)+1}`,元数据 `restores: geo-seo-v1` → run.yaml 指向新版本 → changelog 记录。理由:若直接把现行版本改回 v1,之后再迭代会重新产出 `v2`,与 `history/geo-seo-v2/` 不可变归档形成**同名不同容**冲突,recalc 语义歧义。纯文件操作。

## 5. DAG 全链闭环

新图(v1.1 重排,修数据依赖倒置——P2 `--suggest --week N` 读 `data/analysis/w{N}/eval_report.json`,原序 generate 在 assess 之前则新周永远读不到本周报告、节点恒跳过):
`collect → fetch → snapshot → assess → research → generate → rules → report`
(拓扑成立:assess 只需 L1+L3+快照;research 需 L1+L3;generate 需 playbook+本周 eval_report;rules 需 eval_report+aggregates;report 收尾。)

- `research` 节点:P1 延迟的薄包装,包 `research.run(week)`(需网络+Kimi)。
- `generate` 节点:包 generate 逻辑;**自动选 `--suggest` 首名候选**,除非 `content/drafts/` 已有未人审草稿 → **跳过并记原因**(一次只积压一篇的队列纪律);只产草稿**永不发布**。
- `assess`:评分逻辑不变;**竞品评分上下文修正(v1.1)**——原实现对所有竞品传**站点的** static_signals(analyst.py),叠加候选信号 about_page_present 读站点 pages 列表后全体竞品会白拿分。改为竞品传 `static={}`(静态类信号 0 分 = 下界 proxy),报告 gap 处注明「竞品评分 = 下界代理,不可直读」(既有已知限制的显式化;完整 per-entity SiteContext 重构记为已知限制不做)。草稿从不进评分、评分基于当前线上 site(整合 spec §10 不变式保持)。
- `rules` 节点:keeper 对 w{N} 迭代(eval_report wN + research_aggregates wN),产 `data/analysis/wN/rules_iteration.json` 机读摘要。
- `report` 节点:读 eval_report + rules_iteration.json 渲染。时序语义:本周报告用 vN 评分,变更自下周生效(评分与变更摘要分离)。**⚠️ 跨周对比并非净归因**(v1.1 措辞降级):页面变更/模型 API 漂移/规则与权重变更/GSC 28 天滚动窗/收录延迟同为混杂——报告观察项列明;`recalc` 可事后以任意历史版本重算对照。
- **发布关口在 DAG 之外**:人审后用现有 generate CLI 手动发布/`--mark-published`;不发布时全链照常跑完(不变式)。
- 周次推进:`run_pipeline(week)` 手动随时跑;`--next-week` 便捷参数把 run.yaml 周次 +1。
- checkpoint(v1.1 修订):默认续跑语义沿用(thread `w{N}`);现有 `run_pipeline` 见完整 checkpoint 即**早退 no-op**(graph.py)——增 `--force-new-run`:时间戳 thread id(`w{N}-{ts}`)从头跑全链(节点文件级幂等),供补页/改规则后手动复跑同周。

## 6. eval 反哺 playbook(P1 研究环小改)

- `research.run` 输入增加三件:上期 `eval_report`(w{N−1})、`content/published/` 清单、changelog 近期变更。
- playbook 模板新增 **「6. 上期动作→指标对照」** 节,**纯确定性渲染(零 Kimi)**:上周发布 slug → 指标 delta(mention/citation/sov/self_geo/self_seo 环比)→ 规则版本变更摘要 → 诚实注(收录延迟、单周噪音、观察性非因果)。首期显示"无对照"。
- **Kimi prompt 不动**(避免重校准 P1 综合层);生成 agent 已读 playbook → 选题自动带上效果坐标。
- `content/reviews.jsonl` 人审通过率:进报告观察项(整合 spec §8),不进门槛。

## 7. 报告 §5「规则迭代摘要」(reporter 扩展)

- report schema 增 `rules_iteration` 块:`{from_version, to_version | null, entries: [{id, type, status_change, evidence}], weights_before, weights_after, observations[]}`。
- 模板第 5 节确定性渲染;同输入同规则版本字节级一致(golden test 同步更新)。w1 复跑将是首个真实迭代(v1→v2)。

## 8. 测试策略

- **单元**:registry 逐 checker fixture;门槛边界(sample_n 99/100、share 0.149/0.15);权重公式(归一恰 100、夹值、全 0 不升版、最大余数法取整);changelog 渲染 golden;recalc/rollback。
- **集成**:keeper 端到端——w1 真实 `research_aggregates.json`(**重生成含 unique 桶**)+ `eval_report.json` 拷入 `tests/fixtures/rules/` → 断言 v1→v2 条目(has_breadcrumblist active 7/34、faq 停 draft)与**权重不变**(首周持续性门槛);rollback 产新单调版本(restores 元数据);DAG 新图 fake 节点测试(顺序 = 重排后);generate 未审草稿跳过纪律;Task 0 守卫(未审/拒审/flagged 未 override 均拒绝归档)。
- **黄金**:`test_v1_semantics_unchanged`(新引擎重算 w1 = 归档分数);报告 §5 golden。
- **存量**:247 tests 不破坏;`score_geo/score_seo` 签名不变。

## 9. 交付物与偏差记录

**新模块**:`geo/assess/registry.py`;`geo/rules/` 下 `evidence.py`(证据计数器)/ `gate.py`(门槛)/ `weights.py`(公式)/ `keeper.py`(单轮迭代编排)/ `run.py`(CLI:`iterate --week N | recalc | rollback | show`)。
**改动**:两 scorer 重写为解释器;`loader.py` 增 version 参数 + 去单例;`research/features.py` 增 unique 桶聚合;`research/run.py` + playbook 模板(第 6 节);reporter schema + 模板(§5);`graph.py` 全链(重排序 + --force-new-run);`generate/run.py` mark-published 守卫 + 发布 stamp;`analyst.py` 竞品 static={}。
**新目录/产物**:`rules/history/`;`data/analysis/wN/rules_iteration.json`;playbook 第 6 节。

**与整合 spec 的偏差(需同步回写 §7/§10/§11)**:
1. 定时复跑(launchd/cron)→ **手动随时复跑**(决策 #5,用户 2026-08-19);"定时复跑"验收以手动复跑等价满足。
2. `signals:` v1 成员与代码的漂移校正(about_page_present/author_schema 撤下)——记入 changelog,语义无操作。
3. 整合 spec §5 的「被引源」表述统一降级为「**被检索源**」(retrieved;三家 API 无法统一拆分答案正文引用,豆包 annotations 例外注记)——P1 playbook 措辞随 research 反哺一并校正。
4. P2 尾巴加固随 P3 落地(plan Task 0):mark-published 校验最新人审 verdict(pass/minor;flagged 需显式 --override + reason)→ 补 stamp `published_at`/`--url` → 发布 URL 路径不在 targets.yaml site.pages 时打印待加行(实测 `/news/self-consumption-guide` 未入 13 页清单,静态自审现不覆盖该页)。

**运行约束(沿用)**:项目根 `python3.11 -m ...`(非 .venv);网络操作(Kimi/GSC/fetch)需 `dangerouslyDisableSandbox`;禁 `git add -A`;数据/密钥均 gitignored,测试 fixture 从真实数据拷贝入库。

## 10. v1.1 修订记录(2026-08-19,外部评审后)

外部评审(codex,`docs/codex_suggest.md`)8 条,逐条对照代码/数据核实后的处置:

| # | 评审主张 | 核实 | 处置 |
|---|---|---|---|
| 1 | 134 为出现次数非独立样本;字段是检索池非答案引用 | ✅ 证实(1469 记录 / 34 唯一 URL / youtube 14 次) | **采纳**:唯一 URL 计数(§2)+ 语义诚实化 |
| 2 | 观察性相关不能自动改规则 | ✅ 证实(P1 §4.3 明文禁因果表述) | **折中采纳**:条目保留自动;权重加 2 周持续性(§3)——比评审建议(advisory-only)宽,比原稿保守 |
| 3 | v1 零漂移数学不成立(eeat 第 4 项会丢) | ⚠️ 对 spec 措辞成立;对 plan 不成立(plan Task 1/3 已含 org_or_person_schema 与双 crawler 拆分) | **采纳为文档修正**:§1 补完整映射表 |
| 4 | DAG 依赖倒置 + checkpoint 复跑 no-op | ✅ 证实(generate 新周恒跳过;graph.py 早退) | **采纳**:重排 + --force-new-run(§5) |
| 5 | 版本模型无法精确重算;回滚版本号冲突 | ✅ 证实(同名 v2 冲突推演成立) | **采纳**:manifest 绑 commit + 回滚新单调版本(§4) |
| 6 | 竞品评分借站点静态信号 | ✅ 证实(analyst.py) | **最小修**:竞品 static={} + 报告注记(§5);SiteContext 重构记已知限制 |
| 7 | 归因不净;targets 漏新页;发布归档缺元数据 | ✅ 三点证实 | **采纳**:Task 0 + 措辞降级(§5/§9) |
| 8 | mark-published 只挡 rejected | ✅ 证实(run.py) | **采纳**:verdict 守卫 + override 通道(§9 偏差 4) |

附带新发现(修订期核实):citability 的 list_count 读 `h_counts.ul_count` 死路径恒 0(features.py 读顶层 `ul_count` 是通的)——v1 保持零漂移不改,记录待后续版本决策(§1 澄清 2)。

---

*P3 RulesKeeper 设计,2026-08-19 brainstorming 通审(六问 + 方案 A 确认)| v1.1 修订 2026-08-19(外部评审 8 条核实处置见 §10;plan 已同步修订)*
