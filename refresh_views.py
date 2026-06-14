import os
from dotenv import load_dotenv
from db.connection import get_engine
from sqlalchemy import text

load_dotenv()
engine = get_engine()

with engine.begin() as conn:
    print("Refreshing mv_player_percentiles...")
    conn.execute(text("REFRESH MATERIALIZED VIEW mv_player_percentiles"))
    print("Refreshing mv_team_map_winrates...")
    conn.execute(text("REFRESH MATERIALIZED VIEW mv_team_map_winrates"))

print("Views refreshed successfully!")
