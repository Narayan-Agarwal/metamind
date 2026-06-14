-- MetaMind — Regional Leaderboard
-- Cross-region comparison of player performance aggregates
-- Demonstrates: GROUP BY region, materialized view usage, cross-entity aggregation

SELECT
    p.region,
    COUNT(DISTINCT mv.player_id)            AS player_count,
    ROUND(AVG(mv.avg_acs), 1)              AS avg_acs,
    ROUND(AVG(mv.avg_kd), 2)               AS avg_kd,
    ROUND(AVG(mv.consistency_score), 1)    AS avg_consistency,
    ROUND(AVG(mv.avg_kast), 1)             AS avg_kast,
    ROUND(AVG(mv.avg_fb), 2)               AS avg_first_kills,

    -- Best individual performer per region
    (SELECT b.name FROM mv_player_percentiles b
     JOIN players p2 ON b.player_id = p2.player_id
     WHERE p2.region = p.region
     ORDER BY b.avg_acs DESC LIMIT 1)      AS top_player_name,

    (SELECT MAX(b.avg_acs) FROM mv_player_percentiles b
     JOIN players p2 ON b.player_id = p2.player_id
     WHERE p2.region = p.region)            AS top_player_acs

FROM mv_player_percentiles mv
JOIN players p ON mv.player_id = p.player_id
WHERE p.region IS NOT NULL
GROUP BY p.region
ORDER BY avg_acs DESC;
