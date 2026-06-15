import streamlit as st
import os
from sqlalchemy import text
import pandas as pd

st.title("Debug")

try:
    db_url = st.secrets["DB_URL"]
except Exception:
    db_url = os.environ.get("DB_URL")

st.write("DB_URL found:", bool(db_url))
st.write("DB_URL preview:", db_url[:50] if db_url else "NONE")

from sqlalchemy import create_engine
engine = create_engine(db_url, pool_pre_ping=True)

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM players"))
        count = result.scalar()
        st.success(f"Connected! Players count: {count}")
except Exception as e:
    st.error(f"Connection failed: {str(e)}")
