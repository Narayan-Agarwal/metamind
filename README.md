# 🧠 MetaMind — Esports Analytics Platform

> Built on the complete 2021–2026 VCT dataset — 916 tracked pros, 14,170+ stat rows, and custom analytics covering ACS percentile rankings, consistency scoring, agent profiling, and a South Asia player spotlight.

[![CI](https://github.com/Narayan-Agarwal/metamind/actions/workflows/ci.yml/badge.svg)](https://github.com/Narayan-Agarwal/metamind/actions)
[![Streamlit](https://img.shields.io/badge/Streamlit-Live%20Demo-ff4b4b?logo=streamlit)](https://metamind-uww554njd8jwjzee7oupfr.streamlit.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 📌 Live Demo

🔗 **[metamind-uww554njd8jwjzee7oupfr.streamlit.app](https://metamind-uww554njd8jwjzee7oupfr.streamlit.app/)**

---

## 🏗️ Architecture
```
┌─────────────────────────────┐
│     Kaggle CSV Datasets     │
│  3 datasets · 158 CSV files │
│     2021–2026 VCT data      │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│        ETL Pipeline         │
│  normalize → clean → dedup  │
│  validate → batch upsert    │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│   Neon PostgreSQL (Cloud)   │
│  9 tables + 2 materialized  │
│  views (percentiles, stats) │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Streamlit Dashboard        │
│  4 pages · Plotly charts    │
│  Radar · Scatter · Gauge    │
│  1hr query-level caching    │
└─────────────────────────────┘
```

---

## 🎯 Key Technical Highlights

| Skill | Evidence |
|---|---|
| **Database Design** | 9-entity normalised schema, 2 materialized views with `PERCENT_RANK()` and `STDDEV`-based consistency scoring |
| **SQL Sophistication** | Window functions (`PERCENT_RANK()`, `AVG() OVER`), CTEs, conditional aggregation, `ON CONFLICT` upserts |
| **Metric Engineering** | Form Score (PEAKING/DECLINING/CONSISTENT), Consistency Score (CV-based, 0–100), ACS Percentile Rank |
| **Dashboard Engineering** | 4-page Streamlit app, crimson/gold VCT theme, Plotly radar/scatter/gauge/donut charts, query-level caching |
| **Data Pipeline** | ETL across 158 CSVs from 3 Kaggle datasets → 9-table normalised PostgreSQL schema with batch upserts |
| **Testing & CI/CD** | 26 unit tests across 6 modules, pytest-mock for DB isolation, GitHub Actions CI with PYTHONPATH configuration |

---

## 📊 Data Coverage

| Source | Scope | Scale |
|---|---|---|
| **VCT 2021–2023** | 3 full seasons | 11,328 players · per-match stats |
| **Champions Tour 2024** | 15 regional events + 2 Masters + Champions | Full player/match data |
| **VCT Champions 2025** | Paris — world championship | Per-map stats, economy, performance |

> **Note:** `economy_stats` and `performance_stats` tables are populated by ETL but excluded from dashboard visualisation due to sparse data quality in the source CSVs. They are retained in the schema for future iteration.

---

## 📱 Pages

| Page | What it does |
|---|---|
| **Home** | Platform overview, top 5 performers strip, explore cards |
| **Player Intelligence** | Select any pro — ACS percentile rank, radar profile, agent DNA donut, consistency gauge, form badge |
| **Player Comparison** | Compare up to 3 players — radar overlay, mirrored stat duel bars, side-by-side gauges |
| **Scout's Dashboard** | Filter 916 players by consistency tier, skill-vs-consistency scatter map, player lookup, South Asia spotlight |

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.11+
- PostgreSQL database (recommend [Neon](https://neon.tech))

### 1. Clone and install

```bash
git clone https://github.com/Narayan-Agarwal/metamind.git
cd metamind
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file at the project root:

```bash
DB_URL=postgresql+psycopg://user:password@host/dbname?sslmode=require
```

### 3. Deploy schema

```bash
psql $DB_URL -f data/schema.sql
```

### 4. Run ETL pipeline

```bash
python -m data.etl
```

### 5. Launch dashboard

```bash
streamlit run app.py
```

---

## 🔍 Showcase SQL Queries

### 1. Player Percentile Rankings — PERCENT_RANK()

```sql
WITH base AS (
    SELECT
        p.player_id, p.name, p.region,
        AVG(ps.acs)          AS avg_acs,
        AVG(ps.kd_ratio)     AS avg_kd,
        AVG(ps.first_kills)  AS avg_fb,
        AVG(ps.hs_percent)   AS avg_hs,
        AVG(ps.kast)         AS avg_kast,
        COUNT(ps.stat_id)    AS matches_played,
        100 - (STDDEV(ps.acs) / NULLIF(AVG(ps.acs), 0) * 100) AS consistency_score
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.player_id
    GROUP BY p.player_id, p.name, p.region
    HAVING COUNT(ps.stat_id) >= 5
)
SELECT *,
    PERCENT_RANK() OVER (ORDER BY avg_acs) AS acs_percentile,
    PERCENT_RANK() OVER (ORDER BY avg_kd)  AS kd_percentile
FROM base;
```

### 2. Consistency Score — CV-Based Stability Metric

```sql
SELECT
    p.name,
    AVG(ps.acs)    AS avg_acs,
    STDDEV(ps.acs) AS std_acs,
    100 - (STDDEV(ps.acs) / NULLIF(AVG(ps.acs), 0) * 100) AS consistency_score
FROM player_stats ps
JOIN players p ON ps.player_id = p.player_id
GROUP BY p.player_id, p.name
HAVING COUNT(*) >= 5
ORDER BY consistency_score DESC;
```

### 3. Player Form Engine — Rolling Window Analysis

```sql
WITH ordered AS (
    SELECT ps.*, m.match_date,
        ROW_NUMBER() OVER (ORDER BY m.match_date) AS match_num
    FROM player_stats ps
    JOIN matches m ON ps.match_id = m.match_id
    WHERE ps.player_id = :player_id
)
SELECT *,
    AVG(acs) OVER (
        ORDER BY match_num ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS rolling_acs_3
FROM ordered
ORDER BY match_num;
```

### 4. Economy Analysis — Conditional Aggregation

```sql
-- economy_stats table: populated but excluded from dashboard (sparse data)
SELECT
    m.map_name,
    COUNT(*)                                                   AS games,
    ROUND(AVG(es.pistol_won::float / NULLIF(2,0) * 100), 1)  AS pistol_win_pct,
    ROUND(AVG(es.eco_won), 1)                                  AS avg_eco_won,
    ROUND(AVG(es.full_buy_won), 1)                             AS avg_full_buy_won
FROM economy_stats es
JOIN matches mt ON es.match_id = mt.match_id
JOIN maps m      ON es.map_id  = m.map_id
WHERE es.team_id = :team_id
GROUP BY m.map_name
ORDER BY m.map_name;
```

---

## 📂 Project Structure

```
MetaMind/
├── app.py                    # Home page — hero, top performers, explore cards
├── pages/
│   ├── 1_Player.py           # Player Intelligence — radar, agent DNA, gauges
│   ├── 2_Team_Map.py         # Player Comparison — radar overlay, stat duel bars
│   └── 3_Leaderboard.py      # Scout's Dashboard — scatter map, scoreboard
├── data/
│   ├── schema.sql            # 9 tables + 2 materialized views
│   ├── fetch/
│   │   └── kaggle_loader.py  # Reads all Kaggle CSV data (158 files)
│   ├── etl.py                # Master ETL orchestrator
│   ├── db_loader.py          # SQLAlchemy batch upsert engine
│   └── scheduler.py          # APScheduler ETL runner (local use)
├── db/
│   ├── connection.py         # Neon PostgreSQL — lazy streamlit import for CI
│   └── queries.py            # 16 SQL query functions
├── analytics/
│   ├── consistency.py        # Consistency Score (CV-based, 0–100)
│   ├── form_engine.py        # PEAKING / DECLINING / CONSISTENT
│   ├── edge_score.py         # Weighted 5-metric edge score
│   └── insights.py           # Multi-signal insight generation
├── tests/                    # 26 unit tests — pytest + pytest-mock
│   ├── test_consistency.py
│   ├── test_db_loader.py
│   ├── test_edge_score.py
│   ├── test_etl.py
│   ├── test_form_engine.py
│   └── test_queries.py
└── .github/
    └── workflows/ci.yml      # GitHub Actions CI — PYTHONPATH=. · Python 3.11
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built by [Narayan Agarwal](https://github.com/Narayan-Agarwal) as a DA/SWE portfolio project.*

<!-- CI verified green: 18/18 tests passing -->
