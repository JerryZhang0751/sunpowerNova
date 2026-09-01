# SunHestia GEO Playbook · w3
> rule_version geo-seo-v3 | L1=45 | 被引源分析 sample_n=32(缺失122/js_only3)
> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。

## 1. 被引格式特征
### comparison_table（对比表）
- cited_n=17 sample_n=32 confidence=ok platforms=['doubao']
### qa（Q&A）
- cited_n=5 sample_n=32 confidence=ok platforms=['doubao']
- 结论：对比表（comparison_table）共现中等（32 中 17，unique 25 中 12），定义（definition）32 中 20；而问答（qa）格式显著偏低：32 中仅 5（unique 25 中 3）。纯 Q&A 叙述形态在带引用回答中明显欠代表。｜行动：避免仅以问答段落承载关键信息；将对比内容表格化、定义内容条目化。Q&A 内容可作为补充而非主体。
### list（清单）
- cited_n=30 sample_n=32 confidence=ok platforms=['doubao']
- 结论：在 doubao 平台，被引用回答中列表（list）格式几乎无处不在：32 个样本中 30 个含列表且带引用（unique 25 个中 23 个）。列表是与引用共现最强的格式特征。注意：观测仅覆盖 doubao，且为共现关系而非因果。｜行动：核心落地页（产品对比、决策指南）采用可扫描的分点列表结构，确保关键结论以列表条目形式呈现，便于模型抽取。
### definition（定义段）
- cited_n=20 sample_n=32 confidence=ok platforms=['doubao']
### spec_card（规格卡）
- cited_n=28 sample_n=32 confidence=ok platforms=['doubao']
- 结论：规格卡（spec_card）格式与被引用高度共现：32 个样本中 28 个（unique 25 个中 21 个）出现于带引用的回答，仅次于列表。结构化参数表似乎是 doubao 回答引用来源时的常见载体。｜行动：为每个产品/方案页添加机器可读的规格卡（功率、容量、价格、质保等字段），与列表结构配合使用。

## 2. 被引来源特征
```json
{
  "domain_type": {
    "other": 31,
    "news_review": 1
  },
  "page_type": {
    "blog": 9,
    "other": 7,
    "news": 2,
    "comparison": 11,
    "product": 1,
    "spec": 2
  },
  "schema": {
    "": 9,
    "BreadcrumbList": 11,
    "Organization": 6,
    "FAQPage": 8,
    "BlogPosting": 1,
    "NewsArticle": 2,
    "CollectionPage": 1,
    "Article": 3,
    "WebSite": 2,
    "TechArticle": 4,
    "SoftwareApplication": 2,
    "NewsMediaOrganization": 2,
    "AnalysisArticle": 2
  },
  "has_publish_date": 8,
  "ugc": 0,
  "resolved": 32,
  "unique_n": 25,
  "schema_unique": {
    "": 8,
    "BreadcrumbList": 7,
    "Organization": 4,
    "FAQPage": 5,
    "BlogPosting": 1,
    "NewsArticle": 2,
    "CollectionPage": 1,
    "Article": 2,
    "WebSite": 1,
    "TechArticle": 2,
    "SoftwareApplication": 1,
    "NewsMediaOrganization": 1,
    "AnalysisArticle": 1
  },
  "schema_unique_platforms": {
    "": [
      "doubao"
    ],
    "BreadcrumbList": [
      "doubao"
    ],
    "Organization": [
      "doubao"
    ],
    "FAQPage": [
      "doubao"
    ],
    "BlogPosting": [
      "doubao"
    ],
    "NewsArticle": [
      "doubao"
    ],
    "CollectionPage": [
      "doubao"
    ],
    "Article": [
      "doubao"
    ],
    "WebSite": [
      "doubao"
    ],
    "TechArticle": [
      "doubao"
    ],
    "SoftwareApplication": [
      "doubao"
    ],
    "NewsMediaOrganization": [
      "doubao"
    ],
    "AnalysisArticle": [
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
意图簇：[{'intent': 'brand', 'n': 6}, {'intent': 'product-category', 'n': 9}, {'intent': 'decision', 'n': 9}, {'intent': 'geo', 'n': 3}, {'intent': 'cost', 'n': 6}, {'intent': 'comparison', 'n': 6}, {'intent': 'self-consumption', 'n': 6}]  选题缺口候选：['hestia solar', 'maximise solar self-consumption', 'self consumption', 'self consumption battery', 'self consumption of solar power', 'self consumption solar', 'solar hestia', 'solar self consumption', 'solar self-consumption']

## 5. 可复用内容模板
- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。

## 6. 上期动作→指标对照
- 上期发布: self-consumption(2026-08-18); solar-only-vs-solar-plus-battery-storage(2026-08-28)
- mention_rate: None → 前期 0.133(Δ不可算:某期数据缺失)
- citation_rate: None → 前期 0.08866666666666667(Δ不可算:某期数据缺失)
- sov: None → 前期 0.034999999999999996(Δ不可算:某期数据缺失)
- self_geo: 41.2 → 前期 43.4(Δ-2.2)
- self_seo: 49.9 → 前期 49.8(Δ+0.1)
- 规则版本: —
- ⚠️ 收录有延迟、单周样本小;对照为观察性相关,非因果归因。
