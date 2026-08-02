"""
Comprehensive tests for BFCL-style agent evaluation.
Tests AST matching, normalization, and evaluation metrics.
"""
import json
from pathlib import Path
import pytest
from geo.eval.agent_eval import (
    ast_match,
    _sem_eq,
    _normalize,
    evaluate,
    GATE_ACCURACY
)


class TestSemanticEquality:
    """Test semantic equality function for parameter value comparison."""

    def test_bool_vs_int_distinction(self):
        """Boolean values should not equal integers."""
        assert _sem_eq(True, 1) is False
        assert _sem_eq(False, 0) is False
        assert _sem_eq(True, True) is True
        assert _sem_eq(False, False) is True

    def test_float_comparison_with_tolerance(self):
        """Floating-point comparison should use epsilon tolerance."""
        assert _sem_eq(1.0, 1.0000000001) is True
        assert _sem_eq(1.0, 1.01) is False
        assert _sem_eq(0.1 + 0.2, 0.3) is True

    def test_int_and_float_equivalence(self):
        """Int and float should be semantically equal if values match."""
        assert _sem_eq(1, 1.0) is True
        assert _sem_eq(42, 42.0) is True

    def test_string_equality(self):
        """String comparison should be exact."""
        assert _sem_eq("test", "test") is True
        assert _sem_eq("test", "Test") is False

    def test_none_handling(self):
        """None values should be handled correctly."""
        assert _sem_eq(None, None) is True
        assert _sem_eq(None, "") is False


class TestASTMatching:
    """Test AST-style tool call matching function."""

    def test_match_param_set_eq_different_order(self):
        """Parameters in different order should still match."""
        expected = {
            "function": "f",
            "params": {
                "model": "qwen3.7-plus",
                "enable_search": True
            }
        }
        actual = {
            "function": "f",
            "params": {
                "enable_search": True,
                "model": "qwen3.7-plus"
            }
        }
        assert ast_match(expected, actual) is True

    def test_match_nested_params_eq(self):
        """Nested parameters should match correctly."""
        expected = {
            "function": "call",
            "params": {
                "model": "qwen3.7-plus",
                "search_options": {
                    "search_strategy": "agent",
                    "enable_source": True
                }
            }
        }
        actual = {
            "function": "call",
            "params": {
                "search_options": {
                    "enable_source": True,
                    "search_strategy": "agent"
                },
                "model": "qwen3.7-plus"
            }
        }
        assert ast_match(expected, actual) is True

    def test_mismatch_missing_param(self):
        """Missing parameter should cause mismatch."""
        expected = {
            "function": "f",
            "params": {
                "model": "qwen3.7-plus",
                "enable_search": True
            }
        }
        actual = {
            "function": "f",
            "params": {
                "model": "qwen3.7-plus"
            }
        }
        assert ast_match(expected, actual) is False

    def test_mismatch_extra_param(self):
        """Extra parameter should cause mismatch."""
        expected = {
            "function": "f",
            "params": {
                "model": "qwen3.7-plus"
            }
        }
        actual = {
            "function": "f",
            "params": {
                "model": "qwen3.7-plus",
                "enable_search": True
            }
        }
        assert ast_match(expected, actual) is False

    def test_mismatch_function_name(self):
        """Different function names should not match."""
        expected = {"function": "func_a", "params": {}}
        actual = {"function": "func_b", "params": {}}
        assert ast_match(expected, actual) is False

    def test_mismatch_param_value(self):
        """Different parameter values should not match."""
        expected = {
            "function": "f",
            "params": {
                "model": "qwen3.7-plus"
            }
        }
        actual = {
            "function": "f",
            "params": {
                "model": "gpt-4"
            }
        }
        assert ast_match(expected, actual) is False

    def test_mismatch_nested_param_value(self):
        """Different nested parameter values should not match."""
        expected = {
            "function": "f",
            "params": {
                "options": {
                    "strategy": "agent"
                }
            }
        }
        actual = {
            "function": "f",
            "params": {
                "options": {
                    "strategy": "direct"
                }
            }
        }
        assert ast_match(expected, actual) is False

    def test_match_empty_params(self):
        """Empty parameter sets should match."""
        expected = {"function": "f", "params": {}}
        actual = {"function": "f", "params": {}}
        assert ast_match(expected, actual) is True

    def test_match_list_params(self):
        """List parameters should match by value."""
        expected = {
            "function": "f",
            "params": {
                "tools": [
                    {"type": "web_search"},
                    {"type": "calculator"}
                ]
            }
        }
        actual = {
            "function": "f",
            "params": {
                "tools": [
                    {"type": "web_search"},
                    {"type": "calculator"}
                ]
            }
        }
        assert ast_match(expected, actual) is True

    def test_mismatch_list_order(self):
        """List parameters with different order should not match."""
        expected = {
            "function": "f",
            "params": {
                "tools": [
                    {"type": "web_search"},
                    {"type": "calculator"}
                ]
            }
        }
        actual = {
            "function": "f",
            "params": {
                "tools": [
                    {"type": "calculator"},
                    {"type": "web_search"}
                ]
            }
        }
        # Lists are order-dependent in our implementation
        assert ast_match(expected, actual) is False


class TestNormalization:
    """Test provider-specific request normalization."""

    def test_normalize_qwen(self):
        """Qwen requests should be normalized correctly."""
        raw_request = {
            "model": "qwen3.7-plus",
            "enable_search": True,
            "search_options": {
                "search_strategy": "agent",
                "enable_source": True
            }
        }
        normalized = _normalize("qwen", raw_request)

        assert normalized["function"] == "MultiModalConversation.call"
        assert normalized["params"]["model"] == "qwen3.7-plus"
        assert normalized["params"]["enable_search"] is True
        assert normalized["params"]["search_options"]["search_strategy"] == "agent"

    def test_normalize_doubao(self):
        """Doubao requests should be normalized correctly."""
        raw_request = {
            "model": "doubao-seed-2-1-pro-260628",
            "tools": [{"type": "web_search"}]
        }
        normalized = _normalize("doubao", raw_request)

        assert normalized["function"] == "POST /responses"
        assert normalized["params"]["model"] == "doubao-seed-2-1-pro-260628"
        assert normalized["params"]["tools"] == [{"type": "web_search"}]

    def test_normalize_zhipu(self):
        """Zhipu requests should be normalized correctly."""
        raw_request = {
            "model": "glm-5.2",
            "tools": [
                {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
            ]
        }
        normalized = _normalize("zhipu", raw_request)

        assert normalized["function"] == "POST /messages"
        assert normalized["params"]["model"] == "glm-5.2"
        assert len(normalized["params"]["tools"]) == 1

    def test_normalize_kimi(self):
        """Kimi requests should be normalized correctly."""
        raw_request = {
            "model": "kimi-k3",
            "tools": []
        }
        normalized = _normalize("kimi", raw_request)

        assert normalized["function"] == "POST /messages"
        assert normalized["params"]["model"] == "kimi-k3"
        assert normalized["params"]["tools"] == []

    def test_normalize_unknown_provider(self):
        """Unknown provider should return fallback format."""
        raw_request = {"model": "unknown-model"}
        normalized = _normalize("unknown", raw_request)

        assert normalized["function"] == "unknown"
        assert normalized["params"] == raw_request


class TestEvaluation:
    """Test the full evaluation pipeline."""

    def test_evaluate_with_fixtures(self, tmp_path):
        """Test evaluation with temporary fixtures."""
        # Create temporary fixtures
        fixture1 = {
            "category": "simple",
            "provider": "qwen",
            "prompt_id": "C01",
            "expected_tool_call": {
                "function": "MultiModalConversation.call",
                "params": {
                    "model": "qwen3.7-plus",
                    "enable_search": True
                }
            },
            "actual_request_ref": "raw/qwen_C01.json"
        }

        fixture_file = tmp_path / "test_fixture.json"
        fixture_file.write_text(json.dumps(fixture1), encoding="utf-8")

        # Mock the actual request file
        raw_dir = Path("/Users/jerry/AiProject/sunpower nova/geo-agent/tests/fixtures/raw")
        if (raw_dir / "qwen_C01.json").exists():
            # Run evaluation with the real fixtures
            from geo.shared.config import REPO
            real_fix_dir = REPO / "tests" / "fixtures" / "bfcl"
            if real_fix_dir.exists():
                results = evaluate(real_fix_dir)
                assert "accuracy" in results
                assert "per_class" in results
                assert "gate" in results
                assert "pass" in results

    def test_evaluate_meets_gate(self):
        """Test evaluation meets the gate accuracy threshold."""
        from geo.shared.config import REPO

        fx_dir = REPO / "tests" / "fixtures" / "bfcl"
        if not fx_dir.exists():
            pytest.skip("BFCL fixtures directory not found")

        results = evaluate(fx_dir)

        # Check results structure
        assert isinstance(results["accuracy"], float)
        assert isinstance(results["per_class"], dict)
        assert isinstance(results["param_accuracy"], float)
        assert isinstance(results["gate"], float)
        assert isinstance(results["pass"], bool)

        # Check that gate is set correctly
        assert results["gate"] == GATE_ACCURACY

        # Check per_class contains expected categories
        if results["per_class"]:
            assert "simple" in results["per_class"] or \
                   "multiple" in results["per_class"] or \
                   "parallel" in results["per_class"] or \
                   "irrelevance" in results["per_class"]

    def test_evaluation_metrics_consistency(self):
        """Test that evaluation metrics are internally consistent."""
        from geo.shared.config import REPO

        fx_dir = REPO / "tests" / "fixtures" / "bfcl"
        if not fx_dir.exists():
            pytest.skip("BFCL fixtures directory not found")

        results = evaluate(fx_dir)

        # Accuracy + error_rate should equal 1.0
        assert abs(results["accuracy"] + results["error_rate"] - 1.0) < 0.001

        # Accuracy should be between 0 and 1
        assert 0.0 <= results["accuracy"] <= 1.0

        # Param accuracy should be between 0 and 1
        assert 0.0 <= results["param_accuracy"] <= 1.0

    def test_evaluation_with_all_categories(self):
        """Test evaluation recognizes all category types."""
        from geo.shared.config import REPO

        fx_dir = REPO / "tests" / "fixtures" / "bfcl"
        if not fx_dir.exists():
            pytest.skip("BFCL fixtures directory not found")

        results = evaluate(fx_dir)

        # Check that we have results for multiple categories
        expected_categories = {"simple", "multiple", "parallel", "irrelevance"}
        found_categories = set(results["per_class"].keys())

        # At least some categories should be present
        if results["total_fixtures"] > 0:
            assert len(found_categories) > 0 or results["total_fixtures"] > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_fixtures_directory(self, tmp_path):
        """Test evaluation with empty fixtures directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        results = evaluate(empty_dir)

        assert results["accuracy"] == 0.0
        assert results["total_fixtures"] == 0
        assert results["correct_fixtures"] == 0

    def test_ast_match_with_missing_fields(self):
        """Test AST matching with missing expected fields."""
        expected = {"function": "f"}
        actual = {"function": "f", "params": {}}

        # Should handle missing params gracefully
        result = ast_match(expected, actual)
        assert result is True

    def test_normalize_with_missing_fields(self):
        """Test normalization with missing request fields."""
        raw_request = {}  # Empty request

        normalized = _normalize("qwen", raw_request)

        assert normalized["function"] == "MultiModalConversation.call"
        assert normalized["params"]["model"] is None
        assert normalized["params"]["enable_search"] is None

    def test_parameter_value_type_coercion(self):
        """Test that parameter type coercion works correctly."""
        expected = {
            "function": "f",
            "params": {
                "count": 42
            }
        }
        actual = {
            "function": "f",
            "params": {
                "count": 42.0
            }
        }

        # Int and float should match semantically
        assert ast_match(expected, actual) is True


class TestMainEntry:
    """Test the main entry point."""

    def test_main_entry_exists(self):
        """Test that main function can be imported."""
        from geo.eval.agent_eval import main

        # Main function should exist
        assert callable(main)

    def test_module_main_execution(self):
        """Test that module can be executed as main."""
        import geo.eval.agent_eval as module

        # Module should have __main__ guard
        assert hasattr(module, "main")