from __future__ import annotations
from dataclasses import dataclass
from geo.shared.models import L1Record, PromptRow, CitedSource, L3Source

@dataclass
class ResearchItem:
    l1: L1Record
    prompt: PromptRow
    sources: list[tuple[CitedSource, L3Source | None]]

@dataclass
class Coverage:
    total_l1: int
    total_cited_sources: int
    l3_resolved: int
    l3_missing: int
    l3_js_only: int

@dataclass
class ResearchCorpus:
    week: int
    items: list[ResearchItem]
    gsc_queries: list[str]
    coverage: Coverage

@dataclass
class FeatureBucket:
    key: str
    cited_n: int
    sample_n: int
    platforms: list[str]
    low_confidence: bool

@dataclass
class FeatureAggregates:
    week: int
    coverage: Coverage
    formats: list[FeatureBucket]                 # 对比表/Q&A/清单/定义段/规格卡
    sources: dict                                 # §3.2 distribution: {domain_type:{...}, page_type:{...}, ...}
    platforms: dict                               # per-platform: {model:{mention,citation,sov,...}}
    problem_space: dict                           # {intent_clusters:[...], topic_gaps:[...]}

@dataclass
class PlaybookConclusion:
    id: str
    category: str        # format|source|platform|problem_space
    conclusion: str
    sample_n: int
    cited_n: int | None
    platforms: list[str]
    confidence: str      # high|mid|low
    action: str
    examples: list[str]
    bucket_key: str = ""  # for format conclusions: must match FeatureBucket.key

@dataclass
class FetchStats:
    requested: int
    fetched: int
    failed: int
    js_only: int
