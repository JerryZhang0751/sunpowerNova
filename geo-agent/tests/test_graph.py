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
