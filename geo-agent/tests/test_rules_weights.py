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

def test_isolated_positive_delta_weakest_zero_delta_dim_absorbs():
    # w3 实例数值:citability 孤立 +1 → brand(测量最弱零-delta 维 0.0777)让 1
    s = {"citability": 0.92, "schema": 0.28, "brand": 0.0777,
         "eeat": None, "technical_geo": None, "platform": None}
    nw = apply_deltas(W, {"citability": 1}, s)
    assert nw == {**W, "citability": 26, "brand": 19}
    assert_normalized(types.SimpleNamespace(composite="geo", weights=nw))

def test_isolated_negative_delta_strongest_zero_delta_dim_gains():
    s = {"citability": 0.05, "schema": 0.9, "brand": 0.3,
         "eeat": None, "technical_geo": None, "platform": None}
    nw = apply_deltas(W, {"citability": -1}, s)
    assert nw["citability"] == 24 and nw["schema"] == 11   # schema(0.9 最强零-delta)受益
    assert sum(nw.values()) == 100

def test_measured_dim_preferred_over_none_stream():
    # 同有无流维 f 在场,测量最弱维 b(0.05)优先让权
    w = {"a": 30, "b": 10, "c": 20, "d": 20, "e": 15, "f": 5}      # sum 100
    s = {"a": 0.9, "b": 0.05, "c": 0.5, "d": 0.4, "e": 0.3}       # f 缺席 = 无流
    nw = apply_deltas(w, {"a": 1}, s)
    assert nw["a"] == 31 and nw["b"] == 9 and nw["f"] == 5

def test_none_stream_last_resort_all_measured_at_boundary():
    # 测量零-delta 维(b 0.1 / c 0.2)全在 W_MIN → 才动无流维(名字序 d 先)
    w = {"a": 30, "b": 5, "c": 5, "d": 25, "e": 30, "f": 5}       # sum 100
    s = {"a": 0.9, "b": 0.1, "c": 0.2}                            # d/e/f 无流
    nw = apply_deltas(w, {"a": 1}, s)
    assert nw["a"] == 31 and nw["b"] == 5 and nw["c"] == 5 and nw["d"] == 24

def test_compensation_skips_boundary_dims():
    # 最弱测量维 b 已在 W_MIN → 跳到次弱 c 承接
    w = {"a": 30, "b": 5, "c": 20, "d": 20, "e": 20, "f": 5}      # sum 100
    s = {"a": 0.9, "b": 0.05, "c": 0.2, "d": 0.4, "e": 0.3}
    nw = apply_deltas(w, {"a": 1}, s)
    assert nw["a"] == 31 and nw["b"] == 5 and nw["c"] == 19

def test_no_strengths_deterministic_name_fallback():
    nw1 = apply_deltas(W, {"citability": 1})
    nw2 = apply_deltas(W, {"citability": 1})
    assert nw1 == nw2 == {**W, "citability": 26, "brand": 19}     # 零-delta 名字序:brand 最先
    assert sum(nw1.values()) == 100
