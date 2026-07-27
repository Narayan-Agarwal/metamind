import pytest
from data.db_loader import _safe_int, _safe_float, refresh_views

def test_safe_int_with_valid_value():
    assert _safe_int(42) == 42
    assert _safe_int("7") == 7

def test_safe_int_with_none():
    assert _safe_int(None) is None

def test_safe_int_with_invalid():
    assert _safe_int("abc") is None

def test_safe_float_with_valid_value():
    assert _safe_float(3.14) == pytest.approx(3.14)
    assert _safe_float("2.5") == pytest.approx(2.5)

def test_safe_float_with_none():
    assert _safe_float(None) is None

def test_safe_float_with_invalid():
    assert _safe_float("xyz") is None
