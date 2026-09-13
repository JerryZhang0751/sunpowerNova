# Rules changelog
## geo-seo-v2(语义修正:SOV 方向 + 引用证据口径)— 2026-08-24
- 2026-08-25 二次审查#6 补记: v2 升版当日只改了代码语义与 run.yaml 标签,
  规则文件 version 头漏升(仍 v1)——产生"v2 报告标签、v1 规则文件"的审计
  错位,且 rules/history/ 缺失使 do_recalc(version=geo-seo-v2) FileNotFoundError。
  已补: 两文件 version 头升至 v2(内容不变,语义在代码);v1 文件归档
  rules/history/geo-seo-v1/(manifest 绑 a21794e);config 默认版本对齐;
  一致性由 tests/test_rules_loader.py::test_current_rule_files_match_run_yaml_version 锁死。
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

## geo-seo-v3 — 2026-08-28 (week 2)
- version: geo-seo-v2 → geo-seo-v3(本周评分用 geo-seo-v2,变更自下周生效)
- entry has_breadcrumblist [signal_add→schema]: draft (share=13.0%, unique_n=23, platforms=1)
- entry faq_block_count [signal_remove→citability]: draft (share=13.0%, unique_n=23, platforms=1)
- rollback: python3.11 -m geo.rules.run rollback --to geo-seo-v2
- 观察: SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠
- 观察: 证据口径 = 被检索源唯一 URL(页-周);观察性相关、无未检索对照组
- 观察: 权重调整施加 2 周同向持续性门(v1.1)
- 观察: GEO 权重证据已记录(dimension_strengths),待与上期同向后调整(首周或方向反转)

## geo-seo-v4 — 2026-09-01 (week 3)
- version: geo-seo-v3 → geo-seo-v4(本周评分用 geo-seo-v3,变更自下周生效)
- rollback: python3.11 -m geo.rules.run rollback --to geo-seo-v3
- 观察: SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠
- 观察: 证据口径 = 被检索源唯一 URL(页-周);观察性相关、无未检索对照组
- 观察: 权重调整施加 2 周同向持续性门(v1.1)

## geo-seo-v5 — 2026-09-05 (week 4)
- version: geo-seo-v4 → geo-seo-v5(本周评分用 geo-seo-v4,变更自下周生效)
- weights: citability 25→27, brand 20→19, schema 10→9
- rollback: python3.11 -m geo.rules.run rollback --to geo-seo-v4
- 观察: SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠
- 观察: 证据口径 = 被检索源唯一 URL(页-周);观察性相关、无未检索对照组
- 观察: 权重调整施加 2 周同向持续性门(v1.1)

## geo-seo-v6 — 2026-09-09 (week 5)
- version: geo-seo-v5 → geo-seo-v6(本周评分用 geo-seo-v5,变更自下周生效)
- weights: citability 27→28, brand 19→18
- rollback: python3.11 -m geo.rules.run rollback --to geo-seo-v5
- 观察: SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠
- 观察: 证据口径 = 被检索源唯一 URL(页-周);观察性相关、无未检索对照组
- 观察: 权重调整施加 2 周同向持续性门(v1.1)

## geo-seo-v7 — 2026-09-13 (week 6)
- version: geo-seo-v6 → geo-seo-v7(本周评分用 geo-seo-v6,变更自下周生效)
- weights: citability 28→29, brand 18→17
- rollback: python3.11 -m geo.rules.run rollback --to geo-seo-v6
- 观察: SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠
- 观察: 证据口径 = 被检索源唯一 URL(页-周);观察性相关、无未检索对照组
- 观察: 权重调整施加 2 周同向持续性门(v1.1)
