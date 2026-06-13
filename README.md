# 🧠 MetaMind — Esports Analytics Platform

> Transforming 5 years of Valorant pro match data into interactive performance insights, strategic visualizations, and analyst-grade commentary.

[![CI](https://github.com/Narayan-Agarwal/metamind/actions/workflows/ci.yml/badge.svg)](https://github.com/Narayan-Agarwal/metamind/actions)
[![Streamlit](https://img.shields.io/badge/Streamlit-Live%20Demo-ff4b4b?logo=streamlit)](https://metamind-uww554njd8jwjzee7oupfr.streamlit.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 📌 Live Demo

🔗 **[metamind-uww554njd8jwjzee7oupfr.streamlit.app](https://metamind-uww554njd8jwjzee7oupfr.streamlit.app/)**

---

## 🏗️ Architecture

```
                  ┌────────────┐     ┌────────────┐
                  │  Kaggle    │     │  VLR.gg    │
                  │  CSV Data  │     │  Scraper   │
                  └─────┬──────┘     └─────┬──────┘
                        │                  │
                  ┌─────▼──────────────────▼─────┐
                  │       ETL Pipeline           │
                  │  normalize → clean → dedup   │
                  │  tag nationality → validate  │
                  └─────────────┬─────────────────┘
                                │
                  ┌─────────────▼─────────────────┐
                  │    Neon PostgreSQL (Cloud)     │
                  │  9 tables + 2 materialized    │
                  │  views (percentiles, win %)   │
                  └─────────────┬─────────────────┘
                                │
                  ┌─────────────▼─────────────────┐
                  │   Streamlit Dark Dashboard    │
                  │  3 pages × Plotly interactive │
                  │  + Analyst Commentary Engine  │
                  └───────────────────────────────┘
```

---

## 🎯 Key Technical Highlights

| Skill | Evidence |
|---|---|
| **Database Design** | 9-entity normalized schema, 2 materialized views with `PERCENT_RANK()` and `STDDEV`-based consistency scoring |
| **SQL Sophistication** | Window functions (`AVG() OVER`, `LAG()`, `PERCENT_RANK()`), CTEs, conditional aggregation, rolling averages |
| **Metric Engineering** | Form Score (PEAKING/DECLINING/CONSISTENT), Consistency Score (CV-based, 0–100), Edge Score (weighted 5-metric) |
| **Dashboard Engineering** | 3-page Streamlit app, dark theme, Plotly interactive charts, radar comparisons, percentile bars |
| **Data Pipeline** | Automated ETL: local Kaggle CSVs + targeted VLR.gg scrape → PostgreSQL with `ON CONFLICT` upserts |
| **Domain Thinking** | Rule-based analyst commentary engine combining multiple signals per insight card |

---

## 📊 Data Coverage

| Source | Scope | Records |
|---|---|---|
| **VCT Historical** | 2021–2026 seasons | 6 years × per-map per-player stats |
| **Champions Tour 2024** | 15 regional events + 2 Masters + Champions | Full player/match/economy data |
| **VCT Champions 2025** | Paris — richest dataset | Per-map stats, economy, performance |
| **VLR.gg South Asia** | 4 Challengers League events | 15+ Indian players |

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

```bash
cp .env.example .env
# Edit .env and add your Neon PostgreSQL connection string:
# DB_URL=postgresql+psycopg://user:password@host/dbname?sslmode=require
```

### 3. Deploy schema

```bash
psql $DB_URL -f data/schema.sql
```

### 4. Run ETL pipeline

```bash
python -m data.etl --full
```

### 5. Launch dashboard

```bash
streamlit run app.py
```

---

## 🔍 Showcase SQL Queries

### 1. Player Form Engine — Rolling Window Analysis

```sql
-- Rolling ACS average with delta from previous match
WITH ordered AS (
    SELECT ps.*, m.match_date,
        ROW_NUMBER() OVER (ORDER BY m.match_date, ps.stat_id) AS match_num
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
        LAG(acs, 1) OVER (ORDER BY match_num) AS prev_acs
    FROM ordered
)
SELECT *, (acs - prev_acs) AS acs_delta
FROM rolling
ORDER BY match_num;
```

### 2. Player Percentile Rankings — PERCENT_RANK()

```sql
-- Percentile rank per player across all players with 5+ matches
WITH base AS (
    SELECT
        p.player_id, p.name, p.region, p.nationality,
        AVG(ps.acs) AS avg_acs,
        AVG(ps.kd_ratio) AS avg_kd,
        AVG(ps.first_kills) AS avg_fb,
        AVG(ps.hs_percent) AS avg_hs,
        AVG(ps.kast) AS avg_kast,
        COUNT(ps.stat_id) AS matches_played,
        100 - (STDDEV(ps.acs) / NULLIF(AVG(ps.acs), 0) * 100) AS consistency_score
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.player_id
    GROUP BY p.player_id, p.name, p.region, p.nationality
    HAVING COUNT(ps.stat_id) >= 5
)
SELECT *,
    PERCENT_RANK() OVER (ORDER BY avg_acs) AS acs_percentile,
    PERCENT_RANK() OVER (ORDER BY avg_kd)  AS kd_percentile,
    PERCENT_RANK() OVER (ORDER BY avg_fb)  AS fb_percentile
FROM base;
```

### 3. Team Economy Analysis — Conditional Aggregation

```sql
-- Economy win rates per map for a specific team
SELECT
    m.map_name,
    COUNT(*) AS games,
    ROUND(AVG(es.pistol_won::float / NULLIF(2, 0) * 100), 1) AS pistol_win_pct,
    ROUND(AVG(es.eco_won), 1) AS avg_eco_won,
    ROUND(AVG(es.semi_buy_won), 1) AS avg_semi_buy_won,
    ROUND(AVG(es.full_buy_won), 1) AS avg_full_buy_won
FROM economy_stats es
JOIN matches mt ON es.match_id = mt.match_id
JOIN maps m ON es.map_id = m.map_id
WHERE es.team_id = :team_id
GROUP BY m.map_name
ORDER BY m.map_name;
```

### 4. Regional Leaderboard — Cross-Entity Aggregation

```sql
-- Regional comparison using materialized view
SELECT
    p.region,
    COUNT(DISTINCT mv.player_id) AS player_count,
    ROUND(AVG(mv.avg_acs), 1) AS avg_acs,
    ROUND(AVG(mv.avg_kd), 2) AS avg_kd,
    ROUND(AVG(mv.consistency_score), 1) AS avg_consistency,
    ROUND(AVG(mv.avg_kast), 1) AS avg_kast
FROM mv_player_percentiles mv
JOIN players p ON mv.player_id = p.player_id
GROUP BY p.region
ORDER BY avg_acs DESC;
```

---

## 📂 Project Structure

```
MetaMind/
├── app.py                    # Entry point, dark theme, sidebar nav
├── pages/
│   ├── 1_Player.py           # Player Intelligence dashboard
│   ├── 2_Team_Map.py         # Team Map Strategy dashboard
│   └── 3_Leaderboard.py      # Tournament Leaderboard
├── data/
│   ├── schema.sql            # 9 tables + 2 materialized views
│   ├── fetch/
│   │   ├── kaggle_loader.py  # Reads all local CSV data
│   │   └── vlr_scraper.py    # Scrapes VLR.gg SA events
│   ├── etl.py                # Master ETL orchestrator
│   ├── db_loader.py          # SQLAlchemy upsert engine
│   ├── scheduler.py          # APScheduler daily 3AM UTC
│   ├── player_aliases.json   # Name normalization map
│   └── indian_players.json   # Indian player metadata
├── db/
│   ├── connection.py         # Neon PostgreSQL connection
│   └── queries.py            # All SQL query functions
├── analytics/
│   ├── consistency.py        # Consistency Score (0–100)
│   ├── form_engine.py        # PEAKING/DECLINING/CONSISTENT
│   ├── edge_score.py         # Weighted 5-metric comparison
│   └── insights.py           # Multi-signal commentary
├── queries/                   # Showcase SQL files
├── tests/                     # Full test suite
└── .github/workflows/ci.yml  # GitHub Actions CI
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built by [Narayan Agarwal](https://github.com/Narayan-Agarwal) as a DA/BI portfolio project.*
