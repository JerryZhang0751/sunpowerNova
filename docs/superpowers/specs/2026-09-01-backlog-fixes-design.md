# 三项 Backlog 修复设计（①归一化吞孤立 delta ②suggest 去重 ③w2 gap 回填）

- 日期：2026-09-01
- 状态：已批准（brainstorming 通审，3 项分叉均经用户决策）
- 来源：w3 收口（fb9f507）遗留三个 backlog 候选；file:line 已于 2026-09-01 对 main=fb9f507 核实
- 分支：`backlog-fixes`（自 main 切出，主 checkout 开分支非 worktree——项目惯例；①② TDD 红→绿各一提交，③纯数据操作零提交）

## 0. 用户决策记录

| # | 分叉 | 决策 |
|---|---|---|
| 1 | 孤立 delta 的补偿 −1 从哪个维度扣 | **零-delta 维中强度最低者**（有测量强度优先于无流维，无流维最后兜底；方向感知见 §1） |
| 2 | suggest 与已发布内容重复的处置 | **精确过滤 + 抑制计数**（`(page_type, topic)` 精确匹配移除，输出抑制摘要保持透明） |
| 3 | w2 重算结果落地方式 | **核验后替换 canonical**（recalc 产文件 → 核验门 → 备份原版 → 提升 canonical → 重渲 report.html） |

## 1. 范围

w3 三个 backlog 全修，目标 w4 启动前完成。三项相互独立：②①为代码改动（TDD），③为纯数据操作（`data/` 不入库，无 git 提交）。实施顺序：② → ① → ③（②防 w4 撞题最紧迫；③操作收尾错峰）。

---

## 2. ① apply_deltas 补偿语义修复

### 现状（2026-09-01 核实，main=fb9f507）

- `src/geo/rules/weights.py:36-53`：`apply_deltas` 套 delta 并夹值后，若总和≠100，补偿顺序 = `sorted(out, key=lambda k: (-abs(deltas.get(k, 0)), k))`——**非零 delta 维排最前**。
- w3 实证：citability 两周同向 delta=+1 通过 `persisted_deltas` 门（w2=0.826→w3=0.92），但它是唯一 delta 维 → raw 总和 101 → 补偿 −1 按 |delta| 降序落回 citability 自身 → 净变化 0。**孤立单维信号在现公式下永远调不动权**；规则已迭代 v1→v4 四版，权重从未离开 v1 基线（25/20/20/15/10/10）。
- 存量测试（`tests/test_rules_weights.py`）只锁成对 ±delta 场景（总和恰 100，补偿循环不触发）——孤立场景零覆盖，故改动不破坏存量。

### 设计

**新补偿语义**（仅夹值/取整导致总和≠100 时触发）：

1. **零-delta 维优先**：有证据裁决的维度（delta≠0）不被补偿染指，除非零-delta 池全部到边界（W_MIN/W_MAX）耗尽——保持现行 round-robin 跳边界逻辑作为最终兜底。
2. 零-delta 维内部：**有测量强度（strengths[k] 非 None）优先于无流维**；对未测量维度调权 = 无依据断言，故无流维排最后。
3. **方向感知排序**：`diff<0`（需减）按强度**升序**（最弱者让权）；`diff>0`（需加）按强度**降序**（最强者受益）。两方向均符合"权重跟随证据强度"的公式哲学。
4. 同分按名字 ASCII 兜底，全程确定性。

**签名**：`apply_deltas(weights, deltas, strengths=None)`——向后兼容；不传 strengths 时零-delta 维按名字序（确定性回退，文档注明）。调用点 `keeper.py:137` 改传 `strengths`（`dimension_strengths` 原始 dict，None 值由 apply_deltas 内部过滤）。

**排序键**（伪码）：

```python
measured = {k: v for k, v in (strengths or {}).items() if v is not None and k in weights}
if diff < 0:   # 要减 → 弱者让权
    order = sorted(weights, key=lambda k: (deltas.get(k, 0) != 0, k not in measured, measured.get(k, 0.0), k))
else:          # 要加 → 强者受益
    order = sorted(weights, key=lambda k: (deltas.get(k, 0) != 0, k not in measured, -measured.get(k, 0.0), k))
```

**效果推演**（w3 数据若发生在修复后）：w3 strengths = citability 0.92（delta +1）/ schema 0.28 / brand 0.0777 / 其余 None → diff=−1 → 零-delta 池中测量最弱 = brand → **citability 25→26、brand 20→19**。

**不追溯**：w3 的 rules_iteration 与 v4 归档是历史，不动；修复自 w4 生效（w4 的 prev_strengths 读 w3 记录，citability 再走强即重新裁决）。

**模块文档**：`weights.py` 顶部 docstring 同步补新补偿语义说明。

### 测试（新增，`tests/test_rules_weights.py`）

1. 孤立 +1：目标维 +1、零-delta 测量最弱维 −1，总和 100（w3 实例数值断言）。
2. 孤立 −1：目标维 −1、零-delta 测量最强维 +1。
3. 无流维兜底：全部测量维到 W_MIN 边界时才动 None 维。
4. 补偿目标已在边界：跳到下一个合格维度。
5. 不传 strengths：确定性（名字序）+ 总和恒 100。
6. 存量成对用例不回归（已有测试覆盖，跑全量即证）。

---

## 3. ② suggest 精确去重

### 现状（2026-09-01 核实）

- `src/geo/generate/topics.py:18-42`：`suggest_topics` 两个来源——(a) eval_report 弱维度（score<50）套 `GAP_TEMPLATES` 静态文案；(b) GSC 高曝光查询。**均不读 `content/published/`、`content/drafts/`**。
- w2/w3 两篇已发布页 frontmatter 的 `topic:` 字段**完全相同**（同一条 GAP_TEMPLATES platform 文案）——w3 近同题互蚀的系统根因；w4 裸跑会第三次建议同文案。
- frontmatter 已含 `topic` / `page_type` / `slug`（`content/published/*.md` 头部 `---` yaml 块）。

### 设计

- **`_published_keys(repo)`**：扫描 `content/published/*.md` + `content/drafts/*.md`，解析 frontmatter 取 `(page_type, topic)` 集合；**坏/缺 frontmatter 文件跳过不炸**（suggest 是只读诊断命令，单文件损坏不应整体失败）。
- **过滤**：建议的 `(page_type, topic)` 精确命中集合即移除（GSC 来源建议同样规则——查询词天然新鲜，不受影响）。
- **返回值**：`suggest_topics` 扩为 `(out, missing, suppressed)`；`run_suggest`（`src/geo/generate/run.py:140`）同步消费，打印抑制摘要：`已抑制 N 条与已发布/草稿重复的建议（覆盖弱维度: platform, ...）`。
- **不做**：模糊/token 重叠匹配（YAGNI——静态模板文案精确匹配即系统性撞题向量，无真实变体案例，避免阈值调参面）。

### 测试（新增，`tests/test_generate_topics.py` 或就近文件）

1. 已发布同 `(page_type, topic)` 建议被抑制且计数正确。
2. 草稿（`content/drafts/`）同样计入去重。
3. 坏 frontmatter 文件被跳过、其余去重照常。
4. 无关建议照常通过（eval_gap + GSC 两来源各一例）。
5. `run_suggest` 输出含抑制摘要行。

---

## 4. ③ w2 gap=null 回填（纯数据操作）

### 现状（2026-09-01 核实）

- `data/analysis/w2/eval_report.json` 的 `gap: null`（w3 为完整对象）。根因：w2 fetcher IP-pin 事故期竞品 L3 全灭 → `_score_competitors` 空 → gap 跳过；fetch 重做后 **assess 未重跑**。
- `do_recalc`（`src/geo/rules/run.py:13`）已存在：按指定版本重算并产 `eval_report.recalc-{v}.json`，不覆写 canonical。
- **v2 与现行 v4 规则 weights/signals 完全一致**（已核实：仅 entries 的 draft 元数据差异）→ 按 v2 回填既忠实历史（w2 原评分即 v2）又不会改分数。
- 竞品 L3 缓存为内容寻址（`data/sources/` sha1 目录），w2 重做期的 fetch 已落盘——回填大概率直接可得；缺失时补抓（见守卫）。
- `data/` 不入库（gitignored）→ 本项**零 git 提交**。
- w3 的 `40bd22c` 已让 research 容忍 gap 缺失；回填后 w4 research 读 w3/w2 两份报告时 gap 可比。

### 操作序列（python3.11，需网络仅当触发补抓）

1. `do_recalc(repo, week=2, rule_version="geo-seo-v2")` → 产 `eval_report.recalc-geo-seo-v2.json`。
2. **核验门**（任一失败即中止、canonical 不动、上报用户）：
   - `gap` 非空（含 `comp_avg_total` / `dim_diff` / `metrics`）；
   - `self_geo.total == 41.2` ∧ `self_seo.total == 49.9` 分毫不变（确定性重算自证：L1 未变 + v2 规则与当时一致）。
3. 过门后：`eval_report.json` 备份为 `eval_report.gap-null-archived.json` → recalc 文件提升为 canonical `eval_report.json`（删除 recalc 副本）。
4. 用提升后的报告重渲 `reports/w2/report.html`（现行中文仪表盘模板）。
5. 复核：canonical gap 非空、report.html 含 gap 数据、w3 产物未被触碰（`rules_iteration.json`/`changelog.md` 零变更）。

**守卫（gap 仍 null 的分支）**：w2 top-5 竞品域名对应 L3 缺失 → 用 fetcher 补抓这些 URL（走代理 10808）后回到步骤 1。

**不触碰**：w2 `rules_iteration.json`、rules/*.yaml、changelog、run.yaml、任何 tracked 文件。

---

## 5. 验收

- 全量测试绿（414 passed + 2 skipped 基线上净增 ①② 的新用例数）。
- ①单测演示：w3 实例数值（citability 25→26 / brand 20→19）在孤立 delta 用例中复现。
- ②单测演示：w4 场景（platform 弱维 + 已发布两篇同文案）下 suggest 不再出现该建议且打印抑制摘要。
- ③：`data/analysis/w2/eval_report.json` gap 非空、self 分数不变、`reports/w2/report.html` 重渲含 gap；原版留档。
- merge --no-ff → HTTPS 通道推送 → CI test+site 双绿。

## 6. 修订记录

| 日期 | 修订 |
|---|---|
| 2026-09-01 | v1 初版（brainstorming 通审，3 项用户决策见 §0） |
