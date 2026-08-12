"""
Unit tests for Durability analysis (migration plan Phase 1.3).

Covers the advanced versions living in modules.calculations.durability:
calculate_durability_index (method param), calculate_durability_by_season,
get_durability_interpretation, get_durability_recommendations.
"""
import numpy as np
import pandas as pd
import pytest

from modules.calculations import (
    calculate_durability_by_season,
    calculate_durability_index,
    get_durability_interpretation,
    get_durability_recommendations,
)


def _make_watts_profile(n_sec: int, first_half_watts: float, second_half_watts: float) -> pd.DataFrame:
    """Build a 1 Hz DataFrame with two power levels (constant per half)."""
    mid = n_sec // 2
    watts = np.concatenate([
        np.full(mid, first_half_watts),
        np.full(n_sec - mid, second_half_watts),
    ])
    return pd.DataFrame({"watts": watts})


class TestCalculateDurabilityIndex:
    """Tests for calculate_durability_index with method param."""

    def test_half_method_strong_sustainability(self):
        df = _make_watts_profile(3600, 250.0, 245.0)
        di, early, late = calculate_durability_index(df, min_duration_min=20, method="half")
        assert di is not None
        assert 90 <= di <= 100
        assert early == 250
        assert late == 245

    def test_half_method_bad_sustainability(self):
        df = _make_watts_profile(3600, 250.0, 150.0)
        di, _, _ = calculate_durability_index(df, min_duration_min=20, method="half")
        assert di == pytest.approx(60.0, abs=0.1)

    def test_thirds_method(self):
        df = _make_watts_profile(3600, 250.0, 150.0)
        di, _, _ = calculate_durability_index(df, min_duration_min=20, method="thirds")
        # Early third vs late third — same 250 -> 150 drop
        assert di == pytest.approx(60.0, abs=0.1)

    def test_quarter_method(self):
        df = _make_watts_profile(3600, 250.0, 150.0)
        di, _, _ = calculate_durability_index(df, min_duration_min=20, method="quarter")
        assert di == pytest.approx(60.0, abs=0.1)

    def test_unknown_method_falls_back_to_half(self):
        df = _make_watts_profile(3600, 250.0, 245.0)
        di, _, _ = calculate_durability_index(df, min_duration_min=20, method="bogus")
        assert 90 <= di <= 100

    def test_insufficient_duration_returns_none(self):
        df = _make_watts_profile(600, 250.0, 245.0)  # 10 min < 20 min
        result = calculate_durability_index(df, min_duration_min=20, method="half")
        assert result == (None, None, None)

    def test_missing_watts_column_returns_none(self):
        df = pd.DataFrame({"heartrate": [120] * 3600})
        result = calculate_durability_index(df, min_duration_min=20, method="half")
        assert result == (None, None, None)

    def test_zero_early_avg_returns_none(self):
        df = _make_watts_profile(3600, 0.0, 100.0)
        result = calculate_durability_index(df, min_duration_min=20, method="half")
        assert result == (None, None, None)


class TestCalculateDurabilityBySeason:
    """Tests for calculate_durability_by_season sliding-window analysis."""

    def test_returns_dataframe_with_windows(self):
        df = _make_watts_profile(3600, 250.0, 150.0)
        result = calculate_durability_by_season(df, season_length_min=5)
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert {"start_time", "end_time", "durability_index"} <= set(result.columns)

    def test_too_short_returns_empty(self):
        df = _make_watts_profile(300, 250.0, 150.0)  # 5 min < 2 seasons
        result = calculate_durability_by_season(df, season_length_min=5)
        assert result.empty

    def test_missing_watts_returns_empty(self):
        df = pd.DataFrame({"heartrate": [120] * 3600})
        result = calculate_durability_by_season(df, season_length_min=5)
        assert result.empty


class TestGetDurabilityInterpretation:
    """Tests for the detailed interpretation ladder."""

    def test_none_returns_missing_data(self):
        text = get_durability_interpretation(None)
        assert "Brak danych" in text

    def test_elite_level(self):
        assert "Fenomenalna" in get_durability_interpretation(98.5)

    def test_good_level(self):
        assert "Dobra" in get_durability_interpretation(91.0)

    def test_poor_level(self):
        assert "Bardzo słaba" in get_durability_interpretation(70.0)


class TestGetDurabilityRecommendations:
    """Tests for training recommendations."""

    def test_none_di_returns_warning(self):
        recs = get_durability_recommendations(None, 60)
        assert recs
        assert any("Za mało danych" in r for r in recs)

    def test_returns_list_of_strings(self):
        recs = get_durability_recommendations(92.0, 120)
        assert isinstance(recs, list)
        assert recs
        assert all(isinstance(r, str) for r in recs)

    def test_short_workout_hint(self):
        recs = get_durability_recommendations(92.0, 20)
        assert any("<30min" in r for r in recs)

    def test_long_workout_hint(self):
        recs = get_durability_recommendations(92.0, 120)
        assert any(">90min" in r for r in recs)

    def test_low_di_gets_advanced_microtraining(self):
        recs = get_durability_recommendations(80.0, 60)
        assert any("mikrotrening" in r for r in recs)
