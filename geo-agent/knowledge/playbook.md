# SunHestia GEO Playbook · w5
> rule_version geo-seo-v5 | L1=45 | 被引源分析 sample_n=33(缺失116/js_only0)
> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。

## 1. 被引格式特征
### comparison_table（对比表）
- cited_n=6 sample_n=33 confidence=ok platforms=['doubao']
- 结论：comparison_table 与 qa 格式被引较少：33 个样本中分别为 6 个与 4 个，去重后 26 个唯一页面中为 6 个与 3 个。｜行动：对比表格与问答段落可作为补充而非主要投入方向；仅在有明确对比/决策意图的页面部署。
### qa（Q&A）
- cited_n=4 sample_n=33 confidence=ok platforms=['doubao']
- 结论：qa 为本周最不被引用的格式：33 个样本中仅 4 个，去重后 26 个唯一页面中仅 3 个。｜行动：避免将 FAQ/QA 作为核心内容载体；如需覆盖问答意图，可结合 FAQPage schema 但以 list/spec_card 为主体。
### list（清单）
- cited_n=28 sample_n=33 confidence=ok platforms=['doubao']
- 结论：list 是豆包引用页面中最常见的格式：33 个已解析被引样本中 28 个（约 85%）含列表结构，去重后 26 个唯一页面中 22 个为 list。｜行动：在目标内容中优先使用结构化列表（要点式规格、步骤、优缺点清单），并保持列表可被静态渲染直接读取。
### definition（定义段）
- cited_n=13 sample_n=33 confidence=ok platforms=['doubao']
- 结论：definition 格式被引频率中等：33 个样本中 13 个，去重后 26 个唯一页面中 11 个。｜行动：在页面开头提供简洁定义段（术语/品类一句话解释），覆盖 definition 类查询场景。
### spec_card（规格卡）
- cited_n=23 sample_n=33 confidence=ok platforms=['doubao']
- 结论：spec_card 为第二大被引格式：33 个样本中 23 个（约 70%）为规格卡片式内容，去重后 26 个唯一页面中 19 个。｜行动：为产品与品类页建立规格卡片模块（容量、功率、价格区间等字段化呈现），与 list 格式叠加使用。

## 2. 被引来源特征
```json
{
  "domain_type": {
    "other": 32,
    "news_review": 1
  },
  "page_type": {
    "product": 6,
    "other": 8,
    "news": 3,
    "comparison": 8,
    "blog": 8
  },
  "schema": {
    "": 10,
    "LocalBusiness": 3,
    "ElectricalContractor": 2,
    "RoofingContractor": 2,
    "Article": 1,
    "BreadcrumbList": 6,
    "BlogPosting": 2,
    "WebSite": 1,
    "Organization": 2,
    "FAQPage": 2,
    "ItemList": 1,
    "Product": 1,
    "Dataset": 1,
    "NewsArticle": 1
  },
  "has_publish_date": 7,
  "ugc": 0,
  "resolved": 33,
  "unique_n": 26,
  "schema_unique": {
    "": 8,
    "LocalBusiness": 2,
    "ElectricalContractor": 1,
    "RoofingContractor": 1,
    "Article": 1,
    "BreadcrumbList": 6,
    "BlogPosting": 2,
    "WebSite": 1,
    "Organization": 2,
    "FAQPage": 2,
    "ItemList": 1,
    "Product": 1,
    "Dataset": 1,
    "NewsArticle": 1
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
    "Article": [
      "doubao"
    ],
    "BreadcrumbList": [
      "doubao"
    ],
    "BlogPosting": [
      "doubao"
    ],
    "WebSite": [
      "doubao"
    ],
    "Organization": [
      "doubao"
    ],
    "FAQPage": [
      "doubao"
    ],
    "ItemList": [
      "doubao"
    ],
    "Product": [
      "doubao"
    ],
    "Dataset": [
      "doubao"
    ],
    "NewsArticle": [
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
- 上期发布: glossary(2026-09-05); self-consumption(2026-08-18); solar-only-vs-solar-plus-battery-storage(2026-08-28); solar-only-vs-solar-plus-battery(2026-09-01)
- mention_rate: 0.133 → 前期 0.133(Δ+0.0)
- citation_rate: 0.022333333333333334 → 前期 0.022333333333333334(Δ+0.0)
- sov: 0.043333333333333335 → 前期 0.042(Δ+0.0)
- self_geo: 41.2 → 前期 41.1(Δ+0.1)
- self_seo: 49.7 → 前期 50.2(Δ-0.5)
- 规则版本: —
- ⚠️ 收录有延迟、单周样本小;对照为观察性相关,非因果归因。
