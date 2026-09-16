"""detect_vt_transition_zone must match the original per-window pandas/scipy implementation."""

import time

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from modules.calculations.threshold_types import TransitionZone
from modules.calculations.ventilatory import detect_vt_transition_zone


def _reference_transition_zone(
    df, window_duration=60, step_size=10, ve_column="tymeventilation",
    power_column="watts", hr_column="hr", time_column="time",
):
    """Original implementation: boolean mask over the whole frame for every window."""
    if len(df) < window_duration:
        return None, None
    min_time, max_time = df[time_column].min(), df[time_column].max()
    vt1_c, vt2_c = [], []
    Z = 1.96

    for t in range(int(min_time), int(max_time) - window_duration, step_size):
        w = df[(df[time_column] >= t) & (df[time_column] < t + window_duration)]
        if len(w) < 10:
            continue
        mask = ~(w[time_column].isna() | w[ve_column].isna())
        if mask.sum() < 2:
            slope, err = 0.0, 0.0
        else:
            res = stats.linregress(w[time_column][mask], w[ve_column][mask])
            slope, err = res.slope, res.stderr
        low, up = slope - Z * err, slope + Z * err
        row = {
            "avg_watts": w[power_column].mean(),
            "avg_hr": w[hr_column].mean() if hr_column in w else None,
            "std_err": err,
        }
        if low <= 0.05 <= up and 0.02 <= slope <= 0.08:
            vt1_c.append(row)
        if low <= 0.15 <= up and 0.10 <= slope <= 0.20:
            vt2_c.append(row)

    def process_c(c, threshold, err_scale):
        if not c:
            return None
        df_c = pd.DataFrame(c)
        return TransitionZone(
            range_watts=(df_c["avg_watts"].min(), df_c["avg_watts"].max()),
            range_hr=(df_c["avg_hr"].min(), df_c["avg_hr"].max())
            if "avg_hr" in df_c and df_c["avg_hr"].min()
            else None,
            confidence=max(0.1, min(1.0, 1.0 - (df_c["std_err"].mean() * err_scale))),
            method=f"Sliding Window (threshold {threshold})",
            description=f"Region where slope CI overlaps {threshold}.",
        )

    return process_c(vt1_c, 0.05, 100), process_c(vt2_c, 0.15, 50)


def _ramp(seed, gaps=False, shuffle=False):
    rng = np.random.default_rng(seed)
    n = 1800
    t = np.arange(n, dtype=float)
    if gaps:
        t = t + rng.uniform(-0.3, 0.3, n)
    df = pd.DataFrame({
        "time": t,
        "watts": 100 + 30 * (np.arange(n) // 180) + rng.normal(0, 3, n),
        "hr": 95 + 0.05 * np.arange(n) + rng.normal(0, 1, n),
        "tymeventilation": 20 + 0.0000045 * np.arange(n) ** 2.3 + rng.normal(0, 0.8, n),
    })
    if gaps:
        df.loc[rng.choice(n, 120, replace=False), "tymeventilation"] = np.nan
        df.loc[rng.choice(n, 40, replace=False), "watts"] = np.nan
        df.loc[rng.choice(n, 5, replace=False), "time"] = np.nan
    if shuffle:
        df = df.sample(frac=1.0, random_state=seed)
    return df


def _assert_zone_close(actual, expected):
    if expected is None:
        assert actual is None
        return
    assert actual is not None
    np.testing.assert_allclose(actual.range_watts, expected.range_watts, rtol=1e-9)
    if expected.range_hr is None:
        assert actual.range_hr is None
    else:
        np.testing.assert_allclose(actual.range_hr, expected.range_hr, rtol=1e-9)
    assert actual.confidence == pytest.approx(expected.confidence, rel=1e-9)
    assert actual.method == expected.method


@pytest.mark.parametrize("window, step", [(30, 5), (45, 5), (60, 5), (90, 5), (60, 10)])
@pytest.mark.parametrize(
    "variant", [dict(seed=1), dict(seed=2, gaps=True), dict(seed=3, gaps=True, shuffle=True)]
)
def test_matches_reference_implementation(window, step, variant):
    df = _ramp(**variant)

    actual = detect_vt_transition_zone(df, window, step, "tymeventilation", "watts", "hr", "time")
    expected = _reference_transition_zone(
        df, window, step, "tymeventilation", "watts", "hr", "time"
    )

    assert expected[0] is not None or expected[1] is not None  # data exercises detection
    for a, e in zip(actual, expected, strict=True):
        _assert_zone_close(a, e)


def test_without_hr_column():
    df = _ramp(seed=4).drop(columns="hr")

    actual = detect_vt_transition_zone(df, 60, 5, "tymeventilation", "watts", None, "time")
    expected = _reference_transition_zone(df, 60, 5, "tymeventilation", "watts", None, "time")

    for a, e in zip(actual, expected, strict=True):
        _assert_zone_close(a, e)


def test_duplicate_timestamps_raise_like_linregress():
    df = pd.DataFrame({
        "time": np.repeat(np.arange(0.0, 200.0, 20.0), 20),
        "watts": np.full(200, 200.0),
        "hr": np.full(200, 140.0),
        "tymeventilation": np.linspace(20, 60, 200),
    })

    with pytest.raises(ValueError, match="identical"):
        _reference_transition_zone(df, 10, 5)
    with pytest.raises(ValueError, match="identical"):
        detect_vt_transition_zone(df, 10, 5)


def test_sensitivity_windows_are_fast_on_three_hour_ride():
    df = pd.concat([_ramp(seed=s).assign(time=lambda d, k=k: d["time"] + k * 1800)
                    for k, s in enumerate(range(6))], ignore_index=True)

    start = time.perf_counter()
    for window in (30, 45, 60, 90):  # run_sensitivity_analysis
        detect_vt_transition_zone(df, window, 5, "tymeventilation", "watts", "hr", "time")
    assert time.perf_counter() - start < 0.5
