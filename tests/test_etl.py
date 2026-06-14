import pandas as pd
from data.etl import normalize_family_a, normalize_family_c, clean_percentages, deduplicate

def test_normalize_family_a():
    df = pd.DataFrame({
        "Average Combat Score": [250],
        "Player": ["TenZ"]
    })
    norm = normalize_family_a(df)
    assert "acs" in norm.columns
    assert "player_name" in norm.columns

def test_clean_percentages():
    df = pd.DataFrame({
        "hs_percent": ["25%", "30%"],
        "other": ["10", "20"]
    })
    cleaned = clean_percentages(df)
    assert cleaned["hs_percent"].iloc[0] == 25.0
    assert cleaned["other"].iloc[0] == "10"

def test_deduplicate():
    df = pd.DataFrame({
        "player_name_normalized": ["tenz", "tenz", "yay"],
        "match_id": [1, 1, 2]
    })
    dedup = deduplicate(df, subset=["player_name_normalized", "match_id"])
    assert len(dedup) == 2
