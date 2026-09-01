# src/geo/rules/weights.py
"""权重证据强度公式:delta = round(STEP*(S_i - S̄)),夹值 [W_MIN,W_MAX],
最大余数式归一到恰好 100(确定性)。
v1.2 补偿语义:总和校正只动零-delta 维——有证据裁决的维度不被染指;
零-delta 池内有测量强度者优先于无流维;diff<0 弱者让权(强度升序)、diff>0 强者受益(降序);
同分名字 ASCII 兜底。孤立 ±delta 不再被自身吃回(2026-09-01 缺口修复)。"""
from __future__ import annotations

STEP = 3
W_MIN = 5
W_MAX = 35


def compute_deltas(strengths: dict[str, float | None], weights: dict[str, int]) -> dict[str, int]:
    vals = {k: v for k, v in strengths.items() if v is not None and k in weights}
    if not vals:
        return {}
    mean = sum(vals.values()) / len(vals)
    deltas = {k: round(STEP * (v - mean)) for k, v in vals.items()}
    return {k: v for k, v in deltas.items() if v != 0} or {}


def persisted_deltas(strengths: dict[str, float | None],
                     prev_strengths: dict[str, float | None] | None,
                     weights: dict[str, int]) -> dict[str, int]:
    """v1.1:2 周同向持续性——本期与上期 delta 同号才 apply;首周(prev=None)只记录不调权。"""
    if not prev_strengths:
        return {}
    cur = compute_deltas(strengths, weights)
    prev = compute_deltas(prev_strengths, weights)
    return {k: v for k, v in cur.items() if k in prev and (v > 0) == (prev[k] > 0)}


def _clamp(w: int) -> int:
    return max(W_MIN, min(W_MAX, w))


def apply_deltas(weights: dict[str, int], deltas: dict[str, int],
                 strengths: dict[str, float | None] | None = None) -> dict[str, int]:
    raw = {k: weights[k] + deltas.get(k, 0) for k in weights}
    out = {k: _clamp(v) for k, v in raw.items()}
    diff = 100 - sum(out.values())
    if diff:
        measured = {k: v for k, v in (strengths or {}).items()
                    if v is not None and k in weights}
        sign = 1.0 if diff < 0 else -1.0     # 减→强度升序(弱者先让);加→强度降序(强者先得)
        order = sorted(weights, key=lambda k: (deltas.get(k, 0) != 0,      # 零-delta 优先
                                               k not in measured,           # 有流优先于无流
                                               sign * measured.get(k, 0.0),
                                               k))
        step = 1 if diff > 0 else -1
        i = 0
        while diff != 0 and order:
            k = order[i % len(order)]
            if W_MIN <= out[k] + step <= W_MAX:
                out[k] += step
                diff -= step
            i += 1
            if i > 1000:      # 安全阀(理论不可达:总夹值区间 [6*5,6*35] 含 100)
                break
    return out
