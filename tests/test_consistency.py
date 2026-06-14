from analytics.consistency import compute_consistency_score

def test_compute_consistency_score_valid():
    acs_values = [200, 210, 190, 205, 195, 200, 202, 198]
    score = compute_consistency_score(acs_values)
    assert score is not None
    assert 0 <= score <= 100

def test_compute_consistency_score_insufficient_data():
    acs_values = [200, 210]  # Minimum is 8
    score = compute_consistency_score(acs_values)
    assert score is None

def test_compute_consistency_score_clamping():
    # Very high variance to force score below 0
    acs_values = [10, 500, 10, 500, 10, 500, 10, 500]
    score = compute_consistency_score(acs_values)
    assert score is not None
    assert score >= 0
