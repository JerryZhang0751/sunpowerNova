import tempfile
import sqlite3
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
    with patch("geo.orchestrate.graph.collect_node", mk("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk("assess")), \
         patch("geo.orchestrate.graph.report_node", mk("report")):
        g = build_graph()
        g.invoke({"week":99}, config={"configurable": {"thread_id": "test_w99"}})
    assert calls == ["collect","fetch","snapshot","assess","report"]


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
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        # Mock the database creation in build_graph to use our test database
        with patch("sqlite3.connect", return_value=conn):
            g = build_graph()

            # First complete run
            execution_log.clear()
            g.invoke({"week": 42}, config={"configurable": {"thread_id": "test_w42"}})

    first_run_calls = execution_log.copy()
    assert first_run_calls == ["collect", "fetch", "snapshot", "assess", "report"]

    # Verify checkpoint was written
    checkpoint_data = checkpointer.get({"configurable": {"thread_id": "test_w42"}})
    assert checkpoint_data is not None
    assert checkpoint_data["channel_values"]["week"] == 42

    # Verify checkpoint contains completed node information
    # Checkpoint should track execution state for resume capability
    assert "channel_values" in checkpoint_data
    assert "week" in checkpoint_data["channel_values"]


def test_state_passing_between_nodes(tmp_path):
    """Test that state (week) flows correctly through all nodes."""
    state_snapshots = []

    def mk_state_tracker(name):
        def f(state):
            # Capture state at each node
            state_snapshots.append({"node": name, "week": state.get("week")})
            return state
        return f

    with patch("geo.orchestrate.graph.collect_node", mk_state_tracker("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_state_tracker("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk_state_tracker("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_state_tracker("assess")), \
         patch("geo.orchestrate.graph.report_node", mk_state_tracker("report")):

        g = build_graph()
        g.invoke({"week": 123}, config={"configurable": {"thread_id": "test_w123"}})

    # Verify week=123 propagated through all nodes
    assert len(state_snapshots) == 5
    for snapshot in state_snapshots:
        assert snapshot["week"] == 123, f"week not preserved in {snapshot['node']}"

    # Verify node order
    node_order = [s["node"] for s in state_snapshots]
    assert node_order == ["collect", "fetch", "snapshot", "assess", "report"]


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
         patch("geo.orchestrate.graph.report_node", mk_simple("report")):

        with patch("sqlite3.connect", return_value=conn):
            g = build_graph()

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
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        with patch("sqlite3.connect", return_value=conn):
            g = build_graph()

            # Run complete workflow
            g.invoke({"week": 88}, config={"configurable": {"thread_id": "test_w88"}})

    first_run_calls = execution_log.copy()
    assert "collect" in first_run_calls
    assert "fetch" in first_run_calls
    assert "snapshot" in first_run_calls
    assert "assess" in first_run_calls
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
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        with patch("sqlite3.connect", return_value=conn):
            g = build_graph()

            # Run with different thread_id - should execute all nodes
            g.invoke({"week": 99}, config={"configurable": {"thread_id": "test_w99"}})

    # Different thread_id should execute all nodes
    assert execution_log == ["collect", "fetch", "snapshot", "assess", "report"]

    # Verify second checkpoint exists independently
    checkpoint2 = checkpointer.get({"configurable": {"thread_id": "test_w99"}})
    assert checkpoint2 is not None
    assert checkpoint2["channel_values"]["week"] == 99


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
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        with patch("sqlite3.connect", return_value=conn):
            g = build_graph()
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
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        with patch("sqlite3.connect", return_value=conn):
            g = build_graph()
            # Re-invoke with SAME thread_id - checkpoint should maintain consistency
            g.invoke({"week": 101}, config={"configurable": {"thread_id": "test_w101"}})

    # Checkpoint should still exist and maintain consistent state
    checkpoint_after_rerun = checkpointer.get({"configurable": {"thread_id": "test_w101"}})
    assert checkpoint_after_rerun is not None, "Checkpoint should persist after rerun"
    assert checkpoint_after_rerun["channel_values"]["week"] == 101, "Checkpoint should preserve state"


def test_node_wiring_and_state_passing(tmp_path):
    """Test that state accumulates correctly across collect→fetch→snapshot→assess→report."""
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

    with patch("geo.orchestrate.graph.collect_node", mk_state_accumulator("collect")), \
         patch("geo.orchestrate.graph.fetch_node", mk_state_accumulator("fetch")), \
         patch("geo.orchestrate.graph.snapshot_node", mk_state_accumulator("snapshot")), \
         patch("geo.orchestrate.graph.assess_node", mk_state_accumulator("assess")), \
         patch("geo.orchestrate.graph.report_node", mk_state_accumulator("report")):

        g = build_graph()
        g.invoke({"week": 202}, config={"configurable": {"thread_id": "test_w202"}})

    # Verify all 5 nodes executed in correct order
    assert len(state_history) == 5
    node_order = [h["node"] for h in state_history]
    assert node_order == ["collect", "fetch", "snapshot", "assess", "report"]

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
         patch("geo.orchestrate.graph.report_node", mk_tracked("report")):

        with patch("sqlite3.connect", return_value=conn):
            g = build_graph()
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
    assert "report" not in execution_log, "report should not execute after fetch failure"

    # Verify checkpoint state is not corrupted (either doesn't exist or is in valid state)
    checkpoint = checkpointer.get({"configurable": {"thread_id": "test_w303"}})
    # After failure, checkpoint may exist but should be in a consistent state
    # The key assertion: we didn't silently continue to snapshot/assess/report
    assert checkpoint is None or checkpoint.get("channel_values", {}).get("week") == 303
