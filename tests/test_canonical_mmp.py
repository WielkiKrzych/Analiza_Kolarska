"""5-min MMP used by canonical VO2max: same rolling-mean semantics as the UI KPI."""

import numpy as np
import pytest

from modules.calculations.canonical_physio import (
    build_canonical_physiology,
    calculate_vo2max_acsm,
)

DATA = {"metadata": {"athlete_weight_kg": 75}}


def _ride(n=3600):
    power = np.full(n, 200.0)
    power[1000:1300] = 400.0  # best 5 min
    power[2000:2100] = np.nan  # dropout: windows touching it do not count
    power[2050] = 2000.0
    return power.tolist()


def test_vo2max_from_best_five_minutes_skips_windows_with_gaps():
    physio = build_canonical_physiology(DATA, {"power_watts": _ride()})

    assert physio.vo2max.source == "acsm_5min"
    assert physio.vo2max.value == pytest.approx(calculate_vo2max_acsm(400.0, 75))


def test_divergence_check_uses_time_series_mmp():
    data = {**DATA, "metrics": {"vo2max": 80.0}}

    physio = build_canonical_physiology(data, {"power_watts": _ride()})

    assert physio.vo2max.alternatives["time_series_estimate"] == round(
        calculate_vo2max_acsm(400.0, 75), 2
    )

