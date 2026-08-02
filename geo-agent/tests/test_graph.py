from unittest.mock import patch
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
