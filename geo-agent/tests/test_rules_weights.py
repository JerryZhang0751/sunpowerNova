# tests/test_rules_weights.py
import pytest
from geo.rules.weights import compute_deltas, persisted_deltas, apply_deltas, STEP, W_MIN, W_MAX
from geo.rules.loader import assert_normalized
import types

W = {"citability": 25, "brand": 20, "eeat": 20, "technical_geo": 15, "schema": 10, "platform": 10}
S_W1 = {"citability": 0.657, "schema": 7/34, "brand": (0.133 + 0.0887)/2,
        "eeat": None, "technical_geo": None, "platform": None}

def test_raw_delta_computation():
    d = compute_deltas(S_W1, W)                                # 数学不变(出现口径数值仅参考)
    assert d.get("citability") == 1 and d.get("brand") == -1
    nw = apply_deltas(W, d)
    assert nw == {**W, "citability": 26, "brand": 19}
    assert_normalized(types.SimpleNamespace(composite="geo", weights=nw))   # 和恰 100

def test_first_week_persistence_gate_blocks():
    assert persisted_deltas(S_W1, None, W) == {}               # v1.1:首周无上期 → 不调权

def test_second_week_same_direction_applies():
    prev = {**S_W1, "citability": 0.65, "schema": 0.15, "brand": 0.11}
    d = persisted_deltas(S_W1, prev, W)
    assert d.get("citability") == 1 and d.get("brand") == -1   # 两周同向 → 通过
    assert sum(apply_deltas(W, d).values()) == 100

def test_direction_flip_not_applied():
    prev = {**S_W1, "citability": 0.05, "schema": 0.9, "brand": 0.4}
    d = persisted_deltas(S_W1, prev, W)                        # 上期 citability 向下、本期向上
    assert "citability" not in d and "brand" not in d          # 反向维度被持续性门挡下

def test_all_zero_no_change():
    s = {"citability": 0.5, "schema": 0.5, "brand": 0.5,
         "eeat": None, "technical_geo": None, "platform": None}
    assert compute_deltas(s, W) == {}

def test_no_streams_no_change():
    assert compute_deltas({k: None for k in W}, W) == {}

def test_step_cap_and_clamp():
    extreme = {"citability": 1.0, "schema": 0.0, "brand": 0.0,
               "eeat": None, "technical_geo": None, "platform": None}
    d = compute_deltas(extreme, W)
    assert all(abs(v) <= STEP for v in d.values())             # 步长 ≤3
    nw = apply_deltas(W, d)
    assert all(W_MIN <= v <= W_MAX for v in nw.values())
    assert sum(nw.values()) == 100                              # 归一恒真

def test_clamp_collision_still_sums_100():
    # platform(10) 若被连续压到 5 后再压:clamp 保 5,余量由其他维度消化
    w2 = {"a": 35, "b": 5, "c": 20, "d": 20, "e": 10, "f": 10}
    d = {"a": 3, "b": -3, "c": 0, "d": 0, "e": 0, "f": 0}      # b 5-3=2 <W_MIN → clamp 5
    nw = apply_deltas(w2, d)
    assert nw["b"] == W_MIN and sum(nw.values()) == 100
