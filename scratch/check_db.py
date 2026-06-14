import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("D:/projects/MetaMind/.env")
db_url = os.getenv("DB_URL")
if not db_url.startswith("postgresql+psycopg"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://")

engine = create_engine(db_url)
with engine.connect() as conn:
    res = conn.execute(text("SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"))
    print(f"{'schemaname':<15} | {'relname':<30} | {'n_live_tup'}")
    print("-" * 60)
    for row in res:
        print(f"{row[0]:<15} | {row[1]:<30} | {row[2]}")
