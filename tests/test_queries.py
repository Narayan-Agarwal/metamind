import pytest
import pandas as pd
from db.queries import get_all_players, get_leaderboard

def test_get_all_players_returns_dataframe(mocker):
    mock_engine = mocker.MagicMock()
    mock_df = pd.DataFrame({
        "player_id": [1, 2, 3],
        "name": ["Excali", "mw1", "Lightningfast"],
        "region": ["South Asia", "South Asia", "South Asia"],
        "nationality": ["IN", "IN", "IN"]
    })
    mocker.patch("db.queries.pd.read_sql", return_value=mock_df)
    df = get_all_players(mock_engine)
    assert not df.empty
    assert "name" in df.columns
    assert len(df) == 3

def test_get_leaderboard_returns_dataframe(mocker):
    mock_engine = mocker.MagicMock()
    mock_df = pd.DataFrame({
        "rank": [1, 2],
        "name": ["qw1", "WARDELL"],
        "region": [None, None],
        "nationality": [None, None],
        "avg_acs": [301.4, 295.9],
        "avg_kd": [0.0, 0.0],
        "consistency": [72.4, 72.2],
        "kast_pct": [76.2, 85.2],
        "first_kill_pct": [0.0, 0.0],
        "matches_played": [10, 11]
    })
    mocker.patch("db.queries.pd.read_sql", return_value=mock_df)
    df = get_leaderboard(mock_engine, min_matches=10)
    assert not df.empty
    assert "name" in df.columns
    assert "avg_acs" in df.columns
    assert float(df["avg_acs"].iloc[0]) == 301.4
