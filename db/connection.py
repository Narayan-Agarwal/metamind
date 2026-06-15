import os
import streamlit as st
from sqlalchemy import create_engine

def get_engine():
    try:
        db_url = st.secrets["DB_URL"]
    except Exception:
        db_url = os.environ.get("DB_URL")
    
    if not db_url:
        raise ValueError("DB_URL not set")
    
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    return engine
