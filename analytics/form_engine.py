"""
MetaMind — Player form classification engine.

Classifies a player's current trajectory as PEAKING, DECLINING, or
CONSISTENT based on recent ACS relative to their season average and
the coefficient of variation across the window.
"""


def compute_form_status(
    recent_acs: list[float],
    season_avg: float,
    stddev: float,
    mean: float,
) -> str:
    """Classify a player's current form based on recent performance.

    Classification rules (evaluated in order):

    1. **PEAKING** — all of the last 3 ACS values exceed *season_avg*.
    2. **DECLINING** — all of the last 3 ACS values fall below *season_avg*.
    3. **CONSISTENT** — coefficient of variation (σ / μ) is below 15 %, or
       none of the above conditions are met (default).

    Args:
        recent_acs: Chronologically ordered ACS values from the rolling
            window (most recent last).
        season_avg: The player's overall season ACS average.
        stddev: Standard deviation of ACS across the window.
        mean: Mean ACS across the window.

    Returns:
        One of ``'PEAKING'``, ``'DECLINING'``, or ``'CONSISTENT'``.
    """
    if len(recent_acs) < 3:
        return "CONSISTENT"

    last_3 = recent_acs[-3:]

    if all(v > season_avg for v in last_3):
        return "PEAKING"

    if all(v < season_avg for v in last_3):
        return "DECLINING"

    if mean > 0 and (stddev / mean) < 0.15:
        return "CONSISTENT"

    return "CONSISTENT"
