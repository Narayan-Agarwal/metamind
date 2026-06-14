import pytest
from sqlalchemy import text
from db.queries import get_team_map_winrates

def test_get_team_map_winrates(mocker):
    # Mock engine
    mock_engine = mocker.MagicMock()
    
    # Mock pandas read_sql
    import pandas as pd
    mock_df = pd.DataFrame({"map_name": ["Ascent", "Bind"], "win_pct": [65.5, 45.0]})
    mocker.patch("db.queries.pd.read_sql", return_value=mock_df)
    
    df = get_team_map_winrates(mock_engine, 1)
    
    assert not df.empty
    assert len(df) == 2
    assert "map_name" in df.columns
    assert "win_pct" in df.columns
    assert df["map_name"].iloc[0] == "Ascent"
