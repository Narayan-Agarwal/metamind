from analytics.edge_score import compute_edge_score

def test_compute_edge_score():
    player_a = {
        "avg_acs": 250,
        "avg_kd": 1.2,
        "consistency_score": 80,
        "avg_fb": 0.15,
        "avg_kast": 75
    }
    player_b = {
        "avg_acs": 220,
        "avg_kd": 1.0,
        "consistency_score": 85,
        "avg_fb": 0.10,
        "avg_kast": 70
    }
    score = compute_edge_score(player_a, player_b)
    assert score["player_a_score"] > score["player_b_score"]
    assert score["player_a_wins"] == 4
    assert score["player_b_wins"] == 1
