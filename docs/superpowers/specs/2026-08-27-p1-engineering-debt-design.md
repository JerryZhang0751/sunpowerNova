# P1 工程债修复设计（5 项）

- 日期：2026-08-27
- 状态：已批准（brainstorming 通审，5 项分叉均经用户决策）
- 来源：`engineering-audit-2026-08-24` P1 清单（file:line 已于 2026-08-27 对当前 main=d82258a 重新核实）
- 分支：`p1-eng-debt`（自 main 切出，TDD 红→绿，merge --no-ff 合入）

## 0. 用户决策记录

| # | 分叉 | 决策 |
|---|---|---|
| 1 | cost_budget_yuan 死配置 | **删除**（所有调用路径结构上已 bounded：重试≤2、超时预算、nudge 轮数上限；拒绝假精度价格表） |
| 2 | Kimi 失败时 playbook 处理 | **保旧+草稿**（正式文件不动，新渲染落 `.draft` 带降级横幅，成功后自动晋升） |
| 3 | 快照冻结守卫是否纳入 | **纳入**（周编号项的完整防线） |
| 4 | fetcher 失败语义 | **失败全不缓存**（传输异常与非 2xx 都不落盘） |
| 5 | 依赖锁方案 | **纯 pip requirements.lock**（从当前绿环境冻结，CI 改装 lock） |

## 1. 范围

修 2026-08-24 工程审查 P1 全部五项；P2/P3 余项不动（见审计 memory）。五项相互独立，按审计序 ①→⑤ 实施。

---

## 2. ① playbook/platform-profiles 覆写保护

### 现状（2026-08-27 核实）

- `src/geo/research/run.py:66-68`：`run_research` 结尾无条件 `write_text` 覆写 `knowledge/playbook.md` 与 `knowledge/platform-profiles.md`。
- `src/geo/research/kimi.py:28-33`：`synthesize` 捕获一切异常后 `return []`；`run.py:54-60` 外层再 try/except 一次——两层防护都拦不住空结论照样渲染覆写。
- 事故史：w123 空渲染覆写真 playbook（08-19，subagent 带外直调 `run_research` 触发）；w202 同型（直接调 `run_research(202)` 绕过 DAG）。

### 设计

- **原子写**：`research/run.py` 新增 `_atomic_write(path, text)`（写 `<path>.tmp` + `os.replace`）。playbook、platform-profiles、research_aggregates 三处写入全走它。
- **晋升门（degraded 判定）**：
  - playbook：`kimi_enabled and not conclusions` → degraded。
  - platform-profiles：`kimi_enabled and verified 非空但所有 value 的 answer 均为空` 或 `verified == {}` → degraded。（单平台查证抖动是常态——08-18 实测 1 家/轮；**全空**才是失败。）
  - 两文件独立判定、独立晋升（可能一好一坏）。
- **degraded 路径**：渲染结果写 `knowledge/playbook.md.draft` / `knowledge/platform-profiles.md.draft`，顶部降级横幅（render 层新增 header 参数）：
  `> ⚠️ 本轮 Kimi 综合不可用（时间戳），结论为空——确定性聚合仍有效。此为草稿，未晋升；正式 playbook 保持上一成功轮。`
  **正式文件不动**。`run_research` 返回 dict 增加 `degraded: bool` 与 `draft_paths: list[str]`。
- **晋升路径**：非 degraded → 写正式文件；写前若正式文件已存在，先备份到 `knowledge/.history/{stem}-w{week}-{YYYYMMDD-HHMMSS}.md`（`knowledge/.history/` 加入 .gitignore——git 已是主备份，本地 history 仅防"工作树未提交期间被覆写"）。若同名 `.draft` 残留则一并清理。
- **显式确定性模式**：`--no-kimi`（`kimi_enabled=False`）是有意为之 → 直接写正式文件（不设门），header 加注记行 `> 确定性模式（--no-kimi）：本 playbook 未含 Kimi 综合结论。`
- `kimi.py` 不改语义（返 `[]` 合法），失败 log.warning 升格为含异常类型与重试建议。

### 测试（红→绿）

1. `synth_fn` 抛异常 → playbook.md 原内容不变；`.draft` 存在且含横幅；返回 `degraded=True`。
2. 成功轮 → 正式文件更新、`.history` 出现备份、无 `.draft` 残留。
3. `--no-kimi` → 正式文件直接写且含确定性注记、无 `.draft`。
4. 原子性：mock `os.replace` 前抛异常 → 正式文件完好、无半成品。
5. profiles 独立门：synthesize 成功但 web_search 全失败 → playbook 晋升、profiles 走 draft。

---

## 3. ② fetcher 失败不落缓存

### 现状（2026-08-27 核实）

- `src/geo/fetch/fetcher.py:79-88`：`except UnsafeURLError: raise`（08-24 后已不落盘）；**其余一切异常 → `js_only=True` 照常落盘** text.md + meta.json → 网络瞬断/超时 = URL 永久 js_only，跨周复用，URL 永久退出研究语料（corpus 排除）。
- 非 2xx 响应（403/429/503）同样被缓存成 js_only。
- `research/sample.py:fetch_topn`：`FetchStats.js_only` 恒 0（注释自认 reserved）。

### 设计

- 新增 `class FetchError(RuntimeError)`（定义在 `fetch/fetcher.py`）。
- `fetch_source` 语义：
  - `UnsafeURLError` → 原样上抛（不变）。
  - 其他传输异常（timeout / connect / TLS / 解码）→ `raise FetchError(...) from e`，**不落盘**。
  - 响应终态非 2xx → `raise FetchError(f"HTTP {status}")`，**不落盘**（重定向循环内的 3xx 已由 `_safe_get` 处理，到此处即终态）。
  - **2xx 且 trafilatura 抽不出正文** → `js_only=True` 照常缓存（真 JS-only，`http_status=2xx` 在档）。
  - 2xx 且抽出正文 → 正常缓存。
- 调用方不改：`graph.py fetch_node` 的 `except Exception: pass` 与 `sample.py fetch_topn` 的 `failed+=1` 天然兼容 FetchError。
- **存量毒化自愈**：缓存命中分支增加判定——`rec.js_only and rec.http_status is None` → 视为 miss 重抓（异常路径 `status=None`，与 2xx-空正文缓存 `http_status=200` 可区分）。无需清理脚本，存量毒化条目自动失效。
- `fetch_topn` 顺手接通 `js_only` 计数（`fetch_source` 返回值读 `js_only`）。
- `meta_llm.extract_semantic` 失败返 `{}` 属 P2 静默降级项，**不在本次范围**。

### 测试（红→绿）

1. `_safe_get` 抛 `httpx.ConnectError` → `FetchError` 上抛、`source_dir` 无 text.md/meta.json。
2. 返回 403 / 500 → `FetchError`、不落盘。
3. 2xx 空正文 → 缓存 `js_only=True, http_status=200`。
4. 缓存命中毒化条目（`js_only=True, http_status=None` 的旧 meta.json）→ 重抓而非复用。
5. `fetch_topn` 的 `FetchStats.js_only` 计数正确（1 js_only + 1 failed + 1 fetched）。

---

## 4. ③ 依赖锁 + 黄金锁路径统一

### 现状（2026-08-27 核实）

- `pyproject.toml` 全 `>=`（openai 已漂到 2.52 vs spec >=1.40）；无任何锁文件。
- CI（`.github/workflows/ci.yml`）装 `pip install -e geo-agent[dev]`——每次解析最新满足版本。
- `tests/test_v1_semantics.py:21-24`：skipif 查 `data/raw/w1`，但断言读 `data/analysis/w1/eval_report.json`——干净 clone 上 `analysis/w1` 缺失而 `raw/w1` 存在（或反之）时行为是 error 而非 skip；路径口径不一致=假信心。

### 设计

- `scripts/gen_lockfile.py`：遍历当前绿环境（`/tmp/pylibs312`，376 tests 验证）的 `importlib.metadata.distributions()`，写 `geo-agent/requirements.lock`（全量 `pkg==ver`，含 dev 依赖），头部注释记录冻结来源与日期。提交入库。日后依赖变更时重跑重冻。
- CI 改为 `pip install -r geo-agent/requirements.lock`（pytest 由 `pythonpath=["src"]` 提供包路径，无需 editable 安装）。
- `pyproject.toml` 的 `>=` 保留为抽象声明（双层标准做法）；lock 是唯一具体安装源。
- **一致性测试**（新 `tests/test_lockfile.py`）：lock 存在、可解析、且覆盖 pyproject `[project]` 与 `[dev]` 的全部直接依赖名——新增依赖忘重冻时 CI 红。
- **黄金锁 skipif 修正**：条件改为测试实际需要的全部路径——`data/raw/w1` 与 `data/analysis/w1/eval_report.json` 同时存在才跑，否则 skip（CI 无 gitignored 数据、必然 skip 是设计使然，但本地路径缺失不再伪装成 skip-pass）。

### 测试（红→绿）

1. lock 覆盖 pyproject 全部直接依赖（含 dev）。
2. lock 行格式合法（`name==version`，允许注释与空行）。
3. 黄金锁测试：构造 `analysis/w1` 缺失场景验证 skipif 生效（非 error）。

---

## 5. ④ 周编号防线（测试带 + 入口校验 + 残留清理 + 快照冻结守卫）

### 现状（2026-08-27 核实）

- 周编号全库裸 int；`run_collection` 无 repo 参数（全局 REPO）；collector / research 各有 `__main__` 裸调入口；`graph.run_pipeline` 无 week 校验。
- 测试与生产同命名空间：`data/analysis/` 已混 `w42/w77/w88/w99/w101/w123/w202`，`data/raw/w99`、`data/snapshots/{w5,w99}` 同为残留。
- `tests/test_gsc.py` 传了 `tmp_path, monkeypatch` 但**函数体完全没用**——`snapshot_gsc(week=99)` 直写生产 `data/snapshots/w99`。
- 误用最不可恢复的伤害：对历史周重跑 `snapshot_gsc` → GSC 28 天窗口已移动 → 基线快照被今日数据覆盖 → 43.4/49.8 的重算基础被毁（08-13 的合法重跑当时快照 degraded；干净快照不该被重冻结）。

### 设计

- **新 `src/geo/shared/weeks.py`**：
  - `TEST_WEEK_MIN = 900`、`TEST_WEEK_MAX = 999`（测试保留带）；`TEST_WEEK = 901` 便捷常量。
  - `validate_production_week(week: int) -> int`：`week < 1` 或 `TEST_WEEK_MIN <= week <= TEST_WEEK_MAX` → `raise ValueError`（报错文案给出指引：生产周 1–899；测试请用 `TEST_WEEK`）。
- **入口接线**（仅 CLI/编排入口，库函数不加——测试带 tmp repo 直调合法；已核实五个入口的 `__main__` 均存在）：
  - `orchestrate/graph.py run_pipeline`（覆盖 `__main__` 路径）；
  - `collect/collector.py __main__`；
  - `research/run.py __main__`；
  - `rules/run.py __main__`；
  - `generate/run.py __main__`。
- **测试迁移**：全部测试周编号（99/123/202/101/42…）改用 `TEST_WEEK`/9xx；`test_gsc` 未使用的 `tmp_path/monkeypatch` 形参清理。
- **残留清理**（一次性，删前逐个核实确系测试产物）：`data/analysis/{w42,w77,w88,w99,w101,w123,w202}`、`data/raw/w99`、`data/snapshots/{w5,w99}`。生产 sqlite 的 test 线程属 P2，不动。
- **快照冻结守卫**（已核实 `gsc.json` 顶层有 `degraded` 字段、`static_signals.json` 无）：
  - `snapshot_gsc`：`data/snapshots/w{week}/gsc.json` 已存在且 `degraded != True` → log + 返回现有内容（跳过重冻结）；missing 或上次 `degraded=True` → 允许重写（08-13 的 SSLEOFError 重跑即 degraded 场景，语义吻合）。
  - `snapshot_static_signals`：`static_signals.json` 存在即跳过（无 degraded 概念，纯存在性守卫）。
  - 两处快照写入改原子写（tmp + `os.replace`）。崩溃续跑天然幂等（同周重入=skip）。

### 测试（红→绿）

1. `validate_production_week`：900–999 拒、0/-1 拒、1/53/899 放行。
2. `run_pipeline(901)` 在入口被 ValueError 拒（monkeypatch 免建真图）。
3. 快照守卫：干净快照存在 → 二次调用跳过、文件内容与 mtime 语义不变（返回现有 dict）；degraded 快照 → 允许重写。
4. 快照原子性：写入中断不留半文件。

---

## 6. ⑤ cost_budget_yuan 删除

### 现状（2026-08-27 核实）

- `shared/config.py:15` `cost_budget_yuan: float = 100.0`——解析后全库零引用（grep 全仓仅此一处）。run.yaml 有对应行与注释。曾为 codex 质检 #7 同题。

### 设计

- `RunSpec` 删字段；run.yaml 删该行（pydantic v2 BaseModel 默认 `extra='ignore'`，存量 run.yaml 兼容）。
- 不做替代熔断：调用路径已结构化 bounded——collector 重试 `stop_after_attempt(2)`、Qwen 300s 块间+600s 总预算、Kimi nudge `max_rounds=10`、fetch 每 URL 30s 且清单 bounded（~24+40）、采集 manifest 95% 门。

### 测试

既有 RunSpec/配置相关测试更新断言（无 cost_budget 字段）；新增一条锁定 `run.yaml` 与 `RunSpec` 字段集一致（防未来再积死配置——run.yaml 出现 RunSpec 未声明键即 fail，迫使其显式决策）。

---

## 7. 执行策略

- 分支 `p1-eng-debt` 自 main=d82258a；顺序 ①→⑤（审计序，相互独立）；每项 TDD 红→绿。
- 测试环境：`PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ --timeout=120 -p no:cacheprovider`（.venv 沙箱封锁的既定替代；/tmp/pylibs312 若失守则先 `pip install --target` 重建）。
- 完成门：全量绿（当前基线 376 passed + 2 skipped，预期净增约 15–20 条）+ 黄金锁 43.4/49.8 零漂移 + `merge --no-ff` + push + CI 双绿（必要时 `gh workflow run CI --ref main`）。
- 不动：P2/P3 余项、rules 语义、任何评分口径。

## 8. 风险与边界

- ② 改变失败语义后，被封 URL 每轮重试 ~30s（bounded，可接受）；存量毒化自愈判定 `http_status is None` 理论上可能误伤"真 2xx 但 status 恰未记录"的老条目——重抓一次无害（幂等缓存重写）。
- ④ 快照守卫若未来需要"强制重冻结"（如口径升级），走 `force` 参数显式开口（本次不实现，报错文案提示手工删除快照文件即可）。
- ③ lock 冻结自 /tmp/pylibs312，与用户 .venv 的版本可能略有出入——以 376 绿环境为准；.venv 用户侧自行 `pip install -r` 对齐（非阻塞）。
