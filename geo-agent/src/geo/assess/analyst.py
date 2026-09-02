"""Analyst: deterministic evaluation report assembly from L2 records, GEO/SEO scores, and competitive benchmarks."""

from __future__ import annotations
import csv
import json
from dataclasses import dataclass
from geo.shared.config import REPO, settings
from geo.shared.models import L1Record, L2Record, L3Source, CompositeScore
from geo.shared.l1 import iter_l1
from geo.shared.storage import sha1_url, read_run_records, legacy_source_dirs
from geo.assess.geo_scorer import score_geo
from geo.assess.seo_scorer import score_seo
from geo.assess.benchmarker import gap

# 数据质量门(与 collector.COLLECTION_GATE 同值;此处独立常量避免 assess→collect 重依赖)
COLLECTION_GATE = 0.95


@dataclass
class MentionMetrics:
    """Metrics for brand mentions and citations per model.
    sov = 品牌声量份额 brand/(brand+竞品提及), 0–1(2026-08-24 审查#2 修正方向)。"""
    model: str
    planned: int
    valid: int
    mention: int
    cited: int
    position_sum: float | None
    sov: float

    @property
    def mention_rate(self) -> float:
        """Calculate mention rate (mentions / valid responses)."""
        return round(self.mention / self.valid, 3) if self.valid else 0.0

    @property
    def citation_rate(self) -> float:
        """Calculate citation rate (citations with link / valid responses)."""
        return round(self.cited / self.valid, 3) if self.valid else 0.0

    @property
    def avg_position(self) -> float | None:
        """Calculate average citation position (only for citations)."""
        if self.position_sum is not None:
            return round(self.position_sum, 1)
        return None

    @property
    def failed(self) -> int:
        """planned − valid:采集失败数(2026-08-24 审查#5,不得从分母消失)。"""
        return max(0, self.planned - self.valid)

    @property
    def success_rate(self) -> float | None:
        return round(self.valid / self.planned, 3) if self.planned else None


def _load_l3_source(week: int, url: str) -> L3Source | None:
    """Load L3 source by URL for a week (2026-09-02 D1: 周目录+legacy 回退链).

    Walks ``storage.legacy_source_dirs(week, REPO)`` — ``w{week}`` first, plus
    the ``w3`` terminal legacy state for week<3 (w1-w3 的历史评估消费的是迁移前
    共享缓存=迁移后 w3/ 态;黄金锁 43.4 通路). week>=4 reads its own week only —
    a miss is honest absence. meta+text 齐备才算完整(不成对的崩溃残留判 miss,
    由 fetcher 重抓自愈). Must stay aligned with ``geo.fetch.fetcher.fetch_source``
    / ``geo.shared.storage.source_dir``; a mismatch here silently disables GEO
    scoring + benchmarker in production (Critical-1 regression).
    """
    url_hash = sha1_url(url)[:12]
    for base in legacy_source_dirs(week, REPO):
        meta_path = base / url_hash / "meta.json"
        if not (meta_path.exists() and (base / url_hash / "text.md").exists()):
            continue
        try:
            return L3Source(**json.loads(meta_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def _load_static_signals(week: int) -> dict:
    """Load static signals snapshot for a given week."""
    snapshot_path = REPO / "data" / "snapshots" / f"w{week}" / "static_signals.json"
    if snapshot_path.exists():
        try:
            return json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _load_gsc_snapshot(week: int) -> dict:
    """Load GSC snapshot for a given week."""
    gsc_path = REPO / "data" / "snapshots" / f"w{week}" / "gsc.json"
    if gsc_path.exists():
        try:
            return json.loads(gsc_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _sov_share(brand_mentions: int, competitor_mentions: int) -> float:
    """SOV = 品牌声量份额 brand/(brand+竞品提及), 0–1。

    2026-08-24 审查#2 修正: 旧实现是"每回答平均竞品数"且越高分越高——
    竞品越多品牌分反而越高(W1 出现 SOV=3.78 同时 brand 满分)。份额口径
    方向正确: 竞品声量越大 → 份额越低。
    """
    denom = brand_mentions + competitor_mentions
    return round(brand_mentions / denom, 3) if denom else 0.0


def _extract_brand_metrics(l1s: list[L1Record]) -> dict:
    """Extract brand metrics from L1 records for GEO scoring."""
    # Aggregate brand signals across all L1 records
    total = len(l1s)
    if total == 0:
        return {"mention": 0, "cited": 0, "sov": 0.0, "entity_known": False, "on_youtube": False, "on_reddit": False, "on_wikipedia": False, "on_linkedin": False}

    mentioned = sum(1 for l in l1s if l.l2.mentioned)
    cited = sum(1 for l in l1s if l.l2.cited_with_link)
    sov = _sov_share(mentioned, sum(len(l.l2.competitors_mentioned) for l in l1s))

    # Check if brand entity is known (mentioned in any response)
    entity_known = mentioned > 0

    # For platform presence, we'd need external data - using False as P0 proxy
    return {
        "mention": mentioned,
        "cited": cited,
        "sov": round(sov, 3),
        "entity_known": entity_known,
        "on_youtube": False,  # P0 proxy - would need external verification
        "on_reddit": False,
        "on_wikipedia": False,
        "on_linkedin": False
    }


def competitor_domains_by_count(week: int, n: int = 10) -> list[str]:
    """Top-N competitor domains by citation frequency (deterministic: count desc, domain asc).

    Shared by fetch_node (fetches their L3 into data/sources/) and assemble
    (reads it back) so the two agree on exactly which competitors to score.
    Returns bare hostnames (e.g. 'energysage.com').
    """
    from urllib.parse import urlparse
    from collections import Counter
    try:
        site_host = urlparse(settings.targets["site"]["url"]).netloc
    except Exception:
        site_host = ""   # settings 不可用时（如单测 mock）不排除任何域名
    c: Counter = Counter()
    for l in iter_l1(week, REPO):
        for s in l.l2.cited_sources:
            host = urlparse(s.url).netloc
            if host and host != site_host:
                c[host] += 1
    return [d for d, _ in sorted(c.items(), key=lambda x: (-x[1], x[0]))[:n]]

def _score_competitors(week: int, static_signals: dict | None) -> list:
    """竞品 GEO 评分:score_geo 第三参传 {} —— 竞品无全站快照,静态类信号按 0 计(下界 proxy)。
    不得借用目标站 static_signals(含 pages 列表):否则 about_page_present 等站点级
    信号会让全体竞品白拿分(v1.1 修正,外部评审 item 6)。"""
    comp_geos = []
    for comp_domain in competitor_domains_by_count(week, 5):
        comp_url = f"https://{comp_domain}"
        comp_l3 = _load_l3_source(week, comp_url)
        if comp_l3:
            comp_brand_signals = {"mention": 0, "cited": 0, "sov": 0.0, "entity_known": False,
                                  "on_youtube": False, "on_reddit": False,
                                  "on_wikipedia": False, "on_linkedin": False}
            try:
                comp_geos.append(score_geo(comp_l3, comp_brand_signals, {}))
            except (KeyError, TypeError, ValueError):
                continue
    return comp_geos


def assemble(week: int, *, rules_geo=None, rules_seo=None,
             out_name: str = "eval_report.json", rule_version: str | None = None,
             write: bool = True, seo_dims_aggregation: str = "mean") -> dict:
    """
    Assemble deterministic evaluation report from L2 records, GEO/SEO scores, and competitive benchmarks.

    This function is deterministic - same inputs + rule_version → identical report.
    No LLM involvement, pure aggregation of versioned snapshots.

    Args:
        week: Week number to analyze
        rules_geo: Optional GEO rules dict for recalc injection (default: use current version)
        rules_seo: Optional SEO rules dict for recalc injection (default: use current version)
        out_name: Output filename (default: "eval_report.json")
        rule_version: Rule version to tag in report (default: from settings.run.rule_version)
        write: False → 只计算并返回 dict,不写 eval_report.json/source_scores.csv
            (黄金锁等只读重算用;2026-09-02 backlog 守卫补强)
        seo_dims_aggregation: "mean" | "first_page"——SEO 维度跨页聚合口径。
            本任务(2026-09-02)只加参数与校验:两值暂都沿用 first_page 旧逻辑
            (dims=seo_scores[0].dims,默认路径零变化);T11 实现 mean 分支并切默认。

    Returns:
        dict: Evaluation report with metrics, scores, and competitive differentials
    """
    if seo_dims_aggregation not in ("mean", "first_page"):
        raise ValueError(
            f"seo_dims_aggregation 非法: {seo_dims_aggregation!r}(仅接受 'mean' | 'first_page')")
    rule_version = rule_version or settings.run.rule_version
    l1s = list(iter_l1(week, REPO))

    # Group L1 records by model
    by_model = {}
    for l in l1s:
        by_model.setdefault(l.model, []).append(l)

    # planned 分母(2026-08-24 审查#5): runs.jsonl 里唯一 (model,prompt,run) 键数。
    # 无 manifest 的历史周回退 planned=valid(legacy,门不可判定)。
    manifest = read_run_records(week)
    planned_by_model: dict[str, int] = {}
    if manifest:
        for m, _, _ in {(r.model, r.prompt_id, r.run) for r in manifest}:
            planned_by_model[m] = planned_by_model.get(m, 0) + 1

    # Calculate metrics per model(含 manifest 里全败、盘上 0 条 L1 的模型)
    metrics = {}
    for model in list(by_model) + [m for m in planned_by_model if m not in by_model]:
        items = by_model.get(model, [])
        valid = len(items)
        mention = sum(1 for i in items if i.l2.mentioned)
        cited = sum(1 for i in items if i.l2.cited_with_link)

        # Calculate average position (only for citations)
        positions = [i.l2.citation_position for i in items if i.l2.citation_position is not None]
        position_sum = sum(positions) / len(positions) if positions else None

        # SOV = 品牌声量份额(2026-08-24 审查#2:旧"平均竞品数"方向颠倒)
        sov = _sov_share(mention, sum(len(i.l2.competitors_mentioned) for i in items))

        metrics[model] = MentionMetrics(
            model=model,
            planned=planned_by_model.get(model, valid),
            valid=valid,
            mention=mention,
            cited=cited,
            position_sum=position_sum,
            sov=sov
        )

    # Get prompt set version from first L1 record (if available)
    prompt_set_version = l1s[0].prompt_set_version if l1s else ""

    # ===== REAL SCORING INTEGRATION =====
    # Load snapshot data
    static_signals = _load_static_signals(week)
    gsc_snapshot = _load_gsc_snapshot(week)

    # Calculate self-audit GEO score (using brand L3 + static signals)
    self_geo_score = None
    brand_l3 = _load_l3_source(week, static_signals.get("site", "https://sunhestia.com"))
    if brand_l3 and static_signals:
        brand_metrics = _extract_brand_metrics(l1s)
        try:
            self_geo_score = score_geo(brand_l3, brand_metrics, static_signals, rules=rules_geo)
        except (KeyError, TypeError, ValueError):
            # Missing required data for scoring - will remain None
            pass

    # Calculate SEO scores for each page in static_signals
    seo_scores = []
    if static_signals and gsc_snapshot:
        pages = static_signals.get("pages", [])
        for page in pages:
            try:
                page_url = page.get("url")

                # Cross-load L3 (Task 9) for this page so content signals are REAL,
                # not fabricated. title/meta_desc come from the static-signals
                # snapshot (captured by extract_structural at snapshot time, same
                # versioned input → deterministic); L3 supplies word_count (real
                # trafilatura text length) + Kimi semantic E-E-A-T. Where a field
                # is genuinely unavailable in the P0 snapshot, it is marked
                # unknown/degraded (None → scores 0) per the Global Constraint,
                # never given a fabricated concrete value.
                page_l3 = _load_l3_source(week, page_url) if page_url else None
                sem = (page_l3.semantic if page_l3 else {}) or {}
                st_l3 = (page_l3.structural if page_l3 else {}) or {}

                title = page.get("title") or st_l3.get("title") or ""
                meta_desc = page.get("meta_desc") or st_l3.get("meta_desc") or ""

                if page_l3 and page_l3.text:
                    word_count = len(page_l3.text.split())      # real extracted-text length
                else:
                    word_count = None                            # unknown → degraded, NOT fabricated

                content_signals = {
                    "word_count": word_count,
                    "has_author_byline": sem.get("has_author_byline"),            # real (Kimi) or None
                    "has_publish_date": sem.get("has_publish_date"),              # real (Kimi) or None
                    "cites_external_sources": sem.get("cites_external_sources"),  # real (Kimi) or None
                    "content_signals_source": "l3" if page_l3 else "missing",
                    "p0_content_degraded": page_l3 is None or not page_l3.text,
                }

                # Prepare page data for SEO scoring
                page_data = {
                    "url": page_url,
                    "https": page.get("https", False),
                    "http_status": page.get("http_status"),
                    "in_sitemap": page.get("in_sitemap", False),
                    "robots_not_blocked": True,  # P0 proxy
                    "canonical_self": page.get("canonical") == page_url,
                    "has_viewport": page.get("has_viewport", False),
                    "http2": True,  # P0 proxy
                    "renderable_static": True,  # P0 proxy
                    "title": title,               # real extracted <title>
                    "h_counts": page.get("h_counts", {}),
                    "meta_desc": meta_desc,        # real extracted <meta description>
                }

                page_seo = score_seo(page_data, gsc_snapshot, content_signals, rules=rules_seo)
                seo_scores.append(page_seo)
            except (KeyError, TypeError, ValueError):
                # Skip pages that can't be scored
                continue

    # Aggregate SEO scores (average across all pages)
    self_seo_score = None
    if seo_scores:
        avg_total = round(sum(s.total for s in seo_scores) / len(seo_scores), 1)
        # Create aggregated CompositeScore
        from geo.shared.models import DimScore
        self_seo_score = CompositeScore(
            total=avg_total,
            dims=seo_scores[0].dims  # Use first page's dimensions as representative
        )

    # Score competitors — deterministic top-5 by citation count (matches fetch_node)
    comp_geos = _score_competitors(week, static_signals)

    # Calculate competitive gap
    gap_result = None
    if self_geo_score and comp_geos:
        # Aggregate metrics for gap calculation
        gap_metrics = {
            "mention_rate": sum(m.mention_rate for m in metrics.values()) / max(1, len(metrics)),
            "citation_rate": sum(m.citation_rate for m in metrics.values()) / max(1, len(metrics)),
            "avg_position": None,  # Would be computed from cited positions
            "sov": sum(m.sov for m in metrics.values()) / max(1, len(metrics))
        }
        try:
            gap_result = gap(self_geo_score, comp_geos, gap_metrics)
        except (KeyError, TypeError, ValueError):
            # Skip gap calculation if data insufficient
            pass

    # Convert CompositeScores to dicts for JSON serialization
    self_geo_dict = None
    if self_geo_score:
        self_geo_dict = {
            "total": self_geo_score.total,
            "dims": [{"name": d.name, "score": d.score, "weight": d.weight, "signals": d.signals}
                    for d in self_geo_score.dims]
        }

    self_seo_dict = None
    if self_seo_score:
        self_seo_dict = {
            "total": self_seo_score.total,
            "dims": [{"name": d.name, "score": d.score, "weight": d.weight, "signals": d.signals}
                    for d in self_seo_score.dims]
        }

    # 采集质量门:manifest 存在时按各家最低成功率判 ok(2026-08-24 审查#5);
    # legacy(无 manifest)分母不可追溯 → min_success_rate=None,不得虚报 1.0
    rates = [m.success_rate for m in metrics.values() if m.success_rate is not None]
    collection_gate = {
        "manifest": bool(manifest),
        "threshold": COLLECTION_GATE,
        "min_success_rate": (min(rates) if rates else None) if manifest else None,
        "ok": (min(rates) >= COLLECTION_GATE) if (manifest and rates) else True,
    }

    # Build report structure with REAL scores
    report = {
        "week": week,
        "rule_version": rule_version,
        "prompt_set_version": prompt_set_version,
        "metrics": {
            model: {
                "planned": m.planned,
                "valid": m.valid,
                "failed": m.failed,
                "success_rate": m.success_rate,
                "mention_rate": m.mention_rate,
                "citation_rate": m.citation_rate,
                "avg_position": m.avg_position,
                "sov": m.sov
            }
            for model, m in metrics.items()
        },
        "collection_gate": collection_gate,
        "self_geo": self_geo_dict,  # Real GEO score from Task 14
        "self_seo": self_seo_dict,  # Real SEO score from Task 15
        "gap": gap_result,  # Real competitive gap from Task 16
        "authority_gap_note": "权威分基于 P0 代理；外部权威(backlinks/DA)未计入"
    }

    # write=False: 只读重算(黄金锁/对照实验)——不落任何盘,仅返回 dict
    if write:
        # Create output directory
        out = REPO / "data" / "analysis" / f"w{week}"
        out.mkdir(parents=True, exist_ok=True)

        # Write eval_report.json
        (out / out_name).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8"
        )

        # Write source_scores.csv
        with (out / "source_scores.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["model", "prompt_id", "mentioned", "cited", "position", "competitors"])
            for l in l1s:
                w.writerow([
                    l.model,
                    l.prompt_id,
                    int(l.l2.mentioned),
                    int(l.l2.cited_with_link),
                    l.l2.citation_position if l.l2.citation_position else "",
                    ";".join(l.l2.competitors_mentioned)
                ])

    return report