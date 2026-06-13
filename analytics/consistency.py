"""
MetaMind — Consistency score calculator.

Measures how reliably a player performs by comparing the spread of their
ACS values against their average.  A score of 100 means zero variance;
lower scores indicate more volatile performances.
"""

import statistics


def compute_consistency_score(
    acs_values: list[float],
    min_matches: int = 8,
) -> float | None:
    """Compute a 0–100 consistency score from a sequence of ACS values.

    Formula::

        Consistency = 100 − (σ(ACS) / μ(ACS) × 100)

    The result is clamped to **[0, 100]**.

    Args:
        acs_values: Per-match ACS values (must contain at least *min_matches*
            entries for a meaningful result).
        min_matches: Minimum number of matches required.  Returns ``None``
            when the sample is too small.

    Returns:
        A float in [0, 100] representing consistency, or ``None`` if the
        sample is insufficient or the mean is zero.
    """
    if len(acs_values) < min_matches:
        return None

    mean = statistics.mean(acs_values)
    if mean == 0:
        return None

    stdev = statistics.stdev(acs_values)
    score = 100.0 - (stdev / mean * 100.0)
    return max(0.0, min(100.0, score))
