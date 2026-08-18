# SunHestia GEO Playbook · w1
> rule_version geo-seo-v1 | L1=45 | 被引源分析 sample_n=134(缺失1315/js_only20)
> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。

## 1. 被引格式特征
### comparison_table（对比表）
- cited_n=51 sample_n=134 confidence=ok platforms=['doubao', 'qwen', 'zhipu']
### qa（Q&A）
- cited_n=0 sample_n=134 confidence=ok platforms=[]
### list（清单）
- cited_n=88 sample_n=134 confidence=ok platforms=['doubao', 'qwen', 'zhipu']
### definition（定义段）
- cited_n=52 sample_n=134 confidence=ok platforms=['doubao', 'qwen', 'zhipu']
### spec_card（规格卡）
- cited_n=75 sample_n=134 confidence=ok platforms=['doubao', 'qwen', 'zhipu']

## 2. 被引来源特征
```json
{
  "domain_type": {
    "other": 122,
    "news_review": 9,
    "manufacturer": 3
  },
  "page_type": {
    "spec": 2,
    "other": 48,
    "news": 5,
    "comparison": 51,
    "product": 4,
    "unknown": 7,
    "blog": 17
  },
  "schema": {
    "TechArticle": 4,
    "BreadcrumbList": 26,
    "FAQPage": 11,
    "Organization": 8,
    "": 44,
    "NewsArticle": 2,
    "WebSite": 7,
    "LocalBusiness": 3,
    "Article": 15,
    "BlogPosting": 8,
    "VideoObject": 5
  },
  "has_publish_date": 20,
  "ugc": 0,
  "resolved": 134
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
    "citation_rate": 0.133
  },
  "zhipu": {
    "n": 15,
    "mention_rate": 0.133,
    "citation_rate": 0.133
  }
}
```

## 4. 问题空间与选题
意图簇：[{'intent': 'brand', 'n': 6}, {'intent': 'product-category', 'n': 9}, {'intent': 'decision', 'n': 9}, {'intent': 'geo', 'n': 3}, {'intent': 'cost', 'n': 6}, {'intent': 'comparison', 'n': 6}, {'intent': 'self-consumption', 'n': 6}]  选题缺口候选：['hestia solar', 'photovoltaic self consumption', 'self consumption', 'self consumption solar', 'solar self consumption', 'solar self-consumption']

## 5. 可复用内容模板
- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。
