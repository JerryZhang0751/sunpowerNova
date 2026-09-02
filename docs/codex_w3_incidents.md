# w3 实跑错误汇总 —— 供 codex 复检与验证

> 生成：2026-09-01（w3 收口后）
> 范围：2026-09-01 w3 周迭代（`geo-agent` 全链 + 发布）中三起**阻断性错误**（已修）与三项**发现未修**。
> 修复 commit 均直接在 main（实跑抢修、无分支评审）：`e6e1531` / `40bd22c` / `67ea368`；w3 全量提交区间 `4343635..fb9f507`（main=origin/main=fb9f507）。
> 测试基线递进：410 → 412 → 413 → **414 passed + 2 skipped**（每修复各 +1/+2 测试，零回归）。

---

## 复检环境与纪律（先读）

- 测试：`cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`（`.venv` 若可直用亦可）；⚠️ 管道 `| tail` 会吞 summary/exit code——裸跑读输出。
- ⚠️ **勿触发真实采集**：生产周号 1–3 是真实数据（API 计费）；测试周号带 900-999 有 `validate_production_week` 守卫。live 测试默认 skip。本复检应可完全离线完成（代码阅读 + 单测 + 盘上数据）。
- 关键数据路径：
  - `geo-agent/data/raw/w3/runs.jsonl`（采集 manifest；当前 188 行 = planned 53 + ok 45 + failed 8 + skipped_exists 82；manifest 追加式，resume 会重复注册 planned，`collection_health` 按唯一 (model,prompt_id,run) 去重）
  - `geo-agent/data/analysis/w{1,2,3}/eval_report.json`、`data/analysis/w{2,3}/rules_iteration.json`
  - `geo-agent/knowledge/playbook.md`（w3 已晋升）、`geo-agent/content/reviews.jsonl`（3 条）
- 崩溃现场日志已不可考（后台任务临时文件），错误信息以本文转录为准；数据侧证据（runs.jsonl 的 failed 行、w2 eval_report 的 null）都在盘上可复核。

---

## 错误 1（P0 级）：qwen API 错误块被聚合成「空答案」，账号额度耗尽不可见

### 症状与现场
- w3 采集首跑：doubao 15/15、zhipu 15/15、**qwen 11/15**——K03/M01/M03/S02 四题报 `qwen 返回空答案`，41/45=91.1% < 95% 门，`collect_node` 阻断：
  ```
  RuntimeError: 采集成功率 73.3% < 95% 门槛,阻断流水线: {'doubao': {...1.0}, 'zhipu': {...1.0},
  'qwen': {'planned': 15, 'valid': 11, 'success_rate': 0.733}}
  ```
- 同周裸跑续跑（collect 幂等只补 4 题）**再次同样失败**（tenacity 每题 2 次尝试，两轮共 4 次/题全挂）→ 判定非瞬态、系统性。

### 证据（逐 chunk 原始流探针）
对失败题 M03 与对照题 C01（首跑早些时候**成功**的题）各发一次探针，两家均返回**单个 0.2s 错误块**：
```
[chunk 1] code=Unknown status=None out_keys=[] content=null
message: {"request_id":"...","code":"AllocationQuota.FreeTierOnly",
          "message":"Free quota exhausted. To continue accessing the model on a paid basis,
          please add funds or disable the \"use free tier only\" mode in the management console."}
```
→ 早成功的 C01 复测同错 = **账号免费额度在采集中途耗尽**（挂的恰好是排在后面的题=调用序效应，非题目相关）。与 w1 豆包「安全体验模式」429 同类（账号侧）。用户控制台解锁后单题探针恢复（65s/5415 字符/45 引用）。

### 根因
`geo/collect/qwen_client.py` 的流聚合循环**不检查 `r.code`**：DashScope 的错误伪块（`code="Unknown"`，真实错误码在 `message` JSON 里）被当普通块处理，`output` 为空 → 聚合出空 answer → `collector._one` 只能抛 `InvalidCollection("qwen 返回空答案")`（collector 侧空答案门 r2 已有；客户端侧透传缺失）。= 工程审查（2026-08-24）M 级遗留「qwen 错误流块不查 r.code」的客户端侧半项。

### 修复（`e6e1531`）
`qwen_client.py`：
- 新增 `class QwenAPIError(RuntimeError)`；
- 流循环（总预算检查之后）加守卫：
  ```python
  code = getattr(r, "code", None)
  if code and code not in (200, "200"):
      raise QwenAPIError(f"DashScope API 错误(code={code}): {getattr(r, 'message', '')}")
  ```
- 与 collector 的交互：`_one` 的 tenacity（stop_after_attempt=2, reraise）重试用尽后上抛，runs.jsonl 的 `error` 字段携带真实错误码。
- 测试（TDD 红2绿2）：`tests/test_qwen_client.py::test_collect_qwen_raises_api_error_chunk`（流首错误块）、`test_collect_qwen_error_chunk_after_content_still_raises`（内容块后错误块同样抛，不返回残缺答案）。

### ⚠️ 证据边界（复检重点）
- **抛出路径只有单测（mock）证据**：额度恢复后补采成功，w3 的 8 条 failed 行全是修复前的「qwen 返回空答案」——`QwenAPIError` 未在真实错误块上端到端触发过。
- **生产证据只覆盖「守卫不误伤成功路径」**：修复在树上时 qwen 补采 4 题 + 后续周内调用全部正常（成功流块的 code 为 200/None 时放行）。

### codex 复检点
1. 守卫的**误报面**：DashScope 成功流块是否存在 `code` 非 200/"200" 且非空的合法形态（如 SDK 版本差异、部分 chunk 携带其它状态码）？当前判据 `if code and code not in (200,"200")` 是否会把任何成功形态误判为错误。
2. 守卫位置在总预算检查之后：预算耗尽先 break、错误块不抛——语义是否可接受（w3 顺序=先预算后守卫，首块即错的场景 0.2s 内预算必不超，实际无影响；但值得确认无死角）。
3. 错误块出现在**最后一个 chunk**（流末失败）时 `answer_parts` 已有部分内容——现实现直接 raise 丢弃部分答案（测试 2 锁定此语义）。是否符合「宁可不写 L1 不可写残缺」的采集门哲学。
4. `tenacity` 对 `QwenAPIError` 同样重试 2 次：额度类**确定性错误**重试是浪费但无害（0.2s×2）——是否值得按错误类型短路（设计判断，非必须）。

---

## 错误 2（P1 级）：research 反馈对照节 `None - float` TypeError（w2 数据洞在 w3 首次暴露）

### 症状与现场
research 节点崩溃，playbook 渲染失败：
```
graph.py:64 research_node → run.py:77 run_research → render.py:61 render_playbook
→ render.py:32 _feedback_section → render.py:30 row
TypeError: unsupported operand type(s) for -: 'NoneType' and 'float'
```
崩溃点在 `_promote()` 调用的参数求值处 → **未发生任何写盘**，`knowledge/playbook.md` 仍为 w2 版（mtime 08-29 佐证），无知识污染。

### 根因（两层）
1. **触发**：`_feedback_section` 的对照语义是 `latest=week-1`、`prev=week-2`。w3 是**第一个两者同时存在**的周（w2 跑时 prev=w0 不存在，只走「首期基线」分支）——首次进入 Δ 减法分支。
2. **数据洞**：`_collect_feed` 读各周 `eval_report.json` 的 `gap.metrics`，而 **w2 的整个 gap 为 null**（盘上可复核：w1/w3 的 mention_rate/citation_rate/sov 均为浮点，w2 全 null）。w2 gap=null 的成因：`analyst.py` 仅在 `self_geo_score and comp_geos` 都非空时计算 gap——w2 首跑正逢 fetcher 代理事故（top-40 抓取 0/40），竞品 L3 全灭 → `_score_competitors` 返回空 → gap 跳过；**w2 的「诚实重做」重跑了 fetch→research→rules 但没有重跑 assess**，null 固化进 w2 报告。
3. 旧 `row()` 用 `lat[k]`/`prev[k]` 直接下标 + 无 None 检查 → `None - float` 崩溃。（= 工程审查 M 级遗留「render.py:30 None 相减 TypeError」，此前从未被触发。）

### 修复（`40bd22c`）
`render.py` `row()`：
```python
v = lat.get(k)
if prev:
    p = prev.get(k)
    if v is None or p is None:
        return f"- {label}: {v} → 前期 {p}(Δ不可算:某期数据缺失)"
    return f"- {label}: {v} → 前期 {p}(Δ{round(v - p, 1):+})"
```
（附带消除了 `prev[k]` 缺键的 KeyError 面。）测试：`tests/test_render.py::test_render_playbook_feedback_section_tolerates_null_metrics`（w2-null + w1-float 的 feed：不抛、有值行照常展示、null 行含「数据缺失」标注）。w3 playbook §6 已按此渲染（`geo-agent/knowledge/playbook.md` 可见 w2 三指标行 = 「Δ不可算:某期数据缺失」）。

### codex 复检点
1. `row()` 的 None 语义是否完备：`lat` 非 None 但**整键缺失**（.get → None）也走「数据缺失」分支——是否与「无数据」分级合理。
2. **w2 gap=null 是否应回填**（见「发现未修」C）：`assemble(2)` 重算会引用**当前** `data/sources/` 的共享 L3 池（含 w3 期抓取）——跨周来源混用的口径问题，需要裁决而不是顺手修。
3. `_feedback_section` 其余行（published 行的 `p['slug']`/`p['created']` 下标）是否同样存在缺键面（`_collect_feed` 构造时 created 有默认值，理论安全——请复核）。

---

## 错误 3（P1 级）：generate 草稿生成 Kimi 调用 180s 超时 ×2 挂节点

### 症状与现场
research 完成后 generate 节点失败退出：
```
generate_draft 第 1 次失败: Request timed out.
geo.generate.kimi.GenerateError: Kimi 生成两次失败: Request timed out.
```
（进程为后台 detached 运行，非前台 600s SIGTERM——已排除 runbook 已知的「前台杀重试」因素。）

### 根因
`generate/kimi.py::_kimi_chat` 默认 `timeout=180`。**同轮 research 层的 Kimi 调用（120/180s）全部成功** → API 可达，问题是**草稿生成为长补全**超出 180s。历史证据：模型记录 Kimi 实测响应 50–215s（w2 首调也曾在 180s 超时一次、靠重试救回）——180s 配置低于已观测长尾。

### 修复（`67ea368`）
`generate/kimi.py::_kimi_chat` 默认 `timeout: 180 → 300`（研究层 `research/kimi.py` 的 120s/180s 各自独立、不动）。测试：`tests/test_generate_kimi.py::test_kimi_chat_timeout_covers_documented_tail`（patch `openai.OpenAI`，断言构造 kwargs `timeout >= 300`）。**生产证据**：修复后续跑中 generate 首调耗时 >180s 未再报超时（旧配置必挂），草稿落盘 validation=passed。

### codex 复检点
1. 300s 的依据是「历史实测长尾 215s + 余量」——是否应改为可配置（settings）而非硬编码默认（工程审查另有「模型名/参数 7 处硬编码」未结项，本修复延续了这个模式，属权衡而非疏漏，请评估）。
2. 审计项「`_kimi_chat` ×3 超时各异（research×2 + generate）」仍未统一——本修复后 120/180/300 三档并存，是否值得收敛（backlog 判断）。
3. `GenerateError` 重试=2 次×300s 最长阻塞 ~10min，DAG 无节点级墙钟——可接受性评估。

---

## 发现未修（本轮沉淀的开放项，供 codex 评估/裁决）

### A. 规则引擎归一化吞掉「孤立的 ±delta」→ 单维持续信号永远调不动权重
- **实证**（用盘上真实数据跑 `geo/rules/weights.py` 三函数，可复现）：
  ```
  w3 compute_deltas: {'brand': -1, 'citability': 1}      # strengths: brand 0.0777/cit 0.92/schema 0.28(取整为0被滤)
  w2 compute_deltas: {'citability': 1, 'schema': -1}
  persisted_deltas:  {'citability': 1}                    # citability 两周同向 +1 → 通过 2 周持续性门 ✓
  apply_deltas:      权重不变                            # 25+1=26 → 总和 101 → 归一化按 |delta| 降序
                                                         # 把补偿 -1 落回 citability 自身 → 25
  ```
- 即：**w3 发生了首个真实权重裁决且 citability 胜出，但被归一化 no-op 吞掉**。语义后果：仅当存在成对 ±delta（如 P3 演练的 cit+1/brand−1）时权重才会动；单一维度连续走强在现公式下**结构性无效**。
- 位置：`geo/rules/weights.py::apply_deltas` 的 sum-to-100 补偿循环（order=`-abs(deltas.get(k,0))`）。候选修法方向（未实施）：补偿负担落到非证据维度 / 全维最大余数法——**属评分语义变更，需用户决策**。

### B. generate `--suggest` 无「已发布去重」→ w3 草稿与 w2 已发布页近同题
- w3 草稿 `solar-only-vs-solar-plus-battery`（comparison）与 w2 已上线 `/news/solar-only-vs-solar-plus-battery-storage/` 内容重合度极高（同题、同规格卡、FAQ 答案几乎同文）。选题只看 GSC 印记+playbook 缺口，不对照 `content/published/`。
- **用户已知情裁决发布**（reviews.jsonl 第 3 条 notes 留痕「内容互蚀风险,作对比观察」）——w4 起可观察互蚀双页的 GSC/被引对照。去重逻辑是 backlog。

### C. w2 `eval_report.json` 的 `gap=null` 数据洞（错误 2 的上游）
- 成因见错误 2；w2 报告的竞品差值节缺失/三指标 null 已固化。是否用现有竞品 L3 回填 `assemble(2)`（涉及跨周来源混用口径）待裁决。

### D.（轻微，发布环节）草稿 JSON-LD 的 `@id`/`mainEntityOfPage` 缺 `/news/` 前缀
- w2、w3 连续两篇草稿均生成 `https://sunhestia.com/<slug>`（缺 `/news/`）；两次均在人工建页时按最终 URL 修正（未改生成器）。建议生成器用 targets/news 路径约定补齐。

---

## 附：w3 运行账目（复核用）

| 项 | 值 |
|---|---|
| runs.jsonl | planned 53 / ok 45 / failed 8 / skipped_exists 82（追加式 manifest，resume 重复注册 planned；唯一键去重后 45/45=100%） |
| failed 8 行 | 全部为修复前「qwen 返回空答案」（4 题 × 2 轮）；**无** QwenAPIError 行（见错误 1 证据边界） |
| 分数 | GEO 41.1（43.4→41.2→41.1）/ SEO 50.2（49.8→49.9→50.2） |
| 规则 | geo-seo-v3→v4；双 draft 维持；权重 before==after |
| 交付 | 第 3 篇 `/news/solar-only-vs-solar-plus-battery/` 上线（双域名 200、check 0/0/0、build 17 页、部署 477f6462） |
| CI | run 33507660138（test+site 双绿）@fb9f507 |
