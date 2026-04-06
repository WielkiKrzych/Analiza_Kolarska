"""
SRP: Moduł odpowiedzialny za obliczenia W' Balance (Skarbiec Beztlenowy).
"""

from typing import Union
import numpy as np
import pandas as pd
import io
from numba import jit

from ..utils import _serialize_df_to_parquet_bytes


@jit(nopython=True, fastmath=True)
def calculate_w_prime_fast(watts, time, cp, w_prime_cap):
    """Szybkie obliczenie W' Balance przy użyciu Numba JIT.

    Implementacja modelu różnicowego W' Skiba/Morton.

    FIXED: Added exponential W' reconstitution (Skiba model)
    When power drops below CP, W' recovers exponentially with time constant τ.

    Args:
        watts: Tablica mocy [W]
        time: Tablica czasów [s]
        cp: Critical Power [W]
        w_prime_cap: Pojemność W' [J]

    Returns:
        Tablica wartości W' Balance w czasie
    """
    n = len(watts)
    w_bal = np.empty(n, dtype=np.float64)
    curr_w = w_prime_cap

    prev_time = time[0]

    # FIXED: Skiba exponential recovery time constant (τ)
    # τ = W' / (CP - P_below) typically ~300-600s for trained athletes
    # Using dynamic τ based on power deficit
    tau_base = w_prime_cap / cp * 300.0  # Base τ in seconds

    for i in range(n):
        if i == 0:
            dt = 1.0
        else:
            dt = time[i] - prev_time
            if dt <= 0:
                dt = 1.0
            prev_time = time[i]

        # Differential W' Model: dW/dt = CP - P
        # FIXED: Add exponential recovery when below CP
        power_diff = cp - watts[i]

        if power_diff > 0:
            # Below CP: Exponential reconstitution (Skiba model)
            # W'(t) = W'_remaining + (W'_cap - W'_remaining) * (1 - e^(-dt/τ))
            # Simplified: recover proportionally to time below CP
            tau = tau_base * (cp / max(watts[i], 1.0))  # Dynamic τ
            recovery_rate = (w_prime_cap - curr_w) / tau
            delta = recovery_rate * dt
        else:
            # Above CP: Linear depletion
            delta = power_diff * dt

        # Integral
        curr_w += delta

        # Boundary conditions
        if curr_w > w_prime_cap:
            curr_w = w_prime_cap
        elif curr_w < 0:
            curr_w = 0.0

        w_bal[i] = curr_w

    return w_bal


def calculate_w_prime_biexp(
    watts,
    time,
    cp: float,
    w_prime_cap: float,
    sport: int = 0,
) -> np.ndarray:
    """Bi-exponential W' Balance model (Caen et al., 2021).

    Uses two recovery time constants to model fast (PCr/aerobic) and slow
    (oxidative) reconstitution of W' below Critical Power.

    When power > CP: W' depletes linearly (dW/dt = CP - P).
    When power <= CP: W' recovers via bi-exponential reconstitution:
        W'(t) = W'_cap - (W'_cap - W'_curr) * [A_f * exp(-dt/τ_f) + A_s * exp(-dt/τ_s)]
    where A_f + A_s = 1 (fast + slow amplitude fractions).

    Sport-dependent parameters adjust the time constants:
        - 0 = cycling:   τ_f ~ 50s,  τ_s ~ 400s,  A_f ~ 0.65
        - 1 = running:   τ_f ~ 30s,  τ_s ~ 300s,  A_f ~ 0.70
        - 2 = swimming:  τ_f ~ 20s,  τ_s ~ 200s,  A_f ~ 0.75

    Args:
        watts: Array of power values [W].
        time: Array of time values [s].
        cp: Critical Power [W].
        w_prime_cap: W' capacity [J].
        sport: 0=cycling, 1=running, 2=swimming.

    Returns:
        Array of W' balance values [J] over time.
    """
    watts = np.asarray(watts, dtype=np.float64)
    time = np.asarray(time, dtype=np.float64)

    # Sport-specific bi-exponential parameters
    _BIEXP_PARAMS = {
        0: (50.0, 400.0, 0.65),  # cycling:  (tau_fast, tau_slow, A_fast)
        1: (30.0, 300.0, 0.70),  # running
        2: (20.0, 200.0, 0.75),  # swimming
    }
    tau_f, tau_s, a_f = _BIEXP_PARAMS.get(sport, _BIEXP_PARAMS[0])
    a_s = 1.0 - a_f  # slow amplitude fraction

    n = len(watts)
    w_bal = np.empty(n, dtype=np.float64)
    curr_w = w_prime_cap

    prev_time = time[0]

    for i in range(n):
        if i == 0:
            dt = 1.0
        else:
            dt = time[i] - prev_time
            if dt <= 0:
                dt = 1.0
            prev_time = time[i]

        power_diff = cp - watts[i]

        if power_diff > 0:
            # Below CP: bi-exponential reconstitution
            deficit = w_prime_cap - curr_w
            recovery_factor = a_f * np.exp(-dt / tau_f) + a_s * np.exp(-dt / tau_s)
            curr_w = w_prime_cap - deficit * recovery_factor
        else:
            # Above CP: linear depletion
            curr_w += power_diff * dt

        # Boundary conditions
        if curr_w > w_prime_cap:
            curr_w = w_prime_cap
        elif curr_w < 0.0:
            curr_w = 0.0

        w_bal[i] = curr_w

    return w_bal


def _calculate_w_prime_balance_cached(df_bytes: bytes, cp: float, w_prime: float):
    """Cached version of W' Balance calculation."""
    try:
        bio = io.BytesIO(df_bytes)
        try:
            df_pd = pd.read_parquet(bio)
        except Exception:
            bio.seek(0)
            df_pd = pd.read_csv(bio)

        if "watts" not in df_pd.columns:
            df_pd["w_prime_balance"] = np.nan
            return df_pd

        watts_arr = df_pd["watts"].to_numpy(dtype=np.float64)

        if "time" in df_pd.columns:
            time_arr = df_pd["time"].to_numpy(dtype=np.float64)
        else:
            time_arr = np.arange(len(watts_arr), dtype=np.float64)

        w_bal = calculate_w_prime_fast(watts_arr, time_arr, float(cp), float(w_prime))

        df_pd["w_prime_balance"] = w_bal
        return df_pd

    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"W' calculation failed: {e}")
        # Try to return DataFrame with zero W' balance
        try:
            bio = io.BytesIO(df_bytes)
            try:
                df_pd = pd.read_parquet(bio)
            except (ImportError, ValueError):
                bio.seek(0)
                df_pd = pd.read_csv(bio)
            df_pd["w_prime_balance"] = 0.0
            return df_pd
        except (pd.errors.ParserError, ValueError, KeyError) as recovery_error:
            logging.getLogger(__name__).error(f"W' recovery failed: {recovery_error}")
            return pd.DataFrame({"w_prime_balance": []})


def calculate_w_prime_balance(_df_pl_active, cp: float, w_prime: float) -> pd.DataFrame:
    """Calculate W' Balance for the entire workout.

    Args:
        _df_pl_active: DataFrame with workout data
        cp: Critical Power [W]
        w_prime: W' capacity [J]

    Returns:
        DataFrame with added 'w_prime_balance' column
    """
    if isinstance(_df_pl_active, dict):
        df_pd = pd.DataFrame(_df_pl_active)
    elif hasattr(_df_pl_active, "to_pandas"):
        df_pd = _df_pl_active.to_pandas()
    else:
        df_pd = _df_pl_active.copy()

    if "time" not in df_pd.columns:
        df_pd["time"] = np.arange(len(df_pd), dtype=float)

    df_bytes = _serialize_df_to_parquet_bytes(df_pd)
    result_df = _calculate_w_prime_balance_cached(df_bytes, float(cp), float(w_prime))
    return result_df


# ============================================================
# NEW: Recovery Score - TrainerRoad Readiness Inspired
# ============================================================


def calculate_recovery_score(
    w_bal_end: float,
    w_prime_capacity: float,
    time_since_effort_sec: int = 0,
    tau_seconds: float = 400.0,
    time_bonus_max: float = 30.0,
    return_rich: bool = False,
) -> Union[float, "RecoveryScoreResult"]:
    """Calculate Recovery Score based on W' balance state.

    Estimates readiness for next high-intensity effort based on
    current W' balance and time since last effort.

    Recovery Score 0-100:
    - 90-100: Fully recovered, ready for any intensity
    - 70-90: Well recovered, can do threshold work
    - 50-70: Partially recovered, endurance zone preferred
    - 30-50: Fatigued, recovery ride only
    - <30: Exhausted, rest needed

    Args:
        w_bal_end: Current W' balance (J)
        w_prime_capacity: Full W' capacity (J)
        time_since_effort_sec: Time since last high-intensity effort
        tau_seconds: Time constant for W' reconstitution (default: 400s)
        time_bonus_max: Maximum time bonus points (default: 30)
        return_rich: If True, return RecoveryScoreResult; if False, return float

    Returns:
        RecoveryScoreResult object (or float if return_rich=False)
    """
    from models import RecoveryScoreResult

    if w_prime_capacity <= 0:
        if return_rich:
            return RecoveryScoreResult(
                score=0.0,
                w_pct=0.0,
                time_bonus=0.0,
                tau_seconds=tau_seconds,
                time_bonus_max=time_bonus_max,
                recommendation=("❌ Brak danych", "Brak danych W'"),
            )
        return 0.0

    # Base score from W' percentage
    w_pct = (w_bal_end / w_prime_capacity) * 100

    # Time bonus (W' recovers over time)
    time_bonus = 0.0
    if time_since_effort_sec > 0:
        # Exponential recovery model
        recovery_factor = 1 - np.exp(-time_since_effort_sec / tau_seconds)
        time_bonus = recovery_factor * time_bonus_max

    score = min(100, w_pct + time_bonus)
    score = round(max(0, score), 0)

    if return_rich:
        recommendation = get_recovery_recommendation(score)
        return RecoveryScoreResult(
            score=score,
            w_pct=w_pct,
            time_bonus=time_bonus,
            tau_seconds=tau_seconds,
            time_bonus_max=time_bonus_max,
            recommendation=recommendation,
        )
    return score


def get_recovery_recommendation(score: float) -> tuple:
    """Get training recommendation based on Recovery Score.

    Args:
        score: Recovery Score (0-100)

    Returns:
        Tuple of (zone_recommendation, description)
    """
    if score >= 90:
        return (
            "🟢 Pełna gotowość",
            "Możesz wykonać dowolny trening, włącznie z VO2max i sprintami.",
        )
    elif score >= 70:
        return (
            "🟢 Dobra gotowość",
            "Trening progowy lub Sweet Spot OK. Unikaj maksymalnych wysiłków.",
        )
    elif score >= 50:
        return (
            "🟡 Częściowe odzyskanie",
            "Zalecana strefa Z2/Z3. Skup się na objętości, nie intensywności.",
        )
    elif score >= 30:
        return ("🟠 Zmęczenie", "Tylko łatwa jazda regeneracyjna (Z1). Odpoczywaj.")
    else:
        return ("🔴 Wyczerpanie", "Dzień wolny lub bardzo łatwa aktywność. Priorytet: regeneracja.")


def estimate_w_prime_reconstitution(
    depleted_pct: float, recovery_time_sec: int, tau: float = 400
) -> float:
    """Estimate W' reconstitution after recovery period.

    Uses exponential recovery model: W'(t) = W'_depleted * (1 - e^(-t/tau))

    Args:
        depleted_pct: How much W' was depleted (0-100%)
        recovery_time_sec: Recovery time in seconds
        tau: Time constant for W' reconstitution (default 400s)

    Returns:
        Estimated W' as percentage of capacity after recovery
    """
    remaining_pct = 100 - depleted_pct

    # How much of the depletion is recovered
    recovery_factor = 1 - np.exp(-recovery_time_sec / tau)
    recovered = depleted_pct * recovery_factor

    return round(remaining_pct + recovered, 1)
