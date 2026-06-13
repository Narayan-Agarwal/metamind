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


def load_family_a(data_root: Path) -> dict[str, pd.DataFrame]:
    """Load all Family A datasets (vct_2021 … vct_2026).

    Args:
        data_root: Absolute path to the MetaMind project root.

    Returns:
        Dictionary keyed by ``"{folder}_{file_key}"`` → DataFrame.
        Missing / unreadable files are silently skipped.
    """
    config = _load_config(data_root)
    chunk_size: int = config.get("etl", {}).get("chunk_size", 50_000)
    folders: list[str] = config.get("data", {}).get("family_a_folders", [])

    result: dict[str, pd.DataFrame] = {}

    for folder_rel in folders:
        folder_path = data_root / folder_rel
        folder_name = folder_path.name  # e.g. "vct_2024"

        if not folder_path.is_dir():
            logger.warning("Family A folder missing: %s", folder_path)
            continue

        logger.info("Loading Family A folder: %s", folder_name)

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
                        "Filtered %s overview Side='both': %d → %d rows",
                        folder_name,
                        before,
                        len(df),
                    )

                # Tag with the source folder year
                df["source_folder"] = folder_name
                result[f"{folder_name}_{key}"] = df

    logger.info("Family A load complete — %d datasets", len(result))
    return result


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


def load_family_c(data_root: Path) -> dict[str, pd.DataFrame]:
    """Load all Family C datasets (CT2024 folders + root-level CSVs).

    Args:
        data_root: Absolute path to the MetaMind project root.

    Returns:
        Dictionary keyed by ``"{source}_{file_key}"`` → DataFrame.
    """
    config = _load_config(data_root)
    folders: list[str] = config.get("data", {}).get("family_c_folders", [])
    root_csv_dir: str = config.get("data", {}).get("family_c_root", "data/")

    result: dict[str, pd.DataFrame] = {}

    # --- CT2024 sub-folders ---
    for folder_rel in folders:
        folder_path = data_root / folder_rel
        folder_label = folder_path.name

        if not folder_path.is_dir():
            logger.warning("Family C folder missing: %s", folder_path)
            continue

        logger.info("Loading Family C folder: %s", folder_label)
        result.update(_load_family_c_folder(folder_path, folder_label))

    # --- Root-level CSVs (VCT Champions 2025 Paris) ---
    root_path = data_root / root_csv_dir
    if root_path.is_dir():
        logger.info("Loading Family C root-level CSVs from: %s", root_path)
        result.update(_load_family_c_folder(root_path, "vct_champions_2025_root"))
    else:
        logger.warning("Family C root CSV directory missing: %s", root_path)

    logger.info("Family C load complete — %d datasets", len(result))
    return result


# ---------------------------------------------------------------------------
# Combined loader
# ---------------------------------------------------------------------------

def load_all(data_root: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Load all datasets from both families.

    Args:
        data_root: Project root path.  Defaults to two levels up from this file.

    Returns:
        Combined dictionary of all loaded DataFrames.
    """
    if data_root is None:
        data_root = Path(__file__).resolve().parent.parent
    data_root = Path(data_root)

    logger.info("Starting full data load from: %s", data_root)

    combined: dict[str, pd.DataFrame] = {}
    combined.update(load_family_a(data_root))
    combined.update(load_family_c(data_root))

    logger.info(
        "Full load complete — %d total datasets, %d total rows",
        len(combined),
        sum(len(df) for df in combined.values()),
    )
    return combined
