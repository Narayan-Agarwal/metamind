"""
MetaMind — Edge Score engine for head-to-head player comparison.

Computes a weighted composite score across five key metrics to determine
which player holds the statistical advantage in a matchup.
"""

from __future__ import annotations

from typing import Any

# Metric weights — must sum to 1.0
WEIGHTS: dict[str, float] = {
    "avg_acs": 0.30,
    "avg_kd": 0.25,
    "consistency_score": 0.20,
    "avg_fb": 0.15,
    "avg_kast": 0.10,
}


def _safe_float(value: Any) -> float:
    """Coerce a value to float, defaulting to 0.0 on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _min_max_normalize(val_a: float, val_b: float) -> tuple[float, float]:
    """Min-max normalise two values into [0, 1].

    If both values are identical the result is (0.5, 0.5).

    Returns:
        Tuple of (normalised_a, normalised_b).
    """
    min_val = min(val_a, val_b)
    max_val = max(val_a, val_b)
    spread = max_val - min_val

    if spread == 0:
        return 0.5, 0.5

    return (val_a - min_val) / spread, (val_b - min_val) / spread


def compute_edge_score(player_a: dict, player_b: dict) -> dict:
    """Compare two players across five weighted metrics.

    Each metric is min-max normalised using only the two players' values,
    then multiplied by its weight.  The weighted sums determine each
    player's overall edge score, and per-category wins are tallied.

    Args:
        player_a: Dict containing at least the keys defined in ``WEIGHTS``.
        player_b: Dict containing at least the keys defined in ``WEIGHTS``.

    Returns:
        A dict with the following structure::

            {
                "player_a_wins": int,       # categories won by A
                "player_b_wins": int,       # categories won by B
                "player_a_score": float,    # weighted composite [0, 1]
                "player_b_score": float,    # weighted composite [0, 1]
                "category_results": {
                    "<metric>": {
                        "a_raw": float,
                        "b_raw": float,
                        "a_norm": float,
                        "b_norm": float,
                        "winner": "A" | "B" | "TIE",
                        "weight": float,
                    },
                    ...
                },
            }
    """
    a_total = 0.0
    b_total = 0.0
    a_wins = 0
    b_wins = 0
    category_results: dict[str, dict] = {}

    for metric, weight in WEIGHTS.items():
        a_raw = _safe_float(player_a.get(metric))
        b_raw = _safe_float(player_b.get(metric))

        a_norm, b_norm = _min_max_normalize(a_raw, b_raw)

        a_total += a_norm * weight
        b_total += b_norm * weight

        if a_norm > b_norm:
            winner = "A"
            a_wins += 1
        elif b_norm > a_norm:
            winner = "B"
            b_wins += 1
        else:
            winner = "TIE"

        category_results[metric] = {
            "a_raw": a_raw,
            "b_raw": b_raw,
            "a_norm": round(a_norm, 4),
            "b_norm": round(b_norm, 4),
            "winner": winner,
            "weight": weight,
        }

    return {
        "player_a_wins": a_wins,
        "player_b_wins": b_wins,
        "player_a_score": round(a_total, 4),
        "player_b_score": round(b_total, 4),
        "category_results": category_results,
    }
