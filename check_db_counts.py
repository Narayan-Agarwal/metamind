import os
from dotenv import load_dotenv
from db.connection import get_engine
import pandas as pd

load_dotenv()
engine = get_engine()

sql = """
SELECT schemaname, relname, n_live_tup 
FROM pg_stat_user_tables 
ORDER BY n_live_tup DESC;
"""

df = pd.read_sql(sql, engine)
print(df)
