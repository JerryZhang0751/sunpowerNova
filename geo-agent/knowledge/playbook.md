# SunHestia GEO Playbook · w7
> rule_version geo-seo-v7 | L1=45 | 被引源分析 sample_n=35(缺失140/js_only1)
> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。

## 1. 被引格式特征
### comparison_table（对比表）
- cited_n=13 sample_n=35 confidence=ok platforms=['doubao']
- 结论：对比表（comparison_table）引用居中：35 个样本中 13 次被引，24 个唯一答案中仅 7 个唯一被引，引用贡献中等。｜行动：在决策与对比意图页面补充对比表格（如 solar vs solar+battery），但不必作为唯一主力格式。
### qa（Q&A）
- cited_n=1 sample_n=35 confidence=ok platforms=['doubao']
- 结论：纯问答（qa）格式几乎不被引用：35 个样本中仅 1 次被引，24 个唯一答案中仅 1 个唯一被引，为最弱格式。｜行动：避免以纯 Q&A 作为内容主格式；问答内容应改写为列表或 FAQ schema 嵌入正文的混合形式。
### list（清单）
- cited_n=31 sample_n=35 confidence=ok platforms=['doubao']
- 结论：列表（list）是被引用最多的内容格式：35 个样本中 31 次带引用，24 个唯一答案中 20 个唯一被引，显著高于其他所有格式，是当前平台最主要的可引用呈现形式。｜行动：将核心话题优先改造为结构化列表（Top N、步骤清单、要点罗列），并保证列表在 HTML 中以可抓取的标记呈现。
### definition（定义段）
- cited_n=12 sample_n=35 confidence=ok platforms=['doubao']
- 结论：定义型内容（definition）引用中等偏低：35 个样本中 12 次被引，24 个唯一答案中 8 个唯一被引。｜行动：定义/科普内容作为辅助层，与列表或规格卡组合呈现，而非独立成篇。
### spec_card（规格卡）
- cited_n=25 sample_n=35 confidence=ok platforms=['doubao']
- 结论：规格卡（spec_card）引用表现第二：35 个样本中 25 次被引，24 个唯一答案中 19 个唯一被引，说明参数化、结构化的产品规格内容容易被引用。｜行动：为产品与品类页建设标准化规格卡（参数表+Product schema），覆盖品类与决策意图查询。

## 2. 被引来源特征
```json
{
  "domain_type": {
    "other": 35
  },
  "page_type": {
    "other": 3,
    "spec": 1,
    "product": 6,
    "news": 3,
    "blog": 17,
    "comparison": 5
  },
  "schema": {
    "": 9,
    "LocalBusiness": 1,
    "ElectricalContractor": 1,
    "RoofingContractor": 1,
    "WebSite": 1,
    "Organization": 7,
    "Product": 2,
    "NewsArticle": 1,
    "Dataset": 3,
    "BreadcrumbList": 11,
    "FAQPage": 7,
    "Article": 2,
    "TechArticle": 4,
    "BlogPosting": 2
  },
  "has_publish_date": 12,
  "ugc": 0,
  "resolved": 35,
  "unique_n": 24,
  "schema_unique": {
    "": 6,
    "LocalBusiness": 1,
    "ElectricalContractor": 1,
    "RoofingContractor": 1,
    "WebSite": 1,
    "Organization": 4,
    "Product": 2,
    "NewsArticle": 1,
    "Dataset": 1,
    "BreadcrumbList": 5,
    "FAQPage": 3,
    "Article": 1,
    "TechArticle": 2,
    "BlogPosting": 1
  },
  "schema_unique_platforms": {
    "": [
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
    "WebSite": [
      "doubao"
    ],
    "Organization": [
      "doubao"
    ],
    "Product": [
      "doubao"
    ],
    "NewsArticle": [
      "doubao"
    ],
    "Dataset": [
      "doubao"
    ],
    "BreadcrumbList": [
      "doubao"
    ],
    "FAQPage": [
      "doubao"
    ],
    "Article": [
      "doubao"
    ],
    "TechArticle": [
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
    "citation_rate": 0.067
  }
}
```

## 4. 问题空间与选题
意图簇：[{'intent': 'brand', 'n': 6}, {'intent': 'product-category', 'n': 9}, {'intent': 'decision', 'n': 9}, {'intent': 'geo', 'n': 3}, {'intent': 'cost', 'n': 6}, {'intent': 'comparison', 'n': 6}, {'intent': 'self-consumption', 'n': 6}]  选题缺口候选：['hestia solar', 'maximise solar self-consumption', 'self consumption', 'self consumption battery', 'self consumption of solar power', 'self consumption solar', 'solar self consumption', 'solar self consumption home system', 'solar self-consumption', 'solar vs solar with battery storage']

## 5. 可复用内容模板
- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。

## 6. 上期动作→指标对照
- 上期发布: about-the-team(2026-09-13); glossary(2026-09-05); home-solar-battery-deep-dive(2026-09-09); self-consumption(2026-08-18); solar-only-vs-solar-plus-battery-storage(2026-08-28); solar-only-vs-solar-plus-battery(2026-09-01)
- mention_rate: 0.133 → 前期 0.133(Δ+0.0)
- citation_rate: 0.06666666666666667 → 前期 0.06666666666666667(Δ+0.0)
- sov: 0.046000000000000006 → 前期 0.04800000000000001(Δ-0.0)
- self_geo: 42.8 → 前期 43.3(Δ-0.5)
- self_seo: 50.1 → 前期 49.9(Δ+0.2)
- 规则版本: —
- ⚠️ 收录有延迟、单周样本小;对照为观察性相关,非因果归因。
