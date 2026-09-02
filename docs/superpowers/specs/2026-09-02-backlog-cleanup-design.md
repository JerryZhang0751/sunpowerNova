# Backlog 全量清仓设计（19 项，两阶段）

日期：2026-09-02 ｜ 基线：main=45d25b5（458 passed + 2 skipped，CI 双绿）
动机：w4 前清空全部工程 backlog，消除"后续污染"风险面（测试写生产库、error 页永久冻结、L3 覆盖式缓存持续吞历史、静默降级不可见、sqlite 无 WAL 崩溃即损 checkpoint 等）。

## 0. 用户决策记录（2026-09-02 brainstorming）

| # | 决策点 | 决定 |
|---|---|---|
| D1 | L3 缓存按周隔离方案 | **A 周目录隔离**：`data/sources/w{week}/{sha1[:12]}`，每周独立快照自洽；跨周同 URL 真重抓（~60 URL/周 ≈2-5 分钟，失败 URL 当周诚实缺失） |
| D2 | static 快照 error 页例外 | **degraded 可重取**：对齐 GSC 快照语义，error 页/robots 拉取失败 → `degraded:true`，冻结守卫放行重取 |
| D3 | robots 拉取失败（未知）计分 | **None→False 保守**：不送分 + 报告呈现 degraded；实测站点 robots 全 Allow，正常周无影响 |
| D4 | SEO 总分与维度图非同源 | **全页平均**：dims 改跨页均值与总分同源；w4 起为 New 口径，报告+changelog 标注与 w1-w3（第 1 页口径）的断点；总分曲线不受影响 |
| D5 | research 墙钟预算 | **每平台 600s + 全局 3600s**（monotonic deadline）；耗尽 → 剩余平台标"外部未验证（预算）"诚实降级不崩；单次 timeout 180s 不动（codex 明令 research 层超时值不动）；`_web_search_chat` 补 `max_retries=0` |
| D6 | m0_report.json / verify_gemini36.py | **删报告 + 泛化脚本**：m0_report.json 删除（一次性产物，git 历史可寻）；verify_gemini36.py 中转站 URL 泛化为占位符后保留（relay 结论可复现证据）；不 rewrite git 历史（私有仓+无密钥本体） |
| D7 | 孤儿 fixture qwen_B02_postfix.json | **删除**（关键结论已存项目记忆 sunhestia-negative-llm-perception；未跟踪文件删除即消失，用户知情） |
| D8 | gsc_probe*.py / README | probe **gitignore**（不入库、status 去污染，README 注明存在）；README **根一个**（双线定位/闭环图/快速上手/新机器迁移清单/文档地图） |

**实现者裁量记录**（无评分语义影响，理由如附）：
- run.yaml 三处只修**原子性**不保注释——保注释需引入 ruamel.yaml 依赖（lock 109 pins 不动），且现文件已零注释；注释维护在 run.yaml.example。
- agent_eval 的 kimi 分支**删除**而非修端点——BFCL（§4-bis）评估范围=采集层三客户端的工具调用，分析层 Kimi 不属；该分支为 copy-paste 死分支（零 fixture 触发）。删后加测试锁"BFCL 仅覆盖采集层三 provider"。
- 竞品 12 名单硬编码（collector.py:92）**不动**——三周零变化、无迭代需求（YAGNI）；"与 targets.yaml 双份"已消失。
- sqlite"迁移故事"**不适用**——表结构由 langgraph SqliteSaver 管理，自建表为零。
- 黄金锁只读化采用 `assemble(write=False)` 参数——最小改动，生产路径默认行为不变。

## 1. 范围（2026-09-02 三路并行盘点对账结论）

核实 30 项：**19 项仍存在（本 spec 全修）**；已修复 7 项（targets.yaml 代理已 10808 / CI 版本+site job+workflow_dispatch 齐备 / run.yaml.example 键集一致 / data/raw 无测试残留 / analyst 裸 `except:` 清零 / 竞品双份消失 / atomic_write_text 已存在）；误报 2 项（"robots 解析反向"——真实缺陷是通配组缺口见 §9；黄金锁"二次跑假绿"——已有字面量兜底，但覆写参照仍修，见 §6）；新发现 2 项（test_graph.py 写生产 state/runs.sqlite → §2；黄金锁覆写盘上参照 → §6）。

阶段一（§2-§7）= 零评分语义影响的工程卫生；阶段二（§8-§12）= 数据与评分语义变更（w4 起生效，w1-w3 冻结产物零改动）。

---

## 阶段一：工程卫生

## 2. sqlite 加固与测试隔离

**现状**：`orchestrate/graph.py:110-111` `sqlite3.connect(...)` 后无 WAL/busy_timeout、全程无 close（连接泄漏）；`tests/test_graph.py:24` 直接调真实 `build_graph()` → 测试线程写进生产 `state/runs.sqlite`（10.5MB，test_w99 污染实锤）。

**设计**：
- 连接后执行 `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000`，再交 `SqliteSaver`。
- `run_pipeline` 持连接引用，`finally: conn.close()`；`build_graph` 作为被编译方不负责关闭（调用方所有权，docstring 注明）。
- `test_graph.py` 改 patch：checkpointer 用 tmp sqlite（`tmp_path`），与既有 `test_collector` patch 模式对齐。
- 生产库清洗：备份 `state/runs.sqlite` → 删除 `test_*` 线程（langgraph thread API 或 SQL，以备份可回滚为前提）。

**测试（红→绿）**：新测试断言连接参数（WAL 生效、busy_timeout）；test_graph 改造后生产库 mtime/sha 不再随测试变化（隔离验证：跑套件前后 `state/runs.sqlite` 不变）。

## 3. 配置集中

**现状**：模型名硬编码 12 处无集中配置（kimi-k3×5：research/kimi.py:19,80、fetch/meta_llm.py:16、generate/kimi.py:64、generate/brand.py:170；qwen3.7-plus×2：collect/qwen_client.py:67、research/render.py:89；doubao×3：collect/doubao_client.py:74,82 带 `-260628` 后缀 + render.py:90 不带——两处已不一致；glm-5.2×2：zhipu_client.py:46,54 + render.py:91）；`shared/config.py:32-34` `settings.run` 每次 `RunSpec(**yaml.safe_load(...))` 完整读盘。

**设计**：
- `shared/config.py` 增 `MODELS: dict[str, ModelSpec]`（api_code + display_name per provider）；doubao 不一致以 api 真值 `doubao-seed-2-1-pro-260628` 为准，display 统一。
- 12 处引用改读 `settings.MODELS[...]`；render.py 展示名映射改为查表。
- `settings.run`/`targets` 缓存：以文件 `st_mtime` 为键（mtime 未变返回缓存解析结果）；keeper/`--next-week` 改写 run.yaml 后 mtime 变化自动失效，无需显式 invalidate。

**测试**：MODELS 与三客户端/meta_llm/generate 实际调用的一致性锁（grep 级：src 下不再出现裸模型码字面量——用测试 import config 后断言各处读 config）；mtime 缓存行为（改写文件后新值可见）。

## 4. 共享层去重与死代码

**现状**：`_kimi_chat` 三份（research/kimi.py:16 timeout=120 支持 tools / generate/kimi.py:57 timeout=300+max_retries=0 已独立演化 / generate/brand.py:167 timeout=120）；`_iter_l1` 两份均无逐条容错（assess/analyst.py:58-62 连目录存在都不查、research/corpus.py:10-16 有 base.exists 但无 per-record try）；`report/schema.py` 零调用者纯死代码；`eval/agent_eval.py:110-117` kimi 分支与 zhipu 分支逐字相同且端点错（`/messages`，Kimi 实为 OpenAI 兼容 `chat.completions`）+ 零 fixture 触发=死分支。

**设计**：
- 抽 `shared/kimi_client.py`：`make_kimi_client(timeout, max_retries)` 构造器 + 统一 `_chat` 帮助函数（支持 tools 参数）。**各层现值保留**：research 120/180s、generate 300s+retries0、brand 120s——本项只去重不改值（codex 明令 research 层不动）。
- 抽 `_iter_l1` 单实现到 `shared/`（如 io_utils 或新 l1_utils）：查目录存在 + per-record `try/except` 计数告警 + 跳过坏行；analyst/corpus 共用。坏 JSON 从"整体崩溃"变"跳过+可见计数"。
- 删 `report/schema.py`；删 agent_eval kimi 分支 + 其 fixture 引用（如有）。

**测试**：`_iter_l1` 容错（坏行跳过+计数）；BFCL 覆盖集锁（evaluate 结果 provider 集合 ⊆ {qwen,doubao,zhipu}）；全量套件不因删除回归。

## 5. run.yaml 原子写 + io_utils fsync

**现状**：写 run.yaml 三处均裸 `write_text(safe_dump(...))` 非原子（orchestrate/graph.py:147-150 `--next-week`、rules/run.py:63-66 do_rollback、rules/keeper.py:170-173 iterate）；`io_utils.atomic_write_text`（io_utils.py:6-10）无 fsync。

**设计**：三处改 `atomic_write_text`（注释剥光已既成事实，见 §0 裁量）；`atomic_write_text` 补 `os.fsync`（文件级；目录级不做的理由：单进程场景 os.replace 原子性已足）。

**测试**：三处写入走原子路径（patch/monkeypatch 验证调用）；fsync 后 tmp 消失+内容完整。

## 6. 测试与守卫补强

**现状**：恒真测试 2 处（tests/test_prompts.py:10 `assert X==X`、tests/test_fetcher.py:33-35 同字面量两侧）；黄金锁 tests/test_v1_semantics.py:49 每次 `assemble(1)` 无条件覆写 `data/analysis/w1/eval_report.json` 盘上参照（漂移首跑即毁参照，虽有字面量兜底不假绿）；`generate/run.py:222-223` `--suggest` 未过 `validate_production_week`（`--topic` 有）；`fetch/gsc.py:45-47` rule_version 不匹配告警分支零测试覆盖；`run.yaml.example` rule_version=geo-seo-v2 滞后实际 v4 无锁；`generate/run.py:109-112` 同 slug 无条件写 drafts（published 同 slug 时落影子文件；09-02 c2d0de1 已有近重复 flag 门但草稿覆盖静默、人工 override 后 published 仍可被覆写）。

**设计**：
- 恒真测试改真断言（PROMPT_SET_VERSION 非空+稳定格式；sha1_url 对不同 URL 不同值+确定性重复调用同值）。
- `assemble` 增 `write: bool = True` 参数；黄金锁测试传 `write=False` 只读重算+断言，盘上参照不再被测试触碰。
- `--suggest` 接 `validate_production_week`（与 `--topic` 对齐）。
- 补 gsc rule_version mismatch 测试（不匹配仍冻结 + log.warning 可见）。
- run.yaml.example 增 coherence 锁测试（example 的 rule_version == 当前生效版本；升版时测试红，迫使同步——消灭"v1 滞后"复发）。
- `run_generate` 写盘前查 `content/published/{slug}.md` 存在 → 拒绝写 drafts + 明确报错（`--override --reason` 可越过，与 flagged 门同通道）；已有近重复门保持。

**测试**：各守卫红→绿（published 同 slug 拒绝/override 放行；suggest 901 被拦；example 版本锁红绿演示）。

## 7. P3 文件处置

**现状**：见 §0 D6-D8 + `.claude/worktrees/`（6.3M）未被根 .gitignore 覆盖污染 status；`site/DEPLOY.md:28` 推荐 `wrangler login`（代理后 CSRF 坏，真实流程=.cf_token）；全库零 README。

**设计**：
- 删 `geo-agent/scripts/m0_report.json`、删 `geo-agent/tests/fixtures/raw/qwen_B02_postfix.json`（D7，删除前向用户最终确认一次——不可逆）。
- `verify_gemini36.py` 中转站 URL 泛化为 `<RELAY_BASE_URL>` 占位 + docstring 注明 key 走环境变量。
- 根 `.gitignore` 追加 `.claude/worktrees/` 与 `geo-agent/scripts/gsc_probe*.py`。
- `site/DEPLOY.md` 重写部署节：`.cf_token` + `CLOUDFLARE_ACCOUNT_ID` + `npx wrangler pages deploy` 真实流程（源自周迭代 runbook 实操命令）。
- 新建根 `README.md`：双线定位（GEO 实验 + 多 Agent 平台）、6 环节闭环 ASCII 图、快速上手（安装/测试/周迭代入口）、**新机器迁移清单**（git clone + data/state/reports ~18MB + .env + GSC key + site/.cf_token + 代理 10808 + python3.11/node——呼应 2026-09-02 可移植性讨论）、文档地图（spec/plan/runbook 指针）。不含任何密钥/项目号。

**测试**：`git status` 未跟踪污染清零（除 .claude/worktrees/ 既有目录被 ignore 后不可见）；README 存在性+无敏感串扫描（grep 项目号/密钥模式）。

---

## 阶段二：数据与评分语义（w4 起生效；w1-w3 冻结产物零改动）

## 8. L3 缓存周目录隔离（D1 方案 A）

**现状**：`shared/storage.py:12-16` `source_dir` 键=sha1(URL) 无周维度——w3 已覆盖 w2 页面态（w2 SEO 49.9 永不可复算，2026-09-01 已证）；`fetch/fetcher.py:115-116` text.md/meta.json 两文件各自原子但无成对事务（中间崩溃留孤儿 text.md）；读路径两条口径不一致——`fetcher.py:90-92` 只判 text 存在就读 meta（FileNotFoundError）→ `research/sample.py:27-33` 吞成 failed → 该 URL **永久不可抓**（每次先在读缓存处崩）；`analyst.py:74-77` 先判 meta 存在 → 静默 None。盘上现况：`data/sources/` 186 个 12 位 hash 目录。

**设计**：
- `source_dir(repo, week, url)` = `data/sources/w{week}/{sha1[:12]}`；全部调用方（fetcher 读写、analyst `_load_l3_source`、research/sample 等）接 week 参数。
- **成对原子**：写序改 meta.json → text.md（text 存在 = 完整对标志）；读命中 = 两文件齐备，缺任一 = miss 触发重抓（消灭"永久 failed"路径；孤儿 text.md 在下次抓取时被覆盖修复）。
- **存量迁移**：186 目录 `mv` 进 `data/sources/w3/`（=09-01 后混合态；spec 如实记录：w1/w2 页面态不可恢复为既成事实，w3 目录是"w3 评估实际消费的态"——重算 w3 = 可复现）。
- 同周 resume 缓存命中保留；跨周同 URL 真重抓（D1 已批代价）。

**测试**：键含周维度（同 URL 不同周不同目录）；缺 meta 判 miss 重抓；写序（先 meta 后 text）；迁移脚本幂等（重复跑不炸）。

## 9. static 快照 degraded + robots fail-closed + 解析修正

**现状**：`fetch/site_signals.py:64-71` 快照存在即冻结（注释自认"无 degraded 概念"），error 页（http_status=None+error 字段）永久冻进周数据；`site_signals.py:75-77` robots 拉取异常 → robots="" → `:11-17` `_robots_allows_ai` 空/未匹配一律 True（fail-open 送分，经 registry.py:43-44 进 GEO 加权）；解析缺口：`:14-15` `if not block: return True` 忽略 `User-agent: *` 组（被封当允许）+ `"Disallow: /" in block` 子串误伤 `Disallow: /private`（过严向）；`tests/test_site_signals.py:42-91` 把 fail-open 锁成预期、`:302-313` 断言任意内容冻结。

**设计**：
- **解析修正**：`_robots_allows_ai` 支持 bot 专属组优先、无专属组时回落 `User-agent: *` 组；Disallow 路径匹配精确化（规则行解析，非子串包含）；无任何组/空 robots → True（真·无限制语义保留）。
- **fail-closed（D2/D3）**：robots 拉取异常 → `robots_ai=None`；快照顶层 `degraded=true`（守卫放行重取，对齐 gsc.py:44 语义）；`assess/registry.py` None → False 计（不送分）；报告呈现 robots 真实状态（None 显示"未知(degraded)"）。
- **error 页例外（D2）**：快照组装时任一页 `error` 字段/http_status 非 200 → 顶层 `degraded=true`；守卫改为"存在且非 degraded → 冻结"（degraded 快照可整体重取）。跑前预热从必需降为保险。
- 既有测试按新语义重写（旧断言即 bug 固化）。

**测试**：通配组 Disallow → False；`Disallow: /private` 不误伤全站；拉取失败 → None+degraded+守卫重取；error 页快照 degraded 可重取；干净快照仍冻结。

## 10. SEO 呈现一致性（D4）+ avg_position + 成本呈现

**现状**：`assess/analyst.py:321-330` `total`=各页均值但 `dims=seo_scores[0].dims`（注释自认"代表页"）→ 报告 `report.html.j2:551`（总分=均值）与 `:603-612`（维度图=第 1 页）数字对不上；`analyst.py:342` `gap.metrics.avg_position` 恒 None 硬编码占位（per-model avg_position 已在 `:227-228,391` 真实计算，w3 fixture 见 5.5/6.5，未接入）；成本：L1 usage 已记录（w3 实测 45 个中 15 个非空 token 数）但未汇总、未入 eval_report、报告零呈现（spec v1.1 要求"记录并呈现"，成本不考核）。

**设计**：
- `dims` 改全页各维度平均（数值语义=站点级；与 total 同源）；eval_report 结构不变（dims 值变）；**changelog + 报告注明 w4 起 dims 口径=全页平均，w1-w3=第 1 页口径，跨周 dims 对比有断点**（总分曲线不受影响，一直是均值）。
- `avg_position` 接入：把 `:227-228` 已算的 per-model 值按 gap 语义聚合（品牌 mention 页的平均排名）进 `gap.metrics.avg_position`；记忆注记"恒 None 勿消费"随之作废。
- **成本节**：analyst 汇总 L1 usage → `eval_report.cost = {per_provider: {calls_with_usage, total_tokens(拆 input/output 若有)}, generated_at_week}`；报告加"成本（token 用量，不折价）"小节——无价格表（P1 既定：拒绝假精度）。RunRecord/runs.jsonl 契约**不动**（采集层零改动）。

**测试**：dims 聚合（多页 fixture 均值断言）；avg_position 非 None 且与 per-model 一致；cost 节存在+数值来自 L1 usage；报告模板渲染含成本节。

## 11. research 墙钟预算（D5）

**现状**：`research/kimi.py:73-97` `_drive_web_search` 仅 `max_rounds=10` 无 deadline；`:99-102` `_web_search_chat` timeout=180 且未设 `max_retries=0`（SDK 默认重试 2 → 单轮最坏 3×180s）；`:104-121` `web_search_verify` 7 平台循环无聚合预算——最坏 ≈10.5h 无界。

**设计**：
- `_web_search_chat` 加 `max_retries=0`（对齐 generate 层 09-02 模式）。
- `web_search_verify`：每平台 deadline 600s（`time.monotonic`）+ 全局 3600s；进入循环前查余量，不足 → 该平台返回"外部未验证（预算耗尽）"结论（playbook 既有"外部未验证"标记复用，注明原因）；run_research 返回值/research_aggregates 记录 budget_exhausted 平台清单（可见性）。
- 单次 timeout 180s 不动（codex 明令）；research `_kimi_chat` 120s 不动。
- 长步骤 detached 运行纪律仍适用（runbook 不变）。

**测试**：mock 时间/慢响应下预算截断（每平台/全局两级）；耗尽 → 结论标"外部未验证（预算）"非异常；正常路径零行为变化。

## 12. 静默降级可见化（不改评分结果，只加可见性）

**现状**：`fetch/meta_llm.py:21-22` Kimi 失败 `return {}` 零标记 → 下游 meta.json `semantic={}` 与"真无语义字段"不可区分 → E-E-A-T 静默 0 分（analyst.py:292-296 的 degraded 判定不覆盖"有 L3 但 Kimi 失败"）；`analyst.py` 4 处评分相关静默吞（:258-260 self_geo 整段 None、:317-319 单页 SEO continue、:346-349 gap None、:179-180 竞品 continue）零日志（全文件无 logging）。

**设计**：
- meta_llm 失败 → 返回 `{"_degraded": true}` 哨兵（或 L3Source 加 `semantic_degraded` 字段——以实现简洁者为准）写进 meta.json；analyst 的 `p0_content_degraded` 判定纳入该标记。
- analyst 全文件接 logging（`logging.getLogger(__name__)`）；4 处吞异常加 `warning`（含 week/页面/异常摘要）+ eval_report 增 `degraded_events` 计数节（如 `{"self_geo_skipped": 0, "page_seo_skipped": 0, ...}`）——**评分数值零变化**（黄金锁证明），丢失变得可见。
- 报告质量门行呈现 degraded_events（非零亮黄）。

**测试**：meta_llm 失败路径落标记；坏输入下 warning 产出+degraded_events 计数；黄金锁 43.4/49.8 零漂移（证明纯可见性）。

---

## 13. 执行策略

- 分支 `backlog-cleanup` 自 main=45d25b5；顺序=阶段一（§2-§7）→ 阶段二（§8-§12）；每项 TDD 红→绿；§7 的两个删除（D6 报告/D7 fixture）执行前向用户做一次不可逆确认。
- 测试环境：`cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`（.venv 沙箱封锁既定替代；/tmp 失守则 requirements.lock 重装）。
- 完成门：全量绿（基线 458+2，预期净增 40+ 条）+ **黄金锁 43.4/49.8 零漂移** + w1-w3 冻结产物零改动（`data/raw|analysis|snapshots` 现有文件不动；L3 迁移仅 `mv`）+ `merge --no-ff` 入 main + push（HTTPS 通道）+ CI test+site 双绿（必要时 `gh workflow run CI --ref main`）。
- 交付后更新项目记忆（runbook 的 w4 注意项：L3 周目录/robots fail-closed/SEO dims 新口径/degraded 可重取）。

## 14. 风险与边界

- **§8 迁移**：`mv` 186 目录有瞬态窗口（失败可重跑，幂等）；w4 起跨周重抓使代理抖动失败率（~10%）进入当周数据——诚实缺失优于失真复用，报告 degraded 可见。
- **§9 口径**：robots fail-closed 只在拉取失败周生效（实测站点全 Allow）；static degraded 重取语义与 GSC 对齐已验证先例。旧测试重写=承认旧断言是 bug 固化（r2 先例）。
- **§10 断点**：SEO dims 口径切换是可见变更——changelog+报告双标注；若未来需 w1-w3 新口径重算，**不可行**（L3 历史不可恢复，本 spec §8 只保 w3 起可复现）——已知且接受。
- **§11**：预算截断产生的"外部未验证（预算）"结论与真查无结论在 playbook 中以原因字段区分，避免混淆置信度语义。
- **通用**：不动采集层契约（RunRecord/runs.jsonl）、不动 rules 评分权重与门槛、不跑真实采集/Kimi/发布、不 rewrite git 历史、不动 research 单次超时值。
- 工作量评估：19 项 ≈ 12-14 个 TDD 任务，两阶段一次分支交付；任何一项实施中发现与盘点证据不符（行号漂移正常，语义不符例外）→ 停下回spec 补修订记录再继续。
