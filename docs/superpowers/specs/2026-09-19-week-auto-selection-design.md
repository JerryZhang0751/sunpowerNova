# 执行周次自动化（week auto-selection）设计

- 日期：2026-09-19
- 状态：已批准（用户 2026-09-19 口头批准设计呈现）
- 范围：仅周次选择自动化；不调整评分、规则迭代算法、内容生成逻辑或站点代码
- 输入：用户方案文档《SunPower Nova 执行周次自动化优化方案》（八节全文）+ 2026-09-19 代码核实

## §0 背景与目标

现状：每周迭代启动前需手工修改 `run.yaml` 的 `week` 字段（runbook 长期记录"手改只动一行、勿用 `--next-week` 因会剥光 yaml 注释"）。周次推进是流水线唯一剩余的手工前置步骤。

目标：完整流水线入口（`geo.orchestrate.graph`）无参数运行时自动选周：

```
本次周次 = 已完成的最大生产周次 + 1
```

没有历史执行记录的新项目从 w1 开始。周次表示执行批次，不与自然日历周绑定。

## §1 现状核实（2026-09-19 代码事实，均已逐条验证）

| 模块 | 事实 |
|---|---|
| `orchestrate/graph.py:178` | CLI 兜底 `a.week or settings.run.week`（显式 0 会被吞成未输入——本设计废除该写法）|
| `orchestrate/graph.py:153` | 完成判定已存在：`snap.values.get("week") == week and not snap.next`（w202 事故修复沉淀）|
| `orchestrate/graph.py:163` | 续跑已存在：部分态 `invoke(None)` 只跑 pending 节点 |
| `orchestrate/graph.py:121-129/165/174` | `_bump_run_yaml_week` / `next_week` 参数 / `--next-week` CLI——全部删除 |
| `shared/config.py:19` | `RunSpec.week: int = 1`——删除字段 |
| `shared/config.py:43` | 缓存注释把 `graph --next-week` 列为运行时写入方——同步改为仅 keeper.iterate / do_rollback |
| `collect/collector.py:193` | 独立入口 `python -m geo.collect.collector` 读 `settings.run.week`——改显式 `--week N` |
| `report/reporter.py:73` | 独立入口读 `settings.run.week`——改显式 `--week N` |
| `research/run.py:149`、`generate/run.py:220` | 已有独立 `--week`（default=1）——保留现状，不接入自动递增 |
| `rules/run.py:83-84` | iterate/recalc 已 required `--week`——不动 |
| `rules/keeper.py:170-174`、`rules/run.py:63-67` | 运行期写 run.yaml 只动 `rule_version` 键——**保留**（与周次无关）|
| `shared/weeks.py` | `validate_production_week` + 测试保留带 [900,999]——接线复用 |

**生产库实测（副本只读查询）**：`state/runs.sqlite` 恰好 7 个根命名空间线程 `w1`–`w7`（`checkpoint_ns=''`），逐一 `app.get_state()` 全部 `values.week=N, next=(), tasks=0` = 完成态。自动选周在副本上应得 **8**。当前无强制重跑线程、无测试线程残留。

**langgraph 1.2.11 API 事实**：`SqliteSaver` 无 `list_threads` 方法；表结构 `checkpoints(thread_id TEXT, checkpoint_ns TEXT, checkpoint_id, parent_checkpoint_id, type, checkpoint BLOB, metadata BLOB)`。线程枚举只能 `SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns=''`——**纯 TEXT 列查询，不触碰 checkpoint/metadata BLOB**（符合方案§3.3"不要自行解码 checkpoint 二进制内容"）；每线程状态读取一律走现有 `app.get_state()`。

## §2 设计总览

新增模块 `src/geo/orchestrate/auto_week.py`（graph.py 保持瘦），`run_pipeline` 重排，入口加轻量进程锁。

```
auto_week.py（新）:
  list_root_threads(conn) -> list[str]
      # SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns=''
      # sqlite3.DatabaseError → 包装为明确报错（库损坏不降级 w1）
  parse_production_thread(thread_id) -> (week:int, is_force:bool) | None
      # ^w(\d+)$ → 普通；^w(\d+)-\d{8}-\d{6}$ → 强制（graph.py:136-138 生成格式）
      # 其余（test_wN 等）→ None 排除；N 落入 [900,999] 测试保留带 → 排除
  is_complete(snap, week) -> bool
      # 完成判定共享助手：values.week==week 且 next==() 且无带 error/interrupt 的 task
      # graph.run_pipeline 的完成检查改调同一函数（方案§3"抽取并复用"）
  classify_threads(app) -> Classification
      # completed: dict[week -> list[thread_id]]（普通+强制都计）
      # incomplete_normal: dict[week -> thread_id]
      # incomplete_force: dict[week -> list[thread_id]]
      # 生产线程 snap.values.week ≠ 线程名 N、或 get_state 抛错 → 明确报错列线程名
  weekly_artifacts_exist(repo) -> bool
      # data/analysis/w*/、data/raw/w*/、reports/w*/ 任一存在
  select_week(app, repo) -> WeekSelection
      # 见 §4 算法；返回 week / max_completed / mode(new|resume) / 提示明细
```

```
run_pipeline 新序（graph.py）:
  1. week 显式给定 → validate_production_week（先于锁，不碰 state 目录）
  2. force_new_run 且 week is None → ValueError（CLI 侧 parser.error 同步）
  3. 取进程锁 pipeline_lock（§6）
  4. conn = _new_run_conn()；app = build_graph(conn)
  5. week is None → week = select_week(app, REPO).week（一次定死，日志输出选周明细）
  6. 原有逻辑不动：thread_id 命名（w{week} / w{week}-{ts}）、完成跳过、
     partial 判定与 invoke(None) 续跑、finally conn.close()
  7. finally 释放锁
```

周次在启动时确定一次，通过现有 state（`S.week`）传递给全部节点，执行途中不重新计算。

## §3 完成状态判定（复用现有语义）

1. 枚举根命名空间（`checkpoint_ns=''`）的生产线程（§2 正则）。
2. 每线程只查最新状态：`app.get_state({"configurable": {"thread_id": tid}})`。
3. 完成 = `values.week == N` **且** `next == ()` **且** 无带 error/interrupt 的 task。（生产库实测完成态 tasks=0；崩溃态 `next=(失败节点,)` 已足够判未完成，task 检查为方案§3.5 要求的补位。）
4. 枚举出的生产线程若 `values.week ≠ N`（含空 values）或状态读取抛错 → **明确报错并列线程名**，不跳过不降级。
5. N 必须通过生产周次约束（正整数、不在 [900,999]）才参与统计；`test_wN` 前缀线程不参与。
6. 对所有已完成生产周次**按整数取最大值**，不按字符串排序。
7. 强制重跑线程（`wN-YYYYMMDD-HHMMSS`）完成后同样计入完成周次。

**明确不得替代完成判定的信号**：`data/raw/wN` 目录存在、采集清单（runs.jsonl）存在、`eval_report.json` 已生成、`report.html` 单独存在——这些产物可能在部分执行、失败或手工操作中产生。

"完成"沿用现有流程语义：允许 generate 因已有草稿正常跳过；不要求人工审核或站点发布。

## §4 选周算法与运行行为

```
selected = None
if completed 非空:
    selected = max(completed) + 1          # 整数最大值
    validate_production_week(selected)     # 落测试带 → 报错，不擅自跳号
else:
    if weekly_artifacts_exist(repo):
        raise 停止：提示恢复执行数据库或显式 --week（不得凭文件夹猜完成）
    selected = 1                            # 真正空白项目
# 守卫（仅自动路径）：
if selected ∈ incomplete_force 且 selected ∉ incomplete_normal:
    raise 停止：明确报出未完成强制线程信息，避免悄悄另开普通线程重复执行
mode = resume if selected ∈ incomplete_normal else new
```

| 场景 | 行为 |
|---|---|
| w7 完成，无 w8 记录 | 自动开始 w8（new）|
| w7 完成，w8 中途失败 | 仍选 w8，从原 checkpoint 续跑（resume，`invoke(None)`）|
| w8 完成，再次运行 | 自动开始 w9 |
| 显式 `--week 7`，w7 已完成 | 保留原有跳过行为 |
| 显式 `--week 8`，w8 未完成 | 保留原有续跑行为 |
| 显式 `--week 7 --force-new-run` | 保留现有强制重跑语义（时间戳线程）|
| 真正空白项目（无历史状态、无按周产物）| 从 w1 开始 |

约束：

- `run_pipeline` 的 `week` 参数改为可选（`week: int | None = None`）；仅 `week is None` 时自动选择。**不得**用 `a.week or ...`（显式 0 必须走到校验报错）。
- 自动路径选中的周若有未完成**普通**线程与未完成强制线程并存：resume 普通线程（强制线程仅在启动日志提示）。
- 显式 `--week` 路径不受强制线程守卫影响（保留原语义：无普通线程则新开普通线程全量执行）。
- 较低周次存在未完成记录时，仍取"最大完成周 + 1"，不擅自补齐历史缺口。
- 启动日志至少说明：最大完成周、本次执行周、新建还是续跑。例：
  `[week-select] 最大完成生产周: 7 → 本次执行 w8（新建线程）` /
  `[week-select] 最大完成生产周: 7 → 本次执行 w8（续跑线程 w8, pending: ['collect']）`

自动选周只属于完整流水线入口。独立采集、报告重渲染、研究或规则重算不开启也不完成一轮流水线，不参与完成统计。

## §5 移除配置写回机制

删除清单：

- `RunSpec.week` 字段（`shared/config.py:19`）
- `run.yaml` 第 1 行 `week: 7`；`run.yaml.example` 第 1 行 `week: 1`（其余行含注释原样保留；example 顶部加一行注释说明周次由流水线自动选择）
- `_bump_run_yaml_week()`（`graph.py:121-129`）
- `run_pipeline` 的 `next_week` 参数（`graph.py:131/165`）
- CLI `--next-week` 参数及帮助文本（`graph.py:174`）
- `tests/test_io_utils.py` 的 `test_graph_next_week_writes_run_yaml_atomically`（功能已删；通用原子写测试保留）
- `tests/test_rules_keeper.py:17`、`tests/test_rules_run.py:26` fixture dict 中的 `"week": 1` 键

不保留第二套周次来源或兼容计数器。

**保留**（验收口径="不再因周次推进读写 week"，非禁止流水线改 run.yaml 其他字段）：

- `rules/keeper.py` iterate 与 `rules/run.py` do_rollback 对 `run.yaml.rule_version` 的运行期更新（另一项既有功能，写回只动 rule_version 键）
- `config.py:43` 缓存注释改述为"运行时写入方：keeper.iterate / do_rollback"

配置缓存测试改用保留字段验证缓存失效（`test_config_models.py` 三个缓存测试：`week: 3→4` 改 `runs: 1→2`；`test_config.py` 的 env/yaml 加载断言同步去 week）。

独立入口显式化：

- `collector.py __main__`：argparse，`--week` **required**（经 `validate_production_week`），providers/runs/rule_version 仍取 settings
- `reporter.py __main__`：同上

## §6 状态异常与并发

错误语义（一律明确报错，**不得降级为 w1**）：

| 异常 | 行为 |
|---|---|
| 数据库损坏 / 读取失败（sqlite3.DatabaseError）| 明确报错 |
| 生产线程状态 week 与线程名不一致 / 状态无法解析 | 明确报错并列线程名 |
| 数据库缺失或无有效生产记录，**但**按周产物存在 | 停止自动选周，提示恢复执行数据库或显式 `--week` |
| 自动计算结果落入 [900,999] | `validate_production_week` 报错，不跳号 |
| 选中的周只有未完成强制重跑线程 | 报出线程信息并停止 |

无历史迁移需求：w1–w7 已有可识别完成 checkpoint。

**进程锁**：

- 锁对象：`REPO/state/pipeline.lock`（文件锁，`fcntl.flock(fd, LOCK_EX | LOCK_NB)`）
- 获取时机：**选周前**（run_pipeline 第 3 步）；释放：执行结束或异常退出的 `finally`（close fd 即释放；锁文件残留无害，不删除）
- 重复启动：第二个进程立即报错提示已有流水线运行（含锁文件路径），不排队等待
- 仅完整流水线入口（run_pipeline）加锁；独立 collector/reporter/research/rules 入口不加
- 同进程顺序调用无影响（flock 随 fd 释放）；无需任务队列或分布式锁

## §7 测试与验收

全部用临时数据库 + mock 节点构造状态，不触碰生产执行状态、不调用真实模型或 GSC。

**新增 `tests/test_auto_week.py`**（选周单元）：

1. 空白项目（无 checkpoint、无产物）自动选 w1
2. 已完成 w7 → 选 w8
4. w8 完成后 → 选 w9
5. w9、w10 完成 → 按**数值**选 w11（防字符串排序 "w10"<"w9"）
6. `test_wN` 线程、N∈[900,999] 线程不影响结果
7. 完成的强制线程计入完成周次；未完成线程（普通/强制）不被误计
10. 库缺失但 `data/analysis|data/raw|reports` 产物存在 → 报错不回退 w1；库损坏（写垃圾字节）→ 明确报错
- 生产线程 values.week 与线程名不一致 → 明确报错
- 选中周只有未完成强制线程 → 报出线程并停止

**`tests/test_graph.py` 增补**（run_pipeline 集成）：

3. w8 在 fetch 崩溃后，`run_pipeline(week=None)` 仍选 w8 续跑，collect 不重复执行
- `run_pipeline(week=None)` 空白 → w1；启动日志含最大完成周/执行周/新建或续跑
8. 显式选周完成跳过、`--force-new-run` 时间戳线程（既有测试保持）
9. 显式 0、负数、测试保留周次被拒（`validate_production_week` 先于锁）
12. 自动选周与完成处理不修改 run.yaml（内容/mtime 断言）；keeper rule_version 升版功能回归不动（既有测试）
13. 锁：测试侧先持有 flock → `run_pipeline` 立即报错；释放后可运行
- `test_run_pipeline_closes_own_conn` 补 `monkeypatch.setattr(G, "REPO", tmp_path)`（加锁后避免在真实 state/ 建 lock 文件）

**`tests/test_collector.py` / `tests/test_reporter.py` 增补**（item 11）：独立入口无 `--week` → 报错退出；有 `--week N` → 正确传递（mock run_collection/render，sys.argv 注入）。

**既有测试更新**：`test_config.py`、`test_config_models.py`（缓存字段改 runs）、`test_io_utils.py`（删 next_week 写回测试）、`test_rules_keeper.py` / `test_rules_run.py`（fixture 去 week 键）；`test_run_yaml_example.py`（键集断言自动适配，无需改）。

**收口验收**：

1. GEO Agent 离线全量回归（`PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/ --timeout=120`）EXIT=0
2. 生产数据库临时副本上只验证 `select_week` 结果 = 8，**不启动真实 w8**

## §8 文档更新（仓库根 README.md）

- 运行示例改为无参数默认形态：`python -m geo.orchestrate.graph`
- 参数表：`--week N` 行改为"显式选择生产周（省略时自动 = 最大完成生产周 + 1）"；删除 `--next-week` 行；`--force-new-run` 行补"须同时显式传 `--week`"
- 补充：自动选周规则一句话说明、显式续跑示例（`--week 8`）、强制重跑示例（`--week 7 --force-new-run`）、并发锁行为、库缺失/产物并存时的报错语义
- §关键配置表 run.yaml 行描述去掉"周号"
- 删除手工维护 week 与 `--next-week` 的全部说明

## §9 范围外（明确不做）

- 评分、规则迭代算法、内容生成逻辑、站点代码：零改动
- research/generate CLI 的 default=1：保留现状（不接入自动递增）
- 不引入任务队列、分布式锁、定时器
- 不迁移/回填历史完成记录（w1–w7 checkpoint 已可识别）
- 工作树既有未提交余量（演讲文稿/ppt-*/探针/HTML 概览）零触碰
