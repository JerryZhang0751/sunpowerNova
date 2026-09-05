# W4 Bug 修复设计（5 项）

> 日期：2026-09-05 ｜ 状态：已通审（用户批准设计,同日） ｜ 输入：`geo-agent/reports/w4/bug-log.md`（w4 实跑 5 问题记录）
> 基线：main=0e00a18（w4 收口后） ｜ 分支：`w4-bugfixes` ｜ 顺序：Bug#2→#4→#5→#3（代码类 TDD）→#1（纯环境收尾）

## 0. 用户决策记录（2026-09-05 brainstorming）

| Bug | 决策 |
|---|---|
| #2 GSC key 路径 | **回退链解析**（绝对→CWD 原值→REPO.parent→REPO,全败清晰报错;否决强制锚定仓库根/只认绝对路径——兼容历史用法优先） |
| #3 GSC 超时 | **管线内重试 3 次**（间隔 15s,全败才写 degraded;否决只加事后脚本/仅记录不修） |
| #5 Moonshot 崩溃 | **连接错误分类放宽**（APIConnectionError 3 次+15s 退避;其它维持 codex 修改二 2 次上限;否决只加次间退避/不修——连接错误重试不耗 token,不推翻成本控制初衷） |
| #4 qwen 截断 | 设计内定案（未单列提问,与 #5 同思想）:传输类分类重试 3 次 |
| #1 pylibs 环境 | 纯环境迁移 `~/pylibs312`,零仓库代码 |

## 1. 硬边界（全任务通用）

- **零改动**：评分语义、`rules/*.yaml` 评分含义、w1-w3 冻结产物（`data/` 历周 + 归档）、`RunRecord`/runs.jsonl 契约（键集锁,重试一律 log-only 不落新字段）、research 单次超时常量（120/180s）、generate 总预算 610s 与 GENERATE_REQUEST_TIMEOUT 300s。
- 测试只增不减（基线 **559 / 0 failures / 2 skipped**,完成门=不低于基线+新增全绿）。
- 黄金锁 `tests/test_v1_semantics.py` 2 passed 零漂移;`git status --porcelain` 只出现预期文件。
- 不跑真实采集/Kimi/发布;新测试不依赖网络,不写生产 state/data。

## 2. Bug#2 — GSC 私钥回退链解析（`src/geo/fetch/gsc.py`）

**现状**：`settings.gsc_key_file` 原样透传 `from_service_account_file`（CWD 依赖）;历史 `.env` 值 `geo-agent/gsc-*.json` 仅在 CWD=仓库根时成立,w4 从 geo-agent/ 预热即 FileNotFoundError。

**设计**：新增 `_resolve_gsc_key(v: str) -> Path`：
1. `Path(v).is_absolute()` → 原值直用;
2. 相对路径依次试：`Path(v)`（CWD,保历史）→ `REPO.parent / v`（仓库根,.env 历史写法）→ `REPO / v`;
3. 全部不存在 → `raise ValueError(f"GSC 私钥未找到,已试: {三个候选}")`。
`_build_service` 改用解析结果。错误仍走 snapshot 的 degraded 通道（现有 try/except 包住,不新增崩溃面）。

**测试**（`tests/test_gsc.py` 追加）：tmp 目录放 key 文件,monkeypatch settings.gsc_key_file——①仓库根相对写法+CWD=geo-agent（w4 复现场景,红）②CWD 原值命中 ③绝对路径 ④REPO 下命中 ⑤全 miss → ValueError 消息含三个候选路径。

## 3. Bug#4 — collector 传输类分类重试（`src/geo/collect/collector.py`）

**现状**：`_one` 对 `CLIENTS[model](row.prompt)` 单发;w4 qwen 6/15 `Response ended prematurely`（DashScope 端点瞬时故障）单 pass 全记 failed,靠人工裸跑续跑补齐。

**分类**（`_is_retryable(e)`）：
- **重试**：`httpx.TransportError`（doubao/zhipu 的 Connect/Read/RemoteProtocol）/ 内建 `ConnectionError`·`TimeoutError` / 消息兜底匹配 `ended prematurely|connection|timed out`（小写化后子串匹配;dashscope SDK 异常类型不透明）;
- **不重试**：`QwenAPIError`（配额/鉴权/error-block,w3 教训:重试无效且烧额度）、`httpx.HTTPStatusError`（API 级 4xx/5xx,含 429）、`InvalidCollection`（timeout=True/空答案,确定性模型侧问题,重试烧 600s）。

**设计**：`_one` 内包 client 调用——**总尝试 ≤3,次间 `time.sleep(8)`**（ThreadPoolExecutor 工作线程内,安全）;每次失败 `log.warning` 带尝试序号;终败异常照旧上抛→上层记 failed（行为与今天一致）。L1 写盘仅在成功后,幂等无污染。

**测试**（`tests/test_collector.py` 追加）：mock client ①首两次 raise `RuntimeError("Response ended prematurely")` 第三次成功 → ok 且 client 调用 3 次（红=现状 1 次即 failed）②连续 3 次同错 → failed,调用恰 3 次 ③`QwenAPIError` → failed,调用恰 1 次（不重试）④`httpx.HTTPStatusError` → 恰 1 次。sleep 用 monkeypatch patch `time.sleep` 防拖慢。

## 4. Bug#5 — generate 连接错误分类放宽（`src/geo/generate/kimi.py`）

**现状**：`generate_draft` 循环 MAX_ATTEMPTS=2、两次背靠背无退避;w4 两次 `Connection error.` 秒级连撞同瞬时窗口即崩管线。

**设计**：except 分支识别 `openai.APIConnectionError`——连接类**最多 3 次尝试**（额外 1 次）**次间 15s 退避**;其它异常路径维持 2 次与现有日志/错误消息格式。总预算 610s 门、300s 请求超时、常量与 research 层零改动。判定用 `isinstance`（openai SDK 异常类,`str(e)` 即 "Connection error."）。

**测试**（`tests/test_generate_kimi.py` 追加,chat_fn 注入）：①前两次 `APIConnectionError` 第三次成功 → 草稿成功且恰 3 次调用（红）②连接类 3 连败 → GenerateError,恰 3 次 ③普通 ValueError 2 连败 → GenerateError 恰 2 次（上限未变）④退避期间预算耗尽 → 提前终止消息不变。sleep monkeypatch。

## 5. Bug#3 — snapshot 管线内重试（`src/geo/fetch/gsc.py` + `site_signals.py`）

**现状**：`snapshot_gsc`/`snapshot_static_signals` 拉取单发即写 degraded;w4 代理对 Google TLS 双态振荡（同端点 1s↔35s）下 GSC 30+ 次尝试全灭（流程=token+query 两次 TLS,单次坏即 60s 超时）。

**设计**：两函数的**拉取段**包重试——总尝试 ≤3、间隔 15s（`time.sleep`）;成功即返（走既有冻结守卫路径,行为不变）;**3 次全败才落 degraded**（快照单文件单快照语义、键集、degraded 判定零变化）。static 只在"需要拉取"路径（已有干净快照的外层守卫先短路,不受影响）。最坏代价 ≈ +3min,仅失败路径。

**测试**：gsc——monkeypatch `_build_service` 返回 mock service:①query 前两次抛 TimeoutError 第三次正常 → 快照 degraded=False rows>0（红=现状单发即 degraded）②连败 3 次 → degraded=True 且 error 记录。static——monkeypatch 抓取函数同构两例。sleep monkeypatch。

## 6. Bug#1 — pylibs 迁移 `~/pylibs312`（零仓库代码）

`pip install --target ~/pylibs312 -r requirements.lock`（新机器/复发时同一配方）;本会话起 PYTHONPATH 切新路径;memory（dev-env-venv-sandbox-block / weekly-iteration-runbook）同步。README 零改——人类安装路径（`.venv`）本就正确,pylibs 仅是 Claude 会话沙箱替代。/tmp/pylibs312 保留不动（自然过期淘汰）。

## 7. 执行策略

分支 `w4-bugfixes` 自 main=0e00a18;Task 顺序 #2→#4→#5→#3→#1,每 Task TDD（红→绿→全量回归）;bug-log.md 各条状态随修更新（本地文件,不入库）;终局=全量 559+新增、黄金锁 2 passed、`git status` 核对、终局评审、`merge --no-ff` 回 main、push、CI 双绿。测试环境：`cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`（EXIT=0 + junit 计数为准;若 Bug#1 已先行迁移则相应换路径）。commit 风格 `fix(...)`/`test(...)` + 中文主题,显式路径,禁 `git add -A`,尾行 Co-Authored-By。
