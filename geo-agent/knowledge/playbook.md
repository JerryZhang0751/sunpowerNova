# SunHestia GEO Playbook · w4
> rule_version geo-seo-v4 | L1=45 | 被引源分析 sample_n=21(缺失142/js_only6)
> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。

## 1. 被引格式特征
### comparison_table（对比表）
- cited_n=2 sample_n=21 confidence=ok platforms=['doubao']
- 结论：comparison_table 极少被引用（21 中仅 2，去重 17 中仅 1），尽管问题空间中 comparison 意图占 6/45。当前对比表形态的内容未被引擎采纳，或对比类查询的回答未走表格化引用路径。｜行动：对比类需求暂以列表+规格卡片承载；小规模试验把核心对比维度做成精简 HTML 表格并观察后续周次引用变化。
### qa（Q&A）
- cited_n=1 sample_n=21 confidence=ok platforms=['doubao']
### list（清单）
- cited_n=20 sample_n=21 confidence=ok platforms=['doubao']
- 结论：在 doubao 已观测的带引用回答中，list（列表）是绝对主导格式：21 个样本中 20 个被引用回答采用列表结构（去重后 17 个中 16 个）。列表化内容（要点枚举、参数罗列、候选清单）是获得引用概率最高的呈现方式。｜行动：核心落地页与内容页优先改造为清晰列表结构（特性、型号、步骤、对比要点），并保证列表项自足、可被单独摘引。
### definition（定义段）
- cited_n=8 sample_n=21 confidence=ok platforms=['doubao']
- 结论：definition 与 qa 格式引用占比偏低：definition 21 中 8（去重 17 中 7），qa 21 中仅 1（去重 17 中 1）。纯定义/问答体不是当前主要引用载体。｜行动：定义与 FAQ 内容可作为页面辅助模块保留，但不应作为主打格式投入；优先把定义嵌进列表/规格卡片上下文中。
### spec_card（规格卡）
- cited_n=16 sample_n=21 confidence=ok platforms=['doubao']
- 结论：spec_card（规格卡片）为第二高引用格式：21 个样本中 16 个被引用回答包含规格卡片（去重 17 中 12），显示结构化参数/规格块在 doubao 引用中权重很高。注意该结论仅基于 doubao 单平台数据。｜行动：为产品/品类页补充机器可读的规格卡片（参数名-值对），覆盖功率、价格、容量、适用场景等高频决策字段。

## 2. 被引来源特征
```json
{
  "domain_type": {
    "other": 21
  },
  "page_type": {
    "blog": 1,
    "other": 11,
    "comparison": 1,
    "product": 4,
    "news": 4
  },
  "schema": {
    "": 6,
    "Organization": 1,
    "Product": 1,
    "Article": 1
  },
  "has_publish_date": 5,
  "ugc": 0,
  "resolved": 21,
  "unique_n": 17,
  "schema_unique": {
    "": 4,
    "Organization": 1,
    "Product": 1,
    "Article": 1
  },
  "schema_unique_platforms": {
    "": [
      "doubao"
    ],
    "Organization": [
      "doubao"
    ],
    "Product": [
      "doubao"
    ],
    "Article": [
      "doubao"
    ]
  }
}
```

## 3. 分平台差异
```json
{
  "doubao": {
    "n": 15,
    "mention_rate": 0.133,
    "citation_rate": 0.0
  },
  "qwen": {
    "n": 15,
    "mention_rate": 0.133,
    "citation_rate": 0.0
  },
  "zhipu": {
    "n": 15,
    "mention_rate": 0.133,
    "citation_rate": 0.067
  }
}
```

## 4. 问题空间与选题
意图簇：[{'intent': 'brand', 'n': 6}, {'intent': 'product-category', 'n': 9}, {'intent': 'decision', 'n': 9}, {'intent': 'geo', 'n': 3}, {'intent': 'cost', 'n': 6}, {'intent': 'comparison', 'n': 6}, {'intent': 'self-consumption', 'n': 6}]  选题缺口候选：[]

## 5. 可复用内容模板
- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。

## 6. 上期动作→指标对照
- 上期发布: self-consumption(2026-08-18); solar-only-vs-solar-plus-battery-storage(2026-08-28); solar-only-vs-solar-plus-battery(2026-09-01)
- mention_rate: 0.133 → 前期 0.133(Δ+0.0)
- citation_rate: 0.022333333333333334 → 前期 0.022333333333333334(Δ+0.0)
- sov: 0.042 → 前期 0.04466666666666666(Δ-0.0)
- self_geo: 41.1 → 前期 41.2(Δ-0.1)
- self_seo: 50.2 → 前期 49.9(Δ+0.3)
- 规则版本: —
- ⚠️ 收录有延迟、单周样本小;对照为观察性相关,非因果归因。
