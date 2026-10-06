# MetaMind — Esports Analytics Platform

Valorant esports (VCT) analytics platform: season data from Kaggle CSV dumps (VCT 2021–2026, Champions Tour 2024, VCT Champions 2025) through a tested ETL into a normalised PostgreSQL schema, served by a four-page Streamlit dashboard with Plotly charts and one-hour query caching.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon%20compatible-4169E1?logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?logo=streamlit&logoColor=white)
[![CI](https://github.com/Narayan-Agarwal/metamind/actions/workflows/ci.yml/badge.svg)](https://github.com/Narayan-Agarwal/metamind/actions)
![Tests](https://img.shields.io/badge/Tests-24%20passed-brightgreen)
![License](https://img.shields.io/badge/License-MIT-green)

> This is a **personal analytics project built from public esports stat dumps**, not an official
> Valorant/ Riot Games product and not affiliated with VLR.gg.

## The problem

VCT match and player statistics are published as per-season Kaggle CSV dumps with inconsistent
schemas, drifted player names and duplicated rows. Turning six seasons of per-match player stats
into stable player profiles — percentile ranks, consistency measures, form and head-to-head
comparisons — needs a cleaning pipeline, a normalised warehouse with window-function views, and a
dashboard on top. MetaMind is that stack, small enough to run on a laptop.

## Architecture

```mermaid
flowchart LR
    A["Kaggle season CSVs<br/>vct_2021 … vct_2026 folders,<br/>Champions Tour 2024 folders,<br/>VCT Champions 2025 root CSVs<br/>(downloaded locally)"] -->|"normalise → clean →<br/>dedup → validate"| B["ETL pipeline<br/>data/etl.py → data/db_loader.py<br/>SQLAlchemy batch upserts<br/>(ON CONFLICT)"]
    C["VLR.gg South Asia event stats<br/>(optional, --full mode,<br/>requests + BeautifulSoup)"] --> B
    B --> D["PostgreSQL (Neon compatible)<br/>9 tables + 2 materialized views:<br/>mv_player_percentiles,<br/>mv_team_map_winrates"]
    D --> E["Streamlit dashboard<br/>4 pages · Plotly<br/>st.cache_data(ttl=3600)"]
    F["analytics/<br/>consistency · form engine ·<br/>edge score · insights"] --> E
```

**Pipeline:** `python -m data.etl [--full] [--folder vct_2021] [--skip-db] [--limit N]`

- **Schema** (`data/schema.sql`): 9 tables — teams, players, tournaments, maps, matches,
  player_stats, map_results, economy_stats, performance_stats — plus two materialized views
  (`mv_player_percentiles` with `PERCENT_RANK()`, `mv_team_map_winrates`).
- **ETL** (`data/etl.py`, `data/db_loader.py`): chunked CSV reading (overview.csv is 100 MB+),
  name-alias resolution (`data/player_aliases.json`), outlier thresholds from `config.yaml`
  (e.g. ACS ≤ 600), batch upserts keyed on natural ids.
- **Analytics** (`analytics/`): CV-based consistency score (0–100), rolling form engine
  (PEAKING / DECLINING / CONSISTENT), weighted head-to-head edge score, rule-based insight text.
- **Dashboard** (`app.py`, `pages/`): Home, Player Intelligence, Player Comparison,
  Global Leaderboard — every DB call cached for 1 hour (`@st.cache_data(ttl=3600)`).
- **South Asia spotlight**: an optional VLR.gg scraper (`data/fetch/vlr_scraper.py`, run only in
  `--full` mode; event URLs and a 2-second request delay are configured in `config.yaml`).

## How to run locally

Prerequisites: Python 3.11+ and a PostgreSQL database (a [Neon](https://neon.tech) free-tier
database works).

```cmd
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pytest pytest-mock
copy .env.example .env
```

Put your connection string in `.env` as `DB_URL=postgresql://user:password@host/dbname`
(add `?sslmode=require` for Neon — the app also reads `DB_URL` from Streamlit secrets on cloud).

```cmd
psql -f data\schema.sql "<your-db-url>"
.venv\Scripts\python -m data.etl --limit 500
.venv\Scripts\python -m data.etl
.venv\Scripts\python -m pytest -q
.venv\Scripts\streamlit run app.py
```

Notes: the Kaggle CSVs are **not** in this repo — download them locally and lay them out as
`data\vct_<year>\…` / Champions-Tour folders exactly as expected by
`data/fetch/kaggle_loader.py` (all paths come from `config.yaml`). `--limit 500` is a safe first
run; `--full` additionally scrapes VLR.gg. `tests/` needs the database only for nothing — the
suite is isolated with mocks, so it runs without a DB.

## Tests

24 pytest tests across 6 modules (`tests/`), database calls mocked with pytest-mock.
Verified 2026-10-06, local run: **24 passed in ~3 s**. The same suite runs in
[CI](https://github.com/Narayan-Agarwal/metamind/actions) (Python 3.11, `PYTHONPATH=.`).

## Showcase SQL

The dashboard's analytics are SQL-first; the queries live in [`queries/`](queries/) and
[`db/queries.py`](db/queries.py) (16 query functions):

| Purpose | File |
|---|---|
| ACS / KD percentile ranks (`PERCENT_RANK()`) | [`queries/player_percentile.sql`](queries/player_percentile.sql) |
| Rolling 3-match form window | [`queries/player_form_engine.sql`](queries/player_form_engine.sql) |
| Regional leaderboard | [`queries/regional_leaderboard.sql`](queries/regional_leaderboard.sql) |
| Map economy breakdown (conditional aggregation) | [`queries/team_economy_analysis.sql`](queries/team_economy_analysis.sql) |

Example — percentile ranking with an STDDEV-based consistency score:

```sql
WITH base AS (
    SELECT p.player_id, p.name, p.region,
           AVG(ps.acs)      AS avg_acs,
           AVG(ps.kd_ratio) AS avg_kd,
           COUNT(ps.stat_id) AS matches_played,
           100 - (STDDEV(ps.acs) / NULLIF(AVG(ps.acs), 0) * 100) AS consistency_score
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.player_id
    GROUP BY p.player_id, p.name, p.region
    HAVING COUNT(ps.stat_id) >= 5
)
SELECT *, PERCENT_RANK() OVER (ORDER BY avg_acs) AS acs_percentile
FROM base;
```

## Data sources

- **Kaggle VCT season dumps (2021–2026, Champions Tour 2024, VCT Champions 2025)** — downloaded
  locally as CSV files; this repo does not redistribute them. See the datasets' own terms on
  Kaggle.
- **VLR.gg** — event stats pages for the South Asia spotlight, scraped politely (2 s delay,
  descriptive User-Agent) only when `--full` is used. Public pages; see VLR.gg's own terms.

## Limitations

- `economy_stats` and `performance_stats` are populated by the ETL but **excluded from the
  dashboard** because of sparse data quality in the source CSVs; the SQL for them
  ([`queries/team_economy_analysis.sql`](queries/team_economy_analysis.sql)) is kept for
  iteration.
- The APScheduler module (`data/scheduler.py`) exists for automated local ETL runs but is **not
  started automatically** by the app; nothing runs on a schedule in this repo.
- No publicly viewable demo is linked here — the Streamlit Community Cloud URL currently sits
  behind Streamlit's login wall.
- Row counts (players, matches) are intentionally not quoted: they depend on which season dumps
  you load, and nothing in the repo pins a fixed dataset.

## Deployment (Streamlit Community Cloud)

1. The app entrypoint is `app.py` (multipage; pages in `pages/`).
2. At <https://share.streamlit.io> → **New app** → repo, branch `main`, main file `app.py`.
3. In **Settings → Secrets** add (TOML): `DB_URL = "postgresql://...your-connection-string..."`.
4. Deploy. `db/connection.py` reads `st.secrets["DB_URL"]` first, then falls back to `.env`.

## Project structure

```
metamind/
├── app.py                    # Home page
├── pages/
│   ├── 1_Player.py           # Player Intelligence — radar, agent DNA, gauges
│   ├── 2_Team_Map.py         # Player Comparison — radar overlay, stat duel bars
│   └── 3_Leaderboard.py      # Global Leaderboard — scatter map, scoreboard
├── data/
│   ├── schema.sql            # 9 tables + 2 materialized views
│   ├── etl.py                # ETL orchestrator (CLI: --full/--folder/--skip-db/--limit)
│   ├── db_loader.py          # SQLAlchemy batch upsert engine
│   ├── fetch/kaggle_loader.py# Season CSV reader (paths from config.yaml)
│   ├── fetch/vlr_scraper.py  # Optional VLR.gg South Asia scraper
│   └── scheduler.py          # APScheduler runner (local use; not auto-started)
├── db/
│   ├── connection.py         # DB_URL from st.secrets → env fallback
│   └── queries.py            # 16 SQL query functions
├── analytics/                # consistency, form engine, edge score, insights
├── queries/                  # showcase .sql files
├── tests/                    # 24 pytest tests (mocked DB)
├── config.yaml               # scraper URLs, ETL thresholds, data paths
└── .github/workflows/ci.yml  # CI: pytest on Python 3.11
```

## Licence

MIT — see [LICENSE](LICENSE).

*Built by [Narayan Agarwal](https://github.com/Narayan-Agarwal).*
