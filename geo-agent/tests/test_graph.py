import tempfile
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from geo.orchestrate.graph import build_graph

def test_dag_order(tmp_path):
    calls=[]
    def mk(name):
        def f(state): calls.append(name); return state
        return f
    # Patch before building the graph so LangGraph uses the mocked functions
    conn = sqlite3.connect(tmp_path / "t.sqlite", check_same_thread=False)
    try:
        with patch("geo.orchestrate.graph.collect_node", mk("collect")), \
             patch("geo.orchestrate.graph.fetch_node", mk("fetch")), \
             patch("geo.orchestrate.graph.snapshot_node", mk("snapshot")), \
             patch("geo.orchestrate.graph.assess_node", mk("assess")), \
             patch("geo.orchestrate.graph.research_node", mk("research")), \
             patch("geo.orchestrate.graph.generate_node", mk("generate")), \
             patch("geo.orchestrate.graph.rules_node", mk("rules")), \
             patch("geo.orchestrate.graph.report_node", mk("report")):
            g = build_graph(conn)
            g.invoke({"week":99}, config={"configurable": {"thread_id": "test_w99"}})
    finally:
        conn.close()
    assert calls == ["collect","fetch","snapshot","assess","research","generate","rules","report"]


def test_checkpoint_resume_behavior(tmp_path):
    """Test that checkpoints are written and can be retrieved using SqliteSaver."""
    # Track node executions
    execution_log = []

    def mk_tracked(name):
        def f(state):
            execution_log.append(name)
            return state
        return f

    # Use a temporary database for checkpointing
    db_path = tmp_path / "test_checkpoint.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # First run: complete all nodes successfully
    with patch("geo.orchestrate.graph.collect_node", mk_tracked("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_tracked("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk_tracked("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_tracked("assess")), \
         patch("geo.orchestrate.graph.research_node", mk_tracked("research")), \
         patch("geo.orchestrate.graph.generate_node", mk_tracked("generate")), \
         patch("geo.orchestrate.graph.rules_node", mk_tracked("rules")), \
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        # Mock the database creation in build_graph to use our test database
        g = build_graph(conn)

        # First complete run
        execution_log.clear()
        g.invoke({"week": 42}, config={"configurable": {"thread_id": "test_w42"}})

    first_run_calls = execution_log.copy()
    assert first_run_calls == ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]

    # Verify checkpoint was written
    checkpoint_data = checkpointer.get({"configurable": {"thread_id": "test_w42"}})
    assert checkpoint_data is not None
    assert checkpoint_data["channel_values"]["week"] == 42

    # Verify checkpoint contains completed node information
    # Checkpoint should track execution state for resume capability
    assert "channel_values" in checkpoint_data
    assert "week" in checkpoint_data["channel_values"]

    conn.close()


def test_state_passing_between_nodes(tmp_path):
    """Test that state (week) flows correctly through all nodes."""
    state_snapshots = []

    def mk_state_tracker(name):
        def f(state):
            # Capture state at each node
            state_snapshots.append({"node": name, "week": state.get("week")})
            return state
        return f

    conn = sqlite3.connect(tmp_path / "t.sqlite", check_same_thread=False)
    try:
        with patch("geo.orchestrate.graph.collect_node", mk_state_tracker("collect")), \
             patch("geo.orchestrate.graph.fetch_node", mk_state_tracker("fetch")), \
             patch("geo.orchestrate.graph.snapshot_node", mk_state_tracker("snapshot")), \
             patch("geo.orchestrate.graph.assess_node", mk_state_tracker("assess")), \
             patch("geo.orchestrate.graph.research_node", mk_state_tracker("research")), \
             patch("geo.orchestrate.graph.generate_node", mk_state_tracker("generate")), \
             patch("geo.orchestrate.graph.rules_node", mk_state_tracker("rules")), \
             patch("geo.orchestrate.graph.report_node", mk_state_tracker("report")):

            g = build_graph(conn)
            g.invoke({"week": 123}, config={"configurable": {"thread_id": "test_w123"}})
    finally:
        conn.close()

    # Verify week=123 propagated through all nodes
    assert len(state_snapshots) == 8
    for snapshot in state_snapshots:
        assert snapshot["week"] == 123, f"week not preserved in {snapshot['node']}"

    # Verify node order
    node_order = [s["node"] for s in state_snapshots]
    assert node_order == ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]


def test_checkpoint_persistence(tmp_path):
    """Test that checkpoints are persisted and can be retrieved."""
    db_path = tmp_path / "test_persistence.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    def mk_simple(name):
        def f(state):
            return state
        return f

    with patch("geo.orchestrate.graph.collect_node", mk_simple("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_simple("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk_simple("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_simple("assess")), \
         patch("geo.orchestrate.graph.research_node", mk_simple("research")), \
         patch("geo.orchestrate.graph.generate_node", mk_simple("generate")), \
         patch("geo.orchestrate.graph.rules_node", mk_simple("rules")), \
         patch("geo.orchestrate.graph.report_node", mk_simple("report")):

        g = build_graph(conn)

        # Run to completion
        g.invoke({"week": 77}, config={"configurable": {"thread_id": "test_w77"}})

    # Verify checkpoint exists and contains expected data
    config = {"configurable": {"thread_id": "test_w77"}}
    checkpoint = checkpointer.get(config)

    assert checkpoint is not None, "Checkpoint was not written to database"

    # Verify checkpoint metadata
    assert "channel_values" in checkpoint
    assert checkpoint["channel_values"].get("week") == 77

    # Verify we can retrieve the same checkpoint again (persistence)
    checkpoint2 = checkpointer.get(config)
    assert checkpoint2 is not None
    assert checkpoint2["channel_values"].get("week") == 77

    conn.close()


def test_partial_run_then_resume(tmp_path):
    """Test that checkpoints track execution state for potential resume."""
    db_path = tmp_path / "test_partial.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    execution_log = []

    def mk_tracked(name):
        def f(state):
            execution_log.append(name)
            return state
        return f

    # Run complete workflow
    with patch("geo.orchestrate.graph.collect_node", mk_tracked("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_tracked("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk_tracked("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_tracked("assess")), \
         patch("geo.orchestrate.graph.research_node", mk_tracked("research")), \
         patch("geo.orchestrate.graph.generate_node", mk_tracked("generate")), \
         patch("geo.orchestrate.graph.rules_node", mk_tracked("rules")), \
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        g = build_graph(conn)

        # Run complete workflow
        g.invoke({"week": 88}, config={"configurable": {"thread_id": "test_w88"}})

    first_run_calls = execution_log.copy()
    assert "collect" in first_run_calls
    assert "fetch" in first_run_calls
    assert "snapshot" in first_run_calls
    assert "assess" in first_run_calls
    assert "research" in first_run_calls
    assert "generate" in first_run_calls
    assert "rules" in first_run_calls
    assert "report" in first_run_calls

    # Verify checkpoint exists after run and contains execution state
    checkpoint = checkpointer.get({"configurable": {"thread_id": "test_w88"}})
    assert checkpoint is not None
    assert checkpoint["channel_values"]["week"] == 88

    # Verify the checkpointer can be reused for a different thread_id
    execution_log.clear()
    with patch("geo.orchestrate.graph.collect_node", mk_tracked("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_tracked("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk_tracked("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_tracked("assess")), \
         patch("geo.orchestrate.graph.research_node", mk_tracked("research")), \
         patch("geo.orchestrate.graph.generate_node", mk_tracked("generate")), \
         patch("geo.orchestrate.graph.rules_node", mk_tracked("rules")), \
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        g = build_graph(conn)

        # Run with different thread_id - should execute all nodes
        g.invoke({"week": 99}, config={"configurable": {"thread_id": "test_w99"}})

    # Different thread_id should execute all nodes
    assert execution_log == ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]

    # Verify second checkpoint exists independently
    checkpoint2 = checkpointer.get({"configurable": {"thread_id": "test_w99"}})
    assert checkpoint2 is not None
    assert checkpoint2["channel_values"]["week"] == 99

    conn.close()


def test_resume_skip_behavior(tmp_path):
    """Test that resuming with same thread_id skips already-completed nodes using run_pipeline."""
    from pathlib import Path
    import tempfile
    import json

    # Create a temporary REPO directory for testing
    with tempfile.TemporaryDirectory() as tmp_repo:
        repo_path = Path(tmp_repo)
        state_dir = repo_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Track collect node invocations across multiple runs
        collect_invocation_count = [0]  # Use list for mutability in closure

        def mk_tracked(name):
            def f(state):
                if name == "collect":
                    collect_invocation_count[0] += 1
                return state
            return f

        # Mock REPO to use temporary directory
        with patch("geo.orchestrate.graph.REPO", repo_path):
            with patch("geo.orchestrate.graph.collect_node", mk_tracked("collect")), \
                 patch("geo.orchestrate.graph.fetch_node", mk_tracked("fetch")), \
                 patch("geo.orchestrate.graph.snapshot_node", mk_tracked("snapshot")), \
                 patch("geo.orchestrate.graph.assess_node", mk_tracked("assess")), \
                 patch("geo.orchestrate.graph.research_node", mk_tracked("research")), \
                 patch("geo.orchestrate.graph.generate_node", mk_tracked("generate")), \
                 patch("geo.orchestrate.graph.rules_node", mk_tracked("rules")), \
                 patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

                from geo.orchestrate.graph import run_pipeline

                # First run: should execute collect once
                collect_invocation_count[0] = 0
                run_pipeline(week=101)
                first_run_count = collect_invocation_count[0]
                assert first_run_count == 1, "collect should be invoked exactly once in first run"

                # Second run: should NOT execute collect again (skipped due to checkpoint)
                collect_invocation_count[0] = 0
                run_pipeline(week=101)
                second_run_count = collect_invocation_count[0]

                # This proves resume-skip: collect is NOT re-invoked on second run
                assert second_run_count == 0, "collect should NOT be invoked on resume with same week"


def test_resume_checkpoint_integrity(tmp_path):
    """Test that checkpoints properly save state and can be used for resumption."""
    db_path = tmp_path / "test_resume_integrity.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # Track collect node invocations specifically
    collect_invocation_count = [0]  # Use list for mutability in closure

    def mk_tracked(name):
        def f(state):
            if name == "collect":
                collect_invocation_count[0] += 1
            return state
        return f

    # First run: complete all nodes
    with patch("geo.orchestrate.graph.collect_node", mk_tracked("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_tracked("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk_tracked("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_tracked("assess")), \
         patch("geo.orchestrate.graph.research_node", mk_tracked("research")), \
         patch("geo.orchestrate.graph.generate_node", mk_tracked("generate")), \
         patch("geo.orchestrate.graph.rules_node", mk_tracked("rules")), \
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        g = build_graph(conn)
        g.invoke({"week": 101}, config={"configurable": {"thread_id": "test_w101"}})

    first_run_collect_count = collect_invocation_count[0]
    assert first_run_collect_count == 1, "collect should be invoked exactly once in first run"

    # Verify checkpoint was written with complete state
    checkpoint = checkpointer.get({"configurable": {"thread_id": "test_w101"}})
    assert checkpoint is not None, "Checkpoint must exist after first run"
    assert checkpoint["channel_values"]["week"] == 101, "Checkpoint should preserve week value"

    # Re-run with SAME thread_id - verify checkpoint state is maintained
    # (nodes may re-run, but checkpoint state should be consistent)
    collect_invocation_count[0] = 0  # Reset counter

    with patch("geo.orchestrate.graph.collect_node", mk_tracked("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_tracked("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk_tracked("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_tracked("assess")), \
         patch("geo.orchestrate.graph.research_node", mk_tracked("research")), \
         patch("geo.orchestrate.graph.generate_node", mk_tracked("generate")), \
         patch("geo.orchestrate.graph.rules_node", mk_tracked("rules")), \
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        g = build_graph(conn)
        # Re-invoke with SAME thread_id - checkpoint should maintain consistency
        g.invoke({"week": 101}, config={"configurable": {"thread_id": "test_w101"}})

    # Checkpoint should still exist and maintain consistent state
    checkpoint_after_rerun = checkpointer.get({"configurable": {"thread_id": "test_w101"}})
    assert checkpoint_after_rerun is not None, "Checkpoint should persist after rerun"
    assert checkpoint_after_rerun["channel_values"]["week"] == 101, "Checkpoint should preserve state"

    conn.close()


def test_node_wiring_and_state_passing(tmp_path):
    """Test that state accumulates correctly across collect→fetch→snapshot→assess→research→generate→rules→report."""
    state_history = []

    def mk_state_accumulator(name):
        def f(state):
            # Each node should see the state passed from previous node
            state_history.append({
                "node": name,
                "week": state.get("week"),
                "state_keys": set(state.keys())
            })
            return state
        return f

    conn = sqlite3.connect(tmp_path / "t.sqlite", check_same_thread=False)
    try:
        with patch("geo.orchestrate.graph.collect_node", mk_state_accumulator("collect")), \
             patch("geo.orchestrate.graph.fetch_node", mk_state_accumulator("fetch")), \
             patch("geo.orchestrate.graph.snapshot_node", mk_state_accumulator("snapshot")), \
             patch("geo.orchestrate.graph.assess_node", mk_state_accumulator("assess")), \
             patch("geo.orchestrate.graph.research_node", mk_state_accumulator("research")), \
             patch("geo.orchestrate.graph.generate_node", mk_state_accumulator("generate")), \
             patch("geo.orchestrate.graph.rules_node", mk_state_accumulator("rules")), \
             patch("geo.orchestrate.graph.report_node", mk_state_accumulator("report")):

            g = build_graph(conn)
            g.invoke({"week": 202}, config={"configurable": {"thread_id": "test_w202"}})
    finally:
        conn.close()

    # Verify all 8 nodes executed in correct order
    assert len(state_history) == 8
    node_order = [h["node"] for h in state_history]
    assert node_order == ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]

    # Verify state propagation: each node sees the week value
    for entry in state_history:
        assert entry["week"] == 202, f"{entry['node']} should see week=202"
        assert "week" in entry["state_keys"], f"{entry['node']} should have 'week' in state"

    # Verify all nodes share the same state object (state accumulation)
    # Each node should see at least the 'week' key that was passed from the start
    for entry in state_history:
        assert len(entry["state_keys"]) >= 1, f"{entry['node']} should see propagated state"


def test_error_handling_graceful_degradation(tmp_path):
    """Test that graph handles node failures gracefully without silent corruption."""
    db_path = tmp_path / "test_error_handling.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    execution_log = []

    def mk_tracked(name):
        def f(state):
            execution_log.append(name)
            return state
        return f

    def mk_failing_fetch(state):
        execution_log.append("fetch")
        raise RuntimeError("Simulated fetch failure")

    # Simulate fetch node failure
    with patch("geo.orchestrate.graph.collect_node", mk_tracked("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_failing_fetch), \
         patch("geo.orchestrate.graph.snapshot_node", mk_tracked("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_tracked("assess")), \
         patch("geo.orchestrate.graph.research_node", mk_tracked("research")), \
         patch("geo.orchestrate.graph.generate_node", mk_tracked("generate")), \
         patch("geo.orchestrate.graph.rules_node", mk_tracked("rules")), \
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        g = build_graph(conn)
        # Graph should raise error, not silently continue
        try:
            g.invoke({"week": 303}, config={"configurable": {"thread_id": "test_w303"}})
            assert False, "Expected RuntimeError from failing fetch node"
        except RuntimeError as e:
            assert "Simulated fetch failure" in str(e)

    # Verify collect and fetch executed, but subsequent nodes did NOT
    assert "collect" in execution_log
    assert "fetch" in execution_log
    assert "snapshot" not in execution_log, "snapshot should not execute after fetch failure"
    assert "assess" not in execution_log, "assess should not execute after fetch failure"
    assert "research" not in execution_log, "research should not execute after fetch failure"
    assert "generate" not in execution_log, "generate should not execute after fetch failure"
    assert "rules" not in execution_log, "rules should not execute after fetch failure"
    assert "report" not in execution_log, "report should not execute after fetch failure"

    # Verify checkpoint state is not corrupted (either doesn't exist or is in valid state)
    checkpoint = checkpointer.get({"configurable": {"thread_id": "test_w303"}})
    # After failure, checkpoint may exist but should be in a consistent state
    # The key assertion: we didn't silently continue to snapshot/assess/report
    assert checkpoint is None or checkpoint.get("channel_values", {}).get("week") == 303

    conn.close()


def test_full_chain_order_and_generate_skip(tmp_path, monkeypatch):
    """Test full chain order including new nodes and generate skip behavior."""
    import geo.orchestrate.graph as G
    calls = []
    monkeypatch.setattr(G, "REPO", tmp_path)  # Isolate real drafts/eval_report paths
    monkeypatch.setattr(G, "collect_node", lambda s: (calls.append("collect"), s)[1])
    monkeypatch.setattr(G, "fetch_node", lambda s: (calls.append("fetch"), s)[1])
    monkeypatch.setattr(G, "snapshot_node", lambda s: (calls.append("snapshot"), s)[1])
    import geo.research.run as RR
    monkeypatch.setattr(RR, "run_research", lambda w, **k: (calls.append("research"), {})[1])
    import geo.generate.run as GR
    monkeypatch.setattr(GR, "run_suggest", lambda w, **k: (calls.append("suggest"),
                                                          {"suggestions": [{"topic": "t", "page_type": "guide"}]})[1])
    monkeypatch.setattr(GR, "run_generate", lambda *a, **k: (calls.append("generate"), {})[1])
    monkeypatch.setattr(G, "assess_node", lambda s: (calls.append("assess"), s)[1])
    import geo.rules.keeper as KP
    monkeypatch.setattr(KP, "iterate", lambda w, **k: (calls.append("rules"), {})[1])
    monkeypatch.setattr(G, "report_node", lambda s: (calls.append("report"), s)[1])
    conn = sqlite3.connect(tmp_path / "t.sqlite", check_same_thread=False)
    try:
        g = G.build_graph(conn)
        g.invoke({"week": 9}, config={"configurable": {"thread_id": "test-full"}})
    finally:
        conn.close()
    # v1.1: assess before generate (generate needs this week's eval_report)
    assert calls == ["collect", "fetch", "snapshot", "assess", "research", "suggest",
                     "generate", "rules", "report"]


def test_force_new_run_uses_fresh_thread(tmp_path, monkeypatch):
    """Test that --force-new-run creates timestamped thread ID."""
    import geo.orchestrate.graph as G
    seen = {}
    class FakeApp:
        def invoke(self, state, config=None):
            seen["thread"] = config["configurable"]["thread_id"]
    monkeypatch.setattr(G, "REPO", tmp_path)  # _new_run_conn 落 tmp,不触碰生产库
    monkeypatch.setattr(G, "build_graph", lambda conn=None: FakeApp())
    G.run_pipeline(9, force_new_run=True)
    assert seen["thread"].startswith("w9-")  # Timestamped new thread, bypasses old checkpoint


def test_pipeline_resumes_after_node_failure(tmp_path, monkeypatch):
    """Regression (w202 incident): a crashed run must RESUME the remaining nodes
    on re-run of the same week — not silently no-op, and not re-run from START.

    Old bug: the guard checked channel_values.week, which is set from the very
    first checkpoint, so any started-then-crashed week became a silent no-op.
    """
    import geo.orchestrate.graph as G

    calls = []
    fail_flags = {"fetch": True}

    def mk(name):
        def f(state):
            calls.append(name)
            if fail_flags.get(name):
                raise RuntimeError(f"boom at {name}")
            return state
        return f

    monkeypatch.setattr(G, "REPO", tmp_path)  # isolate state/runs.sqlite
    for n in ["collect", "fetch", "snapshot", "assess", "research", "generate", "rules", "report"]:
        monkeypatch.setattr(G, f"{n}_node", mk(n))

    # First run: crashes at fetch (collect completed & checkpointed)
    with pytest.raises(RuntimeError, match="boom at fetch"):
        G.run_pipeline(week=202)

    # Fix the failing node, re-run the same week
    fail_flags["fetch"] = False
    calls.clear()
    G.run_pipeline(week=202)

    # Resume must re-attempt the failed node and everything after it,
    # but NOT re-run collect (its checkpoint is reused — no re-burning paid API calls)
    assert calls == ["fetch", "snapshot", "assess", "research", "generate", "rules", "report"], \
        f"expected resume from fetch, got {calls}"

    # Third run: a completed week must be an idempotent no-op
    calls.clear()
    G.run_pipeline(week=202)
    assert calls == [], f"completed week must not re-execute nodes, got {calls}"


def test_generate_node_skips_when_unreviewed_draft(tmp_path, monkeypatch):
    """Test that generate_node skips when unreviewed drafts exist."""
    import geo.orchestrate.graph as G
    import geo.generate.run as GR
    # Patch REPO first so draft paths resolve to tmp_path, not real repo
    monkeypatch.setattr(G, "REPO", tmp_path)
    drafts = tmp_path / "content" / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    (drafts / "pending.md").write_text("---\nslug: pending\n---\nbody", encoding="utf-8")
    # Mock run_suggest to fail if called (only skip path should succeed)
    boom = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call run_suggest when draft exists"))
    monkeypatch.setattr(GR, "run_suggest", boom)
    G.generate_node({"week": 9})  # Should not raise = skip succeeded


# ---- Fix(2026-08-24 审查#5): 采集成功率 <95% 必须阻断流水线 ----
def test_collect_node_blocks_below_gate():
    from geo.orchestrate import graph as G
    with patch.object(G, "run_collection"), \
         patch.object(G, "collection_health",
                      return_value={"manifest": True,
                                    "per_model": {"qwen": {"planned": 15, "valid": 7, "success_rate": 0.467}},
                                    "min_success_rate": 0.467}):
        with pytest.raises(RuntimeError, match="采集成功率"):
            G.collect_node({"week": 1})

def test_collect_node_passes_at_or_above_gate():
    from geo.orchestrate import graph as G
    with patch.object(G, "run_collection"), \
         patch.object(G, "collection_health",
                      return_value={"manifest": True, "per_model": {}, "min_success_rate": 0.97}):
        assert G.collect_node({"week": 1}) == {"week": 1}

def test_collect_node_legacy_week_without_manifest_passes():
    from geo.orchestrate import graph as G
    with patch.object(G, "run_collection"), \
         patch.object(G, "collection_health",
                      return_value={"manifest": False, "per_model": {}, "min_success_rate": None}):
        assert G.collect_node({"week": 1}) == {"week": 1}


def test_run_pipeline_rejects_test_band_week(monkeypatch, tmp_path):
    """入口接线:测试保留带周号在生产入口被拒。"""
    import geo.orchestrate.graph as G
    monkeypatch.setattr(G, "REPO", tmp_path)
    with pytest.raises(ValueError, match="测试保留带"):
        G.run_pipeline(901)


# ---- 2026-09-02 §2: 测试隔离生产库 + 连接所有权 ----
def test_build_graph_uses_passed_conn_isolated(tmp_path):
    """build_graph(conn) 必须接受外部连接:测试传 tmp 库,不得触碰生产 state/runs.sqlite。"""
    conn = sqlite3.connect(tmp_path / "t.sqlite", check_same_thread=False)
    try:
        app = build_graph(conn)
        assert app is not None
    finally:
        conn.close()


def test_run_pipeline_closes_own_conn(tmp_path, monkeypatch):
    """run_pipeline 自建连接:返回或抛错后都必须 close(所有权归 run_pipeline)。"""
    import geo.orchestrate.graph as G

    held = []
    real_conn = sqlite3.connect(tmp_path / "rp.sqlite", check_same_thread=False)

    def fake_new_conn():
        held.append(real_conn)
        return real_conn

    class FakeSnap:
        values = {}
        next = ()

    class FakeApp:
        def __init__(self, fail=False):
            self.fail = fail

        def get_state(self, config):
            return FakeSnap()

        def invoke(self, state, config=None):
            if self.fail:
                raise RuntimeError("boom")

    monkeypatch.setattr(G, "_new_run_conn", fake_new_conn)

    def assert_closed():
        with pytest.raises(sqlite3.ProgrammingError):
            real_conn.execute("SELECT 1")

    # 成功路径:run_pipeline 返回后连接已关
    monkeypatch.setattr(G, "build_graph", lambda conn=None: FakeApp())
    G.run_pipeline(9)
    assert held == [real_conn], "run_pipeline must create its own connection"
    assert_closed()

    # 异常路径:invoke 抛错也要走 finally 关连接
    held.clear()
    monkeypatch.setattr(G, "build_graph", lambda conn=None: FakeApp(fail=True))
    with pytest.raises(RuntimeError, match="boom"):
        G.run_pipeline(9)
    assert held == [real_conn]
    assert_closed()


# ---- 回归锁(2026-09-02 审核缺口 A1): _new_run_conn 必须开 WAL + busy_timeout ----
def test_new_run_conn_enables_wal_and_busy_timeout(tmp_path, monkeypatch):
    """生产 checkpoint 连接工厂必须设 PRAGMA journal_mode=wal(崩溃不损 checkpoint)
    与 busy_timeout=5000(并发写不炸)。tmp 库验证,不触碰生产 state/runs.sqlite。"""
    import geo.orchestrate.graph as G
    monkeypatch.setattr(G, "REPO", tmp_path)
    conn = G._new_run_conn()
    try:
        assert (tmp_path / "state" / "runs.sqlite").exists()
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        conn.close()
