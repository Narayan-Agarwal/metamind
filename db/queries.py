import pandas as pd
from sqlalchemy import text

def get_all_players(engine):
    return pd.read_sql("""
        SELECT player_id, name, region, nationality
        FROM mv_player_percentiles
        WHERE name IS NOT NULL
        ORDER BY name
    """, engine)

def get_player_percentiles(engine, player_id):
    return pd.read_sql("""
        SELECT * FROM mv_player_percentiles
        WHERE player_id = %(pid)s
    """, engine, params={"pid": int(player_id)})

def get_player_stats(engine, player_id):
    return pd.read_sql("""
        SELECT 
            ps.kills, ps.deaths, ps.assists,
            ps.acs, ps.kd_ratio, ps.kast, ps.adr,
            ps.first_kills, ps.hs_percent,
            ps.agent,
            m.match_date,
            m.team1_score, m.team2_score,
            m.match_id,
            mp.map_name,
            t.name AS tournament_name
        FROM player_stats ps
        JOIN matches m ON ps.match_id = m.match_id
        LEFT JOIN maps mp ON m.map_id = mp.map_id
        LEFT JOIN tournaments t 
            ON m.tournament_id = t.tournament_id
        WHERE ps.player_id = %(pid)s
        ORDER BY m.match_date DESC
        LIMIT 30
    """, engine, params={"pid": int(player_id)})

def get_all_teams(engine):
    return pd.read_sql("""
        SELECT team_id, name, region
        FROM teams
        WHERE name IS NOT NULL
        ORDER BY name
    """, engine)

def get_team_map_stats(engine, team_id):
    return pd.read_sql("""
        SELECT 
            map_name,
            games_played,
            wins,
            win_pct,
            avg_atk_rounds,
            avg_def_rounds
        FROM mv_team_map_winrates
        WHERE team_id = %(tid)s
        ORDER BY win_pct DESC
    """, engine, params={"tid": int(team_id)})

def get_team_stats(engine, team_id):
    return pd.read_sql("""
        SELECT
            COUNT(*) AS total_matches,
            SUM(CASE WHEN winner_team_id = %(tid)s 
                THEN 1 ELSE 0 END) AS wins,
            ROUND(
                AVG(CASE WHEN winner_team_id = %(tid)s
                THEN 100.0 ELSE 0 END
            ), 1) AS win_rate
        FROM matches
        WHERE team1_id = %(tid)s 
        OR team2_id = %(tid)s
    """, engine, params={"tid": int(team_id)})

def get_leaderboard(engine, min_matches=10, sort_by='avg_acs', region=None):
    where = "WHERE matches_played >= %(min)s"
    params = {"min": min_matches}
    if region and region != 'All':
        where += " AND region = %(region)s"
        params["region"] = region
    
    valid_sorts = ['avg_acs','avg_kd', 'consistency_score','avg_kast','avg_fb','consistency','kast_pct','first_kill_pct']
    sort_map = {'consistency': 'consistency_score', 'kast_pct': 'avg_kast', 'first_kill_pct': 'avg_fb'}
    sort_by = sort_map.get(sort_by, sort_by)
    if sort_by not in ['avg_acs','avg_kd','consistency_score','avg_kast','avg_fb']:
        sort_by = 'avg_acs'
    
    return pd.read_sql(f"""
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY {sort_by} DESC NULLS LAST
            ) AS rank,
            name,
            region,
            nationality,
            ROUND(avg_acs::numeric, 1) AS avg_acs,
            ROUND(avg_kd::numeric, 2) AS avg_kd,
            ROUND(consistency_score::numeric, 1) 
                AS consistency,
            ROUND(avg_kast::numeric, 1) AS kast_pct,
            ROUND(avg_fb::numeric, 2) 
                AS first_kill_pct,
            matches_played
        FROM mv_player_percentiles
        {where}
        ORDER BY {sort_by} DESC NULLS LAST
    """, engine, params=params)

def get_regional_comparison(engine):
    return pd.read_sql("""
        SELECT
            region,
            COUNT(*) AS player_count,
            ROUND(AVG(avg_acs)::numeric, 1) 
                AS avg_acs,
            ROUND(AVG(avg_kd)::numeric, 2) 
                AS avg_kd,
            ROUND(AVG(consistency_score)::numeric,1)
                AS avg_consistency
        FROM mv_player_percentiles
        WHERE region IS NOT NULL
        GROUP BY region
        ORDER BY avg_acs DESC
    """, engine)

def get_indian_spotlight(engine):
    known_indian = ['Excali','Rawfiul','Antidote',
        'Venka','Vibhor','mw1','Deathmaker','hellff',
        'Rite2Ace','Amaterasu','Marzil','Techno',
        'Lightningfast','Karam1L','Rishi','Saarang']
    placeholders = ','.join([f"'{n}'" for n in known_indian])
    return pd.read_sql(f"""
        SELECT
            name,
            ROUND(avg_acs::numeric,1) AS avg_acs,
            ROUND(avg_kd::numeric,2) AS avg_kd,
            ROUND(consistency_score::numeric,1) 
                AS consistency,
            ROUND(acs_percentile*100::numeric,0) 
                AS global_percentile,
            matches_played
        FROM mv_player_percentiles
        WHERE name IN ({placeholders})
        ORDER BY avg_acs DESC
        LIMIT 5
    """, engine)

def get_platform_stats(engine):
    with engine.connect() as conn:
        return {
            'players': conn.execute(text(
                "SELECT COUNT(*) FROM players"
            )).scalar(),
            'matches': conn.execute(text(
                "SELECT COUNT(*) FROM matches"
            )).scalar(),
            'maps': conn.execute(text(
                "SELECT COUNT(*) FROM maps"
            )).scalar(),
            'tournaments': conn.execute(text(
                "SELECT COUNT(DISTINCT year) "
                "FROM tournaments "
                "WHERE year IS NOT NULL"
            )).scalar(),
        }

# NEW QUERIES FOR TEAM ANALYTICS
def get_team_players(engine, team_id):
    return pd.read_sql("""
        SELECT 
            p.player_id,
            p.name,
            p.nationality,
            mv.avg_acs,
            mv.avg_kd,
            mv.consistency_score,
            mv.matches_played,
            mv.avg_kast,
            mv.avg_fb,
            mv.acs_percentile
        FROM players p
        JOIN mv_player_percentiles mv 
            ON p.player_id = mv.player_id
        WHERE p.team_id = %(tid)s
        ORDER BY mv.avg_acs DESC
    """, engine, params={"tid": int(team_id)})

def get_team_aggregate_stats(engine, team_id):
    return pd.read_sql("""
        SELECT
            ROUND(AVG(ps.acs)::numeric, 1) 
                AS team_avg_acs,
            ROUND(AVG(ps.kd_ratio)::numeric, 2) 
                AS team_avg_kd,
            ROUND(AVG(ps.kast)::numeric, 1) 
                AS team_avg_kast,
            ROUND(AVG(ps.adr)::numeric, 1) 
                AS team_avg_adr,
            ROUND(AVG(ps.hs_percent)::numeric, 1) 
                AS team_avg_hs,
            COUNT(DISTINCT ps.player_id) 
                AS player_count,
            COUNT(ps.stat_id) 
                AS total_appearances
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        WHERE p.team_id = %(tid)s
    """, engine, params={"tid": int(team_id)})

def get_team_agent_usage(engine, team_id):
    return pd.read_sql("""
        SELECT
            ps.agent,
            COUNT(*) AS times_played,
            ROUND(AVG(ps.acs)::numeric, 1) 
                AS avg_acs_on_agent,
            ROUND(AVG(ps.kd_ratio)::numeric, 2) 
                AS avg_kd_on_agent
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        WHERE p.team_id = %(tid)s
        AND ps.agent IS NOT NULL
        GROUP BY ps.agent
        ORDER BY times_played DESC
        LIMIT 8
    """, engine, params={"tid": int(team_id)})

def get_global_team_stats(engine):
    return pd.read_sql("""
        SELECT
            t.team_id,
            t.name AS team_name,
            t.region,
            COUNT(DISTINCT p.player_id) 
                AS player_count,
            ROUND(AVG(mv.avg_acs)::numeric, 1) 
                AS team_avg_acs,
            ROUND(AVG(mv.avg_kd)::numeric, 2) 
                AS team_avg_kd,
            ROUND(AVG(mv.consistency_score)::numeric,1)
                AS team_consistency
        FROM teams t
        JOIN players p ON p.team_id = t.team_id
        JOIN mv_player_percentiles mv 
            ON mv.player_id = p.player_id
        GROUP BY t.team_id, t.name, t.region
        HAVING COUNT(DISTINCT p.player_id) >= 3
        ORDER BY team_avg_acs DESC
    """, engine)
