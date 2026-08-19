# P3 RulesKeeper · 规则迭代环设计

> 状态:设计定稿 2026-08-19(brainstorming 通审,四节逐节确认)
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

**探索期关键发现(承重)**:当前 YAML `signals:` 是文档注释,真实公式硬编码在 scorer;且已漂移——GEO eeat 的 YAML 列有 `about_page_present`/`author_schema`,代码从未计算(实际算 byline/date/cites/Org-or-Person 四项)。P3 必须先让成员关系从代码搬进数据,条目才有生效路径。

## 1. 评分引擎数据驱动化(信号注册表)

新模块 `geo/assess/registry.py`:

- 每个信号 = `(signal_id → checker)` 纯函数,签名 `(src: L3Source, brand: dict, static: dict) → float(0..100)`;实现从现 scorer **逐字搬迁**(含 `_ratio` 的 lo/hi 区间,如 `faq_block_count: (0,3)`)。GEO + SEO 全部现存信号入册。
- scorer 重写为薄解释器:维度分 = `round(mean([REG[id](...) for id in rules.signals[dim]]), 1)`,权重读 `rules.weights`。今天的公式即 N 项均值,数学同构。
- **去掉模块级 `RULES = load_rules(...)` 单例**,改为显式传参/惰性加载——否则按版本重算(§4)无法注入历史规则。
- 对外签名不变:`score_geo(src, brand, static, rules=None)` / `score_seo(...)`——可选 `rules` 参数缺省加载当前版本,重算路径注入历史版本;247 存量测试不破坏。

**v1 语义校正(一次性,changelog 记录)**:`signals:` 成员改为代码实际计算集合——GEO eeat 撤下从未生效的 `about_page_present`/`author_schema`。语义无操作(它们本就不计分),w1 分数零漂移。

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
    statement: "BreadcrumbList 为被引源 schema 第一名 (26/134 = 19.4%)"
    evidence: {key: "schema.BreadcrumbList", share: 0.194, sample_n: 134,
               platforms: 3, weeks: [1]}
    since_version: geo-seo-v2
```

**候选提取(纯确定性)**:读 `data/analysis/w{N}/research_aggregates.json` 机器可读桶(不解析 playbook.md)。注册表候选信号 → 证据桶的映射是一张**声明式小表**(如 `has_breadcrumblist → schema.BreadcrumbList`);不在映射表的 checker 无证据源、不会被提名。eval_report 的 gap/差值作为辅助证据字段记录,不单独触发条目。

**生命周期与门槛**(常数集中 keeper 模块,可调):

| 转换 | 门槛(累积证据) |
|---|---|
| draft → **active**(signal_add) | `sample_n ≥ 100` 且 `share ≥ 0.15` 且 `platforms ≥ 2` |
| draft → **rejected** | 桶存在且 `share = 0`、`sample_n ≥ 100`、持续 ≥ 2 周(如 w1 qa 格式 0/134) |
| active → **retired** | 证据跌破激活门槛连续 2 周 |
| 任何 → **signal_remove 生效** | 需连续 2 周负证据(移除比添加保守,防抖动) |

## 3. 权重迭代公式

每维度证据强度 `S_i ∈ [0,1]`,只有定义了证据流的维度参与调整:

| 维度 | 证据流 | w1 实测 |
|---|---|---|
| GEO citability | `max(被引格式桶 cited share)` | list 88/134 = 0.657 |
| GEO schema | `max(schema 桶 cited share)` | BreadcrumbList 0.194 |
| GEO brand | `(mention率 + citation率) / 2`(eval_report) | (0.133+0.089)/2 = 0.111 |
| GEO eeat / technical_geo / platform | 暂无证据流 → 中性,不参与 | — |
| SEO 全部 5 支柱 | 暂无(GSC 28d≈7 曝光太薄)→ 休眠,changelog 记观察项 | — |

- 调整:`delta_i = round(STEP × (S_i − S̄))`,`STEP = 3`(步长上限 ±3);权重夹在 `[5, 35]`;整数化后**最大余数法**归一到恰好 100,过 `assert_normalized`(复用 loader 现有校验)。
- **w1 实算示例**:S̄ = 0.321 → citability +1(25→26)、brand −1(20→19)、schema 0。方向符合整合 spec"影响被引大的维度↑、小的↓"。
- 全部 delta 为 0 → **不升版本**,changelog 记"无权重变更"。
- 条目变更与权重变更同轮发生 → 合并一次升版,changelog 分项列出。

## 4. 版本化、changelog、历史重算、回滚

- 版本号沿用单序号 `geo-seo-v{N}`(两文件共享),**有变更才升版**。
- 升版流程:先把**旧文件整体归档**到 `rules/history/geo-seo-v{N}/{geo,seo}-rules.yaml`(不可变快照,entries 随文件归档)→ 再写新文件 → 更新 `run.yaml` 的 `rule_version`(keeper 自动,v1.1 全自动原则;人可在文件层事后回滚)→ 追加 changelog。
- `changelog.md` 由 keeper **唯一写入**、追加式、确定性渲染:版本头(周次/日期)→ 条目状态转换(带证据数字)→ 权重 old→new 表 → 观察项(SEO 休眠等)→ 回滚提示行。
- **历史重算**:`python3.11 -m geo.rules.run recalc --week 1 --rule-version geo-seo-v1`——`load_rules(name, version=None)` 读 `rules/history/` 快照,重算 `assemble(week)`,写 `data/analysis/w1/eval_report.recalc-{version}.json`(**永不覆盖原件**),可 `--render` 出报告变体。纯磁盘重算、零网络。
- **回滚**:`python3.11 -m geo.rules.run rollback --to geo-seo-v1`——归档快照拷回 `rules/` + 改 run.yaml + changelog 记录回滚。纯文件操作。

## 5. DAG 全链闭环

新图:`collect → fetch → snapshot → research → generate → assess → rules → report`

- `research` 节点:P1 延迟的薄包装,包 `research.run(week)`(需网络+Kimi)。
- `generate` 节点:包 generate 逻辑;**自动选 `--suggest` 首名候选**,除非 `content/drafts/` 已有未人审草稿 → **跳过并记原因**(一次只积压一篇的队列纪律);只产草稿**永不发布**。
- `assess`:不变。草稿从不进评分、评分基于当前线上 site(整合 spec §10 不变式保持)。
- `rules` 节点:keeper 对 w{N} 迭代(eval_report wN + research_aggregates wN),产 `data/analysis/wN/rules_iteration.json` 机读摘要。
- `report` 节点:读 eval_report + rules_iteration.json 渲染。**时序语义:本周报告用 vN 评分,变更自下周生效**——评分与变更摘要分离,归因干净。
- **发布关口在 DAG 之外**:人审后用现有 generate CLI 手动发布/`--mark-published`;不发布时全链照常跑完(不变式)。
- 周次推进:`run_pipeline(week)` 手动随时跑;`--next-week` 便捷参数把 run.yaml 周次 +1。
- checkpoint 续跑语义沿用(thread `w{N}`,SqliteSaver)。

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
- **集成**:keeper 端到端——w1 真实 `research_aggregates.json` + `eval_report.json` 拷入 `tests/fixtures/rules/` → 断言 v1→v2 的具体条目与权重;DAG 新图 fake 节点测试(现有模式);generate 未审草稿跳过纪律。
- **黄金**:`test_v1_semantics_unchanged`(新引擎重算 w1 = 归档分数);报告 §5 golden。
- **存量**:247 tests 不破坏;`score_geo/score_seo` 签名不变。

## 9. 交付物与偏差记录

**新模块**:`geo/assess/registry.py`;`geo/rules/` 下 `evidence.py`(证据计数器)/ `gate.py`(门槛)/ `weights.py`(公式)/ `keeper.py`(单轮迭代编排)/ `run.py`(CLI:`iterate --week N | recalc | rollback | show`)。
**改动**:两 scorer 重写为解释器;`loader.py` 增 version 参数 + 去单例;`research/run.py` + playbook 模板(第 6 节);reporter schema + 模板(§5);`graph.py` 全链。
**新目录/产物**:`rules/history/`;`data/analysis/wN/rules_iteration.json`;playbook 第 6 节。

**与整合 spec 的偏差(需同步回写 §7/§10/§11)**:
1. 定时复跑(launchd/cron)→ **手动随时复跑**(决策 #5,用户 2026-08-19);"定时复跑"验收以手动复跑等价满足。
2. `signals:` v1 成员与代码的漂移校正(about_page_present/author_schema 撤下)——记入 changelog,语义无操作。

**运行约束(沿用)**:项目根 `python3.11 -m ...`(非 .venv);网络操作(Kimi/GSC/fetch)需 `dangerouslyDisableSandbox`;禁 `git add -A`;数据/密钥均 gitignored,测试 fixture 从真实数据拷贝入库。

---

*P3 RulesKeeper 设计,2026-08-19 brainstorming 通审(六问 + 方案 A 确认)| 状态:待用户审阅 spec → writing-plans 出实现计划*
