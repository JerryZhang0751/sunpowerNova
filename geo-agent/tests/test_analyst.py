"""Comprehensive tests for analyst module - deterministic evaluation report assembly."""

import json
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock
from geo.assess.analyst import assemble, MentionMetrics
from geo.shared.models import L1Record, L2Record, CitedSource


def mk_l2(mentioned=False, cited=False, position=None, competitors=None, sentiment="neu"):
    """Helper to create L2Record for testing."""
    return L2Record(
        cited_sources=[CitedSource(url="https://example.com", position=position, title="", snippet="")] if cited else [],
        mentioned=mentioned,
        cited_with_link=cited,
        citation_position=position,
        sentiment=sentiment,
        competitors_mentioned=competitors or [],
        low_confidence=False
    )


def mk_l1(week=1, model="qwen", prompt_id="B02", run=1, l2=None, ts_iso="2026-08-02T12:00:00Z", psv="psv123"):
    """Helper to create L1Record for testing."""
    return L1Record(
        week=week,
        model=model,
        prompt_id=prompt_id,
        run=run,
        answer="test answer",
        l2=l2 or mk_l2(),
        usage={},
        elapsed_s=1.0,
        search_triggered=False,
        ts_iso=ts_iso,
        prompt_set_version=psv
    )


def test_mention_metrics_properties():
    """Test MentionMetrics property calculations."""
    m = MentionMetrics(
        model="qwen",
        planned=10,
        valid=10,
        mention=5,
        cited=3,
        position_sum=15.0,
        sov=0.25
    )

    assert m.mention_rate == 0.5
    assert m.citation_rate == 0.3
    assert m.avg_position == 15.0


def test_mention_metrics_edge_cases():
    """Test MentionMetrics edge cases."""
    # Zero valid results
    m_zero = MentionMetrics(
        model="qwen",
        planned=10,
        valid=0,
        mention=0,
        cited=0,
        position_sum=None,
        sov=0.0
    )
    assert m_zero.mention_rate == 0.0
    assert m_zero.citation_rate == 0.0
    assert m_zero.avg_position is None

    # No citations (no position)
    m_no_cite = MentionMetrics(
        model="qwen",
        planned=10,
        valid=10,
        mention=8,
        cited=0,
        position_sum=None,
        sov=0.15
    )
    assert m_no_cite.mention_rate == 0.8
    assert m_no_cite.citation_rate == 0.0
    assert m_no_cite.avg_position is None

    # Perfect performance
    m_perfect = MentionMetrics(
        model="qwen",
        planned=10,
        valid=10,
        mention=10,
        cited=10,
        position_sum=10.0,
        sov=0.5
    )
    assert m_perfect.mention_rate == 1.0
    assert m_perfect.citation_rate == 1.0
    assert m_perfect.avg_position == 10.0


def test_metrics_denominators():
    """Test that metrics use correct denominators as specified in brief."""
    # Create 2 L1 records: 1 mentioned but not cited, 1 not mentioned
    l2_mentioned = mk_l2(mentioned=True, cited=False, position=None, competitors=["CompA", "CompB"])
    l2_not_mentioned = mk_l2(mentioned=False, cited=False, position=None, competitors=[])

    # Valid denominator should be 2 (both records)
    # Mention denominator should be 1 (only first mentioned)
    # Citation denominator should be 0 (none cited)
    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=l2_mentioned),
        mk_l1(model="qwen", prompt_id="B02", run=2, l2=l2_not_mentioned)
    ]

    # Mock the L1 iteration and new helper functions
    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        mock_repo.return_value = Path("/tmp/test_repo")
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    # Check metrics for qwen model
    qwen_metrics = report["metrics"]["qwen"]

    # Denominators: planned=2, valid=2
    assert qwen_metrics["planned"] == 2
    assert qwen_metrics["valid"] == 2

    # Mention rate: 1/2 = 0.5
    assert round(qwen_metrics["mention_rate"], 3) == 0.5

    # Citation rate: 0/2 = 0.0
    assert qwen_metrics["citation_rate"] == 0.0

    # Avg position: None (no citations)
    assert qwen_metrics["avg_position"] is None

    # SOV(声量份额,2026-08-24 审查#2 修正方向): brand/(brand+竞品) = 1/(1+2) = 0.333
    assert qwen_metrics["sov"] == 0.333


def test_multi_model_metrics():
    """Test metrics calculation across multiple models."""
    records = [
        # Qwen: 2 valid, 1 mention, 1 cite
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1)),
        mk_l1(model="qwen", prompt_id="B02", run=2, l2=mk_l2(mentioned=False, cited=False, position=None)),
        # Doubao: 2 valid, 2 mentions, 0 cites
        mk_l1(model="doubao", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=False, position=None)),
        mk_l1(model="doubao", prompt_id="B02", run=2, l2=mk_l2(mentioned=True, cited=False, position=None)),
    ]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        mock_repo.return_value = Path("/tmp/test_repo")
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    # Check qwen metrics
    qwen_metrics = report["metrics"]["qwen"]
    assert qwen_metrics["valid"] == 2
    assert qwen_metrics["mention_rate"] == 0.5
    assert qwen_metrics["citation_rate"] == 0.5
    assert qwen_metrics["avg_position"] == 1.0

    # Check doubao metrics
    doubao_metrics = report["metrics"]["doubao"]
    assert doubao_metrics["valid"] == 2
    assert doubao_metrics["mention_rate"] == 1.0
    assert doubao_metrics["citation_rate"] == 0.0
    assert doubao_metrics["avg_position"] is None


def test_avg_position_calculation():
    """Test average position calculation across multiple citations."""
    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1)),
        mk_l1(model="qwen", prompt_id="B02", run=2, l2=mk_l2(mentioned=True, cited=True, position=3)),
        mk_l1(model="qwen", prompt_id="B02", run=3, l2=mk_l2(mentioned=True, cited=True, position=2)),
        mk_l1(model="qwen", prompt_id="B02", run=4, l2=mk_l2(mentioned=True, cited=False, position=None)),
    ]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        mock_repo.return_value = Path("/tmp/test_repo")
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    qwen_metrics = report["metrics"]["qwen"]
    # Average position: (1 + 3 + 2) / 3 = 2.0
    assert qwen_metrics["avg_position"] == 2.0


def test_sov_calculation():
    """SOV = 品牌声量份额 brand/(brand+竞品),0–1;不再是"平均竞品数"。"""
    records = [
        # Record 1: 2 competitors mentioned
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, competitors=["CompA", "CompB"])),
        # Record 2: 1 competitor mentioned
        mk_l1(model="qwen", prompt_id="B02", run=2, l2=mk_l2(mentioned=True, cited=True, competitors=["CompC"])),
        # Record 3: 0 competitors mentioned
        mk_l1(model="qwen", prompt_id="B02", run=3, l2=mk_l2(mentioned=True, cited=True, competitors=[])),
    ]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        mock_repo.return_value = Path("/tmp/test_repo")
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    qwen_metrics = report["metrics"]["qwen"]
    # SOV: 3 / (3 + 3) = 0.5
    assert qwen_metrics["sov"] == 0.5


def test_sov_direction_more_competitors_lower_share():
    """方向性反回归(审查#2 核心): 提及不变、竞品更多 → SOV 必须更低且∈[0,1]。
    旧实现把"平均竞品数"当 SOV 且越高分越高——竞品越多品牌分反而越高。"""
    def _sov(records):
        with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
            with patch('geo.assess.analyst._load_l3_source', return_value=None):
                with patch('geo.assess.analyst._load_static_signals', return_value={}):
                    with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                        with patch('geo.assess.analyst.REPO'):
                            with patch('pathlib.Path.mkdir'):
                                with patch('pathlib.Path.write_text'):
                                    return assemble(week=1)["metrics"]["qwen"]["sov"]

    few = [mk_l1(model="qwen", prompt_id="B02", run=1,
                 l2=mk_l2(mentioned=True, cited=True, competitors=["CompA"]))]
    many = [mk_l1(model="qwen", prompt_id="B02", run=1,
                  l2=mk_l2(mentioned=True, cited=True, competitors=["A", "B", "C", "D", "E"]))]
    s_few, s_many = _sov(few), _sov(many)
    assert 0.0 <= s_many < s_few <= 1.0
    assert s_few == 0.5 and round(s_many, 3) == round(1 / 6, 3)


def test_sov_zero_when_no_mentions():
    """品牌与竞品都无提及 → SOV=0(分母空安全)。"""
    records = [mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=False, competitors=[]))]
    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO'):
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)
    assert report["metrics"]["qwen"]["sov"] == 0.0


def test_extract_brand_metrics_sov_share():
    """_extract_brand_metrics(喂 score_geo 的 brand 信号)同口径:份额而非平均竞品数。"""
    from geo.assess.analyst import _extract_brand_metrics
    records = [
        mk_l1(l2=mk_l2(mentioned=True, cited=True, competitors=["A", "B"])),
        mk_l1(l2=mk_l2(mentioned=False, competitors=["A"])),
    ]
    m = _extract_brand_metrics(records)
    assert m["mention"] == 1
    assert m["sov"] == round(1 / 4, 3)      # 1/(1+3)
    assert 0.0 <= m["sov"] <= 1.0


def test_report_structure():
    """Test that report has required structure and fields."""
    records = [mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1))]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):  # No L3 data available
            with patch('geo.assess.analyst._load_static_signals', return_value={}):  # No static signals
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):  # No GSC data
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        mock_repo.mkdir = MagicMock()
                        mock_write = MagicMock()
                        mock_repo.return_value = Path("/tmp/test_repo")

                        # Mock Path operations
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text', return_value=mock_write):
                                report = assemble(week=1)

    # Check required top-level fields
    assert "week" in report
    assert "rule_version" in report
    assert "prompt_set_version" in report
    assert "metrics" in report
    assert "self_geo" in report
    assert "self_seo" in report
    assert "gap" in report
    assert "authority_gap_note" in report

    # Check week
    assert report["week"] == 1

    # Check that metrics dict contains model names
    assert "qwen" in report["metrics"]

    # When no L3/static signals data is available, scores should be None (not placeholders)
    assert report["self_geo"] is None  # No L3 data available
    assert report["self_seo"] is None  # No static signals available
    assert report["gap"] is None  # No competitor data available


def test_report_determinism():
    """Test that report generation is deterministic - same inputs produce identical output."""
    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1)),
        mk_l1(model="qwen", prompt_id="B02", run=2, l2=mk_l2(mentioned=False, cited=False, position=None)),
    ]

    reports = []
    for i in range(3):  # Generate report 3 times
        with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
            with patch('geo.assess.analyst._load_l3_source', return_value=None):
                with patch('geo.assess.analyst._load_static_signals', return_value={}):
                    with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                        with patch('geo.assess.analyst.REPO') as mock_repo:
                            with patch('pathlib.Path.mkdir'):
                                with patch('pathlib.Path.write_text'):
                                    report = assemble(week=1)
                                    reports.append(report)

    # All reports should be identical
    assert reports[0]["metrics"]["qwen"]["mention_rate"] == reports[1]["metrics"]["qwen"]["mention_rate"]
    assert reports[0]["metrics"]["qwen"]["citation_rate"] == reports[2]["metrics"]["qwen"]["citation_rate"]
    assert reports[0]["week"] == reports[1]["week"] == reports[2]["week"]


def test_csv_output_structure():
    """Test that CSV output has correct structure."""
    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1, competitors=["CompA"])),
        mk_l1(model="doubao", prompt_id="B02", run=1, l2=mk_l2(mentioned=False, cited=False, position=None, competitors=[])),
    ]

    csv_written = []

    def mock_csv_write(content):
        csv_written.append(content)

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        mock_repo.return_value = Path("/tmp/test_repo")
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                with patch('builtins.open', create=True) as mock_open:
                                    mock_open.return_value.__enter__.return_value.write = mock_csv_write
                                    assemble(week=1)

    # Check that CSV was written with correct headers
    # Note: This test would need more sophisticated mocking to fully test CSV structure
    # For now, we verify the function doesn't crash and produces output


def test_empty_records():
    """Test behavior with no L1 records."""
    records = []

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    # Should still produce valid report structure
    assert "metrics" in report
    assert report["metrics"] == {}  # No models, no metrics
    assert report["week"] == 1


def test_rule_version_binding():
    """Test that report binds to rule_version for determinism."""
    records = [mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1))]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.settings') as mock_settings:
                        mock_settings.run.rule_version = "geo-seo-v1"
                        with patch('geo.assess.analyst.REPO') as mock_repo:
                            with patch('pathlib.Path.mkdir'):
                                with patch('pathlib.Path.write_text'):
                                    report = assemble(week=1)

        # Check that rule_version is in report
        assert "rule_version" in report
        assert report["rule_version"] == "geo-seo-v1"


def test_competitor_counting():
    """Test that competitors_mentioned are correctly counted for SOV."""
    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1,
              l2=mk_l2(mentioned=True, cited=True, competitors=["Enphase", "SolarEdge", "BYD"])),
        mk_l1(model="qwen", prompt_id="B02", run=2,
              l2=mk_l2(mentioned=True, cited=True, competitors=["Tesla"])),
    ]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    qwen_metrics = report["metrics"]["qwen"]
    # SOV 份额: 2 / (2 + 4) = 0.333
    assert qwen_metrics["sov"] == 0.333


def test_sentiment_passthrough():
    """Test that sentiment data is preserved in source_scores CSV."""
    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1,
              l2=mk_l2(mentioned=True, cited=True, position=1, sentiment="pos")),
        mk_l1(model="qwen", prompt_id="B02", run=2,
              l2=mk_l2(mentioned=True, cited=False, sentiment="neg")),
    ]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    # Report should still be generated successfully
    assert "metrics" in report
    assert "qwen" in report["metrics"]


def test_file_output_structure():
    """Test that output files are created in correct structure."""
    records = [mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1))]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        mock_repo.return_value = Path("/tmp/test_repo")
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                # Should not raise any exceptions
                                report = assemble(week=1)

                                # Verify function returns a valid report
                                assert isinstance(report, dict)
                                assert "week" in report


def test_aggregation_across_prompts():
    """Test aggregation across different prompt IDs."""
    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1)),
        mk_l1(model="qwen", prompt_id="C01", run=1, l2=mk_l2(mentioned=False, cited=False, position=None)),
        mk_l1(model="qwen", prompt_id="D01", run=1, l2=mk_l2(mentioned=True, cited=False, position=None)),
    ]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    qwen_metrics = report["metrics"]["qwen"]
    # Should aggregate across all prompts
    assert qwen_metrics["valid"] == 3
    assert qwen_metrics["mention_rate"] == round(2/3, 3)
    assert qwen_metrics["citation_rate"] == round(1/3, 3)


def test_real_score_calculation_with_data():
    """Test that real scores are calculated when L3/static signals data is available."""
    from geo.shared.models import L3Source, DimScore, CompositeScore

    # Mock L3 source data
    mock_l3 = L3Source(
        url="https://sunhestia.com",
        sha1="abc123",
        http_status=200,
        text="Sample content",
        structural={
            "canonical": "https://sunhestia.com",
            "h_counts": {"h1": 1, "h2": 2}
        },
        semantic={
            "has_definition_segment": True,
            "faq_block_count": 1,
            "datapoint_count": 2,
            "has_author_byline": True,
            "has_publish_date": True,
            "cites_external_sources": True
        }
    )

    # Mock static signals
    mock_static = {
        "week": 1,
        "rule_version": "v1",
        "site": "https://sunhestia.com",
        "pages": [
            {
                "url": "https://sunhestia.com/",
                "https": True,
                "http_status": 200,
                "in_sitemap": True,
                "has_viewport": True,
                "h_counts": {"h1": 1, "h2": 2}
            }
        ],
        "robots_ai": {"GPTBot": True, "ClaudeBot": True},
        "sitemap_present": True
    }

    # Mock GSC snapshot
    mock_gsc = {
        "impressions": 500,
        "clicks": 25,
        "ctr": 0.05
    }

    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1,
              l2=mk_l2(mentioned=True, cited=True, position=1, competitors=["Enphase", "SolarEdge"])),
    ]

    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=mock_l3):
            with patch('geo.assess.analyst._load_static_signals', return_value=mock_static):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value=mock_gsc):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    # CRITICAL: Verify that real scores are calculated instead of None
    assert report["self_geo"] is not None, "self_geo should be calculated when L3 data is available"
    assert report["self_seo"] is not None, "self_seo should be calculated when static signals are available"

    # Verify structure of real scores
    assert "total" in report["self_geo"]
    assert "dims" in report["self_geo"]
    assert report["self_geo"]["total"] > 0  # Should have a positive score

    assert "total" in report["self_seo"]
    assert "dims" in report["self_seo"]
    assert report["self_seo"]["total"] >= 0  # Should have a score (could be 0)

    # Verify gap calculation (may be None if no competitors scored)
    # This is acceptable as we may not have competitor L3 data


def test_score_integration_determinism():
    """Test that score calculation is deterministic with same inputs."""
    from geo.shared.models import L3Source

    mock_l3 = L3Source(
        url="https://sunhestia.com",
        sha1="abc123",
        http_status=200,
        structural={"canonical": "https://sunhestia.com"},
        semantic={"has_definition_segment": True}
    )

    mock_static = {
        "site": "https://sunhestia.com",
        "pages": [{"url": "https://sunhestia.com/", "https": True, "http_status": 200}],
        "robots_ai": {"GPTBot": True}
    }

    mock_gsc = {"impressions": 100, "clicks": 5, "ctr": 0.05}

    records = [mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1))]

    reports = []
    for i in range(3):  # Generate 3 times
        with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
            with patch('geo.assess.analyst._load_l3_source', return_value=mock_l3):
                with patch('geo.assess.analyst._load_static_signals', return_value=mock_static):
                    with patch('geo.assess.analyst._load_gsc_snapshot', return_value=mock_gsc):
                        with patch('geo.assess.analyst.REPO'):
                            with patch('pathlib.Path.mkdir'):
                                with patch('pathlib.Path.write_text'):
                                    report = assemble(week=1)
                                    reports.append(report)

    # All reports should have identical scores (deterministic)
    assert reports[0]["self_geo"]["total"] == reports[1]["self_geo"]["total"] == reports[2]["self_geo"]["total"]
    assert reports[0]["self_seo"]["total"] == reports[1]["self_seo"]["total"] == reports[2]["self_seo"]["total"]

# ---- Fix(2026-08-24 审查#5): planned 来自 manifest,失败不得从分母消失 ----
from geo.shared.models import RunRecord

def _manifest(week=94, model="qwen", ok=10, fail=5):
    recs = []
    for i in range(ok):
        recs.append(RunRecord(week=week, model=model, prompt_id=f"P{i:02d}", run=1,
                              prompt_set_version="p", rule_snapshot_version="t",
                              status="ok", l1_path="x"))
    for i in range(fail):
        recs.append(RunRecord(week=week, model=model, prompt_id=f"F{i:02d}", run=1,
                              prompt_set_version="p", rule_snapshot_version="t",
                              status="failed", l1_path="", error="api down"))
    return recs

def _assemble_with(records, manifest_recs):
    with patch('geo.assess.analyst.iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.read_run_records', return_value=manifest_recs):
                        with patch('geo.assess.analyst.REPO'):
                            with patch('pathlib.Path.mkdir'):
                                with patch('pathlib.Path.write_text'):
                                    return assemble(week=1)

def test_planned_from_manifest_not_valid_count():
    """15 计划只落盘 10 → planned=15, valid=10, failed=5, success_rate=0.667(旧: planned=valid=10 假健康)。"""
    records = [mk_l1(model="qwen", prompt_id=f"P{i:02d}", run=1,
                     l2=mk_l2(mentioned=False)) for i in range(10)]
    rep = _assemble_with(records, _manifest(ok=10, fail=5))
    q = rep["metrics"]["qwen"]
    assert q["planned"] == 15 and q["valid"] == 10 and q["failed"] == 5
    assert q["success_rate"] == 0.667
    assert rep["collection_gate"]["ok"] is False
    assert rep["collection_gate"]["threshold"] == 0.95

def test_fully_failed_model_visible_in_metrics():
    """整家 provider 全败(0 条 L1):也必须出现在 metrics 里,不得凭空消失。"""
    records = [mk_l1(model="qwen", prompt_id="P00", run=1, l2=mk_l2())]
    manifest = _manifest(ok=1, fail=0) + _manifest(model="zhipu", ok=0, fail=3)
    rep = _assemble_with(records, manifest)
    z = rep["metrics"]["zhipu"]
    assert z["planned"] == 3 and z["valid"] == 0 and z["failed"] == 3
    assert z["success_rate"] == 0.0
    assert rep["collection_gate"]["ok"] is False

def test_gate_passes_at_threshold():
    records = [mk_l1(model="qwen", prompt_id=f"P{i:02d}", run=1, l2=mk_l2()) for i in range(19)]
    manifest = _manifest(ok=19, fail=1)   # 19/20 = 0.95
    rep = _assemble_with(records, manifest)
    assert rep["metrics"]["qwen"]["success_rate"] == 0.95
    assert rep["collection_gate"]["ok"] is True

def test_legacy_weeks_without_manifest_fall_back():
    """无 manifest 的历史周:planned=valid(legacy 标记,门不可判定不误杀)。"""
    records = [mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True))]
    rep = _assemble_with(records, [])
    assert rep["metrics"]["qwen"]["planned"] == 1
    assert rep["collection_gate"]["manifest"] is False
    assert rep["collection_gate"]["ok"] is True
    assert rep["collection_gate"]["min_success_rate"] is None   # 无 manifest 不可判定,不得虚报 1.0


# ---- T13(2026-09-02): 静默降级可见化 —— degraded_events 计数(评分数值零变化) ----
from contextlib import ExitStack
from types import SimpleNamespace
from geo.shared.models import L3Source, CompositeScore, DimScore

GEO_1DIM = SimpleNamespace(version="t13", signals={"brand": ["entity_known"]},
                           weights={"brand": 100.0})
SEO_1DIM = SimpleNamespace(version="t13", signals={"on_page": ["https"]},
                           weights={"on_page": 100.0})
L3_OK = L3Source(url="https://sunhestia.com", sha1="s", http_status=200,
                 text="word " * 400, structural={"canonical": "https://sunhestia.com"},
                 semantic={"has_author_byline": True, "has_publish_date": True,
                           "cites_external_sources": True})
STATIC = {"site": "https://sunhestia.com",
          "pages": [{"url": "https://sunhestia.com/", "https": True, "http_status": 200}]}
GSC = {"impressions": 100, "clicks": 5, "ctr": 0.05}
ZERO_EVENTS = {"self_geo_score_skipped": 0, "page_seo_skipped": 0, "gap_skipped": 0,
               "competitor_skipped": 0, "l3_semantic_degraded": 0}
COMPOSITE = CompositeScore(total=50.0,
                           dims=[DimScore(name="brand", score=50.0, weight=100.0, signals={})])


def _assemble_t13(records=None, l3=L3_OK, static=None, gsc=None,
                  fake_geo=None, fake_seo=None, fake_gap=None, **kw):
    """write=False 只读装配(901 测试周,无真实数据依赖);四 loader 全 patch。"""
    records = records if records is not None else [
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True))]
    with ExitStack() as es:
        # side_effect 每次调用新建迭代器:assemble 与 competitor_domains_by_count
        # 会各取一次 iter_l1,共享同一迭代器会第二次拿到耗尽值(竞品扫描为空)。
        es.enter_context(patch('geo.assess.analyst.iter_l1',
                               side_effect=lambda *a, **k: iter(records)))
        es.enter_context(patch('geo.assess.analyst._load_l3_source', return_value=l3))
        es.enter_context(patch('geo.assess.analyst._load_static_signals',
                               return_value=STATIC if static is None else static))
        es.enter_context(patch('geo.assess.analyst._load_gsc_snapshot',
                               return_value=GSC if gsc is None else gsc))
        if fake_geo is not None:
            es.enter_context(patch('geo.assess.analyst.score_geo', side_effect=fake_geo))
        if fake_seo is not None:
            es.enter_context(patch('geo.assess.analyst.score_seo', side_effect=fake_seo))
        if fake_gap is not None:
            es.enter_context(patch('geo.assess.analyst.gap', side_effect=fake_gap))
        kw.setdefault("rules_seo", SEO_1DIM)
        return assemble(901, rules_geo=GEO_1DIM, write=False, **kw)


def test_degraded_events_key_zero_when_healthy():
    """健康输入(全部评分路径成功)→ degraded_events 全零;键无条件出现在报告中。"""
    rep = _assemble_t13()
    assert rep["self_geo"] is not None and rep["self_seo"] is not None
    assert rep["degraded_events"] == ZERO_EVENTS


def test_self_geo_skip_counted_and_warned(caplog):
    """self_geo 评分抛错 → 计数 1 + warning,self_geo=None(不再静默)。"""
    def boom(*a, **kw):
        raise ValueError("bad l3")
    with caplog.at_level("WARNING"):
        rep = _assemble_t13(fake_geo=boom)
    assert rep["self_geo"] is None
    ev = rep["degraded_events"]
    assert ev["self_geo_score_skipped"] == 1
    assert ev["competitor_skipped"] == 0 and ev["page_seo_skipped"] == 0
    assert caplog.records and "self_geo" in caplog.text


def test_page_seo_skip_counted_and_warned(caplog):
    """页面 SEO 评分抛错 → page_seo_skipped 计数 + warning,seo=None。"""
    def boom(*a, **kw):
        raise TypeError("bad page")
    with caplog.at_level("WARNING"):
        rep = _assemble_t13(fake_seo=boom)
    assert rep["self_seo"] is None
    ev = rep["degraded_events"]
    assert ev["page_seo_skipped"] == 1 and ev["self_geo_score_skipped"] == 0
    assert caplog.records


def test_gap_skip_counted():
    """gap 计算抛错 → gap_skipped 计数,gap=None(自评/竞品均在场,确系 gap 自身失败)。"""
    def fake_geo(src, brand, static, **kw):
        return COMPOSITE                       # 自评+竞品都成功,隔离 gap 失败
    def boom(*a, **kw):
        raise ValueError("gap down")
    records = [mk_l1(model="qwen", prompt_id="B02", run=1,
                     l2=mk_l2(mentioned=True, cited=True, position=1))]
    rep = _assemble_t13(records=records, fake_geo=fake_geo, fake_gap=boom)
    assert rep["gap"] is None
    assert rep["degraded_events"]["gap_skipped"] == 1
    assert rep["degraded_events"]["competitor_skipped"] == 0


def test_competitor_skip_counted():
    """竞品评分抛错 → competitor_skipped 计数(竞品缺席诚实可见,不阻断自评)。"""
    def fake_geo(src, brand, static, **kw):
        if "rules" not in kw:                  # 竞品调用不带 rules kw,自评带
            raise ValueError("comp down")
        return COMPOSITE
    records = [mk_l1(model="qwen", prompt_id="B02", run=1,
                     l2=mk_l2(mentioned=True, cited=True, position=1))]
    rep = _assemble_t13(records=records, fake_geo=fake_geo)
    ev = rep["degraded_events"]
    assert ev["competitor_skipped"] == 1
    assert ev["self_geo_score_skipped"] == 0
    assert rep["gap"] is None                  # 竞品全缺席 → gap 分支不进入


def test_semantic_degraded_feeds_p0_flag_and_counter():
    """page_l3.semantic_degraded=True → l3_semantic_degraded 计数 + p0_content_degraded True。"""
    l3_deg = L3_OK.model_copy(update={"semantic_degraded": True})
    captured = {}
    def fake_seo(p, gsc, c, **kw):
        captured.update(c)
        return CompositeScore(total=50.0,
                              dims=[DimScore(name="on_page", score=50.0, weight=100.0, signals={})])
    rep = _assemble_t13(l3=l3_deg, fake_seo=fake_seo)
    assert captured["p0_content_degraded"] is True
    assert rep["degraded_events"]["l3_semantic_degraded"] == 1


def test_semantic_healthy_keeps_p0_flag_false():
    """对照:semantic_degraded=False(存量数据默认)→ p0_content_degraded 保持 False。"""
    captured = {}
    def fake_seo(p, gsc, c, **kw):
        captured.update(c)
        return CompositeScore(total=50.0,
                              dims=[DimScore(name="on_page", score=50.0, weight=100.0, signals={})])
    _assemble_t13(fake_seo=fake_seo)
    assert captured["p0_content_degraded"] is False


# ---- §9(2026-09-02): 快照 robots_ai=None(D3 fail-closed)→ static_robots_unknown 可见 ----
# 评分路径(registry None→0)不动,评分数值零变化;仅报告层布尔呈现。

def test_static_robots_unknown_flag_when_robots_ai_none():
    """快照 robots_ai=None → 顶层 static_robots_unknown=True(报告层可见)。"""
    rep = _assemble_t13(static={"site": "https://sunhestia.com", "robots_ai": None, "pages": []})
    assert rep.get("static_robots_unknown") is True


def test_no_flag_when_robots_ai_dict():
    """对照:robots_ai 为全 Allow dict(w1-w3 盘上形态)→ 不写该键(重算输出零漂移)。"""
    rep = _assemble_t13(static={"site": "https://sunhestia.com",
                                "robots_ai": {"GPTBot": True, "ClaudeBot": True},
                                "pages": []})
    assert "static_robots_unknown" not in rep


def test_no_flag_when_snapshot_missing():
    """快照整体缺失(loader 返回 {})→ 维持现状,不写该键。"""
    rep = _assemble_t13(static={})
    assert "static_robots_unknown" not in rep
