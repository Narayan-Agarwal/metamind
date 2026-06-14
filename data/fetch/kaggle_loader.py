"""
MetaMind — Kaggle dataset loader for Valorant esports CSV data.

Reads two dataset families from local folders:
  - Family A: vct_2021 through vct_2026 (nested folder structure)
  - Family C: Champions Tour 2024 folders + root-level VCT Champions 2025 CSVs

All folder paths are read from config.yaml.
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_config(project_root: Path | None = None) -> dict[str, Any]:
    """Load config.yaml from the project root.

    Args:
        project_root: Absolute path to the MetaMind project directory.
                      Defaults to two levels up from this file.

    Returns:
        Parsed YAML configuration dictionary.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config.yaml"
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Family A — vct_2021 … vct_2026
# ---------------------------------------------------------------------------

_FAMILY_A_FILES: dict[str, str] = {
    "players_stats": "players_stats/players_stats.csv",
    "overview": "matches/overview.csv",
    "scores": "matches/scores.csv",
    "maps_scores": "matches/maps_scores.csv",
    "eco_stats": "matches/eco_stats.csv",
    "kills_stats": "matches/kills_stats.csv",
    "tournament_ids": "ids/tournaments_stages_matches_games_ids.csv",
    "player_ids": "ids/players_ids.csv",
    "team_ids": "ids/teams_ids.csv",
}


def _read_csv_safe(
    path: Path,
    *,
    chunksize: int | None = None,
) -> pd.DataFrame | None:
    """Read a CSV, returning ``None`` on missing file / parse error.

    For large files, pass *chunksize* to read in chunks and concatenate.
    """
    if not path.exists():
        logger.warning("File not found, skipping: %s", path)
        return None
    try:
        if chunksize:
            chunks: list[pd.DataFrame] = []
            for chunk in pd.read_csv(path, chunksize=chunksize, low_memory=False):
                chunks.append(chunk)
            if not chunks:
                logger.warning("Empty file (no chunks): %s", path)
                return None
            df = pd.concat(chunks, ignore_index=True)
            logger.info(
                "Loaded %s in chunks (%d rows)", path.name, len(df),
            )
            return df
        df = pd.read_csv(path, low_memory=False)
        logger.info("Loaded %s (%d rows)", path.name, len(df))
        return df
    except Exception:
        logger.exception("Error reading %s", path)
        return None


def yield_family_a(data_root: Path):
    """Yield Family A datasets (vct_2021 … vct_2026) one folder at a time.

    Args:
        data_root: Absolute path to the MetaMind project root.

    Yields:
        Tuple of (folder_name, dict_of_dataframes).
    """
    config = _load_config(data_root)
    chunk_size: int = config.get("etl", {}).get("chunk_size", 50_000)
    folders: list[str] = config.get("data", {}).get("family_a_folders", [])

    for folder_rel in folders:
        folder_path = data_root / folder_rel
        folder_name = folder_path.name  # e.g. "vct_2024"

        if not folder_path.is_dir():
            logger.warning("Family A folder missing: %s", folder_path)
            continue

        logger.info("Loading Family A folder: %s", folder_name)
        result: dict[str, pd.DataFrame] = {}

        for key, rel_csv in _FAMILY_A_FILES.items():
            csv_path = folder_path / rel_csv

            # overview.csv is 100 MB+; use chunked reading
            use_chunks = key == "overview"
            df = _read_csv_safe(
                csv_path,
                chunksize=chunk_size if use_chunks else None,
            )
            if df is not None:
                # Filter overview to Side='both' for totals only
                if key == "overview" and "Side" in df.columns:
                    before = len(df)
                    df = df[df["Side"] == "both"].copy()
                    logger.info(
                        "Filtered %s overview Side='both': %d -> %d rows",
                        folder_name,
                        before,
                        len(df),
                    )

                # Tag with the source folder year
                df["source_folder"] = folder_name
                result[f"{folder_name}_{key}"] = df

        # --- Merge Match ID into Family A match-level datasets ---
        ids_key = f"{folder_name}_tournament_ids"
        if ids_key in result:
            ids_df = result[ids_key]
            join_cols = ["Tournament", "Stage", "Match Type", "Match Name", "Map"]
            # Get unique mapping of match IDs
            if all(c in ids_df.columns for c in join_cols + ["Match ID"]):
                mapping_df = ids_df[join_cols + ["Match ID"]].drop_duplicates()
                
                # Merge into overview
                ov_key = f"{folder_name}_overview"
                if ov_key in result:
                    result[ov_key] = pd.merge(result[ov_key], mapping_df, on=join_cols, how="left")
                    logger.info("Merged Match ID into %s", ov_key)
                
                # Merge into eco_stats
                eco_key = f"{folder_name}_eco_stats"
                if eco_key in result:
                    # eco_stats doesn't always have Map, wait! The spec says it has: Tournament,Stage,Match Type,Match Name,Map,Team...
                    # So we can use the same join cols.
                    result[eco_key] = pd.merge(result[eco_key], mapping_df, on=join_cols, how="left")
                    logger.info("Merged Match ID into %s", eco_key)

                # Merge into kills_stats
                kills_key = f"{folder_name}_kills_stats"
                if kills_key in result:
                    result[kills_key] = pd.merge(result[kills_key], mapping_df, on=join_cols, how="left")
                    logger.info("Merged Match ID into %s", kills_key)

        yield folder_name, result


# ---------------------------------------------------------------------------
# Family C — Champions Tour 2024 folders + root-level CSVs
# ---------------------------------------------------------------------------

_FAMILY_C_FILES: dict[str, str] = {
    "player_stats": "player_stats.csv",
    "detailed_player_stats": "detailed_matches_player_stats.csv",
    "matches": "matches.csv",
    "detailed_maps": "detailed_matches_maps.csv",
    "economy": "economy_data.csv",
    "performance": "performance_data.csv",
    "event_info": "event_info.csv",
}


def _load_family_c_folder(
    folder_path: Path,
    folder_label: str,
) -> dict[str, pd.DataFrame]:
    """Read all Family C CSVs from a single folder.

    Args:
        folder_path: Absolute path to the folder containing CSVs.
        folder_label: Human-readable label for logging / dict keys.

    Returns:
        Dictionary keyed by ``"{folder_label}_{file_key}"`` → DataFrame.
    """
    result: dict[str, pd.DataFrame] = {}

    for key, filename in _FAMILY_C_FILES.items():
        csv_path = folder_path / filename
        df = _read_csv_safe(csv_path)
        if df is not None:
            df["source_folder"] = folder_label
            result[f"{folder_label}_{key}"] = df

    return result


def yield_family_c(data_root: Path):
    """Yield Family C datasets (CT2024 folders + root-level CSVs) one folder at a time.

    Args:
        data_root: Absolute path to the MetaMind project root.

    Yields:
        Tuple of (folder_name, dict_of_dataframes).
    """
    config = _load_config(data_root)
    folders: list[str] = config.get("data", {}).get("family_c_folders", [])
    root_csv_dir: str = config.get("data", {}).get("family_c_root", "data/")

    # --- CT2024 sub-folders ---
    for folder_rel in folders:
        folder_path = data_root / folder_rel
        folder_label = folder_path.name

        if not folder_path.is_dir():
            logger.warning("Family C folder missing: %s", folder_path)
            continue

        logger.info("Loading Family C folder: %s", folder_label)
        yield folder_label, _load_family_c_folder(folder_path, folder_label)

    # --- Root-level CSVs (VCT Champions 2025 Paris) ---
    root_path = data_root / root_csv_dir
    if root_path.is_dir():
        logger.info("Loading Family C root-level CSVs from: %s", root_path)
        yield "vct_champions_2025_root", _load_family_c_folder(root_path, "vct_champions_2025_root")
    else:
        logger.warning("Family C root CSV directory missing: %s", root_path)


# ---------------------------------------------------------------------------
# Combined loader
# ---------------------------------------------------------------------------

def yield_all_folders(data_root: Path | str | None = None):
    """Yield all datasets from both families folder by folder.

    Args:
        data_root: Project root path.  Defaults to two levels up from this file.

    Yields:
        Tuple of (folder_name, dictionary_of_dataframes).
    """
    if data_root is None:
        data_root = Path(__file__).resolve().parent.parent
    data_root = Path(data_root)

    logger.info("Starting streaming data load from: %s", data_root)

    yield from yield_family_a(data_root)
    yield from yield_family_c(data_root)


def load_single_folder(
    folder_name: str,
    data_root: Path | str | None = None,
) -> dict[str, pd.DataFrame]:
    """Load a specific dataset folder by name.

    Args:
        folder_name: The target folder to load (e.g. 'vct_2021').
        data_root: Project root path.

    Returns:
        Dictionary of loaded DataFrames.
    """
    if data_root is None:
        data_root = Path(__file__).resolve().parent.parent
    data_root = Path(data_root)
    
    # Try yielding from Family A
    for name, dfs in yield_family_a(data_root):
        if name == folder_name:
            return dfs
            
    # Try yielding from Family C
    for name, dfs in yield_family_c(data_root):
        if name == folder_name:
            return dfs
            
    logger.warning("Folder %s not found in Family A or C", folder_name)
    return {}
