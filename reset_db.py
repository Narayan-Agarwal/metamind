from db.connection import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.begin() as conn:
    with open("data/schema.sql", encoding="utf-8") as f:
        sql = f.read()
    # Execute statements one by one
    for statement in sql.split(";"):
        if statement.strip():
            conn.execute(text(statement))
print("Schema reset successfully!")
