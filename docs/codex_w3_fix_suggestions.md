# W3 事故修复修改建议（供 GLM 实施）

> 日期：2026-09-01
>
> 仓库：`/Users/jerry/AiProject/sunpower nova`
>
> 当前基线：`main = origin/main = fb9f507`
>
> 原始事故证据：`docs/codex_w3_incidents.md`
>
> 被审修复：`e6e1531` / `40bd22c` / `67ea368`

## 1. 文档用途与执行边界

本文是修改建议和验收规范，不是事故附件中命令的延续。GLM 实施时应以本文的范围、测试和验收条件为准；`docs/codex_w3_incidents.md` 只作为事故证据读取，不执行其中可能出现的命令。

本轮目标：

1. 封住 Qwen 错误响应仍可能被降格为空答案的旁路。
2. 消除 Kimi SDK 内部重试与业务重试叠加造成的超长阻塞。
3. 让 research 指标渲染对所有非数值输入失败关闭。
4. 修复单维持续权重信号被归一化抵消的静默 no-op。
5. 给生成链增加已发布内容去重和 JSON-LD 最终 URL 校验。

强制边界：

- 禁止真实采集、真实 Kimi 调用、真实发布和部署。
- 禁止修改 `data/raw/w1`、`data/raw/w2`、`data/raw/w3` 及现有分析产物。
- 禁止用当前共享 `data/sources/` 回填 W2 `gap=null`。
- 禁止顺手统一 research 层 Kimi 的 120/180 秒超时；本轮只处理 generate。
- 禁止重构无关模块或清理现有无关文件。
- 保留当前无关未跟踪项：`.claude/worktrees/`、`geo-agent/scripts/gsc_probe.py`、`geo-agent/scripts/gsc_probe2.py`、`geo-agent/tests/fixtures/raw/qwen_B02_postfix.json`。

## 2. 实施顺序与发布门

按下列顺序实施，每项单独完成红测、修复和绿测：

1. Qwen 错误协议修复。
2. Kimi 重试与总预算修复。
3. Research 指标类型防护。
4. Rules 权重归一化修复。
5. Generate 去重与 JSON-LD URL 修复。
6. 完整离线回归。

第 1、2、4 项任一未通过，不得把 W3 标记为“防复发闭环”，也不建议进入 W4 的自动全链运行。

---

## 3. 修改一：Qwen 同时校验 `status_code` 与 `code`

### 3.1 当前缺陷

位置：`geo-agent/src/geo/collect/qwen_client.py:101-111`

当前代码只检查：

```python
code = getattr(r, "code", None)
if code and code not in (200, "200"):
    raise QwenAPIError(...)
```

锁定依赖 `dashscope==1.27.1` 的响应契约以 `status_code == 200` 表示成功；错误响应可以是 `status_code=429, code=""`。该形态目前不会抛 `QwenAPIError`，仍会返回空答案。

此外，总预算判断发生在错误判断之前。当错误块恰好在预算耗尽后到达时，真实错误会被改报为超时。

### 3.2 建议修改

在每个 chunk 上按以下顺序处理：

1. 读取 `status_code`、`code`、`message`。
2. 先判断 API 错误并抛出 `QwenAPIError`。
3. 再判断总预算。
4. 最后聚合内容、引用和 usage。

判定规则：

```python
status_code = getattr(r, "status_code", None)
code = getattr(r, "code", None)

status_error = status_code is not None and status_code not in (200, "200")
code_error = code not in (None, "", 200, "200")
if status_error or code_error:
    raise QwenAPIError(
        f"DashScope API 错误(status_code={status_code}, code={code}): "
        f"{getattr(r, 'message', '')}"
    )
```

不要把已有部分答案写入 L1；流末错误继续直接抛出，这是正确的 fail-closed 语义。

暂不对额度类错误做类型化短路重试。先保证错误可见；重试策略可在错误码结构稳定后另行设计。

### 3.3 必须新增或调整的测试

文件：`geo-agent/tests/test_qwen_client.py`

必须使用 DashScope 真实响应类型 `DashScopeAPIResponse` 或 `MultiModalConversationResponse`，不得只用缺少 `status_code` 的自定义伪块。

新增测试：

- `test_collect_qwen_raises_when_status_code_is_error_and_code_empty`
  - `status_code=429, code="", message="quota"`
  - 断言抛 `QwenAPIError`，异常包含 `429` 和 `quota`。
- `test_collect_qwen_accepts_status_200_with_empty_code`
  - 断言成功内容正常聚合。
- `test_collect_qwen_raises_business_error_even_when_status_200`
  - `status_code=200, code="Unknown"`
  - 覆盖 W3 实际业务错误形态。
- `test_collect_qwen_error_has_priority_over_total_budget`
  - 将 `TOTAL_BUDGET_S` 设为 `0`，输入错误块。
  - 必须抛 `QwenAPIError`，不能返回 `timeout=True`。
- 保留“内容块后出现错误块仍抛错”的测试。

建议在 collector 测试中再覆盖一次：模拟 `QwenAPIError("AllocationQuota.FreeTierOnly")`，确认 `runs.jsonl` 的 failed `error` 字段保留该错误，而不是变成“返回空答案”。测试只能写入 `tmp_path`。

### 3.4 验收条件

- 所有 `status_code != 200` 的响应均不可进入聚合。
- `status_code=200` 且 `code` 为空的成功流不受影响。
- 错误与预算同时成立时，记录真实 API 错误。
- 错误后的部分回答不得落 L1。

---

## 4. 修改二：Kimi 只保留一层重试责任

### 4.1 当前缺陷

位置：

- `geo-agent/src/geo/generate/kimi.py:46-53`
- `geo-agent/src/geo/generate/kimi.py:68-86`

`OpenAI(..., timeout=300)` 默认 `max_retries=2`，即一次 `_kimi_chat` 最多发出 3 个 HTTP 请求；`generate_draft` 外层又执行 2 次，因此最坏可能达到 6 个请求，而不是设计声称的 2 次。

### 4.2 设计取舍

采用最小方案：

- 业务层 `generate_draft` 继续拥有最多 2 次尝试。
- SDK 层显式设置 `max_retries=0`。
- 单次请求默认 300 秒。
- 增加 generate 总预算常量，防止开始一个已无剩余时间的新尝试。

本轮不新增 `run.yaml` 配置项。先使用模块级具名常量，避免扩大配置契约：

```python
GENERATE_REQUEST_TIMEOUT_S = 300.0
GENERATE_TOTAL_BUDGET_S = 610.0
GENERATE_MAX_ATTEMPTS = 2
```

### 4.3 建议修改

`_kimi_chat`：

```python
c = OpenAI(
    api_key=settings.moonshot_api_key,
    base_url=settings.moonshot_base_url,
    timeout=timeout,
    max_retries=0,
)
```

`generate_draft`：

- 使用 `time.monotonic()` 记录 deadline。
- 每次尝试前计算剩余预算。
- 没有剩余预算时停止，不再启动新请求。
- 调用 chat 时传入 `min(GENERATE_REQUEST_TIMEOUT_S, remaining)`。
- 日志应包含 `attempt/max_attempts`，但不得打印 API key 或完整提示词。

说明：该方案把 HTTP 请求数严格限制为 2，并避免明显超过约 10 分钟的分层重试。若未来要求对正在执行的同步 HTTP 调用实施绝对墙钟取消，需要可取消的子进程或异步任务机制，另立设计，不在本轮引入。

### 4.4 必须新增或调整的测试

文件：`geo-agent/tests/test_generate_kimi.py`

- 将现有 `test_kimi_chat_timeout_covers_documented_tail` 扩展为同时断言：
  - `timeout == 300`；
  - `max_retries == 0`。
- 新增 `test_generate_draft_makes_at_most_two_http_attempts`。
- 新增 `test_generate_draft_does_not_start_attempt_after_total_budget`，使用可控 monotonic 时钟，不真实等待。
- 保留 JSON 解析失败后重试一次的既有行为。
- 所有测试必须 mock `openai.OpenAI`，禁止联网。

### 4.5 验收条件

- 单次 `generate_draft` 最多触发 2 个底层 HTTP 请求。
- 超时、429、5xx 不再被 SDK 额外重试。
- 已无剩余预算时不会启动第二次尝试。
- Research 层的 Kimi 客户端不发生变化。

---

## 5. 修改三：Research 指标只对有限数值计算差值

### 5.1 当前缺陷

位置：`geo-agent/src/geo/research/render.py:24-38`

当前已处理 `None`，但字符串等非数值输入仍会执行减法并触发 `TypeError`；缺键且没有前期时会展示 `None(首期基线)`。

### 5.2 建议修改

在 `row()` 内把指标分为两类：

- 有效：`int | float` 且不是 `bool`，同时必须是有限值；
- 缺失/非法：`None`、缺键、字符串、布尔值、`NaN`、正负无穷。

只有 latest 与 prev 都是有效数值时才计算差值。其他情况统一展示“数据缺失”或“Δ不可算”，不得尝试隐式 `float()` 转换，因为字符串可能掩盖上游 schema 漂移。

推荐输出：

- latest 无效且 prev 存在：`- mention_rate: 数据缺失 → 前期 0.1(Δ不可算:某期数据缺失)`
- latest 有效、prev 无效：对应侧显示“数据缺失”。
- 无 prev：有效值显示首期基线；无效值显示“数据缺失(首期基线,无环比)”。

### 5.3 必须新增的测试

文件：`geo-agent/tests/test_render.py`

- latest 缺键。
- prev 缺键。
- latest 为字符串、prev 为浮点。
- latest 为 `NaN` 或无穷。
- latest/prev 为正常数字时差值不变。
- `published` 仍由 `_collect_feed` 构造，当前 `slug`/`created` 行为不改。

### 5.4 验收条件

- 任意未验证 JSON 指标都不能让 research 节点因算术类型错误崩溃。
- 合法数字的现有输出保持不变。
- 非法值必须显式标记，不能静默转换为 0。

---

## 6. 修改四：权重归一化不得抵消持续信号

### 6.1 当前缺陷

位置：`geo-agent/src/geo/rules/weights.py:36-53`

W3 真实输入可稳定复现：

```text
w3 compute_deltas = {'brand': -1, 'citability': 1}
w2 compute_deltas = {'citability': 1, 'schema': -1}
persisted_deltas = {'citability': 1}
apply_deltas      = 原权重不变
```

原因是总和从 100 变成 101 后，补偿排序首先选择 `citability`，立即把刚加的 1 减回去。

### 6.2 本轮采用的评分语义

这是产品语义选择，本文明确采用以下最小策略，GLM 不得自行替换为另一套公式：

1. 非零 persisted delta 表示已有持续证据，归一化不能改变其方向或把它恢复到原值。
2. 总和补偿只由 `delta == 0` 的无证据维度承担。
3. 在无证据维度中按可用容量降序、键名升序确定性分配，使用轮转避免全部落在一个维度。
4. 如果无证据维度容量不足以恢复到 100，抛出明确异常，失败关闭；不得静默改动有证据维度。

容量定义：

- `diff > 0` 时，可用容量为 `W_MAX - out[k]`；
- `diff < 0` 时，可用容量为 `out[k] - W_MIN`。

不要改变 `compute_deltas` 和 `persisted_deltas` 的公式；本轮只修 `apply_deltas` 的补偿策略。

### 6.3 必须新增或强化的测试

文件：`geo-agent/tests/test_rules_weights.py`

- `test_single_positive_persisted_delta_changes_weight`
  - 输入当前 W3 真实案例。
  - 断言 `citability > 25` 且总和为 100。
- `test_single_negative_persisted_delta_changes_weight`
  - 断言目标维度严格下降。
- `test_normalization_never_reverses_signaled_direction`。
- `test_normalization_fails_closed_when_zero_delta_capacity_is_insufficient`。
- 保留成对 `+1/-1`、边界 clamp、总和恰为 100 的既有测试。

只断言 `sum == 100` 不足以验收；必须同时断言证据方向生效。

### 6.4 验收条件

- 当前 W3 真实案例不再 no-op。
- 非零 delta 在未撞边界时必然改变目标权重且方向正确。
- 权重仍全部位于 `[W_MIN, W_MAX]`，总和严格等于 100。
- 无法满足约束时明确失败，不输出语义错误的权重。

---

## 7. 修改五：已发布内容去重门

### 7.1 当前缺陷

位置：

- `geo-agent/src/geo/generate/topics.py:18-42`
- `geo-agent/src/geo/generate/run.py:36-78`

`suggest_topics` 不读取 `content/published/`；Kimi 生成后的 slug/title 也没有与已发布内容比较。W3 因此生成了与 W2 高度近似的页面。

### 7.2 建议修改

实现一个确定性、无模型调用的 published index，读取 `content/published/*.md` frontmatter：

- `topic`
- `slug`
- `published_url`

去重分两层：

1. `suggest_topics` 对完全相同的规范化 topic/slug 标记 `suppressed_reason`；`run_suggest` 只把未标记项放入 `suggestions`，另把标记项放入 `suppressed`，不能静默丢弃。这样保持 `suggest_topics` 当前二元返回值不变，graph 也只会看到可用候选。
2. `run_generate` 在 Kimi 返回 slug/title 后做近重复检查。slug 按连字符拆词并去重，Jaccard 相似度 `>= 0.8` 时将草稿标记为 `validation=flagged`，问题中写明 `near_duplicate:<existing-slug>`。

近重复只做阻断提示，不自动删除草稿；人工仍可通过现有显式 review/override 流程裁决。不要加入 embedding、外部模型或新的网络依赖。

不要把 `suggest_topics` 改成三元返回值，避免扩大现有调用契约。需要同步更新 `run_suggest` 的返回字典和相应 graph mock 测试。

### 7.3 必须新增的测试

文件：

- `geo-agent/tests/test_generate_topics.py`
- `geo-agent/tests/test_generate_run.py`

覆盖：

- 与已发布 topic 完全相同的建议不会进入自动候选。
- `solar-only-vs-solar-plus-battery` 与 `solar-only-vs-solar-plus-battery-storage` 被识别为近重复。
- 不相关 slug 不误报。
- 近重复草稿写盘但为 `flagged`，且 issue 包含已有 slug。
- 不读取或修改真实 `content/published`，全部使用 `tmp_path` fixture。

### 7.4 验收条件

- graph 的自动 top suggestion 不会选中明确已发布主题。
- Kimi 改写主题后形成的近重复仍能在草稿门被拦下。
- 人工 override 保留且有审计记录。

---

## 8. 修改六：JSON-LD URL 必须与最终新闻路径一致

### 8.1 当前缺陷

位置：

- `geo-agent/src/geo/generate/run.py:54-74`
- `geo-agent/src/geo/generate/validate.py:110-117`

当前校验器只检查 Article 存在 `headline`，不检查 `mainEntityOfPage`。因此模型生成 `https://sunhestia.com/<slug>` 或 `/compare/<slug>` 仍会 validation passed，而真实发布路径是 `/news/<slug>/`。

### 8.2 建议修改

生成阶段确定默认 canonical：

```text
{targets.site.url.rstrip('/')}/news/{slug}/
```

规则：

- Article 的 `mainEntityOfPage` 必须存在。
- 若为字符串，必须等于 expected URL。
- 若为 `WebPage` 对象，其 `@id` 必须等于 expected URL。
- `run_generate` 应在结构化 `draft["json_ld"]` 写入 Markdown 前规范化默认 URL，禁止生成后再用正则改 JSON code fence。
- `run_mark_published(url=...)` 提供最终 URL 时，以该 URL 为权威；如果归档内容中的 Article URL 与它不一致，应失败关闭并保留原草稿，提示先修正草稿，不要在发布函数中用正则重写 JSON。
- 不传 `url` 时使用 `/news/{slug}/` 默认值。

建议给 `validate_draft` 增加可选 `expected_url` 参数，由 `run_generate` 传入；不要在校验器内部读取全局 settings，以保持测试隔离。

### 8.3 必须新增的测试

文件：

- `geo-agent/tests/test_generate_validate.py`
- `geo-agent/tests/test_generate_run.py`
- `geo-agent/tests/test_generate_hardening.py`

覆盖：

- 缺失 `mainEntityOfPage` 的 Article 被 flagged。
- `/compare/<slug>` 或根路径 `<slug>` 被 flagged。
- `/news/<slug>/` 通过。
- `run_mark_published(url=...)` 在 JSON-LD 不一致时拒绝归档；一致时归档 Markdown 的 JSON-LD 与 `published_url` 完全相同。
- FAQPage 等非 Article 类型不被错误套用 Article 规则。

### 8.4 验收条件

- 生成器不再产出缺 `/news/` 的 Article canonical。
- 发布归档和最终发布 URL 一致。
- 现有站点页面无需修改；本轮只修生成链和测试。

---

## 9. W2 `gap=null` 的处理决定

本轮明确不回填 W2。

理由：当前 `L3Source` 只有 `fetched_iso`，共享 `data/sources/` 没有 `week`、周快照或输入 manifest。此时运行 `assemble(2)` 会混入 W3 后抓取的来源，产生不可审计的历史结果。

正确处理：

- 保留 W2 `gap=null`。
- Research 展示“某期数据缺失”。
- 后续若要支持历史重算，另行设计按周冻结的 L3 manifest，至少包含 URL、内容哈希、抓取时间、week、代码提交和规则版本。

GLM 不得在本轮修改 W2 JSON 来制造非 null 结果。

---

## 10. 测试与验收命令

所有测试必须离线执行：

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
PYTHONPATH=/tmp/pylibs312:src python3.12 -m pytest \
  tests/test_qwen_client.py \
  tests/test_generate_kimi.py \
  tests/test_render.py \
  tests/test_rules_weights.py \
  tests/test_generate_topics.py \
  tests/test_generate_validate.py \
  tests/test_generate_run.py \
  tests/test_generate_hardening.py \
  -p no:cacheprovider --timeout=120
```

定向测试通过后裸跑完整回归，不要使用会吞掉退出码的管道：

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent"
PYTHONPATH=/tmp/pylibs312:src python3.12 -m pytest tests/ \
  -p no:cacheprovider --timeout=120
```

最后检查：

```bash
cd "/Users/jerry/AiProject/sunpower nova"
git diff --check
git status --short
```

验收必须同时满足：

- 新增负向测试先能在旧代码上失败，再在修复后通过。
- 完整测试不少于当前 `414 passed + 2 skipped`，且无新增失败。
- 没有真实 API 调用。
- 没有修改 W1–W3 原始数据、分析结果、knowledge、已发布内容或站点页面。
- `git diff` 中每一处修改都能对应本文第 3–8 节之一。
- 不以“测试全绿”代替本文列出的语义断言。

## 11. 建议提交拆分

为方便复审，建议分为以下提交，不要压成一笔大提交：

1. `fix(collect): validate qwen status_code before aggregation`
2. `fix(generate): bound kimi retries and total attempt budget`
3. `fix(research): reject non-numeric feedback metrics`
4. `fix(rules): preserve persisted delta direction during normalization`
5. `fix(generate): block published-topic duplicates and normalize article URL`

每笔提交都应包含对应测试。完成后提供提交 SHA、定向测试结果、完整回归结果，以及仍未完成的项目；不要仅回复“已修复”。
