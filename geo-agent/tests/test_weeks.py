import pytest
from geo.shared.weeks import validate_production_week, TEST_WEEK, TEST_WEEK_MIN, TEST_WEEK_MAX

@pytest.mark.parametrize("w", [1, 2, 8, 53, 100, 899])
def test_production_weeks_pass(w):
    assert validate_production_week(w) == w

@pytest.mark.parametrize("w", [0, -1, -100])
def test_nonpositive_rejected(w):
    with pytest.raises(ValueError, match="week"):
        validate_production_week(w)

def test_test_band_rejected():
    for w in (TEST_WEEK_MIN, TEST_WEEK, 950, TEST_WEEK_MAX):
        with pytest.raises(ValueError, match="测试保留带"):
            validate_production_week(w)
