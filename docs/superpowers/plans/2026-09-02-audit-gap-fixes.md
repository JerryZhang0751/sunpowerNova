# 验收审核缺口修复实现计划（4 任务）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-09-02 晚对 backlog 清仓（merge 3b5e0ab）的独立验收审核发现 6 处测试覆盖缺口 + 2 处可补齐的裁量偏差 + 1 处 spec 修订记录缺失。本计划一次分支收口：**零评分语义影响，w1-w3 冻结产物零改动**。

**背景裁决（2026-09-02 用户批准"修改这些缺口"）:**
- **A 类 6 项测试锁**：全部补齐（A1-A6，见 Task 1）。
- **B7（§9 报告"未知(degraded)"呈现）**：**采纳实现**——原 plan 条件项为"模板有呈现位则改"，审核证实模板有 robots 分数呈现格（report.html.j2 technical_geo 信号行），按条件应改而未改；数据层已完备，本批补报告层。评分数值零变化。
- **B8（§10 changelog 断口标注）**：**维持不做**——plan 自审已记录有意偏差（规则版本账本纯净性优先，标注落在报告模板+测试锁）；写入 spec 修订记录即可。
- **B9（§11 budget_exhausted 可见性）**：**采纳实现**——落盘 research_aggregates.json + platform-profiles.md 渲染预算原因。
- **C（spec 回补修订记录）**：在原 spec 末尾追加"验收审核修订记录"节（不建新 spec 文档）。

**Tech Stack:** Python 3.11+（pytest，本机以 3.12 跑）、Jinja2 模板。

## Global Constraints

- **测试环境**（.venv 沙箱封锁既定替代）：
  `cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`
  以 **EXIT=0** 为准（summary 行可能被吞）；计数用 `-o junit_family=xunit2 --junitxml=/tmp/junit.xml` 后解析 tests/errors/failures/skipped。**基线 = 540 tests / 0 failures / 2 skipped（=538 passed；CI 因环境条件 skip 为 536+4，总数同为 540）。完成后只增不减。**
- **边界验证协议（每任务收尾必跑，顺序执行）**：
  1. `git status --porcelain` → 只出现本任务预期文件；
  2. 黄金锁：`PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/test_v1_semantics.py -p no:cacheprovider` → 2 passed（43.4/49.8 零漂移）；
  3. 冻结产物零改动：开工基线已落 `/tmp/frozen_gaps.txt`（`shasum` 文件清单）与 `/tmp/frozen_sources.txt`（`find data/sources -type f | sort`）；每任务后
     `cd geo-agent && shasum -c /tmp/frozen_gaps.txt`（静默 OK）+ `find data/sources -type f | sort | diff /tmp/frozen_sources.txt -`（空输出）；
  4. 全量套件 EXIT=0 且计数不低于基线（junit 解析为准）。
- **禁改**：`rules/*.yaml` 评分语义、`RunRecord`/runs.jsonl 契约、research 单次超时值（120/180s）、generate 300s、collect 层行为、黄金锁断言值（43.4/49.8）、`data/` 下任何 w1-w3 冻结产物、git 历史。**新测试一律不依赖网络/真实 API，不写生产 state/data；tmp 数据用 week 901**（`geo.shared.weeks.TEST_WEEK=901`，生产周号 1-3）。
- **commit 风格**：`test:`/`feat:`/`docs:` + 中文主题；**禁 `git add -A`**，显式路径；commit message 末尾 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。

---

## Task 1: 补 6 项回归锁测试（纯测试 + 1 处 docstring 改写 + 1 个幂等脚本）

**Files:**
- Test: `geo-agent/tests/test_graph.py`（追加 A1）、`geo-agent/tests/test_rules_run.py` + `geo-agent/tests/test_rules_keeper.py`（追加 A2）、`geo-agent/tests/test_config_models.py`（追加 A3）、`geo-agent/tests/test_l1_iter.py`（追加 A4）、`geo-agent/tests/test_generate_run.py`（追加 A5）、新文件 `geo-agent/tests/test_sources_migration.py`（A6）
- Modify: `geo-agent/src/geo/shared/kimi_client.py`（仅 docstring 去掉字面量 "kimi-k3"，改述为"Kimi K3（api_code 见 MODELS 注册表）"类措辞——A3 的 grep 锁要求 src/geo 除 config.py 外零裸 api_code 字面量）
- New: `geo-agent/scripts/migrate_sources_to_week.py`（A6 幂等迁移脚本，复刻 2026-09-02 一次性 shell 循环：把 `data/sources/` 顶层 12 位 hash 目录 `mv` 进 `w3/`，已是 w* 目录则跳过）

**Interfaces / 验收:**
- **A1（sqlite 连接参数锁）**：测试对 tmp 库调用 `geo.orchestrate.graph._new_run_conn()`（或等价路径建 tmp 文件连接）后断言 `PRAGMA journal_mode` 返回 `wal`、`PRAGMA busy_timeout` 返回 `5000`。不触生产 `state/runs.sqlite`。
- **A2（run.yaml 原子路径锁 ×2）**：monkeypatch `geo.rules.run` 与 `geo.rules.keeper` 各自模块命名空间里的 `atomic_write_text`（两者均为 `from geo.shared.io_utils import atomic_write_text` 导入），分别触发 do_rollback 与 iterate 升版路径，断言以 `run.yaml` 文件名被调用且写后内容正确（rule_version 变更生效）。参照既有 `tests/test_graph.py` 中 `--next-week` 的同类测试模式。tmp repo（monkeypatch REPO）。
- **A3（MODELS 一致性锁）**：① `inspect.signature` 断言 `collect_qwen/collect_doubao/collect_zhipu` 的 `model` 参数默认值 == `MODELS[...]["api_code"]`；② 扫描 `src/geo/**/*.py`（排除 `shared/config.py`）断言不出现裸字面量 `qwen3.7-plus`、`doubao-seed-2-1-pro-260628`、`glm-5.2`、`kimi-k3`（**前置：kimi_client.py docstring 改写**，使锁零例外）。
- **A4（iter_l1 告警可见性）**：caplog 断言坏 JSON/坏 schema 行触发 WARNING（消息含 "L1 残缺跳过"），且好行不受影响。
- **A5（--suggest 901 端到端）**：monkeypatch `sys.argv` 为 `["prog", "--suggest", "--week", "901"]` 调 `geo.generate.run.main()` → `pytest.raises(ValueError)`（901=TEST_WEEK 带被拦）；对照组 `--week 3` 正常路径不抛（若 suggest 会真调 Kimi，则 monkeypatch `run_suggest` 捕获参数后返回，断言收到 week==3——**禁真实 API**）。
- **A6（迁移幂等）**：tmp 目录造 3 个 12 位 hex 名目录（各含 meta.json/text.md）+ 1 个 `w3/` 目录；`subprocess` 跑 `scripts/migrate_sources_to_week.py <tmp>` 两次，两次 exit 0 且第二次前后 `sorted(os.listdir)` 与各文件 shasum 完全不变（幂等）；顶层 hash 目录清零、内容并入 `w3/`。
- 步骤：每子项先红后绿（A1/A2/A3② 在当前代码上应直接绿——属"锁"性质，红绿演示不适用；A3② 在 docstring 未改写前为红）。目标测试逐项跑过后跑全量+边界协议。

## Task 2: §9 报告层 robots「未知(degraded)」呈现

**Files:**
- Modify: `geo-agent/src/geo/assess/analyst.py`（读 static 快照处：`robots_ai` 为 None → eval_report 增布字段，如顶层 `static_robots_unknown: true`；命名由实现定，报告侧一致即可）
- Modify: `geo-agent/src/geo/report/templates/report.html.j2`（robots 呈现位：flag 置位时显示「未知(degraded)」而非 0.0 分格；未置位渲染不变）
- Test: `geo-agent/tests/test_analyst.py`（robots None → flag True；全 Allow dict → flag 缺省/falsy）、`geo-agent/tests/test_reporter.py`（flag 置位渲染含「未知(degraded)」；无 flag 渲染不变）

**Interfaces / 验收:**
- 数据流：快照 `robots_ai: null`（D3 fail-closed 已落）→ analyst 暴露布尔 → 模板标签。**评分数值零变化**（registry None→0 分路径不动；黄金锁 2 passed 证明）。
- w1-w3 冻结 eval_report 无该字段 → 旧渲染路径不受影响（字段缺省=falsy）。
- 禁改 registry.py 评分公式与信号集。

## Task 3: §11 budget_exhausted 落盘 + 渲染预算原因

**Files:**
- Modify: `geo-agent/src/geo/research/run.py`（`research_aggregates.json` 写入时带上 `budget_exhausted` 平台清单——run_research 已算好 `exhausted`，落盘缺这一半）
- Modify: `geo-agent/src/geo/research/render.py`（platform-profiles.md 渲染：平台结论带 `budget_exhausted` 原因（global/platform）时，"外部未验证"追加「（预算耗尽:原因）」后缀，与真查无从原因上区分）
- Test: `geo-agent/tests/test_research_kimi.py` 或对应 run/render 测试（aggregates 含清单键；渲染含原因后缀；无预算事件时零变化）

**Interfaces / 验收:**
- `_agg_jsonable` 或其调用处扩展一个键；既有五字段不变。
- 渲染改动仅在 budget_exhausted 键存在时生效；正常平台行零变化。
- 不动 research 单次超时值与预算常量（600/3600）。

## Task 4: spec 回补修订记录（纯 docs）

**Files:**
- Modify: `docs/superpowers/specs/2026-09-02-backlog-cleanup-design.md`（末尾追加「## 15. 验收审核修订记录（2026-09-02 晚）」）

**内容要点**（实施时以 Task A-C 实际落地的命名/文件为准）:
- 独立验收审核结论：19 项核心语义全部落地，完成门硬证据复核（540/0/2、黄金锁 2 passed、冻结产物 shasum 零漂移、CI 双绿）。
- 本批补齐：A1-A6 六项回归锁清单；B7 报告「未知(degraded)」呈现（含字段名/模板位置）；B9 budget_exhausted 落盘+渲染原因。
- 维持偏差：B8 changelog 不追加非版本条目（账本纯净性优先，断点标注在报告模板+测试锁）；§8 source_dir 实签名 `(week, sha1)`（plan:657 既定裁量）与迁移一次性执行（幂等脚本补 `scripts/migrate_sources_to_week.py`）；§6 放行旗标名 `--allow-published-overwrite`（spec 字面 `--override --reason` 用于归档门，两通道语义等价）。
- §14 纪律补账：偏差先前只记于 plan 自审，本节即为 spec 侧修订记录。

---

## 执行策略

- 分支 `audit-gap-fixes` 自 main=3b5e0ab；顺序 Task 1 → 2 → 3 → 4；每任务 TDD + 边界协议；全部完成后终局全量评审（最强模型）→ `merge --no-ff` 回 main → push → CI 双绿确认（`gh run list`）。
