# src/geo/rules/gate.py
"""条目门槛状态机:纯确定性。阈值常数集中于此,可调。"""
from __future__ import annotations
from dataclasses import dataclass

ACTIVATE_UNIQUE_N = 30   # 唯一 URL(页-周)口径;每周抽样 top-N≈30–50(v1.1,原出现口径 100 已弃)
ACTIVATE_SHARE = 0.15
ACTIVATE_PLATFORMS = 2
REJECT_WEEKS = 2      # 连续负证据周数(add→rejected / remove→active)
RETIRE_WEEKS = 2      # 现役 add 条目连续跌破门槛周数 → retired


@dataclass
class EntryDecision:
    signal: str
    kind: str            # signal_add | signal_remove
    target: str
    status: str          # draft | active | rejected | retired
    change: str          # promoted | rejected | retired | draft | stays_draft | unchanged
    evidence: dict       # {bucket, history: [...], weeks, share, unique_n, platforms}


def _meets(h: dict) -> bool:
    return (h["unique_n"] >= ACTIVATE_UNIQUE_N
            and h["share"] >= ACTIVATE_SHARE
            and len(h.get("platforms", [])) >= ACTIVATE_PLATFORMS)


def _negative(h: dict) -> bool:
    return h["share"] == 0 and h["unique_n"] >= ACTIVATE_UNIQUE_N


def evaluate(candidates: list[dict], existing: list[dict], week: int,
             signal_target: dict[str, str]) -> list[EntryDecision]:
    by_signal = {e["signal"]: e for e in existing}
    out: list[EntryDecision] = []
    for cand in candidates:
        sig, kind = cand["signal"], cand["kind"]
        target = signal_target[sig]
        prev = by_signal.get(sig) or {}
        prev_status = prev.get("status", "new")
        hist = [h for h in (prev.get("evidence", {}) or {}).get("history", [])
                if h.get("week") != week]                       # 同周重跑幂等
        cur = {"week": week, "with_n": cand["with_n"], "unique_n": cand["unique_n"],
               "share": cand["share"], "platforms": list(cand["platforms"])}
        hist.append(cur)
        ev = {"bucket": cand["bucket"], "history": hist,
              "weeks": [h["week"] for h in hist],
              "share": cur["share"], "unique_n": cur["unique_n"],
              "platforms": cur["platforms"]}
        tail = hist[-REJECT_WEEKS:]

        if kind == "signal_add" and prev_status == "active":
            if _meets(cur):
                out.append(EntryDecision(sig, kind, target, "active", "unchanged", ev))
                continue
            # Check for negative evidence → rejected
            if len(tail) >= REJECT_WEEKS and all(_negative(h) for h in tail):
                out.append(EntryDecision(sig, kind, target, "rejected", "rejected", ev))
                continue
            # Check for retirement (weak but not completely negative)
            ftail = hist[-RETIRE_WEEKS:]
            if len(ftail) >= RETIRE_WEEKS and all(not _meets(h) for h in ftail):
                out.append(EntryDecision(sig, kind, target, "retired", "retired", ev))
                continue
            # Active stays active until rejection/retirement
            out.append(EntryDecision(sig, kind, target, "active", "unchanged", ev))
            continue

        if kind == "signal_remove":
            if len(tail) >= REJECT_WEEKS and all(_negative(h) for h in tail):
                ch = "unchanged" if prev_status == "active" else "promoted"
                out.append(EntryDecision(sig, kind, target, "active", ch, ev))
            else:
                ch = "stays_draft" if prev_status == "draft" else "draft"
                out.append(EntryDecision(sig, kind, target, "draft", ch, ev))
            continue

        if len(tail) >= REJECT_WEEKS and all(_negative(h) for h in tail):
            out.append(EntryDecision(sig, kind, target, "rejected", "rejected", ev))
            continue
        if _meets(cur):
            ch = "unchanged" if prev_status == "active" else "promoted"
            out.append(EntryDecision(sig, kind, target, "active", ch, ev))
            continue
        ch = "stays_draft" if prev_status == "draft" else "draft"
        out.append(EntryDecision(sig, kind, target, "draft", ch, ev))

    cand_sigs = {c["signal"] for c in candidates}
    for e in existing:                                         # 本周无候选 → 原样保留
        if e["signal"] not in cand_sigs:
            out.append(EntryDecision(e["signal"], e.get("type", "signal_add"),
                                     e.get("target", ""), e.get("status", "draft"),
                                     "unchanged", e.get("evidence", {})))
    return out
