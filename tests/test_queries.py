import pytest
import pandas as pd
from db.queries import (
    get_all_players,
    get_leaderboard,
    get_player_percentiles,
    get_south_asia_spotlight,
    get_acs_distribution,
    get_top_players,
)

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
    assert float(df["avg_acs"].iloc[0]) == pytest.approx(301.4)

def test_get_leaderboard_empty_when_no_data(mocker):
    mock_engine = mocker.MagicMock()
    mocker.patch("db.queries.pd.read_sql", return_value=pd.DataFrame())
    df = get_leaderboard(mock_engine, min_matches=10)
    assert df.empty

def test_get_player_percentiles_returns_row(mocker):
    mock_engine = mocker.MagicMock()
    mock_df = pd.DataFrame({
        "player_id": [1],
        "name": ["Excali"],
        "avg_acs": [274.1],
        "avg_kd": [1.2],
        "avg_kast": [76.0],
        "avg_fb": [0.15],
        "consistency_score": [64.2],
        "acs_percentile": [0.96],
        "matches_played": [12],
        "region": ["South Asia"],
        "nationality": ["IN"]
    })
    mocker.patch("db.queries.pd.read_sql", return_value=mock_df)
    df = get_player_percentiles(mock_engine, player_id=1)
    assert not df.empty
    assert df.iloc[0]["name"] == "Excali"
    assert float(df.iloc[0]["avg_acs"]) == pytest.approx(274.1)

def test_get_south_asia_spotlight_columns(mocker):
    mock_engine = mocker.MagicMock()
    mock_df = pd.DataFrame({
        "name": ["Excali", "mw1"],
        "avg_acs": [274.1, 270.9],
        "avg_kd": [1.2, 1.1],
        "consistency": [64.2, 68.7],
        "global_percentile": [96, 96],
        "matches_played": [12, 10],
        "avg_kast": [76.0, 74.0]
    })
    mocker.patch("db.queries.pd.read_sql", return_value=mock_df)
    df = get_south_asia_spotlight(mock_engine)
    assert not df.empty
    assert "name" in df.columns
    assert "consistency" in df.columns
    assert "global_percentile" in df.columns
    assert len(df) == 2

def test_get_acs_distribution_sorted(mocker):
    mock_engine = mocker.MagicMock()
    mock_df = pd.DataFrame({
        "name": ["PlayerA", "PlayerB", "PlayerC"],
        "avg_acs": [150.0, 200.0, 250.0],
        "consistency_score": [60.0, 70.0, 80.0]
    })
    mocker.patch("db.queries.pd.read_sql", return_value=mock_df)
    df = get_acs_distribution(mock_engine, min_matches=5)
    assert not df.empty
    assert "avg_acs" in df.columns
    assert "consistency_score" in df.columns
    assert len(df) == 3

def test_get_top_players_limit(mocker):
    mock_engine = mocker.MagicMock()
    mock_df = pd.DataFrame({
        "name": [f"Player{i}" for i in range(15)],
        "avg_acs": [float(300 - i*5) for i in range(15)],
        "consistency_score": [75.0] * 15,
        "matches_played": [10] * 15,
        "region": ["South Asia"] * 15
    })
    mocker.patch("db.queries.pd.read_sql", return_value=mock_df)
    df = get_top_players(mock_engine, limit=15)
    assert not df.empty
    assert len(df) == 15
    assert "avg_acs" in df.columns

def test_get_all_players_name_not_null(mocker):
    mock_engine = mocker.MagicMock()
    mock_df = pd.DataFrame({
        "player_id": [1, 2],
        "name": ["Excali", "mw1"],
        "region": ["South Asia", "South Asia"],
        "nationality": ["IN", "IN"]
    })
    mocker.patch("db.queries.pd.read_sql", return_value=mock_df)
    df = get_all_players(mock_engine)
    assert df["name"].notna().all()
