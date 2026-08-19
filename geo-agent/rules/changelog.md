# Rules changelog
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
