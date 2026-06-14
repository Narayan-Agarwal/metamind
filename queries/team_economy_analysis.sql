-- MetaMind — Team Economy Analysis
-- Pistol, eco, semi-buy, and full-buy win analysis per map
-- Demonstrates: CASE-based aggregation, multi-table joins, economy metrics

SELECT
    m.map_name,
    t.name                                              AS team_name,
    COUNT(*)                                            AS games_played,

    -- Pistol round win rate (2 pistol rounds per map)
    ROUND(AVG(es.pistol_won::float / 2.0 * 100), 1)    AS pistol_win_pct,

    -- Average rounds won per economy category
    ROUND(AVG(es.eco_won), 1)                           AS avg_eco_won,
    ROUND(AVG(es.semi_eco_won), 1)                      AS avg_semi_eco_won,
    ROUND(AVG(es.semi_buy_won), 1)                      AS avg_semi_buy_won,
    ROUND(AVG(es.full_buy_won), 1)                      AS avg_full_buy_won,

    -- Economic efficiency: full buys won relative to total
    ROUND(
        AVG(es.full_buy_won)::float /
        NULLIF(AVG(es.eco_won + es.semi_eco_won + es.semi_buy_won + es.full_buy_won), 0) * 100
    , 1)                                                AS full_buy_share_pct

FROM economy_stats es
JOIN matches mt ON es.match_id = mt.match_id
JOIN maps m     ON es.map_id   = m.map_id
JOIN teams t    ON es.team_id  = t.team_id
WHERE es.team_id = :team_id
GROUP BY m.map_name, t.name
ORDER BY m.map_name;
