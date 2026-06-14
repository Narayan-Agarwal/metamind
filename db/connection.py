import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_engine():
    try:
        import streamlit as st
        db_url = st.secrets["DB_URL"]
    except Exception:
        db_url = os.environ.get("DB_URL")
    
    if not db_url:
        raise ValueError("DB_URL not set")
    
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    )
    return engine

def get_session():
    """Create and return a new SQLAlchemy ORM session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

