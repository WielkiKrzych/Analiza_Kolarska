"""
Unit tests for W' balance and recovery models (w_prime.py).

Covers: exponential depletion/reconstitution (Skiba), bi-exponential model
(Caen et al. 2021), recovery score, and reconstitution estimation.
"""
import numpy as np
import pandas as pd
import pytest

from modules.calculations.w_prime import (
    calculate_recovery_score,
    calculate_w_prime_biexp,
    calculate_w_prime_balance,
    calculate_w_prime_fast,
    estimate_w_prime_reconstitution,
    get_recovery_recommendation,
)


class TestCalculateWPrimeFast:
    """Tests for the Skiba-style exponential W' balance model."""

    def test_constant_above_cp_depletes_linearly(self):
        watts = np.full(300, 350.0)  # 100 W above CP for 300 s
        time = np.arange(300.0)
        w_bal = calculate_w_prime_fast(watts, time, cp=250.0, w_prime_cap=20000.0)
        assert len(w_bal) == 300
        # First iteration already applies dW/dt = -(P - CP) = -100 W
        assert w_bal[0] == pytest.approx(19900.0)
        # After 300 s: 20000 - 30000 -> clamped at 0
        assert w_bal[-1] == pytest.approx(0.0)

    def test_below_cp_recovers_toward_cap(self):
        watts = np.full(600, 100.0)  # 150 W below CP
        time = np.arange(600.0)
        w_bal = calculate_w_prime_fast(watts, time, cp=250.0, w_prime_cap=20000.0)
        # Recovery is exponential — strictly increasing, bounded by cap
        assert w_bal[0] == pytest.approx(20000.0)  # starts full
        assert np.all(np.diff(w_bal) >= 0)
        assert np.all(w_bal <= 20000.0 + 1e-9)

    def test_depletion_then_recovery(self):
        watts = np.concatenate([np.full(100, 350.0), np.full(500, 100.0)])
        time = np.arange(600.0)
        w_bal = calculate_w_prime_fast(watts, time, cp=250.0, w_prime_cap=20000.0)
        # Depleted during first 100 s
        assert w_bal[100] < w_bal[0]
        # Then recovered substantially by the end
        assert w_bal[-1] > w_bal[100]

    def test_never_negative(self):
        rng = np.random.default_rng(42)
        watts = rng.uniform(0, 600, 1000)
        time = np.arange(1000.0)
        w_bal = calculate_w_prime_fast(watts, time, cp=250.0, w_prime_cap=20000.0)
        assert np.all(w_bal >= 0.0)
        assert np.all(w_bal <= 20000.0)


class TestCalculateWPrimeBiexp:
    """Tests for the Caen et al. (2021) bi-exponential model."""

    def test_returns_balance_bounded_by_cap(self):
        watts = np.full(600, 100.0)
        time = np.arange(600.0)
        w_bal = calculate_w_prime_biexp(watts, time, cp=250.0, w_prime_cap=20000.0, sport=0)
        assert len(w_bal) == 600
        assert np.all(w_bal >= 0.0)
        assert np.all(w_bal <= 20000.0)

    def test_depletes_above_cp(self):
        watts = np.full(300, 350.0)
        time = np.arange(300.0)
        w_bal = calculate_w_prime_biexp(watts, time, cp=250.0, w_prime_cap=20000.0, sport=0)
        assert w_bal[-1] < w_bal[0]

    def test_recovery_below_cp_monotonic(self):
        watts = np.full(1200, 100.0)
        time = np.arange(1200.0)
        w_bal = calculate_w_prime_biexp(watts, time, cp=250.0, w_prime_cap=20000.0, sport=0)
        assert np.all(np.diff(w_bal) >= 0)

    def test_sport_fallback_unknown_sport(self):
        watts = np.full(300, 100.0)
        time = np.arange(300.0)
        w_bal_unknown = calculate_w_prime_biexp(watts, time, cp=250.0, w_prime_cap=20000.0, sport=99)
        w_bal_cycling = calculate_w_prime_biexp(watts, time, cp=250.0, w_prime_cap=20000.0, sport=0)
        np.testing.assert_array_equal(w_bal_unknown, w_bal_cycling)

    def test_running_recovery_differs_from_cycling(self):
        # Start from a depleted state (100 s at 350 W), then recover below CP
        watts = np.concatenate([np.full(100, 350.0), np.full(1200, 100.0)])
        time = np.arange(1300.0)
        w_bal_cycle = calculate_w_prime_biexp(watts, time, cp=250.0, w_prime_cap=20000.0, sport=0)
        w_bal_run = calculate_w_prime_biexp(watts, time, cp=250.0, w_prime_cap=20000.0, sport=1)
        assert not np.allclose(w_bal_cycle, w_bal_run)


class TestCalculateWPrimeBalance:
    """Tests for the DataFrame-level entry point."""

    def test_adds_w_prime_balance_column(self):
        df = pd.DataFrame(
            {
                "time": np.arange(1200.0),
                "watts": np.concatenate([np.full(600, 300.0), np.full(600, 100.0)]),
            }
        )
        result = calculate_w_prime_balance(df, cp=250.0, w_prime=20000.0)
        assert "w_prime_balance" in result.columns
        assert len(result) == 1200

    def test_accepts_dict_input(self):
        data = {
            "time": np.arange(1200.0),
            "watts": np.full(1200, 100.0),
        }
        result = calculate_w_prime_balance(data, cp=250.0, w_prime=20000.0)
        assert "w_prime_balance" in result.columns

    def test_missing_watts_yields_nan_column(self):
        df = pd.DataFrame({"heartrate": np.full(300, 120.0)})
        result = calculate_w_prime_balance(df, cp=250.0, w_prime=20000.0)
        assert result["w_prime_balance"].isna().all()


class TestCalculateRecoveryScore:
    """Tests for the recovery readiness score."""

    def test_full_capacity_full_score(self):
        score = calculate_recovery_score(w_bal_end=20000.0, w_prime_capacity=20000.0)
        assert score == 100.0

    def test_half_capacity_half_score(self):
        score = calculate_recovery_score(w_bal_end=10000.0, w_prime_capacity=20000.0)
        assert 45 <= score <= 55

    def test_zero_capacity_zero_score(self):
        score = calculate_recovery_score(w_bal_end=0.0, w_prime_capacity=0.0)
        assert score == 0.0

    def test_rich_result_shape(self):
        from models import RecoveryScoreResult

        result = calculate_recovery_score(
            w_bal_end=15000.0,
            w_prime_capacity=20000.0,
            time_since_effort_sec=600,
            return_rich=True,
        )
        assert isinstance(result, RecoveryScoreResult)
        assert result.score >= 70
        assert isinstance(result.recommendation, tuple)
        assert len(result.recommendation) == 2

    def test_time_bonus_increases_score(self):
        base = calculate_recovery_score(w_bal_end=12000.0, w_prime_capacity=20000.0)
        with_bonus = calculate_recovery_score(
            w_bal_end=12000.0, w_prime_capacity=20000.0, time_since_effort_sec=1800
        )
        assert with_bonus >= base


class TestGetRecoveryRecommendation:
    """Tests for the recommendation ladder."""

    @pytest.mark.parametrize(
        "score,expected_zone",
        [
            (95, "Pełna gotowość"),
            (75, "Dobra gotowość"),
            (55, "Częściowe odzyskanie"),
            (35, "Zmęczenie"),
            (10, "Wyczerpanie"),
        ],
    )
    def test_zones(self, score, expected_zone):
        zone, _ = get_recovery_recommendation(score)
        assert expected_zone in zone


class TestEstimateWPrimeReconstitution:
    """Tests for the exponential reconstitution estimate."""

    def test_no_recovery_time_returns_remaining(self):
        assert estimate_w_prime_reconstitution(depleted_pct=50.0, recovery_time_sec=0) == 50.0

    def test_long_recovery_almost_fully_recovered(self):
        remaining = estimate_w_prime_reconstitution(depleted_pct=50.0, recovery_time_sec=3600)
        assert remaining > 99.0

    def test_half_depletion_after_tau(self):
        # After t = tau, ~63% of depletion recovered
        remaining = estimate_w_prime_reconstitution(depleted_pct=50.0, recovery_time_sec=400)
        assert 79 <= remaining <= 83

    def test_always_within_bounds(self):
        for pct in (0.0, 25.0, 100.0):
            for t in (0, 60, 400, 3600):
                result = estimate_w_prime_reconstitution(pct, t)
                assert 0.0 <= result <= 100.0
