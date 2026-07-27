import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    try:
        import streamlit as st
        db_url = st.secrets["DB_URL"]
    except Exception:
        db_url = os.getenv("DB_URL", "")
    if not db_url:
        raise ValueError("DB_URL not set in secrets or environment")
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
