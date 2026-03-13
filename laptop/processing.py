"""Signal processing utilities for force-plate data.

# file: laptop/processing.py
"""

from __future__ import annotations

from typing import Mapping, Tuple


def compute_forces(data: Mapping[str, float]) -> Tuple[float, float, float]:
    """Compute left, right, and total force from a sensor reading."""
    left_force = float(data["top_left"]) + float(data["bottom_left"])
    right_force = float(data["top_right"]) + float(data["bottom_right"])
    total_force = left_force + right_force
    return left_force, right_force, total_force


def compute_symmetry(left_force: float, right_force: float) -> float:
    """Compute left/right loading symmetry percentage.

    Returns 100 when both sides are perfectly balanced.
    """
    total = left_force + right_force
    if total <= 0:
        return 0.0
    return 100.0 * (1.0 - abs(left_force - right_force) / total)
