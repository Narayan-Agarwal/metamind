from analytics.form_engine import compute_form_status

def test_form_status_peaking():
    recent = [250, 260, 270]
    season_avg = 200
    status = compute_form_status(recent, season_avg, 20, 200)
    assert status == "PEAKING"

def test_form_status_declining():
    recent = [150, 160, 140]
    season_avg = 200
    status = compute_form_status(recent, season_avg, 20, 200)
    assert status == "DECLINING"

def test_form_status_consistent():
    recent = [190, 210, 200]
    season_avg = 200
    status = compute_form_status(recent, season_avg, 10, 200)
    assert status == "CONSISTENT"
