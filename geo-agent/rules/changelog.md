# Rules changelog
## geo-seo-v2(语义修正:SOV 方向 + 引用证据口径)— 2026-08-24
- 审查#2: brand.sov_share 的输入 SOV 由"每回答平均竞品数"(值域 0–N,越高分
  越高 → 竞品越多品牌分越高,W1 出现 SOV=3.78 且 brand 满分)改为品牌声量份额
  brand/(brand+竞品提及),值域 0–1,方向正确。公式在 analyst._sov_share,
  registry 阈值带 [0,0.2] 不变(份额≥20% 满分)。
- 审查#1(关联): cited_sources 口径收紧为"答案内证据/provider 明证",检索列表
  移入 retrieved_sources;影响 mention/citation 的上游证据质量,不改 checker。
- weights/membership 无变化(v1 延续);报告语义变化 → 版本 bump,W1 归档重算
  (旧值 47.6/49.8 备份于 data/analysis/w1/eval_report.geo-seo-v1-archived.json,
  黄金锁 tests/test_v1_semantics.py 更新为新语义锁)。
- status: active. version geo-seo-v2。

## geo-seo-v1(成员校正)— 2026-08-19
- signals 成员与代码实际计算集对齐(P3 数据驱动化前置):eeat 撤下从未生效的
  about_page_present/author_schema;technical_geo 收敛为实际 4 项;brand/authority
  信号名对齐 checker id;SEO authority 落回实际 4 项(backlinks_est=unknown 恒 0)。
- 语义无操作(撤下的项本就不计分);分数零漂移由 tests/test_v1_semantics.py 黄金锁死(Task 4)。
- status: active. weights 不变(和=100)。version 保持 geo-seo-v1。

## geo-seo-v1 — 2026-08-02
- init: GEO 6-dim + SEO 5-pillar v1 baseline (seeded from geo-audit/seo-audit skills, spec §4.2).
- status: active. weights normalized to 100.
- evidence: baseline seed (no eval data yet).
