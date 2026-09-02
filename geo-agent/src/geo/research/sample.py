# src/geo/research/sample.py
from __future__ import annotations
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from geo.shared.config import REPO
from geo.shared.storage import sha1_url
from geo.research.models import ResearchCorpus, FetchStats

def _already_fetched(week: int, url: str, repo: Path) -> bool:
    """只查本周目录,无 legacy 回退(2026-09-02 D1)——research top-N 每周重选重抓,
    上周抓过不代表本周还有效;本周没抓过就是没抓过。"""
    return (repo / "data" / "sources" / f"w{week}" / sha1_url(url)[:12] / "meta.json").exists()

def select_topn(corpus: ResearchCorpus, n: int = 40, brand_host: str = "sunhestia.com",
                repo: Path = REPO, *, week: int) -> list[str]:
    freq = Counter()
    for it in corpus.items:
        for cited, _ in it.sources:
            host = urlparse(cited.url).hostname or ""
            if not host or host.endswith(brand_host):
                continue
            freq[cited.url] += 1
    ranked = [u for u, _ in freq.most_common()]
    return [u for u in ranked[:n] if not _already_fetched(week, u, repo)]

def fetch_topn(urls: list[str], week: int) -> FetchStats:
    from geo.fetch.fetcher import fetch_source
    fetched = failed = js = 0
    for u in urls:
        try:
            rec = fetch_source(u, week=week)
            fetched += 1
            if getattr(rec, "js_only", False): js += 1
        except Exception:
            failed += 1
    return FetchStats(requested=len(urls), fetched=fetched, failed=failed, js_only=js)
