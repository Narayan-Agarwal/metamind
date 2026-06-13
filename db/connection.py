"""
MetaMind — Database connection manager.

Provides SQLAlchemy engine and session factories with support for
local .env files and Streamlit Cloud secrets.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


def get_db_url() -> str:
    """Get database URL from environment, supporting both local .env and Streamlit Cloud.

    Resolution order:
        1. ``DB_URL`` environment variable (set via .env or shell).
        2. Streamlit secrets  (``[database] DB_URL`` in secrets.toml).

    Returns:
        str: A valid SQLAlchemy database URL.

    Raises:
        ValueError: If no database URL can be resolved from any source.
    """
    db_url: str | None = os.environ.get("DB_URL")

    if not db_url:
        # Fallback: try Streamlit secrets (available on Streamlit Cloud)
        try:
            import streamlit as st  # noqa: WPS433 — conditional import

            db_url = st.secrets.get("database", {}).get("DB_URL")
        except Exception:  # noqa: BLE001 — broad catch intentional
            pass

    if not db_url:
        raise ValueError(
            "DB_URL environment variable is not set. "
            "Add it to your .env file or Streamlit secrets."
        )

    return db_url


def get_engine():
    """Create and return a SQLAlchemy engine with connection pooling.

    Returns:
        sqlalchemy.engine.Engine: Configured engine instance.
    """
    return create_engine(get_db_url(), pool_pre_ping=True, pool_size=5)


def get_session():
    """Create and return a new SQLAlchemy ORM session.

    Returns:
        sqlalchemy.orm.Session: A freshly opened session bound to the default engine.
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
