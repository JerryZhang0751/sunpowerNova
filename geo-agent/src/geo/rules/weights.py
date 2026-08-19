# src/geo/rules/weights.py
"""权重证据强度公式:delta = round(STEP*(S_i - S̄)),夹值 [W_MIN,W_MAX],
最大余数式归一到恰好 100(确定性:按 |原始delta| 降序、同名 ASCII 升序消化余量)。
v1.1:persisted_deltas 施加 2 周同向持续性——观察性证据无对照基线,单周方向不作数。"""
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


def apply_deltas(weights: dict[str, int], deltas: dict[str, int]) -> dict[str, int]:
    raw = {k: weights[k] + deltas.get(k, 0) for k in weights}
    out = {k: _clamp(v) for k, v in raw.items()}
    diff = 100 - sum(out.values())
    if diff:
        # 按 |原始 delta| 降序、名升序逐维度 ±1,直到和恰 100(跳过已到边界的维度)
        order = sorted(out, key=lambda k: (-abs(deltas.get(k, 0)), k))
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
