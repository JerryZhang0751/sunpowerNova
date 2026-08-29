# SunHestia GEO Playbook · w2
> rule_version geo-seo-v2 | L1=45 | 被引源分析 sample_n=29(缺失123/js_only4)
> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。

## 1. 被引格式特征
### comparison_table（对比表）
- cited_n=5 sample_n=29 confidence=ok platforms=['doubao']
- 结论：对比表（comparison_table）引用率很低：29 个样本中仅 5 个（17%）被引用（去重 4/23），即便用户意图中存在 comparison/decision 类查询，对比表也未成为主要引用载体。｜行动：不要仅依赖大对比表承载对比信息；将对比结论拆解为列表化要点（'A 适合 X 场景，B 适合 Y 场景'），对比表仅作辅助。
### qa（Q&A）
- cited_n=4 sample_n=29 confidence=ok platforms=['doubao']
- 结论：问答（qa）格式引用率最低：29 个样本中仅 4 个（14%）被引用（去重 3/23）。FAQ 式内容当前几乎不被 doubao 引用。｜行动：暂缓大规模 FAQ 建设，或将 FAQ 答案改写为定义段+列表的混合形态再观察引用变化。
### list（清单）
- cited_n=25 sample_n=29 confidence=ok platforms=['doubao']
- 结论：列表（list）是 L3 已解析样本中绝对主导的引用格式：29 个样本中 25 个（86%）以列表形式被引用（去重后 19/23）。在 doubao 上，能被引用的答案几乎必然包含结构化列表。｜行动：目标页面的核心内容应改造为清晰的有序/无序列表结构（选购要点、品牌对比项、参数清单），确保列表项自含完整信息可被直接抽取引用。
### definition（定义段）
- cited_n=11 sample_n=29 confidence=ok platforms=['doubao']
- 结论：定义（definition）格式有中等引用表现：29 个样本中 11 个（38%）被引用（去重 8/23），在概念类查询（如 solar self-consumption）中仍有价值。｜行动：为品类核心概念（自发自用、余电上网等）提供一句话定义开头，后接列表展开，覆盖 definition 与 list 双格式。
### spec_card（规格卡）
- cited_n=22 sample_n=29 confidence=ok platforms=['doubao']
- 结论：规格卡（spec_card）是第二强引用格式：29 个样本中 22 个（76%）被引用（去重后 16/23），与 list 高度共现，说明 doubao 偏好'参数表+要点列表'式的结构化商品内容。｜行动：为每个主推产品建立标准化规格卡（功率、效率、价格、质保等字段齐全的表格），并与 list 格式组合呈现。

## 2. 被引来源特征
```json
{
  "domain_type": {
    "other": 27,
    "news_review": 2
  },
  "page_type": {
    "product": 7,
    "other": 11,
    "news": 3,
    "blog": 2,
    "comparison": 4,
    "unknown": 1,
    "spec": 1
  },
  "schema": {
    "Organization": 2,
    "": 8,
    "BreadcrumbList": 3,
    "WebSite": 1,
    "NewsArticle": 3,
    "Article": 1,
    "TechArticle": 1,
    "FAQPage": 1
  },
  "has_publish_date": 2,
  "ugc": 0,
  "resolved": 29,
  "unique_n": 23,
  "schema_unique": {
    "Organization": 2,
    "": 6,
    "BreadcrumbList": 3,
    "WebSite": 1,
    "NewsArticle": 3,
    "Article": 1,
    "TechArticle": 1,
    "FAQPage": 1
  },
  "schema_unique_platforms": {
    "Organization": [
      "doubao"
    ],
    "": [
      "doubao"
    ],
    "BreadcrumbList": [
      "doubao"
    ],
    "WebSite": [
      "doubao"
    ],
    "NewsArticle": [
      "doubao"
    ],
    "Article": [
      "doubao"
    ],
    "TechArticle": [
      "doubao"
    ],
    "FAQPage": [
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
意图簇：[{'intent': 'brand', 'n': 6}, {'intent': 'product-category', 'n': 9}, {'intent': 'decision', 'n': 9}, {'intent': 'geo', 'n': 3}, {'intent': 'cost', 'n': 6}, {'intent': 'comparison', 'n': 6}, {'intent': 'self-consumption', 'n': 6}]  选题缺口候选：['hestia solar', 'maximise solar self-consumption', 'self consumption', 'self consumption of solar power', 'self consumption solar', 'solar hestia', 'solar self-consumption']

## 5. 可复用内容模板
- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。

## 6. 上期动作→指标对照
- 上期发布: self-consumption(2026-08-18)
- mention_rate: 0.133(首期基线,无环比)
- citation_rate: 0.08866666666666667(首期基线,无环比)
- sov: 0.034999999999999996(首期基线,无环比)
- self_geo: 43.4(首期基线,无环比)
- self_seo: 49.8(首期基线,无环比)
- 规则版本: —
- ⚠️ 收录有延迟、单周样本小;对照为观察性相关,非因果归因。
