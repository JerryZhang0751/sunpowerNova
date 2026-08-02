"""
Schema and serialization utilities for report.json
Ensures deterministic output for golden tests
"""

from __future__ import annotations
import json
from typing import Any

def dumps(report: dict) -> str:
    """
    Serialize report dict to JSON with deterministic formatting.
    Uses sort_keys=True to ensure consistent key ordering.
    """
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)

def num(x: Any) -> str:
    """
    Format numbers to fixed decimal places for determinism.
    Ensures floats are consistently formatted.
    """
    return f"{float(x):.1f}"