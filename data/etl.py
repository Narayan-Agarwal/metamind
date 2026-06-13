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

from data.fetch.kaggle_loader import load_all as load_kaggle_all
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
    "First Kills": "first_kills",
    "First Deaths": "first_deaths",
    "Map": "map_name",
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
    # Only use columns that exist
    key_cols = [c for c in subset if c in df.columns]
    if not key_cols:
        logger.warning("No key columns found for deduplication — skipping")
        return df

    before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    after = len(df)
    logger.info(
        "Deduplication on %s: %d → %d rows (%d removed)",
        key_cols, before, after, before - after,
    )
    return df


# ---------------------------------------------------------------------------
# 9. run_etl — master orchestrator
# ---------------------------------------------------------------------------

def run_etl(
    data_root: Path | str | None = None,
    *,
    full: bool = False,
) -> dict[str, pd.DataFrame]:
    """Run the full ETL pipeline.

    Stages:
        1. Load raw data (Kaggle + optionally VLR.gg)
        2. Normalise column names per family
        3. Clean percentages and economy composites
        4. Normalise player names via aliases
        5. Validate ranges (cap outliers)
        6. Tag nationality
        7. Deduplicate

    Args:
        data_root: Project root path.
        full: If ``True``, also scrape VLR.gg live data.

    Returns:
        Dictionary of cleaned, ready-to-load DataFrames.
    """
    if data_root is None:
        data_root = Path(__file__).resolve().parent.parent
    data_root = Path(data_root)

    aliases_path = data_root / "data" / "player_aliases.json"
    indian_path = data_root / "data" / "indian_players.json"

    logger.info("=" * 60)
    logger.info("MetaMind ETL pipeline starting (full=%s)", full)
    logger.info("=" * 60)

    # --- Stage 1: Load raw data ---
    logger.info("[Stage 1] Loading raw data from Kaggle CSVs …")
    raw_data = load_kaggle_all(data_root)
    logger.info("Loaded %d raw datasets", len(raw_data))

    vlr_df: pd.DataFrame | None = None
    if full:
        logger.info("[Stage 1b] Scraping VLR.gg South Asia events …")
        vlr_df = scrape_vlr_events(data_root)
        logger.info("VLR.gg: %d rows scraped", len(vlr_df))

    # --- Stage 2: Normalise columns ---
    logger.info("[Stage 2] Normalising column names …")
    cleaned: dict[str, pd.DataFrame] = {}
    for key, df in raw_data.items():
        # Determine family by key prefix convention
        if any(key.startswith(f"vct_{y}") for y in range(2021, 2027)):
            df = normalize_family_a(df)
        else:
            df = normalize_family_c(df)
        cleaned[key] = df

    if vlr_df is not None and not vlr_df.empty:
        cleaned["vlr_south_asia"] = vlr_df

    # --- Stage 3: Clean percentages & parse economy ---
    logger.info("[Stage 3] Cleaning percentages and parsing economy data …")
    for key, df in cleaned.items():
        cleaned[key] = clean_percentages(df)
        if "economy" in key.lower() or "eco" in key.lower():
            cleaned[key] = parse_economy_data(cleaned[key])

    # --- Stage 4: Normalise player names ---
    logger.info("[Stage 4] Normalising player names …")
    for key, df in cleaned.items():
        if "player_name" in df.columns:
            cleaned[key] = clean_names(df, aliases_path)

    # --- Stage 5: Validate ranges ---
    logger.info("[Stage 5] Validating value ranges …")
    for key, df in cleaned.items():
        cleaned[key] = validate_ranges(df, data_root)

    # --- Stage 6: Tag nationality ---
    logger.info("[Stage 6] Tagging nationality …")
    for key, df in cleaned.items():
        if "player_name_normalized" in df.columns:
            cleaned[key] = tag_nationality(df, indian_path)

    # --- Stage 7: Deduplicate ---
    logger.info("[Stage 7] Deduplicating …")
    for key, df in cleaned.items():
        cleaned[key] = deduplicate(df)

    total_rows = sum(len(df) for df in cleaned.values())
    logger.info("=" * 60)
    logger.info(
        "ETL pipeline complete — %d datasets, %d total rows",
        len(cleaned), total_rows,
    )
    logger.info("=" * 60)

    return cleaned


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
    parser = argparse.ArgumentParser(
        description="MetaMind ETL pipeline",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline including VLR.gg scraping",
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
    args = parser.parse_args()

    _setup_logging()

    data_root = Path(args.data_root) if args.data_root else None
    result = run_etl(data_root, full=args.full)

    print(f"\n✓ ETL complete. {len(result)} datasets processed.")
    for key, df in sorted(result.items()):
        print(f"  {key}: {len(df):,} rows × {len(df.columns)} cols")

    # Load into database unless --skip-db
    if not args.skip_db:
        print("\nLoading data into database …")
        from data.db_loader import load_all as db_load_all
        counts = db_load_all(etl_data=result)
        print("\n✓ Database load complete.")
        for table, count in counts.items():
            print(f"  {table}: {count:,} operations")


if __name__ == "__main__":
    main()
