"""
MetaMind — Master ETL orchestrator.

Normalises, cleans, and validates raw data from Kaggle CSVs and VLR.gg
scrapes, producing DataFrames ready for ``db_loader``.

Usage (CLI)::

    python -m data.etl --full
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from data.fetch.kaggle_loader import yield_all_folders, load_single_folder
from data.fetch.vlr_scraper import scrape_vlr_events

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------

def _load_config(project_root: Path | None = None) -> dict[str, Any]:
    """Load config.yaml from the project root."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config.yaml"
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# 1. normalize_family_a
# ---------------------------------------------------------------------------

# Mapping from verbose Family A column names → unified names
_FAMILY_A_COLUMN_MAP: dict[str, str] = {
    "Average Combat Score": "acs",
    "Kills:Deaths": "kd_ratio",
    "Kill, Assist, Trade, Survive %": "kast",
    "Kill Assist Trade Survive %": "kast",
    "Average Damage Per Round": "adr",
    "Kills Per Round": "kpr",
    "Assists Per Round": "apr",
    "First Kills Per Round": "fkpr",
    "First Deaths Per Round": "fdpr",
    "Headshot %": "hs_percent",
    "Clutch Success %": "clutch_pct",
    "Rating": "rating",
    "Player": "player_name",
    "Teams": "team",
    "Team": "team",
    "Tournament": "tournament",
    "Stage": "stage",
    "Agents": "agents",
    "Rounds Played": "rounds_played",
    "Kills": "kills",
    "Deaths": "deaths",
    "Assists": "assists",
    "First Deaths": "first_deaths",
    "Map": "map_name",
    "Match ID": "match_id",
}


def normalize_family_a(df: pd.DataFrame) -> pd.DataFrame:
    """Rename verbose Family A columns to the unified schema.

    Args:
        df: Raw Family A DataFrame.

    Returns:
        DataFrame with normalised column names.
    """
    rename_map = {
        col: _FAMILY_A_COLUMN_MAP[col]
        for col in df.columns
        if col in _FAMILY_A_COLUMN_MAP
    }
    out = df.rename(columns=rename_map)
    logger.debug(
        "normalize_family_a: renamed %d columns", len(rename_map),
    )
    return out


# ---------------------------------------------------------------------------
# 2. normalize_family_c
# ---------------------------------------------------------------------------

_FAMILY_C_COLUMN_MAP: dict[str, str] = {
    "k": "kills",
    "d": "deaths",
    "a": "assists",
    "fk": "first_kills",
    "fd": "first_deaths",
    "cl_percent": "clutch_pct",
}


def normalize_family_c(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Family C shorthand columns to the unified schema.

    Args:
        df: Raw Family C DataFrame.

    Returns:
        DataFrame with normalised column names.
    """
    rename_map = {
        col: _FAMILY_C_COLUMN_MAP[col]
        for col in df.columns
        if col in _FAMILY_C_COLUMN_MAP
    }
    out = df.rename(columns=rename_map)
    logger.debug(
        "normalize_family_c: renamed %d columns", len(rename_map),
    )
    return out


# ---------------------------------------------------------------------------
# 3. clean_percentages
# ---------------------------------------------------------------------------

_PCT_COLUMNS = [
    "kast", "hs_percent", "clutch_pct", "adr",
    "kd_ratio", "rating", "kpr", "apr", "fkpr", "fdpr",
]


def clean_percentages(df: pd.DataFrame) -> pd.DataFrame:
    """Strip '%' suffixes from percentage columns and convert to float.

    Args:
        df: DataFrame that may contain string percentage values.

    Returns:
        DataFrame with cleaned numeric percentage columns.
    """
    df = df.copy()
    for col in _PCT_COLUMNS:
        if col not in df.columns:
            continue
        if df[col].dtype == object:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.rstrip("%")
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# 4. parse_economy_data
# ---------------------------------------------------------------------------

_ECO_COMPOSITE_RE = re.compile(r"\d+\s*\((\d+)\)")


def _extract_won(value: Any) -> int | None:
    """Extract the 'won' number from composite economy format '4 (2)'.

    - If the value is a plain integer, return it as-is (Pistol Won).
    - If it matches ``N (W)``, extract *W*.
    - Otherwise return None.
    """
    if pd.isna(value):
        return None
    text = str(value).strip()
    match = _ECO_COMPOSITE_RE.search(text)
    if match:
        return int(match.group(1))
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None


def parse_economy_data(df: pd.DataFrame) -> pd.DataFrame:
    """Parse composite economy columns (``'4 (2)'`` → ``2``).

    Family C economy CSVs store Eco/Semi-eco/Semi-buy/Full buy as
    composite strings like ``'4 (2)'`` meaning *total (won)*.
    ``Pistol Won`` is a plain integer and stays as-is.

    Args:
        df: Raw economy DataFrame.

    Returns:
        DataFrame with integer won-counts.
    """
    df = df.copy()
    composite_cols = [
        "Eco (won)", "Semi-eco (won)", "Semi-buy (won)", "Full buy(won)",
    ]
    for col in composite_cols:
        if col in df.columns:
            df[col] = df[col].apply(_extract_won)

    # Pistol Won — straight integer cast
    if "Pistol Won" in df.columns:
        df["Pistol Won"] = pd.to_numeric(df["Pistol Won"], errors="coerce")

    return df


# ---------------------------------------------------------------------------
# 5. clean_names
# ---------------------------------------------------------------------------

def clean_names(
    df: pd.DataFrame,
    aliases_path: Path | str | None = None,
    *,
    name_column: str = "player_name",
) -> pd.DataFrame:
    """Normalise player names using the alias lookup.

    Adds a ``player_name_normalized`` column.

    Args:
        df: DataFrame with a player name column.
        aliases_path: Path to ``player_aliases.json``.
                      Defaults to ``data/player_aliases.json``.
        name_column: Column containing raw player names.

    Returns:
        DataFrame with an added ``player_name_normalized`` column.
    """
    if aliases_path is None:
        aliases_path = Path(__file__).resolve().parent / "player_aliases.json"
    aliases_path = Path(aliases_path)

    aliases: dict[str, str] = {}
    if aliases_path.exists():
        with open(aliases_path, encoding="utf-8") as fh:
            aliases = json.load(fh)
        logger.info("Loaded %d player aliases", len(aliases))
    else:
        logger.warning("Aliases file not found: %s", aliases_path)

    df = df.copy()
    if name_column in df.columns:
        df["player_name_normalized"] = (
            df[name_column]
            .astype(str)
            .str.strip()
            .map(lambda n: aliases.get(n, n))
        )
    return df


# ---------------------------------------------------------------------------
# 6. validate_ranges
# ---------------------------------------------------------------------------

def validate_ranges(
    df: pd.DataFrame,
    project_root: Path | None = None,
) -> pd.DataFrame:
    """Flag or cap outlier values using thresholds from config.yaml.

    Adds an ``outlier_flag`` boolean column.  Values exceeding the
    configured maximum are capped.

    Args:
        df: DataFrame to validate.
        project_root: Path to the MetaMind project root.

    Returns:
        DataFrame with outliers capped and flagged.
    """
    config = _load_config(project_root)
    thresholds = config.get("etl", {}).get("outlier_thresholds", {})
    acs_max: float = float(thresholds.get("acs_max", 600))
    kills_max: float = float(thresholds.get("kills_max", 60))

    df = df.copy()
    df["outlier_flag"] = False

    if "acs" in df.columns:
        acs_numeric = pd.to_numeric(df["acs"], errors="coerce")
        mask = acs_numeric > acs_max
        if mask.any():
            logger.warning(
                "Capping %d rows with ACS > %s", mask.sum(), acs_max,
            )
            df.loc[mask, "outlier_flag"] = True
            df.loc[mask, "acs"] = acs_max

    if "kills" in df.columns:
        kills_numeric = pd.to_numeric(df["kills"], errors="coerce")
        mask = kills_numeric > kills_max
        if mask.any():
            logger.warning(
                "Capping %d rows with kills > %s", mask.sum(), kills_max,
            )
            df.loc[mask, "outlier_flag"] = True
            df.loc[mask, "kills"] = kills_max

    return df


# ---------------------------------------------------------------------------
# 7. tag_nationality
# ---------------------------------------------------------------------------

def tag_nationality(
    df: pd.DataFrame,
    indian_path: Path | str | None = None,
    *,
    name_column: str = "player_name_normalized",
) -> pd.DataFrame:
    """Cross-reference ``indian_players.json`` to tag nationality/region.

    Args:
        df: DataFrame with a normalised player-name column.
        indian_path: Path to ``indian_players.json``.
        name_column: Column to match against.

    Returns:
        DataFrame with ``nationality`` and ``player_region`` columns added
        where a match is found.
    """
    if indian_path is None:
        indian_path = Path(__file__).resolve().parent / "indian_players.json"
    indian_path = Path(indian_path)

    indian_map: dict[str, dict[str, str]] = {}
    if indian_path.exists():
        with open(indian_path, encoding="utf-8") as fh:
            data = json.load(fh)
        for p in data.get("players", []):
            indian_map[p["name"]] = {
                "nationality": p.get("nationality", ""),
                "region": p.get("region", ""),
            }
        logger.info("Loaded %d Indian player entries", len(indian_map))
    else:
        logger.warning("Indian players file not found: %s", indian_path)

    df = df.copy()
    if name_column not in df.columns:
        logger.warning("Column '%s' not in DataFrame; skipping nationality tag", name_column)
        return df

    if "nationality" not in df.columns:
        df["nationality"] = None
    if "player_region" not in df.columns:
        df["player_region"] = None

    for idx, row in df.iterrows():
        name = str(row[name_column]).strip()
        if name in indian_map:
            df.at[idx, "nationality"] = indian_map[name]["nationality"]
            df.at[idx, "player_region"] = indian_map[name]["region"]

    tagged = df["nationality"].notna().sum()
    logger.info("Tagged %d rows with nationality info", tagged)
    return df


# ---------------------------------------------------------------------------
# 8. deduplicate
# ---------------------------------------------------------------------------

def deduplicate(
    df: pd.DataFrame,
    subset: list[str] | None = None,
) -> pd.DataFrame:
    """Drop duplicate rows based on a composite key.

    Args:
        df: DataFrame to deduplicate.
        subset: Columns forming the composite key.  Defaults to
                ``['player_name_normalized', 'tournament', 'stage', 'map_name']``
                (using only columns actually present).

    Returns:
        Deduplicated DataFrame.
    """
    if subset is None:
        subset = [
            "player_name_normalized",
            "tournament",
            "stage",
            "map_name",
            "match_id",
        ]
    
    # We require at least one key column to deduplicate.
    # We will dynamically find which subset columns are actually present.
    key_cols = [c for c in subset if c in df.columns]
    
    if len(key_cols) < 2:
        # If we only have 0 or 1 key column, it's too risky to deduplicate.
        # e.g., we don't want to deduplicate just on "match_id" without player_name,
        # otherwise we delete all but one player from the match.
        logger.debug("Not enough key columns found for deduplication %s — skipping", key_cols)
        return df

    before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    after = len(df)
    if before > after:
        logger.info(
            "Deduplication on %s: %d -> %d rows (%d removed)",
            key_cols, before, after, before - after,
        )
    return df


# ---------------------------------------------------------------------------
# 9. run_etl — master orchestrator
# ---------------------------------------------------------------------------

def process_folder_data(
    raw_data: dict[str, pd.DataFrame],
    data_root: Path,
    aliases_path: Path,
    indian_path: Path,
) -> dict[str, pd.DataFrame]:
    """Clean, normalise, and deduplicate a dictionary of DataFrames."""
    cleaned: dict[str, pd.DataFrame] = {}
    
    # Stage 2: Normalise columns
    for key, df in raw_data.items():
        if any(key.startswith(f"vct_{y}") for y in range(2021, 2027)):
            df = normalize_family_a(df)
        else:
            df = normalize_family_c(df)
        cleaned[key] = df

    # Stage 3: Clean percentages & parse economy
    for key, df in cleaned.items():
        cleaned[key] = clean_percentages(df)
        if "economy" in key.lower() or "eco" in key.lower():
            cleaned[key] = parse_economy_data(cleaned[key])

    # Stage 4: Normalise player names
    for key, df in cleaned.items():
        if "player_name" in df.columns:
            cleaned[key] = clean_names(df, aliases_path)

    # Stage 5: Validate ranges
    for key, df in cleaned.items():
        cleaned[key] = validate_ranges(df, data_root)

    # Stage 6: Tag nationality
    for key, df in cleaned.items():
        if "player_name_normalized" in df.columns:
            cleaned[key] = tag_nationality(df, indian_path)

    # Stage 7: Deduplicate
    for key, df in cleaned.items():
        cleaned[key] = deduplicate(df)

    return cleaned


def run_etl(
    data_root: Path | str | None = None,
    *,
    full: bool = False,
    single_folder: str | None = None,
    skip_db: bool = False,
    limit: int | None = None,
) -> None:
    """Run the streaming ETL pipeline."""
    if data_root is None:
        data_root = Path(__file__).resolve().parent.parent
    data_root = Path(data_root)

    aliases_path = data_root / "data" / "player_aliases.json"
    indian_path = data_root / "data" / "indian_players.json"

    logger.info("=" * 60)
    logger.info("MetaMind ETL pipeline starting (full=%s, folder=%s, limit=%s)", full, single_folder, limit)
    logger.info("=" * 60)

    from data.db_loader import load_all as db_load_all, refresh_views
    from db.connection import get_engine

    engine = get_engine() if not skip_db else None
    total_datasets = 0
    total_rows = 0

    if single_folder:
        logger.info("[Stage 1] Loading specific folder: %s", single_folder)
        raw_data = load_single_folder(single_folder, data_root)
        if not raw_data:
            logger.error("Folder not found or empty.")
            return

        cleaned = process_folder_data(raw_data, data_root, aliases_path, indian_path)

        # Apply row limit if specified
        if limit is not None:
            for k in cleaned:
                if len(cleaned[k]) > limit:
                    logger.info("Limiting %s from %d to %d rows", k, len(cleaned[k]), limit)
                    cleaned[k] = cleaned[k].head(limit)

        total_datasets += len(cleaned)
        total_rows += sum(len(df) for df in cleaned.values())

        if not skip_db:
            logger.info("Loading %s to database...", single_folder)
            db_load_all(engine=engine, etl_data=cleaned)
            
        # Delete references to free memory
        del raw_data
        del cleaned
    else:
        # Full streaming load
        for folder_name, raw_data in yield_all_folders(data_root):
            if not raw_data:
                continue

            cleaned = process_folder_data(raw_data, data_root, aliases_path, indian_path)

            # Apply row limit if specified
            if limit is not None:
                for k in cleaned:
                    if len(cleaned[k]) > limit:
                        logger.info("Limiting %s from %d to %d rows", k, len(cleaned[k]), limit)
                        cleaned[k] = cleaned[k].head(limit)

            total_datasets += len(cleaned)
            total_rows += sum(len(df) for df in cleaned.values())

            if not skip_db:
                logger.info("Loading %s to database...", folder_name)
                db_load_all(engine=engine, etl_data=cleaned)

            # Clear memory
            del raw_data
            del cleaned

        if full:
            logger.info("[Stage 1b] Scraping VLR.gg South Asia events...")
            vlr_df = scrape_vlr_events(data_root)
            if vlr_df is not None and not vlr_df.empty:
                logger.info("VLR.gg: %d rows scraped", len(vlr_df))
                raw_vlr = {"vlr_south_asia": vlr_df}
                cleaned_vlr = process_folder_data(raw_vlr, data_root, aliases_path, indian_path)
                total_datasets += len(cleaned_vlr)
                total_rows += sum(len(df) for df in cleaned_vlr.values())
                
                if not skip_db:
                    logger.info("Loading VLR.gg data to database...")
                    db_load_all(engine=engine, etl_data=cleaned_vlr)
                    
                del raw_vlr
                del cleaned_vlr

    if not skip_db and engine is not None:
        logger.info("Refreshing materialized views...")
        refresh_views(engine)

    logger.info("=" * 60)
    logger.info("ETL pipeline complete — %d datasets, %d total rows", total_datasets, total_rows)
    logger.info("=" * 60)
    print(f"\n[OK] ETL complete. {total_datasets} datasets, {total_rows:,} rows processed.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    """Configure root logger for ETL pipeline."""
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "etl.log", encoding="utf-8"),
        ],
    )


def main() -> None:
    """CLI entry point for the ETL pipeline."""
    import argparse
    parser = argparse.ArgumentParser(
        description="MetaMind ETL pipeline",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline including VLR.gg scraping",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default=None,
        help="Run ETL for a single folder name (e.g. 'vct_2021')",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Project root directory (default: auto-detect)",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip database loading (ETL transform only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit rows per dataset for testing (e.g. --limit 500)",
    )
    args = parser.parse_args()

    _setup_logging()

    data_root = Path(args.data_root) if args.data_root else None
    run_etl(
        data_root, 
        full=args.full, 
        single_folder=args.folder, 
        skip_db=args.skip_db,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
