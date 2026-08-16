# P2 生成 Agent 设计（Generate Agent）

- **日期**：2026-08-16
- **状态**：✅ **已实现**（2026-08-16，subagent-driven 9 任务 + 最终 opus 全分支评审 + 1 fix wave 全闭环；237 tests + 2 skipped）。分支 `worktree-p2-generate-agent`（off `main` @ `26819da`）已推 origin，**PR 待建**；合并后真跑六步见 §8.2。
- **分支**：`worktree-p2-generate-agent`（实际分支名，EnterWorktree 工具命名；计划文档中写作 `p2-generate-agent`；off `main` @ `26819da`）
- **权威依据**：整合 spec §6（生成 agent）、§9.2（brand.yaml）、§10（人工关口）、§11 P2 行（`docs/superpowers/specs/2026-07-29-sunpower-nova-integration-design.md`）。本文件细化 P2 的实现口径，冲突以整合 spec 为准。
- **前置**：✅ P0 评测地基已交付（165 tests）；✅ P1 研究 agent 已合入 main@4fa000f（186 tests + 1 live）；✅ site/ 15 页在线（brand.yaml 抽取源）；✅ eval w1 报告与 GSC 快照在库。
- **⚠️ 已知欠账**：P1 的 live run（`python3.11 -m geo.research.run --week 1`）尚未执行 → `knowledge/playbook.md` 尚不存在。**不阻塞 P2 实现**（fixture 驱动先行），但 P2 人审验收真跑前须先补跑 P1 live（见 §8 验收路径）。

---

## 1. 目标与范围

P2 在 6 环节闭环中落地「生成」环节：**读 playbook 被引特征 + brand.yaml 单一事实源 + 人指定选题 → 产出带 Schema JSON-LD 建议的官网内容草稿；事实核验确定性化；人审后手动发布**。

**交付物**：

1. `knowledge/brand.yaml` —— 单一事实源（Kimi 辅助抽取 + 确定性校验 + 人审定稿）。
2. `src/geo/generate/` 五模块（`brand/topics/kimi/validate/run`，见 §3）。
3. CLI：`python3.11 -m geo.generate.run`（生成 / 选题建议 / 人审记录 / 发布归档 / brand 引导，见 §6）。
4. 人审数据：`content/reviews.jsonl`（三档 verdict）+ `content/published/`（发布归档）。

**本轮不做（延后）**：

- `.astro` 页面自动渲染与自动发布 —— spec §11 明确「人手动发 site/」，发布链路自动化属 P3+（YAGNI）。
- LangGraph DAG 节点接入（`generate_node`）—— 同 P1 延后策略，模块稳定后再加薄包装。
- 研究结论自动选题 —— 等 playbook 常态产出后再接（P2 只做确定性建议 + 人指定）。
- 多语言内容生成 —— brand.yaml `i18n` 字段仅预留 schema 位。
- 多候选生成 / Win-Rate 重排 —— spec §4-bis 明确本期无 LLM Judge；一次调用产一篇。
- 定时复跑 —— P3 闭环范畴。

---

## 2. brand.yaml —— 单一事实源

### 2.1 生命周期定位

**一次性引导（bootstrap）→ 之后人工维护的上游事实源**。生成流向单向：`brand.yaml → 草稿 → 人审 → site/ 新页`；新事实出现时**人手动更新 brand.yaml**（version +1），不从 site 反向重抽。重新抽取仅低频防御性场景（人绕过生成流直改 site 页 / site 新增非生成页 / 首抽遗漏），故抽取做成**薄的可重跑工具**而非常规环节。

### 2.2 顶层结构

```yaml
version: 1            # 人维护，事实变更即 +1；草稿 frontmatter 记录生成时 brand_version
updated: 2026-08-16
entity:               # 实体定义（取自 index/about/contact/imprint）
  brand: SunHestia
  legal_name: "..."   # imprint 页
  domain: sunhestia.com
  positioning: "..."  # index/about 定位语
  locations: [...]
products:             # 规格库 —— 反幻觉核心锚点（取自 products.astro 等）
  - id: home-battery
    name: SunHestia Home Battery
    specs:
      chemistry: LiFePO4
      capacity_kwh: "5–15"
      warranty_years: 10
faqs:                 # FAQ 库（faq.astro 6 条，问答原样）
  - q: "..."
    a: "..."
glossary:             # 术语表（self-consumption / LiFePO4 / hybrid inverter，取自 news 页）
  - term: "..."
    definition: "..."
banned:               # 口径禁项（校验器按模式扫描）
  - no_pricing
  - no_savings_percentages
competitors: [...]    # 竞品参考（L2 competitors_mentioned 聚合，轻量；不进反幻觉锚点）
i18n: {}              # 多语言预留（本期空）
```

### 2.3 引导（bootstrap）流程 `--bootstrap-brand`

1. 直读本地 `site/src/pages/**/*.astro` 15 页原文（repo 内文件，**不抓线上**）。
2. Kimi K3 提示词：只准从所给页面文本抽取事实 → JSON 输出（`json_object`，比 YAML 文本稳）→ 落 YAML。
3. **确定性校验器** `validate_brand(brand, sources)`：
   - 所有数字字面量（含单位上下文）必须字面出现在源页文本（`version`/`updated` 等元数据字段豁免）；
   - 产品名 / 术语必须字面出现；
   - 未命中项输出清单标红，**人决定修/删**（校验器不静默丢弃）。
4. 人审定稿 → 写入 `knowledge/brand.yaml`。

**防覆写规则**（2026-08-16 实现定稿，最终评审修复）：`knowledge/brand.yaml` 已存在（= 人审定稿在库）时，重跑 bootstrap **一律写 `knowledge/brand.yaml.draft`**（即使零违规），由人对比后决定是否替换——保护 `version` 溯源链（草稿 frontmatter / reviews.jsonl 依赖 `brand_version`）；仅首建（文件不存在且零违规）才直接写 `brand.yaml`。

**校验器核心**（数字清单提取 `numeric_claims_inventory(text)` + 字面归属判定 `claim_in_sources(claim, text)`）与生成环节草稿核验（§5）**复用同一实现**。

---

## 3. 模块架构

`src/geo/generate/`，5 个单元（对称 P1 `research/` 模式，均 <150 行）：

| 文件 | 职责 | 确定性 |
|---|---|---|
| `brand.py` | brand.yaml 加载/版本校验 + bootstrap 抽取（Kimi seam）+ `validate_brand` | 校验✅ 抽取🌐 |
| `topics.py` | `--suggest`：读 eval_report 低分维度 + GSC 查询词簇 → 选题建议列表 | ✅ |
| `kimi.py` | 生成 seam：playbook 摘要 + brand 事实 + topic → `{frontmatter, body_md, json_ld[], fact_anchors[]}` | 🌐（chat_fn 可注入） |
| `validate.py` | 草稿四项核验（§5）+ 事实核对清单渲染 | ✅ |
| `run.py` | CLI 编排（§6）+ 草稿落盘 + 人审/归档命令 | ✅ |

**数据流**：

```
knowledge/brand.yaml · knowledge/playbook.md · input(topic,page_type)
   │ kimi.py (playbook 摘要[确定性解析] + brand 全量 + topic → Kimi K3)
   ▼
DraftResult{frontmatter, body_md, json_ld[], fact_anchors[]}
   │ validate.py (确定性四项核验)
   ▼
content/drafts/{slug}.md  (正文 + Suggested JSON-LD + 事实核对清单附录)
   │ 🔴 人审（三档）── run.py --review 记录 → content/reviews.jsonl
   │    └ pass/minor → 人手动发 site/ → --mark-published → content/published/{slug}.md
   ▼
(供后续评估环节对照已发布内容)
```

---

## 4. 生成流程（kimi.py）

**Kimi 调用前的确定性输入组装**：

1. **playbook 摘要**：确定性解析 `knowledge/playbook.md` 的结构化字段——高被引格式特征（带 cited_n/sample_n）+ §5 内容模板骨架；`--allow-no-playbook` 时以通用 GEO 最佳实践占位，产物头部加「⚠️ 未经研究校准」横幅。
2. **brand.yaml 全量事实**：作为「只能引用这些事实」的硬约束注入 prompt。
3. **topic + page_type**：`--page-type ∈ {faq, spec, comparison, guide}`（默认 guide）。

**Kimi 调用**（沿 P1 seam）：

- system：SunHestia 官网内容写手；纪律：只能用 BRAND FACTS 中的数字与规格，不得编造数字/型号/承诺。
- `temperature=1`（kimi-k3 强制）、`response_format={"type":"json_object"}`、`chat_fn` 可注入（mock 测试）。
- 输出 JSON：`{frontmatter, body_md, json_ld[], fact_anchors[]}`。
  - **fact_anchors** = Kimi 自报草稿中每个数字对应的 brand.yaml 字段路径，**统一 id 式**（如 `products[home-battery].specs.warranty_years`，对 product 重排序稳健）→ 供确定性交叉验证（§5 第 2 项）。
- 一次调用产一篇；不做多候选重排（§1 不做项）。

---

## 5. 草稿契约与确定性核验

### 5.1 `content/drafts/{slug}.md`

````markdown
---
topic: "How to size a home battery"
page_type: guide
slug: how-to-size-a-home-battery
created: 2026-08-16
playbook_week: 1        # --allow-no-playbook 时为 null + 头部警告横幅
brand_version: 1
status: draft           # draft | published | rejected
validation: passed      # passed | flagged
---

（正文 markdown：按 page_type 选骨架——对比表 / 规格卡 / FAQ 块 / 定义段）

## Suggested JSON-LD
```json
{"@context": "https://schema.org", "@type": "Article", ...}
```

<!-- AUTO-GENERATED 事实核对清单（校验器产出，人审加速器）
| 草稿中的 claim | brand.yaml 来源 | 校验 |
|---|---|---|
| 5–15 kWh | products[home-battery].capacity_kwh | ✅ |
| 10-year warranty | products[home-battery].specs.warranty_years | ✅ |
-->
````

### 5.2 validate.py 四项核验

1. **frontmatter 完整性**：必填字段齐全、枚举值合法（page_type/status/validation）。
2. **数字归属核验（脊柱）**：从 body 抽取所有数字 claims（带单位：kWh/W/年/%…；纯排版序号豁免）→ 逐个在 brand.yaml 数字库存匹配 → 与 fact_anchors 交叉验证（anchor 路径真实存在且值吻合）→ 未命中标红。
3. **JSON-LD 结构校验**：合法 JSON、`@type` 合法（Article/FAQPage/HowTo/Product…）、类型必填键齐（如 FAQPage 必有 `mainEntity[]`）。
4. **口径禁项**：banned 模式扫描（货币符号 / 价格句式 / 「节省 xx%」句式）。

核验结果写 frontmatter `validation` 字段 + 草稿尾部核对清单附录。**flagged 不拦截生成、只标红**——裁决权在人审关口（与「发布永远人确认」同一哲学）。

---

## 6. 人审工作流与 CLI

### 6.1 人审流（人肉裁决，工具只记录）

```
草稿生成 → 人读 draft（尾部核对清单加速核对）
  → --review <slug> --verdict pass|minor|reject --notes "..."
      ├─ reject → status: rejected（留档）
      └─ pass/minor → 人手动发 site/（P2 绝不代发）
                       → 人发布后 --mark-published <slug> 归档
```

- `content/reviews.jsonl` 追加 `{slug, verdict, notes, ts, brand_version, playbook_week}` → 喂 §8 报告「生成人审通过率」观察项（P2 只记数据；报告集成属 P3）。
- `--mark-published`：draft → `content/published/{slug}.md` + frontmatter `status: published`（供评估环节对照已发布内容，spec §6）。**守卫**（2026-08-16 实现定稿）：`status: rejected` 的草稿拒绝归档（stderr 说明 + 退出码 1，草稿原样保留）——发布归档仅属 pass/minor 分支。

### 6.2 CLI 总览

```bash
python3.11 -m geo.generate.run --week 1 --suggest                       # 只读选题建议
python3.11 -m geo.generate.run --week 1 --topic "..." --page-type guide  # 生成草稿
                                                         [--allow-no-playbook] [--no-kimi]
python3.11 -m geo.generate.run --review <slug> --verdict pass|minor|reject [--notes "..."]
python3.11 -m geo.generate.run --mark-published <slug>
python3.11 -m geo.generate.run --bootstrap-brand                         # 一次性引导抽取
```

`--topic` 是生成主通道（人显式触发，与「发布永远人确认」同哲学）；`--suggest` 只读打印、不自动生成。

**参数语义**：`--week N` 只作用于 `--suggest` 的数据源定位（`data/analysis/w{N}/eval_report.json` + `data/snapshots/w{N}/gsc.json`）。playbook 不按周存放（P1 产单份 `knowledge/playbook.md`），草稿 frontmatter 的 `playbook_week` 从 playbook 文件头（P1 render 的「生成自 w{N}」行）确定性解析；`--allow-no-playbook` 时为 null。

---

## 7. 错误处理（沿 P1 哲学：诚实标注，不静默编造）

| 失败 | 处理 |
|---|---|
| playbook.md 缺失 | 默认拒跑 + 提示先跑 `python3.11 -m geo.research.run --week 1`；`--allow-no-playbook` 显式降级（产物标「未经研究校准」） |
| brand.yaml 缺失 / version 非法 | 拒跑，提示先 `--bootstrap-brand` |
| Kimi 生成失败 / 非法 JSON | **不产草稿**：重试 1 次后报错退出（生成是主产出，不像 meta_llm 静默降级返空） |
| fact_anchors 缺 / 路径不存在 / 值不吻合 | validation: flagged + 核对清单标红，人审裁决 |
| 校验 flagged（数字未归属等） | 草稿照产 + 标红（同上） |
| `--suggest` 时 eval_report / gsc 快照缺失 | 打印已有部分 + 标注缺失源，不崩 |
| `--review`/`--mark-published` 的 slug 不存在 | 报错退出，列出现有 slug |

---

## 8. 测试策略（照 P1 切分）与验收

### 8.1 测试

- **确定性（入 CI）**：topics（给定 fixture eval_report+gsc → 精确建议列表）；validate 四项（数字归属 / JSON-LD / banned / frontmatter）；`validate_brand` 校验器；run 编排（mock chat_fn）；`--review`/`--mark-published` 命令。
- **mock Kimi**：好 JSON → 正确草稿落盘；坏 JSON → 报错退出（不产半成品）；fact_anchors 缺/错 → flagged。
- **live（`@pytest.mark.live`，手动）**：真 Kimi + fixture mini-playbook + 真 brand.yaml 生成一篇，只验链路通，**不判文本质量**。
- **人审验收（spec §11 P2 行）**：真跑一篇 → 人按三档审 → **至少一篇 pass 且 `validation: passed`** = 达标。

### 8.2 验收路径（真跑顺序）

1. 补跑 P1 live：`python3.11 -m geo.research.run --week 1` → 产真 playbook（同时清 P1 验收欠账）。
2. `--bootstrap-brand` → 校验器通过 → 人审定稿 brand.yaml。
3. `--suggest` 挑题（或人直接给）→ `--topic` 真跑生成。
4. 人审三档 → 至少一篇 pass → 手动发 site/ → `--mark-published` 归档。

### 8.3 验收标准

1. ✅ brand.yaml 与 site 15 页事实一致（校验器通过 + 人审）。
2. ✅ 产出一篇**通过人审、事实无误**（`validation: passed`）的可发布官网内容（含 Schema JSON-LD 建议）。
3. ✅ 确定性测试全绿；Kimi 报错 / 降级路径被测。
4. ✅ 人审三档 + 发布归档数据落盘（供 P3 报告观察项）。

---

## 9. 与上下游衔接（P3 契约）

- **上游 P1**：读 `knowledge/playbook.md` 结构化字段（高被引特征 + 内容模板）；playbook 缺失的降级路径独立可测。
- **下游 评估（P0 已有）**：`content/published/` 供评估环节对照「已发布内容」（spec §6：草稿从不进评分）。
- **下游 P3 RulesKeeper**：`content/reviews.jsonl` 喂「生成人审通过率」报告观察项；草稿 frontmatter 的 `brand_version`/`playbook_week` 支持按版本追溯。

---

## 10. 实现期待核实项（已全部定稿，2026-08-16 实现期落定）

1. **数字抽取的正则边界** ✅ 已定稿：单位边界用 `(?![a-z0-9])` 替代 `\b`（`%` 符号形式可匹配、`kwhz` 类误报已挡，负测在库）；范围（5–15）/连字符形（10-year）/排版序号与年份豁免均 fixture 实测。已知 minor：小数 claim（4.5 kWh）丢整数位——归 P1-live 后校准。
2. **playbook.md 结构化字段的解析规则** ✅ 已核验：`playbook_digest` 三正则与 `research/render.py` 的 `render_playbook` 实际输出逐行一致（最终评审员比对源码确认）；真 playbook 产出后无需再对（格式由 render 端保证）。
3. **JSON-LD 类型必填键清单** ✅ 已落地：Article(headline)/FAQPage(mainEntity)/HowTo(name+step)/Product(name+brand) 四类在 `validate.py` 白名单；已知 minor：空 `json_ld: []` 目前过验（延后校准）。
