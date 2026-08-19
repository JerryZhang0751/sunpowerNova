# tests/test_rules_gate.py
from geo.rules.gate import evaluate, ACTIVATE_UNIQUE_N, ACTIVATE_SHARE

TGT = {"has_breadcrumblist": "schema", "faq_block_count": "citability"}
W1_ADD = {"signal": "has_breadcrumblist", "kind": "signal_add", "bucket": "schema.BreadcrumbList",
          "with_n": 7, "unique_n": 34, "platforms": ["doubao", "qwen", "zhipu"], "share": 0.2059}
W1_RM = {"signal": "faq_block_count", "kind": "signal_remove", "bucket": "formats.qa",
         "with_n": 0, "unique_n": 34, "platforms": [], "share": 0.0}

def test_add_promotes_when_gate_met():
    out = evaluate([W1_ADD], [], 1, TGT)
    d = out[0]
    assert d.status == "active" and d.change == "promoted" and d.target == "schema"
    assert d.evidence["history"][-1]["week"] == 1

def test_add_stays_draft_when_boundary_fails():
    just_under = {**W1_ADD, "with_n": 5, "share": 0.149}             # share 0.149 < 0.15
    d = evaluate([just_under], [], 1, TGT)[0]
    assert d.status == "draft" and d.change == "draft"
    small_n = {**W1_ADD, "unique_n": 29, "with_n": 29}              # unique 29 < 30(share=1)
    d2 = evaluate([small_n], [], 1, TGT)[0]
    assert d2.status == "draft"

def test_add_rejected_needs_two_zero_weeks():
    d1 = evaluate([W1_ADD], [], 1, TGT)[0]                          # 正常转正
    active = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
               "status": "active", "evidence": d1.evidence}]
    zero = {**W1_ADD, "with_n": 0, "share": 0.0, "platforms": []}
    d2 = evaluate([zero], active, 2, TGT)[0]                        # 第 1 周零 → 仍 active
    assert d2.status == "active"
    active2 = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
                "status": "active", "evidence": d2.evidence}]
    d3 = evaluate([zero], active2, 3, TGT)[0]                       # 第 2 周零 → rejected
    assert d3.status == "rejected" and d3.change == "rejected"

def test_retire_needs_two_failing_weeks():
    weak = {**W1_ADD, "with_n": 5, "share": 0.149, "platforms": ["qwen"]}
    d1 = evaluate([weak], [], 1, TGT)[0]                            # draft(不达标)
    entry = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
              "status": "active", "evidence": {"history": [
                  {"week": 0, "with_n": 7, "unique_n": 34, "share": 0.206,
                   "platforms": ["qwen", "zhipu"]}]}}]
    d2 = evaluate([weak], entry, 1, TGT)[0]                         # 跌破第 1 周 → 仍 active
    assert d2.status == "active"
    entry2 = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
               "status": "active", "evidence": d2.evidence}]
    d3 = evaluate([weak], entry2, 2, TGT)[0]                        # 跌破第 2 周 → retired
    assert d3.status == "retired" and d3.change == "retired"

def test_remove_needs_two_negative_weeks():
    d1 = evaluate([W1_RM], [], 1, TGT)[0]                           # 首周 → draft
    assert d1.status == "draft" and d1.kind == "signal_remove"
    d2 = evaluate([W1_RM], [{"signal": "faq_block_count", "type": "signal_remove",
                             "target": "citability", "status": "draft",
                             "evidence": d1.evidence}], 2, TGT)[0]  # 次周 → active(移除生效)
    assert d2.status == "active" and d2.change == "promoted"

def test_existing_without_candidate_kept_unchanged():
    orphan = [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
               "status": "draft", "evidence": {"history": []}}]
    out = evaluate([], orphan, 5, TGT)                              # 本周无候选(数据缺失)
    assert out[0].change == "unchanged" and out[0].status == "draft"

def test_same_week_rerun_idempotent():
    d1 = evaluate([W1_ADD], [], 1, TGT)[0]
    d1b = evaluate([W1_ADD], [{"signal": "has_breadcrumblist", "type": "signal_add",
                               "target": "schema", "status": "active",
                               "evidence": d1.evidence}], 1, TGT)[0]
    assert len(d1b.evidence["history"]) == 1 and d1b.change == "unchanged"
