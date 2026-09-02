"""
BFCL-style tool-call evaluation for collector agents.
AST/signature matching for API call shape, connectivity toggle, params, and citation-field parsing.
Triggered by version-update hook (when tool-chain/model/endpoint/field-caliber changes).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geo.shared.config import REPO

GATE_ACCURACY = 0.95  # AST accuracy ≥ 95% is required for passing


def _sem_eq(a: Any, b: Any) -> bool:
    """
    Semantic equality for parameter values.
    Handles type coercion and floating-point comparison.
    """
    # Handle boolean vs int confusion
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b

    # Handle floating-point comparison
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-9

    # Default equality
    return a == b


def ast_match(expected: dict, actual: dict) -> bool:
    """
    AST-style matching for tool calls.

    Checks:
    1. Function name exact match
    2. Parameter set equivalence (order-independent)
    3. Parameter value semantic equivalence

    Returns True if the actual tool call matches the expected shape.
    """
    # Check function name
    if expected.get("function") != actual.get("function"):
        return False

    # Extract parameters
    expected_params = expected.get("params", {})
    actual_params = actual.get("params", {})

    # Check parameter keys match (order-independent)
    if set(expected_params.keys()) != set(actual_params.keys()):
        return False

    # Check each parameter value
    for key in expected_params:
        expected_value = expected_params[key]
        actual_value = actual_params.get(key)

        # Recursive check for nested dicts
        if isinstance(expected_value, dict) and isinstance(actual_value, dict):
            if set(expected_value.keys()) != set(actual_value.keys()):
                return False
            if not all(_sem_eq(expected_value[k], actual_value[k]) for k in expected_value):
                return False
        elif not _sem_eq(expected_value, actual_value):
            return False

    return True


def _normalize(provider: str, req: dict) -> dict:
    """
    Normalize provider-specific request format into standard {function, params} shape.

    Args:
        provider: Provider name (qwen, doubao, zhipu) — BFCL 只评采集层客户端
        req: Raw request object from fixture

    Returns:
        Normalized tool call with function and params
    """
    if provider == "qwen":
        return {
            "function": "MultiModalConversation.call",
            "params": {
                "model": req.get("model"),
                "enable_search": req.get("enable_search"),
                "search_options": req.get("search_options", {})
            }
        }
    elif provider == "doubao":
        return {
            "function": "POST /responses",
            "params": {
                "model": req.get("model"),
                "tools": req.get("tools", [])
            }
        }
    elif provider == "zhipu":
        return {
            "function": "POST /messages",
            "params": {
                "model": req.get("model"),
                "tools": req.get("tools", [])
            }
        }
    else:
        # Fallback for unknown providers
        return {
            "function": "unknown",
            "params": req
        }


def evaluate(fx_dir: Path) -> dict:
    """
    Evaluate BFCL fixtures and compute metrics.

    Args:
        fx_dir: Directory containing BFCL fixture JSON files

    Returns:
        Evaluation results with accuracy, per-class accuracy, weighted accuracy,
        param accuracy, error rate, and gate pass/fail status
    """
    # Load all fixtures
    fixtures = []
    for fixture_path in fx_dir.glob("*.json"):
        try:
            fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
            fixtures.append(fixture_data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load fixture {fixture_path}: {e}")

    # Initialize metrics
    per_category = {}
    correct = 0
    total = 0
    param_hits = 0
    param_total = 0

    for fixture in fixtures:
        # Get expected tool call
        expected_call = fixture.get("expected_tool_call", {})

        # Load and normalize actual request
        request_ref = fixture.get("actual_request_ref", "")
        request_path = REPO / "tests" / "fixtures" / request_ref

        try:
            raw_data = json.loads(request_path.read_text(encoding="utf-8"))
            actual_request = raw_data.get("request", {})
            actual_call = _normalize(fixture.get("provider", ""), actual_request)
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Failed to load actual request {request_path}: {e}")
            continue

        # Check if tool call matches
        is_correct = ast_match(expected_call, actual_call)

        # For irrelevance category, verify search was NOT actually triggered
        if fixture.get("category") == "irrelevance" and is_correct:
            # Load raw data to check meta.search_triggered
            search_triggered = raw_data.get("meta", {}).get("search_triggered", True)
            is_correct = not search_triggered  # Correct if search was NOT triggered

        # Track per-category results
        category = fixture.get("category", "unknown")
        per_category.setdefault(category, []).append(int(is_correct))

        # Update overall metrics
        correct += int(is_correct)
        total += 1

        # Track parameter-level accuracy
        expected_params = expected_call.get("params", {})
        actual_params = actual_call.get("params", {})
        param_total += len(expected_params)

        for key in expected_params:
            if key in actual_params:
                exp_val = expected_params[key]
                act_val = actual_params[key]

                if isinstance(exp_val, dict) and isinstance(act_val, dict):
                    # Nested parameter check
                    if all(_sem_eq(exp_val.get(k), act_val.get(k)) for k in exp_val):
                        param_hits += 1
                elif _sem_eq(exp_val, act_val):
                    param_hits += 1

    # Compute metrics
    accuracy = correct / total if total > 0 else 0.0
    param_accuracy = param_hits / max(1, param_total)

    # Compute per-category accuracy
    per_category_accuracy = {}
    for category, results in per_category.items():
        cat_accuracy = sum(results) / len(results) if results else 0.0
        per_category_accuracy[category] = round(cat_accuracy, 4)

    # Determine gate status
    passes_gate = accuracy >= GATE_ACCURACY

    return {
        "accuracy": round(accuracy, 4),
        "per_class": per_category_accuracy,
        "weighted_accuracy": round(accuracy, 4),  # Same as accuracy for unweighted case
        "param_accuracy": round(param_accuracy, 4),
        "error_rate": round(1 - accuracy, 4),
        "gate": GATE_ACCURACY,
        "pass": passes_gate,
        "total_fixtures": total,
        "correct_fixtures": correct
    }


def main() -> None:
    """Main entry point for command-line execution."""
    import sys

    # Run evaluation
    fx_dir = REPO / "tests" / "fixtures" / "bfcl"
    results = evaluate(fx_dir)

    # Ensure output directory exists
    output_dir = REPO / "data" / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write results
    output_path = output_dir / "agent_eval.json"
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Print results
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # Exit with appropriate code for gate
    sys.exit(0 if results["pass"] else 1)


if __name__ == "__main__":
    main()