# SunHestia GEO Playbook · w6
> rule_version geo-seo-v7 | L1=45 | 被引源分析 sample_n=37(缺失140/js_only2)
> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。

## 1. 被引格式特征
### comparison_table（对比表）
- cited_n=9 sample_n=37 confidence=ok platforms=['doubao']
- 结论：comparison_table 与 definition 引用率中等（分别为 9/37 与 8/37），在决策/对比类问题中起补充作用，但不是主要被引形态。｜行动：在 decision/comparison 意图页面保留对比表与术语定义模块，作为列表与规格卡片的辅助结构，而非主体。
### qa（Q&A）
- cited_n=3 sample_n=37 confidence=ok platforms=['doubao']
- 结论：qa（问答）形态引用率最低：37 个样本中仅 3 个被引用（去重后 2/21），单纯 FAQ 式结构对引用贡献有限。｜行动：避免把核心信息只放在 FAQ/问答模块中；问答内容应同时以列表或规格卡片形式冗余呈现。
### list（清单）
- cited_n=31 sample_n=37 confidence=ok platforms=['doubao']
- 结论：list（要点列表）是被引用最多的答案形态：37 个已解析样本中 31 个包含 list 结构，21 个去重样本中 16 个被引用，显著高于其他格式。｜行动：将核心卖点、选购要点、步骤类内容组织为清晰的要点列表/排行结构，提高被 AI 答案直接引用与改写的概率。
### definition（定义段）
- cited_n=8 sample_n=37 confidence=ok platforms=['doubao']
### spec_card（规格卡）
- cited_n=20 sample_n=37 confidence=ok platforms=['doubao']
- 结论：spec_card（规格卡片）引用表现次之：37 个样本中 20 个含规格卡片，21 个去重样本中 14 个被引用，说明结构化参数内容（功率、容量、价格、质保等）易被采纳。｜行动：为核心产品/方案建立标准化规格卡片，覆盖容量、功率、价格区间、适配场景等字段，并保持各渠道参数一致。

## 2. 被引来源特征
```json
{
  "domain_type": {
    "news_review": 1,
    "other": 36
  },
  "page_type": {
    "news": 4,
    "product": 6,
    "other": 4,
    "spec": 2,
    "comparison": 8,
    "blog": 13
  },
  "schema": {
    "": 12,
    "Organization": 2,
    "BreadcrumbList": 2,
    "Article": 1,
    "FAQPage": 1,
    "LocalBusiness": 1,
    "ElectricalContractor": 1,
    "RoofingContractor": 1,
    "Product": 1,
    "BlogPosting": 1
  },
  "has_publish_date": 14,
  "ugc": 0,
  "resolved": 37,
  "unique_n": 21,
  "schema_unique": {
    "": 8,
    "Organization": 2,
    "BreadcrumbList": 2,
    "Article": 1,
    "FAQPage": 1,
    "LocalBusiness": 1,
    "ElectricalContractor": 1,
    "RoofingContractor": 1,
    "Product": 1,
    "BlogPosting": 1
  },
  "schema_unique_platforms": {
    "": [
      "doubao"
    ],
    "Organization": [
      "doubao"
    ],
    "BreadcrumbList": [
      "doubao"
    ],
    "Article": [
      "doubao"
    ],
    "FAQPage": [
      "doubao"
    ],
    "LocalBusiness": [
      "doubao"
    ],
    "ElectricalContractor": [
      "doubao"
    ],
    "RoofingContractor": [
      "doubao"
    ],
    "Product": [
      "doubao"
    ],
    "BlogPosting": [
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
    "citation_rate": 0.067
  },
  "zhipu": {
    "n": 15,
    "mention_rate": 0.133,
    "citation_rate": 0.133
  }
}
```

## 4. 问题空间与选题
意图簇：[{'intent': 'brand', 'n': 6}, {'intent': 'product-category', 'n': 9}, {'intent': 'decision', 'n': 9}, {'intent': 'geo', 'n': 3}, {'intent': 'cost', 'n': 6}, {'intent': 'comparison', 'n': 6}, {'intent': 'self-consumption', 'n': 6}]  选题缺口候选：['hestia solar', 'maximise solar self-consumption', 'self consumption', 'self consumption battery', 'self consumption of solar power', 'self consumption solar', 'solar hestia', 'solar self consumption', 'solar self consumption home system', 'solar self-consumption', 'solar vs solar with battery storage']

## 5. 可复用内容模板
- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。

## 6. 上期动作→指标对照
- 上期发布: glossary(2026-09-05); home-solar-battery-deep-dive(2026-09-09); self-consumption(2026-08-18); solar-only-vs-solar-plus-battery-storage(2026-08-28); solar-only-vs-solar-plus-battery(2026-09-01)
- mention_rate: 0.133 → 前期 0.133(Δ+0.0)
- citation_rate: 0.06666666666666667 → 前期 0.022333333333333334(Δ+0.0)
- sov: 0.04800000000000001 → 前期 0.043333333333333335(Δ+0.0)
- self_geo: 43.3 → 前期 41.2(Δ+2.1)
- self_seo: 49.9 → 前期 49.7(Δ+0.2)
- 规则版本: —
- ⚠️ 收录有延迟、单周样本小;对照为观察性相关,非因果归因。
