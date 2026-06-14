import pytest
from sqlalchemy import text
from data.db_loader import get_or_create_team

def test_get_or_create_team_existing(mocker):
    mock_session = mocker.Mock()
    # Simulate existing team
    mock_session.execute.return_value.fetchone.return_value = (1,)
    
    team_id = get_or_create_team(mock_session, "Sentinels")
    assert team_id == 1

def test_get_or_create_team_new(mocker):
    mock_session = mocker.Mock()
    # Simulate not existing, then insertion returning 2
    mock_session.execute.side_effect = [
        mocker.Mock(fetchone=lambda: None),
        mocker.Mock(fetchone=lambda: (2,))
    ]
    
    team_id = get_or_create_team(mock_session, "Paper Rex")
    assert team_id == 2
