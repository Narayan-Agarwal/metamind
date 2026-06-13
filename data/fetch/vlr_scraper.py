"""
MetaMind — VLR.gg scraper for South Asia event statistics.

Scrapes player-stat tables from VLR.gg event pages configured in
``config.yaml``.  Uses requests + BeautifulSoup and respects a
configurable per-request delay.
"""

import logging
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def _load_config(project_root: Path | None = None) -> dict[str, Any]:
    """Load config.yaml from the project root."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config.yaml"
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _clean_stat(value: str) -> str:
    """Strip whitespace and trailing '%' from a stat cell value."""
    text = value.strip()
    # Remove trailing '%' so downstream can parse as float
    if text.endswith("%"):
        text = text[:-1].strip()
    return text


def _parse_stats_table(html: str, url: str) -> list[dict[str, Any]]:
    """Parse the main player-stats table from a VLR.gg event stats page.

    VLR.gg stat pages typically render a ``<table>`` with class
    ``wf-table`` or a ``<table>`` inside ``mod-stats``.

    Returns:
        List of row dicts with normalised column names.
    """
    soup = BeautifulSoup(html, "lxml")

    # Locate the stats table — try common selectors
    table: Tag | None = (
        soup.select_one("table.wf-table")
        or soup.select_one("table.mod-stats")
        or soup.find("table")
    )
    if table is None:
        logger.warning("No stats table found on %s", url)
        return []

    # ---- Header ----
    header_row = table.find("thead")
    if header_row is None:
        logger.warning("No <thead> on %s — falling back to first <tr>", url)
        header_row = table.find("tr")

    raw_headers: list[str] = []
    if header_row:
        for th in header_row.find_all(["th", "td"]):
            raw_headers.append(th.get_text(separator=" ", strip=True).lower())

    # Map raw VLR headers → internal column names
    # VLR columns (typical): Player, Org, Agents, Rnd, R, ACS, K:D, KAST,
    # ADR, KPR, APR, FKPR, FDPR, HS%, CL%,  K, D, A, FK, FD
    _HEADER_MAP: dict[str, str] = {
        "player": "player_name",
        "org": "team",
        "agents": "agents",
        "rnd": "rounds",
        "rnds": "rounds",
        "r": "rating",
        "rating": "rating",
        "acs": "acs",
        "k:d": "kd_ratio",
        "k/d": "kd_ratio",
        "kast": "kast",
        "adr": "adr",
        "kpr": "kpr",
        "apr": "apr",
        "fkpr": "fkpr",
        "fdpr": "fdpr",
        "hs%": "hs_percent",
        "hs": "hs_percent",
        "cl%": "clutch_pct",
        "cl": "clutch_pct",
        "k": "kills",
        "d": "deaths",
        "a": "assists",
        "fk": "first_kills",
        "fd": "first_deaths",
    }

    mapped_headers: list[str] = []
    for h in raw_headers:
        mapped = _HEADER_MAP.get(h, h)
        mapped_headers.append(mapped)

    # ---- Body ----
    rows: list[dict[str, Any]] = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 5:
            continue  # skip malformed rows

        values: list[str] = []
        for cell in cells:
            values.append(_clean_stat(cell.get_text(separator=" ", strip=True)))

        # Pad / trim to match header count
        while len(values) < len(mapped_headers):
            values.append("")
        values = values[: len(mapped_headers)]

        row = dict(zip(mapped_headers, values))
        rows.append(row)

    logger.info("Parsed %d player rows from %s", len(rows), url)
    return rows


def scrape_vlr_events(
    project_root: Path | str | None = None,
) -> pd.DataFrame:
    """Scrape VLR.gg South Asia event stat pages.

    URLs, User-Agent, and request delay are read from ``config.yaml``.

    Args:
        project_root: Path to the MetaMind project root.
                      Defaults to two levels up from this file.

    Returns:
        DataFrame of player stats tagged with ``source='vlrgg'``
        and ``region='South Asia'``.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    project_root = Path(project_root)

    config = _load_config(project_root)
    vlr_cfg: dict[str, Any] = config.get("vlr", {})
    event_urls: list[str] = vlr_cfg.get("event_urls", [])
    user_agent: str = vlr_cfg.get(
        "user_agent", "MetaMind Analytics/1.0 (esports research project)",
    )
    delay: float = float(vlr_cfg.get("request_delay_seconds", 2))

    if not event_urls:
        logger.warning("No VLR.gg event URLs configured in config.yaml")
        return pd.DataFrame()

    headers = {"User-Agent": user_agent}
    all_rows: list[dict[str, Any]] = []

    for idx, url in enumerate(event_urls):
        logger.info("Scraping VLR.gg (%d/%d): %s", idx + 1, len(event_urls), url)

        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException:
            logger.exception("Request failed for %s", url)
            continue

        if resp.status_code == 404:
            logger.warning("404 Not Found — skipping: %s", url)
            continue
        if resp.status_code != 200:
            logger.warning(
                "HTTP %d for %s — skipping", resp.status_code, url,
            )
            continue

        rows = _parse_stats_table(resp.text, url)

        # Derive event name from the URL slug
        event_name = _event_name_from_url(url)
        for row in rows:
            row["event_url"] = url
            row["event_name"] = event_name
            row["source"] = "vlrgg"
            row["region"] = "South Asia"

        all_rows.extend(rows)

        # Polite delay between requests
        if idx < len(event_urls) - 1:
            time.sleep(delay)

    if not all_rows:
        logger.warning("No data scraped from any VLR.gg event page")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Convert numeric columns where possible
    _NUMERIC_COLS = [
        "rounds", "rating", "acs", "kd_ratio", "kast", "adr",
        "kpr", "apr", "fkpr", "fdpr", "hs_percent", "clutch_pct",
        "kills", "deaths", "assists", "first_kills", "first_deaths",
    ]
    for col in _NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    logger.info("VLR.gg scrape complete — %d total rows", len(df))
    return df


def _event_name_from_url(url: str) -> str:
    """Extract a human-readable event name from a VLR.gg URL slug.

    Example:
        ``/event/stats/1966/omen-challengers-league-2024-south-asia-split-1``
        → ``'omen challengers league 2024 south asia split 1'``
    """
    match = re.search(r"/event/stats/\d+/(.+)$", url)
    if match:
        return match.group(1).replace("-", " ")
    return url
