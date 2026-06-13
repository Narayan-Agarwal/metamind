"""
MetaMind — SQLAlchemy-based database loader.

Upserts cleaned ETL data into the PostgreSQL schema (8 core tables +
2 materialized views). Uses batch commits and raw SQL ``INSERT … ON
CONFLICT UPDATE`` for idempotent loads.

All database access goes through ``db.connection.get_engine()``.
"""

import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.connection import get_engine

logger = logging.getLogger(__name__)

# Ensure logs directory exists
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# Default batch size for commits
_BATCH_SIZE = 1000


# ---------------------------------------------------------------------------
# get_or_create helpers
# ---------------------------------------------------------------------------

def get_or_create_team(
    session: Session,
    name: str,
    region: str | None = None,
) -> int:
    """Return existing team_id or create a new team.

    Args:
        session: Active SQLAlchemy session.
        name: Team name (unique key).
        region: Optional region tag.

    Returns:
        The ``team_id`` of the found or created team.
    """
    row = session.execute(
        text("SELECT team_id FROM teams WHERE name = :name"),
        {"name": name},
    ).fetchone()

    if row:
        return row[0]

    result = session.execute(
        text(
            "INSERT INTO teams (name, region) VALUES (:name, :region) "
            "ON CONFLICT (name) DO UPDATE SET region = COALESCE(EXCLUDED.region, teams.region) "
            "RETURNING team_id"
        ),
        {"name": name, "region": region},
    )
    session.flush()
    return result.fetchone()[0]


def get_or_create_player(
    session: Session,
    name: str,
    team_id: int | None = None,
    region: str | None = None,
    nationality: str | None = None,
    source: str = "kaggle",
) -> int:
    """Return existing player_id or create a new player.

    Args:
        session: Active SQLAlchemy session.
        name: Player name (unique key).
        team_id: Optional FK to teams table.
        region: Optional region tag.
        nationality: Optional nationality tag.
        source: Data source identifier.

    Returns:
        The ``player_id`` of the found or created player.
    """
    row = session.execute(
        text("SELECT player_id FROM players WHERE name = :name"),
        {"name": name},
    ).fetchone()

    if row:
        return row[0]

    result = session.execute(
        text(
            "INSERT INTO players (name, name_normalized, team_id, region, nationality, source) "
            "VALUES (:name, :name_normalized, :team_id, :region, :nationality, :source) "
            "ON CONFLICT (name) DO UPDATE SET "
            "  team_id = COALESCE(EXCLUDED.team_id, players.team_id), "
            "  region = COALESCE(EXCLUDED.region, players.region), "
            "  nationality = COALESCE(EXCLUDED.nationality, players.nationality) "
            "RETURNING player_id"
        ),
        {
            "name": name,
            "name_normalized": name.lower().strip(),
            "team_id": team_id,
            "region": region,
            "nationality": nationality,
            "source": source,
        },
    )
    session.flush()
    return result.fetchone()[0]


def get_or_create_tournament(
    session: Session,
    name: str,
    year: int | None = None,
    region: str | None = None,
    tier: str | None = None,
) -> int:
    """Return existing tournament_id or create a new tournament.

    Args:
        session: Active SQLAlchemy session.
        name: Tournament name.
        year: Tournament year.
        region: Regional tag.
        tier: Tier classification.

    Returns:
        The ``tournament_id``.
    """
    row = session.execute(
        text(
            "SELECT tournament_id FROM tournaments "
            "WHERE name = :name AND (year = :year OR (year IS NULL AND :year IS NULL))"
        ),
        {"name": name, "year": year},
    ).fetchone()

    if row:
        return row[0]

    result = session.execute(
        text(
            "INSERT INTO tournaments (name, year, region, tier) "
            "VALUES (:name, :year, :region, :tier) "
            "RETURNING tournament_id"
        ),
        {"name": name, "year": year, "region": region, "tier": tier},
    )
    session.flush()
    return result.fetchone()[0]


def get_or_create_map(session: Session, map_name: str) -> int:
    """Return existing map_id or create a new map entry.

    Args:
        session: Active SQLAlchemy session.
        map_name: Map name (unique key).

    Returns:
        The ``map_id``.
    """
    row = session.execute(
        text("SELECT map_id FROM maps WHERE map_name = :map_name"),
        {"map_name": map_name},
    ).fetchone()

    if row:
        return row[0]

    result = session.execute(
        text(
            "INSERT INTO maps (map_name) VALUES (:map_name) "
            "ON CONFLICT (map_name) DO NOTHING "
            "RETURNING map_id"
        ),
        {"map_name": map_name},
    )
    session.flush()
    new_row = result.fetchone()
    if new_row:
        return new_row[0]

    # Race condition fallback — re-fetch
    row = session.execute(
        text("SELECT map_id FROM maps WHERE map_name = :map_name"),
        {"map_name": map_name},
    ).fetchone()
    return row[0]


# ---------------------------------------------------------------------------
# Upsert functions
# ---------------------------------------------------------------------------

def upsert_match(session: Session, match_data: dict[str, Any]) -> int:
    """Insert or update a match record.

    Args:
        session: Active SQLAlchemy session.
        match_data: Dictionary with keys matching the ``matches`` table columns.

    Returns:
        The ``match_id``.
    """
    result = session.execute(
        text("""
            INSERT INTO matches
                (tournament_id, team1_id, team2_id, map_id, match_date,
                 winner_team_id, team1_score, team2_score, source)
            VALUES
                (:tournament_id, :team1_id, :team2_id, :map_id, :match_date,
                 :winner_team_id, :team1_score, :team2_score, :source)
            ON CONFLICT (match_id) DO UPDATE SET
                winner_team_id = EXCLUDED.winner_team_id,
                team1_score = EXCLUDED.team1_score,
                team2_score = EXCLUDED.team2_score
            RETURNING match_id
        """),
        match_data,
    )
    session.flush()
    return result.fetchone()[0]


def upsert_player_stats(session: Session, stats_data: dict[str, Any]) -> None:
    """Insert or update a player_stats record.

    Uses ``ON CONFLICT (match_id, player_id) DO UPDATE``.

    Args:
        session: Active SQLAlchemy session.
        stats_data: Dictionary with keys matching the ``player_stats`` columns.
    """
    session.execute(
        text("""
            INSERT INTO player_stats
                (match_id, player_id, kills, deaths, assists, acs,
                 kd_ratio, kast, adr, first_kills, first_deaths,
                 hs_percent, clutch_pct, rating, agent)
            VALUES
                (:match_id, :player_id, :kills, :deaths, :assists, :acs,
                 :kd_ratio, :kast, :adr, :first_kills, :first_deaths,
                 :hs_percent, :clutch_pct, :rating, :agent)
            ON CONFLICT (match_id, player_id) DO UPDATE SET
                kills = EXCLUDED.kills,
                deaths = EXCLUDED.deaths,
                assists = EXCLUDED.assists,
                acs = EXCLUDED.acs,
                kd_ratio = EXCLUDED.kd_ratio,
                kast = EXCLUDED.kast,
                adr = EXCLUDED.adr,
                first_kills = EXCLUDED.first_kills,
                first_deaths = EXCLUDED.first_deaths,
                hs_percent = EXCLUDED.hs_percent,
                clutch_pct = EXCLUDED.clutch_pct,
                rating = EXCLUDED.rating,
                agent = EXCLUDED.agent
        """),
        stats_data,
    )


def upsert_map_results(session: Session, results_data: dict[str, Any]) -> None:
    """Insert or update a map_results record.

    Uses ``ON CONFLICT (match_id, team_id) DO UPDATE``.

    Args:
        session: Active SQLAlchemy session.
        results_data: Dictionary with keys matching the ``map_results`` columns.
    """
    session.execute(
        text("""
            INSERT INTO map_results
                (match_id, team_id, map_id, rounds_won, side_start, outcome)
            VALUES
                (:match_id, :team_id, :map_id, :rounds_won, :side_start, :outcome)
            ON CONFLICT (match_id, team_id) DO UPDATE SET
                rounds_won = EXCLUDED.rounds_won,
                side_start = EXCLUDED.side_start,
                outcome = EXCLUDED.outcome
        """),
        results_data,
    )


def upsert_economy_stats(session: Session, econ_data: dict[str, Any]) -> None:
    """Insert or update an economy_stats record.

    Uses ``ON CONFLICT (match_id, team_id) DO UPDATE``.

    Args:
        session: Active SQLAlchemy session.
        econ_data: Dictionary with keys matching the ``economy_stats`` columns.
    """
    session.execute(
        text("""
            INSERT INTO economy_stats
                (match_id, team_id, map_id, pistol_won, eco_won,
                 semi_eco_won, semi_buy_won, full_buy_won)
            VALUES
                (:match_id, :team_id, :map_id, :pistol_won, :eco_won,
                 :semi_eco_won, :semi_buy_won, :full_buy_won)
            ON CONFLICT (match_id, team_id) DO UPDATE SET
                pistol_won = EXCLUDED.pistol_won,
                eco_won = EXCLUDED.eco_won,
                semi_eco_won = EXCLUDED.semi_eco_won,
                semi_buy_won = EXCLUDED.semi_buy_won,
                full_buy_won = EXCLUDED.full_buy_won
        """),
        econ_data,
    )


def upsert_performance_stats(session: Session, perf_data: dict[str, Any]) -> None:
    """Insert or update a performance_stats record.

    Uses ``ON CONFLICT (match_id, player_id) DO UPDATE``.

    Args:
        session: Active SQLAlchemy session.
        perf_data: Dictionary with keys matching the ``performance_stats`` columns.
    """
    session.execute(
        text("""
            INSERT INTO performance_stats
                (match_id, player_id, map_id, kills_2k, kills_3k,
                 kills_4k, kills_5k, clutch_1v1, clutch_1v2,
                 clutch_1v3, clutch_1v4, clutch_1v5)
            VALUES
                (:match_id, :player_id, :map_id, :kills_2k, :kills_3k,
                 :kills_4k, :kills_5k, :clutch_1v1, :clutch_1v2,
                 :clutch_1v3, :clutch_1v4, :clutch_1v5)
            ON CONFLICT (match_id, player_id) DO UPDATE SET
                kills_2k = EXCLUDED.kills_2k,
                kills_3k = EXCLUDED.kills_3k,
                kills_4k = EXCLUDED.kills_4k,
                kills_5k = EXCLUDED.kills_5k,
                clutch_1v1 = EXCLUDED.clutch_1v1,
                clutch_1v2 = EXCLUDED.clutch_1v2,
                clutch_1v3 = EXCLUDED.clutch_1v3,
                clutch_1v4 = EXCLUDED.clutch_1v4,
                clutch_1v5 = EXCLUDED.clutch_1v5
        """),
        perf_data,
    )


# ---------------------------------------------------------------------------
# Materialized view refresh
# ---------------------------------------------------------------------------

def refresh_views(engine: Engine) -> None:
    """Refresh both materialized views.

    Args:
        engine: SQLAlchemy engine.
    """
    logger.info("Refreshing materialized views …")
    with engine.begin() as conn:
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_player_percentiles"))
        logger.info("  ✓ mv_player_percentiles refreshed")
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_team_map_winrates"))
        logger.info("  ✓ mv_team_map_winrates refreshed")
    logger.info("Materialized view refresh complete")


# ---------------------------------------------------------------------------
# Master load orchestrator
# ---------------------------------------------------------------------------

def _safe_int(value: Any) -> int | None:
    """Safely convert a value to int, returning None on failure."""
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def load_all(
    engine: Engine | None = None,
    etl_data: dict[str, pd.DataFrame] | None = None,
) -> dict[str, int]:
    """Orchestrate all upserts from ETL-cleaned DataFrames.

    Iterates over each dataset, resolves FK references via
    ``get_or_create_*`` helpers, and batch-commits every
    ``_BATCH_SIZE`` rows.

    Args:
        engine: SQLAlchemy engine.  Defaults to ``db.connection.get_engine()``.
        etl_data: Dictionary of cleaned DataFrames from ``etl.run_etl()``.

    Returns:
        Dictionary of ``{table_name: rows_inserted}`` counts.
    """
    if engine is None:
        engine = get_engine()
    if etl_data is None:
        etl_data = {}

    SessionFactory = sessionmaker(bind=engine)
    session: Session = SessionFactory()

    counts: dict[str, int] = {
        "teams": 0,
        "players": 0,
        "tournaments": 0,
        "maps": 0,
        "matches": 0,
        "player_stats": 0,
        "map_results": 0,
        "economy_stats": 0,
        "performance_stats": 0,
    }

    try:
        # --- Player stats datasets ---
        for key, df in etl_data.items():
            if "player_stats" not in key and "overview" not in key:
                continue
            if "player_name" not in df.columns and "player_name_normalized" not in df.columns:
                continue

            logger.info("Loading player stats from: %s (%d rows)", key, len(df))
            name_col = (
                "player_name_normalized"
                if "player_name_normalized" in df.columns
                else "player_name"
            )

            for idx, row in df.iterrows():
                player_name = str(row.get(name_col, "")).strip()
                if not player_name or player_name == "nan":
                    continue

                # Resolve FKs
                team_name = str(row.get("team", "")).strip()
                team_id = None
                if team_name and team_name != "nan":
                    team_id = get_or_create_team(
                        session, team_name,
                        region=row.get("player_region"),
                    )
                    counts["teams"] += 1

                player_id = get_or_create_player(
                    session, player_name,
                    team_id=team_id,
                    region=row.get("player_region"),
                    nationality=row.get("nationality"),
                    source=row.get("source", "kaggle"),
                )
                counts["players"] += 1

                tournament_name = str(row.get("tournament", row.get("source_folder", ""))).strip()
                tournament_id = None
                if tournament_name and tournament_name != "nan":
                    tournament_id = get_or_create_tournament(session, tournament_name)
                    counts["tournaments"] += 1

                map_name = str(row.get("map_name", "")).strip()
                map_id = None
                if map_name and map_name != "nan":
                    map_id = get_or_create_map(session, map_name)
                    counts["maps"] += 1

                # Upsert player stat
                agent = str(row.get("agents", row.get("agent", ""))).strip()
                stats = {
                    "match_id": _safe_int(row.get("match_id")),
                    "player_id": player_id,
                    "kills": _safe_int(row.get("kills")),
                    "deaths": _safe_int(row.get("deaths")),
                    "assists": _safe_int(row.get("assists")),
                    "acs": _safe_float(row.get("acs")),
                    "kd_ratio": _safe_float(row.get("kd_ratio")),
                    "kast": _safe_float(row.get("kast")),
                    "adr": _safe_float(row.get("adr")),
                    "first_kills": _safe_int(row.get("first_kills")),
                    "first_deaths": _safe_int(row.get("first_deaths")),
                    "hs_percent": _safe_float(row.get("hs_percent")),
                    "clutch_pct": _safe_float(row.get("clutch_pct")),
                    "rating": _safe_float(row.get("rating")),
                    "agent": agent if agent and agent != "nan" else None,
                }

                # Only upsert if we have a match_id
                if stats["match_id"] is not None:
                    upsert_player_stats(session, stats)
                    counts["player_stats"] += 1

                # Batch commit
                if (idx + 1) % _BATCH_SIZE == 0:
                    session.commit()
                    logger.info(
                        "  Committed batch at row %d for %s", idx + 1, key,
                    )

            session.commit()
            logger.info("  ✓ Finished %s", key)

        # --- Economy datasets ---
        for key, df in etl_data.items():
            if "economy" not in key.lower() and "eco" not in key.lower():
                continue
            if "Team" not in df.columns and "team" not in df.columns:
                continue

            logger.info("Loading economy stats from: %s (%d rows)", key, len(df))
            team_col = "Team" if "Team" in df.columns else "team"

            for idx, row in df.iterrows():
                team_name = str(row.get(team_col, "")).strip()
                if not team_name or team_name == "nan":
                    continue

                team_id = get_or_create_team(session, team_name)

                map_name = str(row.get("map", row.get("map_name", row.get("Map", "")))).strip()
                map_id = None
                if map_name and map_name != "nan":
                    map_id = get_or_create_map(session, map_name)

                econ = {
                    "match_id": _safe_int(row.get("match_id")),
                    "team_id": team_id,
                    "map_id": map_id,
                    "pistol_won": _safe_int(row.get("Pistol Won", row.get("pistol_won"))),
                    "eco_won": _safe_int(row.get("Eco (won)", row.get("eco_won"))),
                    "semi_eco_won": _safe_int(row.get("Semi-eco (won)", row.get("semi_eco_won"))),
                    "semi_buy_won": _safe_int(row.get("Semi-buy (won)", row.get("semi_buy_won"))),
                    "full_buy_won": _safe_int(row.get("Full buy(won)", row.get("full_buy_won"))),
                }

                if econ["match_id"] is not None:
                    upsert_economy_stats(session, econ)
                    counts["economy_stats"] += 1

                if (idx + 1) % _BATCH_SIZE == 0:
                    session.commit()

            session.commit()
            logger.info("  ✓ Finished %s", key)

        # --- Performance datasets ---
        for key, df in etl_data.items():
            if "performance" not in key.lower() and "kills_stats" not in key.lower():
                continue

            logger.info("Loading performance stats from: %s (%d rows)", key, len(df))

            for idx, row in df.iterrows():
                player_name = str(
                    row.get("Player", row.get("player_name", row.get("player_name_normalized", "")))
                ).strip()
                if not player_name or player_name == "nan":
                    continue

                player_id = get_or_create_player(session, player_name)

                map_name = str(row.get("Map", row.get("map_name", ""))).strip()
                map_id = None
                if map_name and map_name != "nan":
                    map_id = get_or_create_map(session, map_name)

                perf = {
                    "match_id": _safe_int(row.get("match_id", row.get("Match ID"))),
                    "player_id": player_id,
                    "map_id": map_id,
                    "kills_2k": _safe_int(row.get("2K", row.get("2k"))),
                    "kills_3k": _safe_int(row.get("3K", row.get("3k"))),
                    "kills_4k": _safe_int(row.get("4K", row.get("4k"))),
                    "kills_5k": _safe_int(row.get("5K", row.get("5k"))),
                    "clutch_1v1": _safe_int(row.get("1v1")),
                    "clutch_1v2": _safe_int(row.get("1v2")),
                    "clutch_1v3": _safe_int(row.get("1v3")),
                    "clutch_1v4": _safe_int(row.get("1v4")),
                    "clutch_1v5": _safe_int(row.get("1v5")),
                }

                if perf["match_id"] is not None:
                    upsert_performance_stats(session, perf)
                    counts["performance_stats"] += 1

                if (idx + 1) % _BATCH_SIZE == 0:
                    session.commit()

            session.commit()
            logger.info("  ✓ Finished %s", key)

        # --- Refresh materialized views ---
        try:
            refresh_views(engine)
        except Exception:
            logger.exception("Failed to refresh materialized views — data is loaded but views are stale")

    except Exception:
        session.rollback()
        logger.exception("Database load failed — transaction rolled back")
        raise
    finally:
        session.close()

    # --- Summary ---
    logger.info("=" * 60)
    logger.info("Database load summary:")
    for table, count in counts.items():
        logger.info("  %-25s %8d operations", table, count)
    logger.info("=" * 60)

    return counts
