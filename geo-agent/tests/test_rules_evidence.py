# tests/test_rules_evidence.py
import json
from pathlib import Path
from geo.rules.evidence import collect_evidence, dimension_strengths, ADD_CANDIDATES, REMOVE_CANDIDATES
FIX = Path(__file__).parent / "fixtures" / "rules"

def setup_module():
    global AGG, EVAL
    AGG = json.loads((FIX / "research_aggregates.json").read_text(encoding="utf-8"))
    EVAL = json.loads((FIX / "eval_report.json").read_text(encoding="utf-8"))

def test_collect_evidence_w1():
    ev = {e["signal"]: e for e in collect_evidence(AGG)}
    bc = ev["has_breadcrumblist"]                       # add 候选(唯一 URL 口径)
    assert bc["kind"] == "signal_add" and bc["with_n"] == 7 and bc["unique_n"] == 34
    assert abs(bc["share"] - 7 / 34) < 0.001
    assert bc["platforms"] == ["doubao", "qwen", "zhipu"]
    qa = ev["faq_block_count"]                          # remove 候选:qa 0/34(唯一)
    assert qa["kind"] == "signal_remove" and qa["with_n"] == 0 and qa["share"] == 0.0

def test_dimension_strengths_w1():
    s = dimension_strengths(AGG, EVAL)
    assert s["citability"] == max(b["unique_cited_n"] / b["unique_n"]      # unique 口径最大格式桶
                                  for b in AGG["formats"] if b.get("unique_n"))
    assert abs(s["schema"] - 7 / 34) < 0.001            # BreadcrumbList 唯一最大
    assert abs(s["brand"] - (0.133 + 0.0887) / 2) < 0.0005
    assert s["eeat"] is None and s["platform"] is None and s["technical_geo"] is None

def test_candidate_maps_static():
    assert ADD_CANDIDATES == {"has_breadcrumblist": "schema.BreadcrumbList"}
    assert REMOVE_CANDIDATES == {"faq_block_count": "qa"}