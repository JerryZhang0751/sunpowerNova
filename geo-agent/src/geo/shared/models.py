from __future__ import annotations
import hashlib
from pydantic import BaseModel, Field

class PromptRow(BaseModel):
    id: str; category: str; prompt: str; market: str; intent: str
    core: bool

class CitedSource(BaseModel):
    position: int | None = None
    url: str
    title: str = ""
    snippet: str = ""
    extract_method: str = "structured"   # structured | inferred

class L2Record(BaseModel):
    cited_sources: list[CitedSource]
    mentioned: bool = False
    cited_with_link: bool = False
    citation_position: int | None = None
    sentiment: str | None = None         # pos | neu | neg | None
    competitors_mentioned: list[str] = Field(default_factory=list)
    low_confidence: bool = False

class L1Record(BaseModel):
    week: int; model: str; prompt_id: str; run: int
    answer: str
    l2: L2Record
    usage: dict = Field(default_factory=dict)
    elapsed_s: float = 0.0
    search_triggered: bool = False
    ts_iso: str
    prompt_set_version: str

class L3Source(BaseModel):
    url: str; sha1: str; http_status: int | None = None
    text: str = ""
    structural: dict = Field(default_factory=dict)   # bs4 可解析：H/表/schema/canonical…
    semantic: dict = Field(default_factory=dict)     # Kimi 推断：页面类型/定义段/E-E-A-T文内…
    js_only: bool = False
    fetched_iso: str = ""

class RunRecord(BaseModel):
    week: int; model: str; prompt_id: str; run: int
    prompt_set_version: str
    rule_snapshot_version: str
    status: str
    l1_path: str

class DimScore(BaseModel):
    name: str; score: float; weight: float; signals: dict
class CompositeScore(BaseModel):
    total: float; dims: list[DimScore]

def prompt_set_version(rows: list[PromptRow]) -> str:
    blob = "\n".join(r.prompt for r in sorted(rows, key=lambda x: x.id)).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:12]

def dedup_key(l1: L1Record) -> tuple:
    return (l1.week, l1.model, l1.prompt_id, l1.run)
