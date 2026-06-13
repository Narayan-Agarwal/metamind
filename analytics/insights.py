"""
MetaMind — Multi-signal insight commentary engine.

Generates human-readable insight cards for players, teams, and the global
leaderboard by evaluating a rule-based set of conditions against
pre-computed analytics data.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(data: dict, key: str, default: Any = None) -> Any:
    """Safely retrieve a value from *data*, returning *default* on miss."""
    return data.get(key, default)


def _make_insight(
    title: str,
    body: str,
    icon: str = "📊",
    signal_strength: str = "medium",
) -> dict[str, str]:
    """Build a standardised insight card dict."""
    return {
        "title": title,
        "body": body,
        "icon": icon,
        "signal_strength": signal_strength,
    }


# ---------------------------------------------------------------------------
# Player insights
# ---------------------------------------------------------------------------

def generate_player_insights(player_data: dict) -> list[dict[str, str]]:
    """Generate a list of insight cards for a single player.

    Evaluated rules (in priority order):

    1. **Elite & reliable** — ACS percentile > 85 AND consistency > 75.
    2. **Entry fragger** — first-kill percentile > 70 AND avg kills > 18.
    3. **India spotlight** — nationality is Indian AND india_rank ≤ 3.
    4. **Peaking** — form is PEAKING AND last-match ACS equals season best.

    Args:
        player_data: Dict with keys such as ``acs_percentile``,
            ``consistency_score``, ``fk_percentile``, ``avg_kills``,
            ``nationality``, ``india_rank``, ``form``, ``last_match_acs``,
            ``season_best_acs``, ``global_percentile``.

    Returns:
        List of insight dicts, each with *title*, *body*, *icon*, and
        *signal_strength*.
    """
    insights: list[dict[str, str]] = []

    acs_pct = _safe_get(player_data, "acs_percentile", 0)
    consistency = _safe_get(player_data, "consistency_score", 0)
    fk_pct = _safe_get(player_data, "fk_percentile", 0)
    avg_kills = _safe_get(player_data, "avg_kills", 0)
    nationality = _safe_get(player_data, "nationality", "")
    india_rank = _safe_get(player_data, "india_rank")
    form = _safe_get(player_data, "form", "CONSISTENT")
    last_match_acs = _safe_get(player_data, "last_match_acs", 0)
    season_best_acs = _safe_get(player_data, "season_best_acs", 0)
    global_pct = _safe_get(player_data, "global_percentile", 0)

    # Rule 1: Elite and reliable
    if acs_pct > 85 and consistency > 75:
        insights.append(
            _make_insight(
                title="Elite & Reliable",
                body=(
                    f"Top {100 - acs_pct:.0f}% in ACS with a consistency "
                    f"score of {consistency:.0f}/100."
                ),
                icon="🏆",
                signal_strength="high",
            )
        )

    # Rule 2: Entry fragger profile
    if fk_pct > 70 and avg_kills > 18:
        insights.append(
            _make_insight(
                title="Entry Fragger Profile",
                body=(
                    f"Takes first bloods at the top {100 - fk_pct:.0f}% rate "
                    f"with {avg_kills:.1f} avg kills per map."
                ),
                icon="⚔️",
                signal_strength="high",
            )
        )

    # Rule 3: India spotlight
    if str(nationality).lower() == "indian" and india_rank is not None and india_rank <= 3:
        insights.append(
            _make_insight(
                title=f"India Rank #{india_rank}",
                body=(
                    f"{global_pct:.0f}th percentile globally by ACS — "
                    f"among the best from India."
                ),
                icon="🇮🇳",
                signal_strength="high",
            )
        )

    # Rule 4: Currently peaking
    if form == "PEAKING" and last_match_acs > 0 and last_match_acs >= season_best_acs:
        insights.append(
            _make_insight(
                title="Currently Peaking",
                body=(
                    f"Career-best ACS of {last_match_acs:.1f} in the last "
                    f"match — currently in peak form."
                ),
                icon="🔥",
                signal_strength="high",
            )
        )

    return insights


# ---------------------------------------------------------------------------
# Team insights
# ---------------------------------------------------------------------------

def generate_team_insights(team_data: dict) -> list[dict[str, str]]:
    """Generate a list of insight cards for a team.

    Evaluated rules:

    1. Strongest / weakest map by win rate.
    2. **Pistol-dependent** — pistol win % > 65 AND eco win % < 30.
    3. **Dominant on structured rounds** — full-buy win % > 70.
    4. Attack vs. defence side bias.

    Args:
        team_data: Dict with keys such as ``map_winrates`` (list of dicts
            with ``map_name`` and ``win_rate``), ``pistol_win_pct``,
            ``eco_win_pct``, ``full_buy_win_pct``, ``attack_win_pct``,
            ``defense_win_pct``.

    Returns:
        List of insight dicts.
    """
    insights: list[dict[str, str]] = []

    # --- Map strength / weakness ---
    map_winrates: list[dict] = _safe_get(team_data, "map_winrates", [])
    if map_winrates:
        strongest = max(map_winrates, key=lambda m: m.get("win_rate", 0))
        weakest = min(map_winrates, key=lambda m: m.get("win_rate", 0))

        insights.append(
            _make_insight(
                title="Strongest Map",
                body=(
                    f"{strongest['map_name']} at "
                    f"{strongest['win_rate']:.0f}% win rate."
                ),
                icon="🗺️",
                signal_strength="medium",
            )
        )
        if strongest["map_name"] != weakest["map_name"]:
            insights.append(
                _make_insight(
                    title="Weakest Map",
                    body=(
                        f"{weakest['map_name']} at "
                        f"{weakest['win_rate']:.0f}% win rate."
                    ),
                    icon="⚠️",
                    signal_strength="medium",
                )
            )

    # --- Pistol-dependent ---
    pistol_pct = _safe_get(team_data, "pistol_win_pct", 0)
    eco_pct = _safe_get(team_data, "eco_win_pct", 50)

    if pistol_pct > 65 and eco_pct < 30:
        insights.append(
            _make_insight(
                title="Pistol-Dependent",
                body=(
                    f"Wins {pistol_pct:.0f}% of pistol rounds but only "
                    f"{eco_pct:.0f}% of eco rounds — relies heavily on "
                    f"pistol momentum."
                ),
                icon="🔫",
                signal_strength="high",
            )
        )

    # --- Dominant on structured rounds ---
    full_buy_pct = _safe_get(team_data, "full_buy_win_pct", 0)
    if full_buy_pct > 70:
        insights.append(
            _make_insight(
                title="Dominant on Structured Rounds",
                body=(
                    f"Full-buy win rate of {full_buy_pct:.0f}% — excels "
                    f"when the team has a full economy."
                ),
                icon="💰",
                signal_strength="high",
            )
        )

    # --- Side bias ---
    atk_pct = _safe_get(team_data, "attack_win_pct", 50)
    def_pct = _safe_get(team_data, "defense_win_pct", 50)

    if abs(atk_pct - def_pct) > 10:
        if atk_pct > def_pct:
            insights.append(
                _make_insight(
                    title="Attack-Side Bias",
                    body=(
                        f"Attack win rate {atk_pct:.0f}% vs. defence "
                        f"{def_pct:.0f}% — stronger on the attacking side."
                    ),
                    icon="⚡",
                    signal_strength="medium",
                )
            )
        else:
            insights.append(
                _make_insight(
                    title="Defence-Side Bias",
                    body=(
                        f"Defence win rate {def_pct:.0f}% vs. attack "
                        f"{atk_pct:.0f}% — stronger on the defending side."
                    ),
                    icon="🛡️",
                    signal_strength="medium",
                )
            )

    return insights


# ---------------------------------------------------------------------------
# Leaderboard / global insights
# ---------------------------------------------------------------------------

def generate_leaderboard_insights(leaderboard_data: dict) -> list[dict[str, str]]:
    """Generate global commentary insights from leaderboard data.

    Evaluated rules:

    1. Top performer globally (rank #1 by ACS).
    2. Most consistent region (highest avg consistency score).
    3. Top Indian player spotlight.

    Args:
        leaderboard_data: Dict with keys:
            - ``top_player``: dict with ``name``, ``avg_acs``, ``team``.
            - ``regional_consistency``: list of dicts with ``region``
              and ``avg_consistency``.
            - ``top_indian_player``: dict with ``name``, ``global_rank``,
              ``avg_acs``.

    Returns:
        List of insight dicts.
    """
    insights: list[dict[str, str]] = []

    # --- Top performer ---
    top_player = _safe_get(leaderboard_data, "top_player")
    if top_player:
        insights.append(
            _make_insight(
                title="Global #1",
                body=(
                    f"{top_player['name']} ({top_player.get('team', 'N/A')}) "
                    f"leads with {top_player.get('avg_acs', 0):.1f} ACS."
                ),
                icon="👑",
                signal_strength="high",
            )
        )

    # --- Most consistent region ---
    regional: list[dict] = _safe_get(leaderboard_data, "regional_consistency", [])
    if regional:
        best_region = max(regional, key=lambda r: r.get("avg_consistency", 0))
        insights.append(
            _make_insight(
                title="Most Consistent Region",
                body=(
                    f"{best_region['region']} has the highest average "
                    f"consistency score at "
                    f"{best_region['avg_consistency']:.1f}/100."
                ),
                icon="🌍",
                signal_strength="medium",
            )
        )

    # --- Top Indian player ---
    top_indian = _safe_get(leaderboard_data, "top_indian_player")
    if top_indian:
        insights.append(
            _make_insight(
                title="Top Indian Player",
                body=(
                    f"{top_indian['name']} — global rank "
                    f"#{top_indian.get('global_rank', '?')} with "
                    f"{top_indian.get('avg_acs', 0):.1f} ACS."
                ),
                icon="🇮🇳",
                signal_strength="medium",
            )
        )

    return insights
