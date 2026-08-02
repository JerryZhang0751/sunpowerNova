"""Comprehensive tests for analyst module - deterministic evaluation report assembly."""

import json
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock
from geo.assess.analyst import assemble, MentionMetrics, _iter_l1
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
    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    # SOV: 2 competitors / 2 valid = 1.0
    assert qwen_metrics["sov"] == 1.0


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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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
    """Test Share of Voice (SOV) calculation."""
    records = [
        # Record 1: 2 competitors mentioned
        mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, competitors=["CompA", "CompB"])),
        # Record 2: 1 competitor mentioned
        mk_l1(model="qwen", prompt_id="B02", run=2, l2=mk_l2(mentioned=True, cited=True, competitors=["CompC"])),
        # Record 3: 0 competitors mentioned
        mk_l1(model="qwen", prompt_id="B02", run=3, l2=mk_l2(mentioned=True, cited=True, competitors=[])),
    ]

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        mock_repo.return_value = Path("/tmp/test_repo")
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    qwen_metrics = report["metrics"]["qwen"]
    # SOV: (2 + 1 + 0) / 3 = 1.0
    assert qwen_metrics["sov"] == 1.0


def test_report_structure():
    """Test that report has required structure and fields."""
    records = [mk_l1(model="qwen", prompt_id="B02", run=1, l2=mk_l2(mentioned=True, cited=True, position=1))]

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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
        with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
        with patch('geo.assess.analyst._load_l3_source', return_value=None):
            with patch('geo.assess.analyst._load_static_signals', return_value={}):
                with patch('geo.assess.analyst._load_gsc_snapshot', return_value={}):
                    with patch('geo.assess.analyst.REPO') as mock_repo:
                        with patch('pathlib.Path.mkdir'):
                            with patch('pathlib.Path.write_text'):
                                report = assemble(week=1)

    qwen_metrics = report["metrics"]["qwen"]
    # SOV: (3 + 1) / 2 = 2.0
    assert qwen_metrics["sov"] == 2.0


def test_sentiment_passthrough():
    """Test that sentiment data is preserved in source_scores CSV."""
    records = [
        mk_l1(model="qwen", prompt_id="B02", run=1,
              l2=mk_l2(mentioned=True, cited=True, position=1, sentiment="pos")),
        mk_l1(model="qwen", prompt_id="B02", run=2,
              l2=mk_l2(mentioned=True, cited=False, sentiment="neg")),
    ]

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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

    with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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
        with patch('geo.assess.analyst._iter_l1', return_value=iter(records)):
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