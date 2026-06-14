-- MetaMind Database Schema
-- 8 Core Tables + 2 Materialized Views
-- PostgreSQL (Neon Cloud)
-- Run: psql $DB_URL -f data/schema.sql

-- ============================================================
-- Drop existing objects (idempotent re-run)
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_team_map_winrates CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_player_percentiles CASCADE;
DROP TABLE IF EXISTS performance_stats CASCADE;
DROP TABLE IF EXISTS economy_stats CASCADE;
DROP TABLE IF EXISTS map_results CASCADE;
DROP TABLE IF EXISTS player_stats CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS maps CASCADE;
DROP TABLE IF EXISTS tournaments CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS teams CASCADE;

-- ============================================================
-- Table 1: teams
-- ============================================================
CREATE TABLE teams (
    team_id            SERIAL PRIMARY KEY,
    name               VARCHAR(100) UNIQUE NOT NULL,
    region             VARCHAR(50),
    tournaments_played INT DEFAULT 0
);

CREATE INDEX idx_teams_region ON teams(region);

-- ============================================================
-- Table 2: players
-- ============================================================
CREATE TABLE players (
    player_id       SERIAL PRIMARY KEY,
    name            VARCHAR(100) UNIQUE NOT NULL,
    name_normalized VARCHAR(100),
    team_id         INT REFERENCES teams(team_id),
    region          VARCHAR(50),
    nationality     VARCHAR(50),
    agent_pool      TEXT[],
    source          VARCHAR(20)
);

CREATE INDEX idx_players_team ON players(team_id);
CREATE INDEX idx_players_region ON players(region);
CREATE INDEX idx_players_name_norm ON players(name_normalized);

-- ============================================================
-- Table 3: tournaments
-- ============================================================
CREATE TABLE tournaments (
    tournament_id SERIAL PRIMARY KEY,
    name          VARCHAR(200),
    year          INT,
    region        VARCHAR(50),
    tier          VARCHAR(10)
);

CREATE INDEX idx_tournaments_year ON tournaments(year);

-- ============================================================
-- Table 4: maps
-- ============================================================
CREATE TABLE maps (
    map_id   SERIAL PRIMARY KEY,
    map_name VARCHAR(50) UNIQUE NOT NULL
);

-- ============================================================
-- Table 5: matches
-- ============================================================
CREATE TABLE matches (
    match_id       SERIAL PRIMARY KEY,
    tournament_id  INT REFERENCES tournaments(tournament_id),
    team1_id       INT REFERENCES teams(team_id),
    team2_id       INT REFERENCES teams(team_id),
    map_id         INT REFERENCES maps(map_id),
    match_date     DATE,
    winner_team_id INT REFERENCES teams(team_id),
    team1_score    INT,
    team2_score    INT,
    source         VARCHAR(20)
);

CREATE INDEX idx_matches_tournament ON matches(tournament_id);
CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_matches_teams ON matches(team1_id, team2_id);

-- ============================================================
-- Table 6: player_stats
-- ============================================================
CREATE TABLE player_stats (
    stat_id      SERIAL PRIMARY KEY,
    match_id     INT REFERENCES matches(match_id),
    player_id    INT REFERENCES players(player_id),
    kills        INT,
    deaths       INT,
    assists      INT,
    acs          NUMERIC(6,2),
    kd_ratio     NUMERIC(5,3),
    kast         NUMERIC(5,2),
    adr          NUMERIC(6,2),
    first_kills  INT,
    first_deaths INT,
    hs_percent   NUMERIC(5,2),
    clutch_pct   NUMERIC(5,2),
    rating       NUMERIC(5,3),
    agent        VARCHAR(50),
    UNIQUE (match_id, player_id)
);

CREATE INDEX idx_player_stats_player ON player_stats(player_id);
CREATE INDEX idx_player_stats_match ON player_stats(match_id);

-- ============================================================
-- Table 7: map_results
-- ============================================================
CREATE TABLE map_results (
    result_id  SERIAL PRIMARY KEY,
    match_id   INT REFERENCES matches(match_id),
    team_id    INT REFERENCES teams(team_id),
    map_id     INT REFERENCES maps(map_id),
    rounds_won INT,
    side_start VARCHAR(10),
    outcome    VARCHAR(10),
    UNIQUE (match_id, team_id)
);

CREATE INDEX idx_map_results_team ON map_results(team_id);
CREATE INDEX idx_map_results_map ON map_results(map_id);

-- ============================================================
-- Table 8: economy_stats
-- ============================================================
CREATE TABLE economy_stats (
    econ_id       SERIAL PRIMARY KEY,
    match_id      INT REFERENCES matches(match_id),
    team_id       INT REFERENCES teams(team_id),
    map_id        INT REFERENCES maps(map_id),
    pistol_won    INT,
    eco_won       INT,
    semi_eco_won  INT,
    semi_buy_won  INT,
    full_buy_won  INT,
    UNIQUE (match_id, team_id)
);

CREATE INDEX idx_economy_stats_team ON economy_stats(team_id);

-- ============================================================
-- Table 9: performance_stats
-- ============================================================
CREATE TABLE performance_stats (
    perf_id    SERIAL PRIMARY KEY,
    match_id   INT REFERENCES matches(match_id),
    player_id  INT REFERENCES players(player_id),
    map_id     INT REFERENCES maps(map_id),
    kills_2k   INT,
    kills_3k   INT,
    kills_4k   INT,
    kills_5k   INT,
    clutch_1v1 INT,
    clutch_1v2 INT,
    clutch_1v3 INT,
    clutch_1v4 INT,
    clutch_1v5 INT,
    UNIQUE (match_id, player_id)
);

CREATE INDEX idx_performance_stats_player ON performance_stats(player_id);

-- ============================================================
-- Materialized View 1: mv_player_percentiles
-- Pre-computed per-player aggregates and percentile ranks
-- ============================================================
CREATE MATERIALIZED VIEW mv_player_percentiles AS
WITH base AS (
    SELECT
        p.player_id,
        p.name,
        p.region,
        p.nationality,
        AVG(ps.acs)                                            AS avg_acs,
        STDDEV(ps.acs)                                         AS acs_stddev,
        AVG(ps.kd_ratio)                                       AS avg_kd,
        AVG(ps.kills)                                          AS avg_kills,
        AVG(ps.first_kills)                                    AS avg_fb,
        AVG(ps.hs_percent)                                     AS avg_hs,
        AVG(ps.kast)                                           AS avg_kast,
        COUNT(ps.stat_id)                                      AS matches_played,
        GREATEST(0, LEAST(100,
            100 - (STDDEV(ps.acs) / NULLIF(AVG(ps.acs), 0) * 100)
        ))                                                     AS consistency_score
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.player_id
    GROUP BY p.player_id, p.name, p.region, p.nationality
    HAVING COUNT(ps.stat_id) >= 5
)
SELECT *,
    PERCENT_RANK() OVER (ORDER BY avg_acs)  AS acs_percentile,
    PERCENT_RANK() OVER (ORDER BY avg_kd)   AS kd_percentile,
    PERCENT_RANK() OVER (ORDER BY avg_fb)   AS fb_percentile
FROM base;

CREATE UNIQUE INDEX idx_mv_player_percentiles_id ON mv_player_percentiles(player_id);

-- ============================================================
-- Materialized View 2: mv_team_map_winrates
-- Pre-computed team map win rates and economy patterns
-- ============================================================
CREATE MATERIALIZED VIEW mv_team_map_winrates AS
SELECT
    mr.team_id,
    m.map_name,
    COUNT(*)                                                           AS games_played,
    SUM(CASE WHEN mr.outcome = 'win' THEN 1 ELSE 0 END)               AS wins,
    ROUND((AVG(CASE WHEN mr.outcome = 'win' THEN 1.0 ELSE 0 END) * 100)::numeric, 1)
                                                                       AS win_pct,
    ROUND(AVG(CASE WHEN mr.side_start = 'attack'
        THEN mr.rounds_won END)::numeric, 1)                                    AS avg_atk_rounds,
    ROUND(AVG(CASE WHEN mr.side_start = 'defense'
        THEN mr.rounds_won END)::numeric, 1)                                    AS avg_def_rounds,
    ROUND((AVG(es.pistol_won::numeric /
        NULLIF(es.pistol_won + (2 - es.pistol_won), 0) * 100))::numeric, 1)     AS pistol_win_pct
FROM map_results mr
JOIN maps m ON mr.map_id = m.map_id
LEFT JOIN economy_stats es
    ON es.match_id = mr.match_id AND es.team_id = mr.team_id
GROUP BY mr.team_id, m.map_name;

CREATE INDEX idx_mv_team_map_winrates_team ON mv_team_map_winrates(team_id);
