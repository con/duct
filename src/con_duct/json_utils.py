"""Centralized JSON file type detection and loading for duct."""

from __future__ import annotations
import json
from typing import Any
from con_duct.duct_main import SUFFIXES

# Suffixes that use JSON Lines format
JSONL_SUFFIXES = (SUFFIXES["usage"], SUFFIXES["usage_legacy"])


def is_jsonl_file(path: str) -> bool:
    """Check if path is a JSON Lines file."""
    if any(path.endswith(s) for s in JSONL_SUFFIXES):
        return True
    return path.endswith(".jsonl")


def is_info_file(path: str) -> bool:
    """Check if path is a duct info file (standard JSON)."""
    return path.endswith(SUFFIXES["info"])


def load_usage_file(path: str) -> list[dict[str, Any]]:
    """Load a duct usage file (JSON Lines format)."""
    with open(path, "r") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_info_file(path: str) -> dict[str, Any]:
    """Load a duct info file (standard JSON)."""
    with open(path, "r") as f:
        result: dict[str, Any] = json.load(f)
        return result
