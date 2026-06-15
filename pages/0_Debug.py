import streamlit as st
from db.connection import get_engine
from sqlalchemy import text
import pandas as pd

st.title("Debug — Database Check")

engine = get_engine()

with engine.connect() as conn:
    # Test 1: Raw connection
    result = conn.execute(text("SELECT 1"))
    st.success("Connection OK")
    
    # Test 2: Table counts
    tables = ['players','matches','player_stats',
              'teams','tournaments','maps',
              'economy_stats','mv_player_percentiles']
    for t in tables:
        try:
            r = conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
            count = r.scalar()
            st.write(f"{t}: {count} rows")
        except Exception as e:
            st.error(f"{t}: ERROR — {e}")
    
    # Test 3: Exact player query
    try:
        df = pd.read_sql(
            "SELECT p.player_id, p.name, p.region, "
            "p.nationality, t.name AS team "
            "FROM players p "
            "LEFT JOIN teams t ON p.team_id = t.team_id "
            "ORDER BY p.name LIMIT 10",
            conn
        )
        st.write("Sample players:", df)
    except Exception as e:
        st.error(f"Player query failed: {e}")
