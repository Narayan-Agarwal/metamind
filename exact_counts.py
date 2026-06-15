import os
from dotenv import load_dotenv
from db.connection import get_engine
import pandas as pd

load_dotenv()
engine = get_engine()

try:
    df = pd.read_sql("SELECT * FROM mv_player_percentiles LIMIT 1", engine)
    print("mv_player_percentiles columns:")
    for col in df.columns:
        print(f" - {col}")
except Exception as e:
    print(f"Error querying mv_player_percentiles: {e}")
