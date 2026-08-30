"""
DFA alpha1 longitudinal tracking — non-invasive lactate threshold estimation.

Extracts the power/HR at which DFA alpha1 crosses target values:
    - alpha1 = 0.75 -> HRVT1, the aerobic threshold (≈LT1/VT1)
    - alpha1 = 0.50 -> HRVT2, the anaerobic threshold (≈LT2/RCP)

References:
    Rogers SA, Gronwald T (2022). DFA alpha1 as HRVT1 marker.
    Rogers B et al. (2021). DFA alpha1 ≈ 0.5 marks the second (anaerobic) threshold.
    Mateo-March M et al. (2024). DFA reliability ICC=0.76-0.86.
    Iannetta D et al. (2024). HRVT1 validation.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

# Canonical DFA alpha1 crossing targets for the two ventilatory/lactate thresholds.
HRVT1_ALPHA1 = 0.75  # aerobic threshold (LT1/VT1)
HRVT2_ALPHA1 = 0.50  # anaerobic threshold (LT2/RCP)


@dataclass
class DFAThresholdSession:
    date: str
    threshold_power: float
    threshold_hr: float
    alpha1_at_threshold: float
    quality_grade: str


@dataclass
class DFALongitudinalTrend:
    sessions: List[DFAThresholdSession]
    power_trend_slope: float
    power_trend_r: float
    direction: str
    confidence: float


def extract_dfa_threshold(
    time_arr: np.ndarray,
    alpha1_arr: np.ndarray,
    power_arr: np.ndarray,
    hr_arr: np.ndarray,
    target_alpha1: float = 0.75,
) -> Optional[Tuple[float, float]]:
    """Find power and HR where DFA alpha1 crosses target value.

    Interpolates between points where alpha1 crosses the target.
    Returns (threshold_power, threshold_hr) or None if no crossing found.
    """
    if len(alpha1_arr) < 10 or len(power_arr) < 10:
        return None

    valid = np.isfinite(alpha1_arr) & np.isfinite(power_arr)
    if not np.any(valid):
        return None

    alpha1 = alpha1_arr[valid]
    power = power_arr[valid]
    hr = hr_arr[valid] if len(hr_arr) == len(alpha1_arr) else np.full(len(alpha1), np.nan)
    hr_valid = hr

    # Find first crossing from above to below target
    above = alpha1 > target_alpha1
    crossings = np.where(np.diff(above.astype(int)) != 0)[0]

    if len(crossings) == 0:
        return None

    idx = crossings[0]
    if idx + 1 >= len(alpha1):
        return None

    frac = (
        (target_alpha1 - alpha1[idx]) / (alpha1[idx + 1] - alpha1[idx])
        if alpha1[idx + 1] != alpha1[idx]
        else 0.5
    )
    frac = np.clip(frac, 0, 1)

    threshold_power = power[idx] + frac * (power[idx + 1] - power[idx])
    threshold_hr = (
        hr_valid[idx] + frac * (hr_valid[idx + 1] - hr_valid[idx])
        if np.isfinite(hr_valid[idx]) and np.isfinite(hr_valid[idx + 1])
        else 0.0
    )

    return float(threshold_power), float(threshold_hr)


def extract_dfa_thresholds_both(
    time_arr: np.ndarray,
    alpha1_arr: np.ndarray,
    power_arr: np.ndarray,
    hr_arr: np.ndarray,
) -> dict:
    """Extract both DFA alpha1 thresholds (HRVT1 and HRVT2) in one call.

    HRVT1 (alpha1=0.75) marks the aerobic threshold, HRVT2 (alpha1=0.50) the
    anaerobic threshold. Together they bracket the moderate/heavy/severe
    intensity domains from a single incremental effort — non-invasively.

    Returns:
        dict with 'hrvt1' and 'hrvt2' keys, each either None (no crossing) or a
        {'power', 'hr', 'alpha1'} dict.
    """
    out: dict = {"hrvt1": None, "hrvt2": None}
    for key, target in (("hrvt1", HRVT1_ALPHA1), ("hrvt2", HRVT2_ALPHA1)):
        res = extract_dfa_threshold(time_arr, alpha1_arr, power_arr, hr_arr, target)
        if res is not None:
            out[key] = {"power": res[0], "hr": res[1], "alpha1": target}
    return out


def calculate_dfa_longitudinal_trend(
    sessions: List[DFAThresholdSession],
) -> DFALongitudinalTrend:
    """Calculate linear regression trend of DFA threshold power over time."""
    if len(sessions) < 2:
        return DFALongitudinalTrend(
            sessions=sessions,
            power_trend_slope=0.0,
            power_trend_r=0.0,
            direction="insufficient_data",
            confidence=0.0,
        )

    powers = np.array([s.threshold_power for s in sessions], dtype=float)
    x = np.arange(len(powers), dtype=float)

    n = len(x)
    sx = np.sum(x)
    sy = np.sum(powers)
    sxx = np.sum(x * x)
    sxy = np.sum(x * powers)
    denom = n * sxx - sx * sx

    if abs(denom) < 1e-12:
        slope = 0.0
        r = 0.0
    else:
        slope = (n * sxy - sx * sy) / denom
        mean_y = sy / n
        ss_res = np.sum((powers - (slope * x + (sy - slope * sx) / n)) ** 2)
        ss_tot = np.sum((powers - mean_y) ** 2)
        r = np.sqrt(max(0, 1 - ss_res / max(ss_tot, 1e-12)))

    direction = "improving" if slope > 0.5 else ("declining" if slope < -0.5 else "stable")
    confidence = min(abs(r), 1.0)

    return DFALongitudinalTrend(
        sessions=sessions,
        power_trend_slope=float(slope),
        power_trend_r=float(r),
        direction=direction,
        confidence=float(confidence),
    )


def cross_validate_with_vt(
    dfa_threshold_power: float,
    vt1_power: float,
    vt2_power: float,
) -> dict:
    """Check if DFA threshold falls between VT1 and VT2."""
    result = {
        "dfa_power": dfa_threshold_power,
        "vt1_power": vt1_power,
        "vt2_power": vt2_power,
        "within_range": False,
        "deviation_pct": 0.0,
    }
    if vt1_power <= 0 or vt2_power <= 0:
        return result

    lower = min(vt1_power, vt2_power)
    upper = max(vt1_power, vt2_power)
    result["within_range"] = lower * 0.9 <= dfa_threshold_power <= upper * 1.1

    if dfa_threshold_power > 0:
        result["deviation_pct"] = ((dfa_threshold_power - vt1_power) / vt1_power) * 100
    return result
