"""
MetaMind -- SQLAlchemy-based database loader (v2 - bulk).

Eliminates per-row DB round-trips by pre-loading all entity caches
in bulk SELECTs, then using raw connection.execute() with explicit
transaction boundaries and batched multi-row INSERTs.

All database access goes through ``db.connection.get_engine()``.
"""

import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from db.connection import get_engine

logger = logging.getLogger(__name__)

# Ensure logs directory exists
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# Batch size for commits (smaller = less chance of Neon timeout)
_BATCH_SIZE = 500

# Sleep between batches to avoid overwhelming Neon connection pooler
_BATCH_SLEEP = 1.0


# ---------------------------------------------------------------------------
# In-memory caches (populated by _preload_caches, updated on insert)
# ---------------------------------------------------------------------------
_team_cache: dict[str, int] = {}       # name -> team_id
_player_cache: dict[str, int] = {}     # name -> player_id
_tournament_cache: dict[str, int] = {} # name -> tournament_id
_map_cache: dict[str, int] = {}        # map_name -> map_id
_match_cache: set[int] = set()         # set of known match_ids


def _preload_caches(conn) -> None:
    """Bulk-load all existing entities into Python dicts with one SELECT each."""
    global _team_cache, _player_cache, _tournament_cache, _map_cache, _match_cache

    _team_cache = {}
    rows = conn.execute(text("SELECT team_id, name FROM teams")).fetchall()
    for row in rows:
        _team_cache[row[1]] = row[0]
    logger.info("Pre-loaded %d teams into cache", len(_team_cache))

    _player_cache = {}
    rows = conn.execute(text("SELECT player_id, name FROM players")).fetchall()
    for row in rows:
        _player_cache[row[1]] = row[0]
    logger.info("Pre-loaded %d players into cache", len(_player_cache))

    _tournament_cache = {}
    rows = conn.execute(text("SELECT tournament_id, name FROM tournaments")).fetchall()
    for row in rows:
        _tournament_cache[row[1]] = row[0]
    logger.info("Pre-loaded %d tournaments into cache", len(_tournament_cache))

    _map_cache = {}
    rows = conn.execute(text("SELECT map_id, map_name FROM maps")).fetchall()
    for row in rows:
        _map_cache[row[1]] = row[0]
    logger.info("Pre-loaded %d maps into cache", len(_map_cache))

    _match_cache = set()
    rows = conn.execute(text("SELECT match_id FROM matches")).fetchall()
    for row in rows:
        _match_cache.add(row[0])
    logger.info("Pre-loaded %d matches into cache", len(_match_cache))


# ---------------------------------------------------------------------------
# Bulk-insert helpers for dimension tables
# Each opens its own short transaction, inserts, commits, closes.
# ---------------------------------------------------------------------------

def _ensure_teams(conn, names: set[str]) -> None:
    """Insert any teams not already in cache. Updates cache with new IDs."""
    new_names = [n for n in names if n and n != "nan" and n not in _team_cache]
    if not new_names:
        return

    for batch_start in range(0, len(new_names), _BATCH_SIZE):
        batch = new_names[batch_start:batch_start + _BATCH_SIZE]
        params = [{"name": n, "region": None} for n in batch]
        conn.execute(
            text(
                "INSERT INTO teams (name, region) VALUES (:name, :region) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            params,
        )
        conn.commit()

    # Re-fetch all to get IDs (including pre-existing)
    rows = conn.execute(text("SELECT team_id, name FROM teams")).fetchall()
    for row in rows:
        _team_cache[row[1]] = row[0]
    logger.info("Teams cache now has %d entries", len(_team_cache))


def _ensure_players(conn, names: set[str]) -> None:
    """Insert any players not already in cache. Updates cache with new IDs."""
    new_names = [n for n in names if n and n != "nan" and n not in _player_cache]
    if not new_names:
        return

    for batch_start in range(0, len(new_names), _BATCH_SIZE):
        batch = new_names[batch_start:batch_start + _BATCH_SIZE]
        params = [
            {"name": n, "name_normalized": n.lower().strip(), "source": "kaggle"}
            for n in batch
        ]
        conn.execute(
            text(
                "INSERT INTO players (name, name_normalized, source) "
                "VALUES (:name, :name_normalized, :source) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            params,
        )
        conn.commit()

    rows = conn.execute(text("SELECT player_id, name FROM players")).fetchall()
    for row in rows:
        _player_cache[row[1]] = row[0]
    logger.info("Players cache now has %d entries", len(_player_cache))


def _ensure_tournaments(conn, names: set[str]) -> None:
    """Insert any tournaments not already in cache. Updates cache with new IDs."""
    new_names = [n for n in names if n and n != "nan" and n not in _tournament_cache]
    if not new_names:
        return

    for batch_start in range(0, len(new_names), _BATCH_SIZE):
        batch = new_names[batch_start:batch_start + _BATCH_SIZE]
        params = [{"name": n} for n in batch]
        conn.execute(
            text(
                "INSERT INTO tournaments (name) VALUES (:name) "
                "ON CONFLICT DO NOTHING"
            ),
            params,
        )
        conn.commit()

    rows = conn.execute(text("SELECT tournament_id, name FROM tournaments")).fetchall()
    for row in rows:
        _tournament_cache[row[1]] = row[0]
    logger.info("Tournaments cache now has %d entries", len(_tournament_cache))


def _ensure_maps(conn, names: set[str]) -> None:
    """Insert any maps not already in cache. Updates cache with new IDs."""
    new_names = [n for n in names if n and n != "nan" and n not in _map_cache]
    if not new_names:
        return

    for batch_start in range(0, len(new_names), _BATCH_SIZE):
        batch = new_names[batch_start:batch_start + _BATCH_SIZE]
        params = [{"map_name": n} for n in batch]
        conn.execute(
            text(
                "INSERT INTO maps (map_name) VALUES (:map_name) "
                "ON CONFLICT (map_name) DO NOTHING"
            ),
            params,
        )
        conn.commit()

    rows = conn.execute(text("SELECT map_id, map_name FROM maps")).fetchall()
    for row in rows:
        _map_cache[row[1]] = row[0]
    logger.info("Maps cache now has %d entries", len(_map_cache))


def _ensure_matches(conn, match_ids: set[int], tournament_lookup: dict[int, int | None]) -> None:
    """Insert placeholder matches for any match_ids not in cache."""
    new_ids = [mid for mid in match_ids if mid not in _match_cache]
    if not new_ids:
        return

    for batch_start in range(0, len(new_ids), _BATCH_SIZE):
        batch = new_ids[batch_start:batch_start + _BATCH_SIZE]
        params = [
            {"match_id": mid, "tournament_id": tournament_lookup.get(mid)}
            for mid in batch
        ]
        conn.execute(
            text(
                "INSERT INTO matches (match_id, tournament_id) "
                "VALUES (:match_id, :tournament_id) "
                "ON CONFLICT (match_id) DO NOTHING"
            ),
            params,
        )
        conn.commit()

    _match_cache.update(new_ids)
    logger.info("Matches cache now has %d entries", len(_match_cache))


# ---------------------------------------------------------------------------
# Safe type converters
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


# ---------------------------------------------------------------------------
# Materialized view refresh
# ---------------------------------------------------------------------------

def refresh_views(engine: Engine) -> None:
    """Refresh both materialized views.

    Args:
        engine: SQLAlchemy engine.
    """
    logger.info("Refreshing materialized views...")
    with engine.connect() as conn:
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_player_percentiles"))
        conn.commit()
        logger.info("  [OK] mv_player_percentiles refreshed")
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_team_map_winrates"))
        conn.commit()
        logger.info("  [OK] mv_team_map_winrates refreshed")
    logger.info("Materialized view refresh complete")


# ---------------------------------------------------------------------------
# Build row dicts from DataFrames (no DB calls, pure Python)
# ---------------------------------------------------------------------------

def _build_player_stats_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a player stats DataFrame into a list of insert-ready dicts."""
    rows = []
    for _, r in df.iterrows():
        match_id_val = _safe_int(r.get("match_id", r.get("Match ID")))
        if match_id_val is None:
            continue

        player_name = str(r.get("player_name_normalized", "")).strip()
        if not player_name or player_name == "nan":
            continue

        player_id = _player_cache.get(player_name)
        if player_id is None:
            continue

        agent = str(r.get("agents", r.get("agent", ""))).strip()

        rows.append({
            "match_id": match_id_val,
            "player_id": player_id,
            "kills": _safe_int(r.get("kills")),
            "deaths": _safe_int(r.get("deaths")),
            "assists": _safe_int(r.get("assists")),
            "acs": _safe_float(r.get("acs")),
            "kd_ratio": _safe_float(r.get("kd_ratio")),
            "kast": _safe_float(r.get("kast")),
            "adr": _safe_float(r.get("adr")),
            "first_kills": _safe_int(r.get("first_kills", r.get("fkpr"))),
            "first_deaths": _safe_int(r.get("first_deaths", r.get("fdpr"))),
            "hs_percent": _safe_float(r.get("hs_percent")),
            "clutch_pct": _safe_float(r.get("clutch_pct")),
            "rating": _safe_float(r.get("rating")),
            "agent": agent if agent and agent != "nan" else None,
        })
    return rows


def _build_economy_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert an economy DataFrame into a list of insert-ready dicts."""
    rows = []
    for _, r in df.iterrows():
        match_id_val = _safe_int(r.get("match_id", r.get("Match ID")))
        if match_id_val is None:
            continue

        team_name = str(r.get("Team", r.get("team", ""))).strip()
        team_id = _team_cache.get(team_name) if team_name and team_name != "nan" else None

        map_name = str(r.get("map", r.get("map_name", r.get("Map", "")))).strip()
        map_id = _map_cache.get(map_name) if map_name and map_name != "nan" else None

        rows.append({
            "match_id": match_id_val,
            "team_id": team_id,
            "map_id": map_id,
            "pistol_won": _safe_int(r.get("Pistol Won", r.get("pistol_won"))),
            "eco_won": _safe_int(r.get("Eco (won)", r.get("eco_won"))),
            "semi_eco_won": _safe_int(r.get("Semi-eco (won)", r.get("semi_eco_won"))),
            "semi_buy_won": _safe_int(r.get("Semi-buy (won)", r.get("semi_buy_won"))),
            "full_buy_won": _safe_int(r.get("Full buy(won)", r.get("full_buy_won"))),
        })
    return rows


def _build_performance_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a performance DataFrame into a list of insert-ready dicts."""
    rows = []
    for _, r in df.iterrows():
        match_id_val = _safe_int(r.get("match_id", r.get("Match ID")))
        if match_id_val is None:
            continue

        player_name = str(r.get("Player", r.get("player_name_normalized", ""))).strip()
        player_id = _player_cache.get(player_name) if player_name and player_name != "nan" else None

        map_name = str(r.get("Map", r.get("map_name", ""))).strip()
        map_id = _map_cache.get(map_name) if map_name and map_name != "nan" else None

        rows.append({
            "match_id": match_id_val,
            "player_id": player_id,
            "map_id": map_id,
            "kills_2k": _safe_int(r.get("2K", r.get("2k"))),
            "kills_3k": _safe_int(r.get("3K", r.get("3k"))),
            "kills_4k": _safe_int(r.get("4K", r.get("4k"))),
            "kills_5k": _safe_int(r.get("5K", r.get("5k"))),
            "clutch_1v1": _safe_int(r.get("1v1", r.get("clutch_1v1"))),
            "clutch_1v2": _safe_int(r.get("1v2", r.get("clutch_1v2"))),
            "clutch_1v3": _safe_int(r.get("1v3", r.get("clutch_1v3"))),
            "clutch_1v4": _safe_int(r.get("1v4", r.get("clutch_1v4"))),
            "clutch_1v5": _safe_int(r.get("1v5", r.get("clutch_1v5"))),
        })
    return rows


# ---------------------------------------------------------------------------
# Batch insert with explicit short transactions
# ---------------------------------------------------------------------------

_PLAYER_STATS_SQL = text("""
    INSERT INTO player_stats
        (match_id, player_id, kills, deaths, assists, acs, kd_ratio,
         kast, adr, first_kills, first_deaths, hs_percent, clutch_pct, rating, agent)
    VALUES
        (:match_id, :player_id, :kills, :deaths, :assists, :acs, :kd_ratio,
         :kast, :adr, :first_kills, :first_deaths, :hs_percent, :clutch_pct, :rating, :agent)
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
        agent = COALESCE(player_stats.agent, EXCLUDED.agent)
""")

_ECONOMY_STATS_SQL = text("""
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
""")

_PERFORMANCE_STATS_SQL = text("""
    INSERT INTO performance_stats
        (match_id, player_id, map_id,
         kills_2k, kills_3k, kills_4k, kills_5k,
         clutch_1v1, clutch_1v2, clutch_1v3, clutch_1v4, clutch_1v5)
    VALUES
        (:match_id, :player_id, :map_id,
         :kills_2k, :kills_3k, :kills_4k, :kills_5k,
         :clutch_1v1, :clutch_1v2, :clutch_1v3, :clutch_1v4, :clutch_1v5)
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
""")


def _batch_execute(engine: Engine, sql_stmt, rows: list[dict], label: str) -> int:
    """Execute INSERT in batches of _BATCH_SIZE with explicit commits and sleeps."""
    total = len(rows)
    inserted = 0

    for batch_start in range(0, total, _BATCH_SIZE):
        batch = rows[batch_start:batch_start + _BATCH_SIZE]
        
        # Grab a fresh connection for just this batch
        with engine.begin() as conn:
            conn.execute(text("SET statement_timeout = '30s'"))
            conn.execute(sql_stmt, batch)
            
        inserted += len(batch)
        logger.info(
            "  %s: committed %d/%d rows",
            label, inserted, total,
        )
        if batch_start + _BATCH_SIZE < total:
            time.sleep(_BATCH_SLEEP)

    return inserted


# ---------------------------------------------------------------------------
# Master load orchestrator
# ---------------------------------------------------------------------------

def load_all(
    engine: Engine | None = None,
    etl_data: dict[str, pd.DataFrame] | None = None,
) -> dict[str, int]:
    """Orchestrate all upserts from ETL-cleaned DataFrames.

    Strategy:
      1. Pre-load all dimension caches in 5 bulk SELECTs
      2. Scan DataFrames to collect unique entity names (pure Python)
      3. Bulk-insert missing dimension rows in short transactions
      4. Build insert-ready row dicts using cached IDs (pure Python)
      5. Batch-insert fact rows with explicit commits and sleeps

    Args:
        engine: SQLAlchemy engine. Defaults to ``db.connection.get_engine()``.
        etl_data: Dictionary of cleaned DataFrames from ``etl.run_etl()``.

    Returns:
        Dictionary of ``{table_name: rows_inserted}`` counts.
    """
    if engine is None:
        engine = get_engine()
    if etl_data is None:
        etl_data = {}

    counts: dict[str, int] = {
        "teams": 0,
        "players": 0,
        "tournaments": 0,
        "maps": 0,
        "matches": 0,
        "player_stats": 0,
        "economy_stats": 0,
        "performance_stats": 0,
    }

    try:
        # ---- Phase 1: Pre-load caches ----
        logger.info("Phase 1: Pre-loading entity caches...")
        with engine.begin() as conn:
            conn.execute(text("SET statement_timeout = '30s'"))
            _preload_caches(conn)

        # ---- Phase 2: Collect unique entity names from all DataFrames ----
        logger.info("Phase 2: Scanning DataFrames for unique entities...")
        all_teams: set[str] = set()
        all_players: set[str] = set()
        all_tournaments: set[str] = set()
        all_maps: set[str] = set()
        all_match_ids: set[int] = set()
        match_tournament_map: dict[int, str] = {}

        for key, df in etl_data.items():
            for col in ["team", "Team"]:
                if col in df.columns:
                    vals = df[col].dropna().astype(str).str.strip().unique()
                    all_teams.update(v for v in vals if v and v != "nan")

            for col in ["player_name_normalized", "player_name", "Player"]:
                if col in df.columns:
                    vals = df[col].dropna().astype(str).str.strip().unique()
                    all_players.update(v for v in vals if v and v != "nan")

            if "tournament" in df.columns:
                vals = df["tournament"].dropna().astype(str).str.strip().unique()
                all_tournaments.update(v for v in vals if v and v != "nan")

            for col in ["map_name", "Map", "map"]:
                if col in df.columns:
                    vals = df[col].dropna().astype(str).str.strip().unique()
                    all_maps.update(v for v in vals if v and v != "nan")

            for col in ["match_id", "Match ID"]:
                if col in df.columns:
                    for _, r in df[[col]].dropna().iterrows():
                        mid = _safe_int(r[col])
                        if mid is not None:
                            all_match_ids.add(mid)

            if "match_id" in df.columns and "tournament" in df.columns:
                for _, r in df[["match_id", "tournament"]].dropna().iterrows():
                    mid = _safe_int(r["match_id"])
                    t = str(r["tournament"]).strip()
                    if mid is not None and t and t != "nan":
                        match_tournament_map[mid] = t

        logger.info(
            "Found: %d teams, %d players, %d tournaments, %d maps, %d matches",
            len(all_teams), len(all_players), len(all_tournaments),
            len(all_maps), len(all_match_ids),
        )

        # ---- Phase 3: Bulk-insert dimension entities ----
        logger.info("Phase 3: Ensuring dimension entities exist...")
        with engine.begin() as conn:
            conn.execute(text("SET statement_timeout = '30s'"))
            _ensure_teams(conn, all_teams)
            counts["teams"] = len(all_teams)

            _ensure_players(conn, all_players)
            counts["players"] = len(all_players)

            _ensure_tournaments(conn, all_tournaments)
            counts["tournaments"] = len(all_tournaments)

            _ensure_maps(conn, all_maps)
            counts["maps"] = len(all_maps)

            match_tid_lookup: dict[int, int | None] = {}
            for mid, tname in match_tournament_map.items():
                match_tid_lookup[mid] = _tournament_cache.get(tname)

            _ensure_matches(conn, all_match_ids, match_tid_lookup)
            counts["matches"] = len(all_match_ids)

        logger.info("All dimensions seeded successfully")

        # ---- Phase 4: Build row dicts (pure Python, no DB) ----
        logger.info("Phase 4: Building insert rows from DataFrames...")

        ps_rows: list[dict] = []
        econ_rows: list[dict] = []
        perf_rows: list[dict] = []

        for key, df in etl_data.items():
            if "player_stats" in key or "overview" in key:
                built = _build_player_stats_rows(df)
                logger.info("  %s: %d player_stats rows built", key, len(built))
                ps_rows.extend(built)

            if "economy_data" in key or "eco_stats" in key:
                built = _build_economy_rows(df)
                logger.info("  %s: %d economy rows built", key, len(built))
                econ_rows.extend(built)

            if "performance_data" in key or "kills_stats" in key:
                built = _build_performance_rows(df)
                logger.info("  %s: %d performance rows built", key, len(built))
                perf_rows.extend(built)

        logger.info(
            "Total rows to insert: %d player_stats, %d economy, %d performance",
            len(ps_rows), len(econ_rows), len(perf_rows),
        )

        # ---- Phase 5: Batch insert fact rows ----
        logger.info("Phase 5: Batch inserting fact rows...")

        if ps_rows:
            n = _batch_execute(engine, _PLAYER_STATS_SQL, ps_rows, "player_stats")
            counts["player_stats"] = n

        if econ_rows:
            n = _batch_execute(engine, _ECONOMY_STATS_SQL, econ_rows, "economy_stats")
            counts["economy_stats"] = n

        if perf_rows:
            n = _batch_execute(engine, _PERFORMANCE_STATS_SQL, perf_rows, "performance_stats")
            counts["performance_stats"] = n

    except Exception:
        logger.exception("Database load failed")
        raise

    # --- Summary ---
    logger.info("=" * 60)
    logger.info("Database load summary:")
    for table, count in counts.items():
        logger.info("  %-25s %8d", table, count)
    logger.info("=" * 60)

    return counts
