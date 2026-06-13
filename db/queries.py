"""
MetaMind — SQL query layer.

Every public function accepts a SQLAlchemy ``Engine`` (plus optional
filter parameters), executes a parameterised query via :func:`pandas.read_sql`,
and returns a :class:`pandas.DataFrame`.

When called from Streamlit pages the caller is expected to wrap these
functions with ``@st.cache_data(ttl=3600)``; the functions themselves
are framework-agnostic.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


# =========================================================================
# Lookup / reference tables
# =========================================================================

def get_all_players(engine: Engine) -> pd.DataFrame:
    """Return all players with id, name, team, and region.

    Returns:
        DataFrame with columns: player_id, name, team, region.
    """
    sql = text("""
        SELECT player_id, name, team, region
        FROM players
        ORDER BY name
    """)
    return pd.read_sql(sql, engine)


def get_all_teams(engine: Engine) -> pd.DataFrame:
    """Return all teams.

    Returns:
        DataFrame with columns: team_id, name, region.
    """
    sql = text("""
        SELECT team_id, name, region
        FROM teams
        ORDER BY name
    """)
    return pd.read_sql(sql, engine)


def get_all_tournaments(engine: Engine) -> pd.DataFrame:
    """Return all tournaments.

    Returns:
        DataFrame with columns: tournament_id, name, year.
    """
    sql = text("""
        SELECT tournament_id, name, year
        FROM tournaments
        ORDER BY year DESC, name
    """)
    return pd.read_sql(sql, engine)


# =========================================================================
# Player analytics
# =========================================================================

def get_player_career_stats(
    engine: Engine,
    player_id: int,
    tournament_id: int | None = None,
    map_id: int | None = None,
) -> pd.DataFrame:
    """Return aggregated career stats for a player with optional filters.

    Joins ``player_stats`` with ``matches`` so that tournament and map
    filters can be applied.

    Args:
        engine: SQLAlchemy engine.
        player_id: Target player.
        tournament_id: Optional tournament filter.
        map_id: Optional map filter.

    Returns:
        DataFrame with per-match stat rows for the player.
    """
    conditions = ["ps.player_id = :player_id"]
    params: dict = {"player_id": player_id}

    if tournament_id is not None:
        conditions.append("m.tournament_id = :tournament_id")
        params["tournament_id"] = tournament_id

    if map_id is not None:
        conditions.append("m.map_id = :map_id")
        params["map_id"] = map_id

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            ps.stat_id,
            ps.player_id,
            ps.match_id,
            ps.agent,
            ps.acs,
            ps.kills,
            ps.deaths,
            ps.assists,
            ps.kd_ratio,
            ps.kast,
            ps.first_kills,
            ps.first_deaths,
            ps.adr,
            m.match_date,
            m.tournament_id,
            m.map_id,
            m.map_name
        FROM player_stats ps
        JOIN matches m ON ps.match_id = m.match_id
        WHERE {where_clause}
        ORDER BY m.match_date
    """)

    return pd.read_sql(sql, engine, params=params)


def get_player_form(
    engine: Engine,
    player_id: int,
    window: int = 10,
) -> pd.DataFrame:
    """Return rolling ACS / KD / Kills using SQL window functions.

    Uses a two-CTE approach:

    1. **ordered** — assigns ``match_num`` via ROW_NUMBER.
    2. **rolling** — computes rolling averages and a LAG for previous ACS.

    Args:
        engine: SQLAlchemy engine.
        player_id: Target player.
        window: Number of preceding rows for the rolling window.

    Returns:
        DataFrame ordered by ``match_num`` with rolling columns.
    """
    sql = text("""
        WITH ordered AS (
            SELECT
                ps.*,
                m.match_date,
                ROW_NUMBER() OVER (
                    ORDER BY m.match_date, ps.stat_id
                ) AS match_num
            FROM player_stats ps
            JOIN matches m ON ps.match_id = m.match_id
            WHERE ps.player_id = :player_id
        ),
        rolling AS (
            SELECT *,
                AVG(acs) OVER (
                    ORDER BY match_num
                    ROWS BETWEEN :window PRECEDING AND CURRENT ROW
                ) AS rolling_acs,
                AVG(kd_ratio) OVER (
                    ORDER BY match_num
                    ROWS BETWEEN :window PRECEDING AND CURRENT ROW
                ) AS rolling_kd,
                AVG(kills) OVER (
                    ORDER BY match_num
                    ROWS BETWEEN :window PRECEDING AND CURRENT ROW
                ) AS rolling_kills,
                LAG(acs, 1) OVER (ORDER BY match_num) AS prev_acs
            FROM ordered
        )
        SELECT * FROM rolling ORDER BY match_num
    """)

    return pd.read_sql(sql, engine, params={"player_id": player_id, "window": window})


def get_player_percentiles(engine: Engine, player_id: int) -> pd.DataFrame:
    """Retrieve percentile data for a single player from the materialised view.

    Returns:
        DataFrame with one row from ``mv_player_percentiles``.
    """
    sql = text("""
        SELECT *
        FROM mv_player_percentiles
        WHERE player_id = :player_id
    """)
    return pd.read_sql(sql, engine, params={"player_id": player_id})


def get_all_percentiles(engine: Engine) -> pd.DataFrame:
    """Retrieve the full ``mv_player_percentiles`` materialised view.

    Returns:
        DataFrame with all players and their percentile rankings.
    """
    sql = text("""
        SELECT *
        FROM mv_player_percentiles
        ORDER BY avg_acs DESC
    """)
    return pd.read_sql(sql, engine)


def get_player_agent_breakdown(
    engine: Engine,
    player_id: int,
) -> pd.DataFrame:
    """Return per-agent averages and win rate for a player.

    Groups by agent and computes AVG of core stats plus win rate.

    Returns:
        DataFrame with columns: agent, matches_played, avg_acs, avg_kd,
        avg_kills, avg_deaths, avg_assists, avg_kast, avg_adr, win_rate.
    """
    sql = text("""
        SELECT
            ps.agent,
            COUNT(*)                          AS matches_played,
            AVG(ps.acs)                       AS avg_acs,
            AVG(ps.kd_ratio)                  AS avg_kd,
            AVG(ps.kills)                     AS avg_kills,
            AVG(ps.deaths)                    AS avg_deaths,
            AVG(ps.assists)                   AS avg_assists,
            AVG(ps.kast)                      AS avg_kast,
            AVG(ps.adr)                       AS avg_adr,
            AVG(CASE WHEN m.winner_team_id = p.team_id
                     THEN 1.0 ELSE 0.0 END)  AS win_rate
        FROM player_stats ps
        JOIN matches m ON ps.match_id = m.match_id
        JOIN players p ON ps.player_id = p.player_id
        WHERE ps.player_id = :player_id
        GROUP BY ps.agent
        ORDER BY matches_played DESC
    """)
    return pd.read_sql(sql, engine, params={"player_id": player_id})


def get_compare_players(
    engine: Engine,
    player_a_id: int,
    player_b_id: int,
) -> pd.DataFrame:
    """Retrieve percentile data for two players for head-to-head comparison.

    Returns:
        DataFrame with two rows (one per player) from ``mv_player_percentiles``.
    """
    sql = text("""
        SELECT *
        FROM mv_player_percentiles
        WHERE player_id IN (:player_a_id, :player_b_id)
    """)
    return pd.read_sql(
        sql,
        engine,
        params={"player_a_id": player_a_id, "player_b_id": player_b_id},
    )


# =========================================================================
# Team analytics
# =========================================================================

def get_team_kpis(
    engine: Engine,
    team_id: int,
    tournament_id: int | None = None,
) -> pd.DataFrame:
    """Return high-level KPIs for a team: win rate, avg rounds, side splits.

    Args:
        engine: SQLAlchemy engine.
        team_id: Target team.
        tournament_id: Optional tournament filter.

    Returns:
        Single-row DataFrame with overall_win_rate, avg_rounds_won,
        avg_rounds_lost, attack_win_pct, defense_win_pct.
    """
    conditions = ["(m.team_a_id = :team_id OR m.team_b_id = :team_id)"]
    params: dict = {"team_id": team_id}

    if tournament_id is not None:
        conditions.append("m.tournament_id = :tournament_id")
        params["tournament_id"] = tournament_id

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            COUNT(*)                                                     AS total_matches,
            AVG(CASE WHEN m.winner_team_id = :team_id
                     THEN 1.0 ELSE 0.0 END)                             AS overall_win_rate,
            AVG(CASE WHEN m.team_a_id = :team_id THEN m.team_a_rounds
                     ELSE m.team_b_rounds END)                           AS avg_rounds_won,
            AVG(CASE WHEN m.team_a_id = :team_id THEN m.team_b_rounds
                     ELSE m.team_a_rounds END)                           AS avg_rounds_lost,
            AVG(CASE WHEN m.team_a_id = :team_id THEN m.team_a_attack_pct
                     ELSE m.team_b_attack_pct END)                       AS attack_win_pct,
            AVG(CASE WHEN m.team_a_id = :team_id THEN m.team_a_defense_pct
                     ELSE m.team_b_defense_pct END)                      AS defense_win_pct
        FROM matches m
        WHERE {where_clause}
    """)

    return pd.read_sql(sql, engine, params=params)


def get_team_map_winrates(engine: Engine, team_id: int) -> pd.DataFrame:
    """Return per-map win rates for a team from the materialised view.

    Returns:
        DataFrame with columns from ``mv_team_map_winrates``.
    """
    sql = text("""
        SELECT *
        FROM mv_team_map_winrates
        WHERE team_id = :team_id
        ORDER BY win_rate DESC
    """)
    return pd.read_sql(sql, engine, params={"team_id": team_id})


def get_team_economy(
    engine: Engine,
    team_id: int,
    tournament_id: int | None = None,
) -> pd.DataFrame:
    """Return economy stats (pistol, eco, full-buy win rates) per map.

    Args:
        engine: SQLAlchemy engine.
        team_id: Target team.
        tournament_id: Optional tournament filter.

    Returns:
        DataFrame with per-map economy breakdown.
    """
    conditions = ["te.team_id = :team_id"]
    params: dict = {"team_id": team_id}

    if tournament_id is not None:
        conditions.append("m.tournament_id = :tournament_id")
        params["tournament_id"] = tournament_id

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            m.map_name,
            AVG(te.pistol_win_pct)     AS avg_pistol_win_pct,
            AVG(te.eco_win_pct)        AS avg_eco_win_pct,
            AVG(te.full_buy_win_pct)   AS avg_full_buy_win_pct,
            AVG(te.force_buy_win_pct)  AS avg_force_buy_win_pct,
            COUNT(*)                   AS matches_played
        FROM team_economy te
        JOIN matches m ON te.match_id = m.match_id
        WHERE {where_clause}
        GROUP BY m.map_name
        ORDER BY m.map_name
    """)

    return pd.read_sql(sql, engine, params=params)


def get_team_players(engine: Engine, team_id: int) -> pd.DataFrame:
    """Return the team's players with their averaged stats.

    Returns:
        DataFrame with player_id, name, avg_acs, avg_kd, avg_kills,
        matches_played — ordered by avg_acs descending.
    """
    sql = text("""
        SELECT
            p.player_id,
            p.name,
            AVG(ps.acs)       AS avg_acs,
            AVG(ps.kd_ratio)  AS avg_kd,
            AVG(ps.kills)     AS avg_kills,
            COUNT(*)          AS matches_played
        FROM players p
        JOIN player_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = :team_id
        GROUP BY p.player_id, p.name
        ORDER BY avg_acs DESC
    """)
    return pd.read_sql(sql, engine, params={"team_id": team_id})


# =========================================================================
# Leaderboard & global
# =========================================================================

def get_leaderboard(
    engine: Engine,
    region: str | None = None,
    min_matches: int = 10,
    sort_by: str = "avg_acs",
    offset: int = 0,
    limit: int = 25,
) -> pd.DataFrame:
    """Return a paginated leaderboard from ``mv_player_percentiles``.

    Args:
        engine: SQLAlchemy engine.
        region: Optional region filter.
        min_matches: Minimum matches threshold.
        sort_by: Column to sort by (must exist in the view).
        offset: Pagination offset.
        limit: Page size.

    Returns:
        DataFrame with up to *limit* rows.
    """
    # Whitelist sort columns to prevent SQL injection
    allowed_sort = {
        "avg_acs", "avg_kd", "avg_kills", "avg_kast",
        "avg_fb", "avg_adr", "consistency_score", "matches_played",
    }
    if sort_by not in allowed_sort:
        sort_by = "avg_acs"

    conditions = ["matches_played >= :min_matches"]
    params: dict = {"min_matches": min_matches, "offset": offset, "limit": limit}

    if region is not None:
        conditions.append("region = :region")
        params["region"] = region

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT *
        FROM mv_player_percentiles
        WHERE {where_clause}
        ORDER BY {sort_by} DESC
        LIMIT :limit OFFSET :offset
    """)

    return pd.read_sql(sql, engine, params=params)


def get_regional_comparison(engine: Engine) -> pd.DataFrame:
    """Return aggregate stats grouped by region.

    Returns:
        DataFrame with per-region averages for ACS, KD, KAST, etc.
    """
    sql = text("""
        SELECT
            p.region,
            COUNT(DISTINCT p.player_id)  AS player_count,
            AVG(ps.acs)                  AS avg_acs,
            AVG(ps.kd_ratio)             AS avg_kd,
            AVG(ps.kast)                 AS avg_kast,
            AVG(ps.kills)                AS avg_kills,
            AVG(ps.adr)                  AS avg_adr,
            AVG(ps.first_kills)          AS avg_first_kills
        FROM players p
        JOIN player_stats ps ON p.player_id = ps.player_id
        GROUP BY p.region
        ORDER BY avg_acs DESC
    """)
    return pd.read_sql(sql, engine)


def get_indian_spotlight(engine: Engine) -> pd.DataFrame:
    """Return the top 3 Indian players ranked by ACS.

    Returns:
        DataFrame with player_id, name, team, avg_acs, avg_kd,
        matches_played — limited to 3 rows.
    """
    sql = text("""
        SELECT
            p.player_id,
            p.name,
            p.team,
            AVG(ps.acs)       AS avg_acs,
            AVG(ps.kd_ratio)  AS avg_kd,
            COUNT(*)          AS matches_played
        FROM players p
        JOIN player_stats ps ON p.player_id = ps.player_id
        WHERE LOWER(p.nationality) = 'indian'
           OR LOWER(p.region) = 'india'
        GROUP BY p.player_id, p.name, p.team
        HAVING COUNT(*) >= 5
        ORDER BY avg_acs DESC
        LIMIT 3
    """)
    return pd.read_sql(sql, engine)


def get_dataset_averages(engine: Engine) -> pd.DataFrame:
    """Return overall dataset averages for delta display on dashboards.

    Returns:
        Single-row DataFrame with avg_acs, avg_kd, avg_kast, avg_adr,
        avg_kills, avg_deaths, avg_first_kills.
    """
    sql = text("""
        SELECT
            AVG(acs)          AS avg_acs,
            AVG(kd_ratio)     AS avg_kd,
            AVG(kast)         AS avg_kast,
            AVG(adr)          AS avg_adr,
            AVG(kills)        AS avg_kills,
            AVG(deaths)       AS avg_deaths,
            AVG(first_kills)  AS avg_first_kills
        FROM player_stats
    """)
    return pd.read_sql(sql, engine)
