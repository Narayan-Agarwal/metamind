import pandas as pd
from sqlalchemy import text

def get_all_players(engine):
    return pd.read_sql("""
        SELECT player_id, name, region, nationality
        FROM players
        WHERE name IS NOT NULL
        ORDER BY name
    """, engine)

def get_player_percentiles(engine, player_id):
    return pd.read_sql("""
        SELECT * FROM mv_player_percentiles
        WHERE player_id = %(pid)s
    """, engine, params={"pid": player_id})

def get_player_stats(engine, player_id):
    return pd.read_sql("""
        SELECT ps.kills, ps.deaths, ps.assists, 
               ps.acs, ps.kd_ratio, ps.kast, ps.adr,
               ps.first_kills, ps.hs_percent,
               m.match_date, m.team1_score, 
               m.team2_score, m.match_id,
               mp.map_name
        FROM player_stats ps
        JOIN matches m ON ps.match_id = m.match_id
        LEFT JOIN maps mp ON m.map_id = mp.map_id
        WHERE ps.player_id = %(pid)s
        ORDER BY m.match_date DESC
        LIMIT 30
    """, engine, params={"pid": player_id})

def get_all_teams(engine):
    return pd.read_sql("""
        SELECT team_id, name, region
        FROM teams
        WHERE name IS NOT NULL
        ORDER BY name
    """, engine)

def get_team_map_stats(engine, team_id):
    return pd.read_sql("""
        SELECT * FROM mv_team_map_winrates
        WHERE team_id = %(tid)s
        ORDER BY win_pct DESC
    """, engine, params={"tid": team_id})

def get_leaderboard(engine, min_matches=10):
    return pd.read_sql("""
        SELECT 
          ROW_NUMBER() OVER (ORDER BY avg_acs DESC) 
            AS rank,
          name,
          region,
          nationality,
          ROUND(avg_acs::numeric, 1) AS avg_acs,
          ROUND(avg_kd::numeric, 2) AS avg_kd,
          ROUND(consistency_score::numeric, 1) 
            AS consistency,
          ROUND(avg_kast::numeric, 1) AS kast_pct,
          ROUND(avg_fb::numeric, 2) AS first_kill_pct,
          matches_played
        FROM mv_player_percentiles
        WHERE matches_played >= %(min)s
        ORDER BY avg_acs DESC
    """, engine, params={"min": min_matches})

def get_regional_comparison(engine):
    return pd.read_sql("""
        SELECT 
          region,
          COUNT(*) AS player_count,
          ROUND(AVG(avg_acs)::numeric, 1) AS avg_acs,
          ROUND(AVG(avg_kd)::numeric, 2) AS avg_kd,
          ROUND(AVG(consistency_score)::numeric, 1) 
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

    return pd.read_sql("""
        SELECT 
          name,
          ROUND(avg_acs::numeric, 1) AS avg_acs,
          ROUND(avg_kd::numeric, 2) AS avg_kd,
          ROUND(consistency_score::numeric, 1) 
            AS consistency,
          ROUND(acs_percentile * 100::numeric, 0) 
            AS global_percentile,
          matches_played
        FROM mv_player_percentiles
        WHERE name = ANY(%(names)s)
        ORDER BY avg_acs DESC
        LIMIT 5
    """, engine, params={"names": known_indian})
