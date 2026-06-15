"""
MetaMind — SQL query layer.

Every public function accepts a SQLAlchemy ``Engine`` (plus optional
filter parameters), executes a parameterised query via :func:`pandas.read_sql`,
and returns a :class:`pandas.DataFrame`.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


# =========================================================================
# Lookup / reference tables
# =========================================================================

def get_all_players(engine: Engine) -> pd.DataFrame:
    sql = text("""
        SELECT p.player_id, p.name, t.name AS team, p.region
        FROM players p
        LEFT JOIN teams t ON p.team_id = t.team_id
        ORDER BY p.name
    """)
    return pd.read_sql(sql, engine)


def get_all_teams(engine: Engine) -> pd.DataFrame:
    sql = text("""
        SELECT team_id, name, region
        FROM teams
        ORDER BY name
    """)
    return pd.read_sql(sql, engine)


def get_all_tournaments(engine: Engine) -> pd.DataFrame:
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
            ps.hs_percent,
            ps.rating,
            m.match_date,
            m.tournament_id,
            m.map_id,
            mp.map_name
        FROM player_stats ps
        JOIN matches m ON ps.match_id = m.match_id
        LEFT JOIN maps mp ON m.map_id = mp.map_id
        WHERE {where_clause}
        ORDER BY m.match_date
    """)

    return pd.read_sql(sql, engine, params=params)


def get_player_form(
    engine: Engine,
    player_id: int,
    window: int = 10,
) -> pd.DataFrame:
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
    sql = text("""
        SELECT *
        FROM mv_player_percentiles
        WHERE player_id = :player_id
    """)
    return pd.read_sql(sql, engine, params={"player_id": player_id})


def get_all_percentiles(engine: Engine) -> pd.DataFrame:
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
            AVG(ps.adr)                       AS avg_adr
        FROM player_stats ps
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
    conditions = ["(m.team1_id = :team_id OR m.team2_id = :team_id)"]
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
            AVG(CASE WHEN m.team1_id = :team_id THEN m.team1_score
                     ELSE m.team2_score END)                             AS avg_rounds_won,
            AVG(CASE WHEN m.team1_id = :team_id THEN m.team2_score
                     ELSE m.team1_score END)                             AS avg_rounds_lost
        FROM matches m
        WHERE {where_clause}
    """)

    return pd.read_sql(sql, engine, params=params)


def get_team_map_winrates(engine: Engine, team_id: int) -> pd.DataFrame:
    sql = text("""
        SELECT *
        FROM mv_team_map_winrates
        WHERE team_id = :team_id
        ORDER BY win_pct DESC
    """)
    return pd.read_sql(sql, engine, params={"team_id": team_id})


def get_team_economy(
    engine: Engine,
    team_id: int,
    tournament_id: int | None = None,
) -> pd.DataFrame:
    conditions = ["es.team_id = :team_id"]
    params: dict = {"team_id": team_id}

    if tournament_id is not None:
        conditions.append("m.tournament_id = :tournament_id")
        params["tournament_id"] = tournament_id

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            mp.map_name,
            AVG(es.pistol_won)       AS pistol_win_pct,
            AVG(es.eco_won)          AS eco_win_pct,
            AVG(es.full_buy_won)     AS full_buy_win_pct,
            AVG(es.semi_buy_won)     AS semi_buy_win_pct,
            AVG(es.semi_eco_won)     AS semi_eco_win_pct,
            COUNT(*)                 AS matches_played
        FROM economy_stats es
        JOIN matches m ON es.match_id = m.match_id
        LEFT JOIN maps mp ON es.map_id = mp.map_id
        WHERE {where_clause}
        GROUP BY mp.map_name
        ORDER BY mp.map_name
    """)

    return pd.read_sql(sql, engine, params=params)


def get_team_players(engine: Engine, team_id: int) -> pd.DataFrame:
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
    # Whitelist sort columns to prevent SQL injection
    allowed_sort = {
        "avg_acs", "avg_kd", "avg_kills", "avg_kast",
        "avg_fb", "avg_hs", "consistency_score", "matches_played",
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
        WHERE p.region IS NOT NULL
        GROUP BY p.region
        ORDER BY avg_acs DESC
    """)
    return pd.read_sql(sql, engine)


def get_indian_spotlight(engine: Engine) -> pd.DataFrame:
    sql = text("""
        SELECT
            p.player_id,
            p.name,
            t.name AS team,
            AVG(ps.acs)       AS avg_acs,
            AVG(ps.kd_ratio)  AS avg_kd,
            COUNT(*)          AS matches_played
        FROM players p
        LEFT JOIN teams t ON p.team_id = t.team_id
        JOIN player_stats ps ON p.player_id = ps.player_id
        WHERE LOWER(p.nationality) = 'indian'
           OR LOWER(p.region) = 'india'
        GROUP BY p.player_id, p.name, t.name
        HAVING COUNT(*) >= 5
        ORDER BY avg_acs DESC
        LIMIT 3
    """)
    return pd.read_sql(sql, engine)


def get_dataset_averages(engine: Engine) -> pd.DataFrame:
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
