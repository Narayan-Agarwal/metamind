-- MetaMind — Player Percentile Rankings
-- Computes per-player aggregates and percentile ranks across dataset
-- Demonstrates: PERCENT_RANK(), STDDEV, HAVING, window over aggregates

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
        -- Consistency Score: 100 - CV×100, clamped to [0, 100]
        GREATEST(0, LEAST(100,
            100 - (STDDEV(ps.acs) / NULLIF(AVG(ps.acs), 0) * 100)
        ))                                                     AS consistency_score
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.player_id
    GROUP BY p.player_id, p.name, p.region, p.nationality
    -- Minimum 5 matches for statistical validity
    HAVING COUNT(ps.stat_id) >= 5
)

-- Percentile rank against all qualified players
SELECT *,
    PERCENT_RANK() OVER (ORDER BY avg_acs)  AS acs_percentile,
    PERCENT_RANK() OVER (ORDER BY avg_kd)   AS kd_percentile,
    PERCENT_RANK() OVER (ORDER BY avg_fb)   AS fb_percentile
FROM base
ORDER BY avg_acs DESC;
