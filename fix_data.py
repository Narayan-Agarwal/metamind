import os
from dotenv import load_dotenv
load_dotenv()

from db.connection import get_engine
from sqlalchemy import text

engine = get_engine()

with engine.begin() as conn:

    # FIX 1: Populate map_results from matches table
    print("Fixing map_results...")
    conn.execute(text("""
        INSERT INTO map_results 
            (match_id, team_id, map_id, 
             rounds_won, outcome)
        SELECT 
            m.match_id,
            m.team1_id,
            m.map_id,
            m.team1_score,
            CASE WHEN m.winner_team_id = m.team1_id 
                THEN 'win' ELSE 'loss' END
        FROM matches m
        WHERE m.map_id IS NOT NULL
        AND m.team1_id IS NOT NULL
        ON CONFLICT (match_id, team_id) DO NOTHING
    """))
    
    conn.execute(text("""
        INSERT INTO map_results 
            (match_id, team_id, map_id, 
             rounds_won, outcome)
        SELECT 
            m.match_id,
            m.team2_id,
            m.map_id,
            m.team2_score,
            CASE WHEN m.winner_team_id = m.team2_id 
                THEN 'win' ELSE 'loss' END
        FROM matches m
        WHERE m.map_id IS NOT NULL
        AND m.team2_id IS NOT NULL
        ON CONFLICT (match_id, team_id) DO NOTHING
    """))
    print("map_results done")

    # FIX 2: Fix tournament years from name
    print("Fixing tournament years...")
    conn.execute(text("""
        UPDATE tournaments
        SET year = CAST(
            SUBSTRING(name FROM '[0-9]{4}') 
            AS INTEGER)
        WHERE year IS NULL
        AND name ~ '[0-9]{4}'
    """))
    print("Tournament years done")

    # FIX 3: Tag Indian players by known names
    print("Tagging Indian players...")
    known_indian = ['Excali','Rawfiul','Antidote',
        'Venka','Vibhor','mw1','Deathmaker','hellff',
        'Rite2Ace','Amaterasu','Marzil','Techno',
        'Lightningfast','Karam1L','Rishi','Saarang']
    placeholders = ','.join(
        [f"'{n}'" for n in known_indian])
    conn.execute(text(f"""
        UPDATE players
        SET nationality = 'Indian',
            region = 'South Asia'
        WHERE name IN ({placeholders})
    """))
    print("Indian players tagged")

    # FIX 4: Refresh materialized views
    print("Refreshing views...")

# Views need autocommit - run separately
with engine.connect() as conn:
    conn.execute(text("COMMIT"))
    conn.execute(text("REFRESH MATERIALIZED VIEW mv_player_percentiles"))
    conn.execute(text("REFRESH MATERIALIZED VIEW mv_team_map_winrates"))
    conn.execute(text("COMMIT"))
    print("Views refreshed")

# VERIFY - show counts
with engine.connect() as conn:
    tables = ['map_results','mv_team_map_winrates',
        'mv_player_percentiles','tournaments']
    for t in tables:
        r = conn.execute(
            text(f"SELECT COUNT(*) FROM {t}"))
        print(f"{t}: {r.scalar()} rows")
    
    # Check years fixed
    r = conn.execute(text("""
        SELECT COUNT(*) FROM tournaments 
        WHERE year IS NOT NULL"""))
    print(f"tournaments with year: {r.scalar()}")
    
    # Check Indian players
    r = conn.execute(text("""
        SELECT COUNT(*) FROM players 
        WHERE nationality = 'Indian'"""))
    print(f"Indian players: {r.scalar()}")
