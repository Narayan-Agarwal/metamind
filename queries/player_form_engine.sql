-- MetaMind — Player Form Engine
-- Rolling ACS/KD average with delta from previous match
-- Demonstrates: Window functions, CTE composition, LAG()

WITH ordered AS (
    -- Establish chronological match ordering for the player
    SELECT
        ps.stat_id,
        ps.match_id,
        ps.player_id,
        ps.acs,
        ps.kd_ratio,
        ps.kills,
        m.match_date,
        ROW_NUMBER() OVER (ORDER BY m.match_date, ps.stat_id) AS match_num
    FROM player_stats ps
    JOIN matches m ON ps.match_id = m.match_id
    WHERE ps.player_id = :player_id
),

rolling AS (
    -- Compute rolling averages over configurable window
    SELECT *,
        AVG(acs) OVER (
            ORDER BY match_num
            ROWS BETWEEN :window PRECEDING AND CURRENT ROW
        ) AS rolling_acs,
        AVG(kd_ratio) OVER (
            ORDER BY match_num
            ROWS BETWEEN :window PRECEDING AND CURRENT ROW
        ) AS rolling_kd,
        AVG(kills) OVER (
            ORDER BY match_num
            ROWS BETWEEN :window PRECEDING AND CURRENT ROW
        ) AS rolling_kills,
        LAG(acs, 1) OVER (ORDER BY match_num) AS prev_acs
    FROM ordered
)

-- Final output with delta computation
SELECT
    match_num,
    match_date,
    acs,
    kd_ratio,
    kills,
    rolling_acs,
    rolling_kd,
    rolling_kills,
    prev_acs,
    (acs - prev_acs) AS acs_delta
FROM rolling
ORDER BY match_num;
