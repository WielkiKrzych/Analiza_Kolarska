"""
Ventilatory Threshold — CPET-grade detection (V2.0, laboratory standard).

Orchestrates the full CPET pipeline:
  vt_cpet_preprocessing  — smoothing, unit normalisation, artifact removal
  vt_cpet_steps          — per-step steady-state aggregation
  vt_cpet_ve_only        — 4-point VE-only detection + 4-domain zone construction

Also contains detect_vt_vslope_savgol() — deprecated wrapper for backward compatibility.
"""

import math
from typing import Any, Optional

import numpy as np
import pandas as pd

from .common import validate_threshold_vs_pmax
from .vt_cpet_preprocessing import preprocess_cpet_data
from .vt_cpet_steps import aggregate_step_data
from .vt_cpet_ve_only import detect_ve_only_thresholds

# A heuristic estimate must never carry measurement-grade confidence.
ESTIMATE_MAX_CONFIDENCE = 0.25
# Pmax-ratio estimates are good to roughly +/-10% of Pmax, no better.
ESTIMATE_MARGIN_PMAX_RATIO = 0.10
# Fallback when step spacing cannot be derived (continuous ramp).
DEFAULT_STEP_RESOLUTION_W = 30.0


def _step_resolution_watts(df_steps) -> float:
    """Median power increment between steps — the protocol's resolution limit."""
    if df_steps is None or len(df_steps) < 2:
        return DEFAULT_STEP_RESOLUTION_W
    diffs = df_steps.sort_values("power")["power"].diff().dropna()
    diffs = diffs[diffs > 0]
    if diffs.empty:
        return DEFAULT_STEP_RESOLUTION_W
    return float(diffs.median())


def detect_vt_vslope_savgol(
    df: pd.DataFrame,
    step_range: Optional[Any] = None,
    power_column: str = "watts",
    ve_column: str = "tymeventilation",
    time_column: str = "time",
    min_power_watts: Optional[int] = None,
) -> dict:
    """
    DEPRECATED: Use detect_vt_cpet() for CPET-grade detection.
    This wrapper calls the new function for backward compatibility.
    """
    import warnings

    warnings.warn(
        "detect_vt_vslope_savgol() is deprecated — use detect_vt_cpet() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return detect_vt_cpet(
        df, step_range, power_column, ve_column, time_column, min_power_watts=min_power_watts
    )


def detect_vt_cpet(  # noqa: C901
    df: pd.DataFrame,
    step_range: Optional[Any] = None,
    power_column: str = "watts",
    ve_column: str = "tymeventilation",
    time_column: str = "time",
    hr_column: str = "hr",
    step_duration_sec: int = 180,
    smoothing_window_sec: int = 25,
    min_power_watts: Optional[int] = None,
) -> dict:
    """
    CPET-Grade VT1/VT2 Detection using Ventilatory Equivalents.

    See sub-modules for algorithm details:
      - vt_cpet_preprocessing: smoothing + unit normalisation
      - vt_cpet_steps: steady-state step aggregation
      - vt_cpet_ve_only: 4-point VE-only + zone construction

    Returns:
        dict with vt1_watts, vt2_watts, metabolic_zones, df_steps, analysis_notes, etc.
    """
    result = {
        "vt1_watts": None,
        "vt2_watts": None,
        "vt1_hr": None,
        "vt2_hr": None,
        "vt1_ve": None,
        "vt2_ve": None,
        "vt1_br": None,
        "vt2_br": None,
        "vt1_step": None,
        "vt2_step": None,
        "df_steps": None,
        "method": "not_detected",
        # Reporting honesty: True when the value comes from a heuristic
        # (Pmax ratio / percentile), not from a detected breakpoint.
        "vt1_is_estimate": False,
        "vt2_is_estimate": False,
        "analysis_notes": [],
        "validation": {"vt1_lt_vt2": False, "vt1_before_vt2": False},
        "ramp_start_step": None,
        "cross_validation": None,  # [Issue #7]
        "vt1_confidence": None,
        "vt1_range_low": None,
        "vt1_range_high": None,
        "vt1_confidence_penalty": 0.0,
        "vt2_confidence": None,
        "vt2_range_low": None,
        "vt2_range_high": None,
        "vt2_confidence_penalty": 0.0,
    }

    cols = {
        "power": power_column.lower(),
        "ve": ve_column.lower(),
        "time": time_column.lower(),
        "hr": hr_column.lower(),
    }

    # 1. Preprocess (copy, validate, normalise units, smooth, remove artifacts)
    data, has_hr = preprocess_cpet_data(df, cols, smoothing_window_sec, result)
    if result.get("error"):
        return result

    # 2. Aggregate per-step steady-state values
    df_steps = aggregate_step_data(
        data, cols, step_range, min_power_watts, has_hr, result
    )
    if df_steps is None:
        return result
    result["df_steps"] = df_steps

    # 3.5 [Issue #7] Cross-validation between detection methods. Dormant since the
    # gas-exchange path was removed: with one detection method there is nothing to
    # cross-validate, but the key stays in the result schema for consumers.
    cross_validation = {
        "enabled": False,
        "vt1_methods": [],
        "vt2_methods": [],
        "vt1_deviation_watts": None,
        "vt2_deviation_watts": None,
        "warning": None,
    }

    # 3. Detect thresholds — VE-only, always.
    # The gas-exchange (V-slope) branch was removed: the hardware in use is a
    # TymeWear VitalPro (VE, breath rate, tidal volume, SmO2), never a VO2 mask.
    # The only VO2 that ever reached the V-slope path was *estimated* from power,
    # which makes the regression circular — it recovers the estimator, not the
    # athlete. detect_ve_only_thresholds() returns a *copy* of result, so it must
    # be reassigned, otherwise every finding is silently discarded and the Pmax
    # fallback below fires on an untouched result.
    result = detect_ve_only_thresholds(df_steps, data, cols, result)

    result["cross_validation"] = cross_validation

    # 4. Global fallback defaults (both paths) [Issue #3]
    # Use Pmax-relative formula for physiological plausibility
    pmax = df_steps["power"].max() if len(df_steps) > 0 else 0

    VT1_PMAX_RATIO_MIN = 0.55  # 55% of Pmax
    VT1_PMAX_RATIO_MAX = 0.65  # 65% of Pmax
    VT2_PMAX_RATIO_MIN = 0.75  # 75% of Pmax
    VT2_PMAX_RATIO_MAX = 0.85  # 85% of Pmax

    if result["vt1_watts"] is None and pmax > 0:
        # Use midpoint of physiological range
        vt1_power = int(pmax * ((VT1_PMAX_RATIO_MIN + VT1_PMAX_RATIO_MAX) / 2))
        result["vt1_watts"] = vt1_power
        result["vt1_is_estimate"] = True
        result["method"] = "pmax_ratio_fallback"
        result["analysis_notes"].append(
            f"⚠️ VT1 NIE WYKRYTY — szacunek z Pmax ({vt1_power}W = 60% z {pmax}W Pmax). "
            f"To nie jest zmierzony próg."
        )

    if result["vt2_watts"] is None and pmax > 0:
        # Use midpoint of physiological range
        vt2_power = int(pmax * ((VT2_PMAX_RATIO_MIN + VT2_PMAX_RATIO_MAX) / 2))
        result["vt2_watts"] = vt2_power
        result["vt2_is_estimate"] = True
        result["method"] = "pmax_ratio_fallback"
        result["analysis_notes"].append(
            f"⚠️ VT2 NIE WYKRYTY — szacunek z Pmax ({vt2_power}W = 80% z {pmax}W Pmax). "
            f"To nie jest zmierzony próg."
        )

    # 5. Physiological validation
    if result["vt1_watts"] >= result["vt2_watts"]:
        result["analysis_notes"].append("⚠️ VT1 >= VT2 - adjusted VT2 to VT1 + 15%")
        result["vt2_watts"] = int(result["vt1_watts"] * 1.15)
    result["validation"]["vt1_lt_vt2"] = result["vt1_watts"] < result["vt2_watts"]

    # C3: Confidence intervals for threshold values
    # VT shifts ±10-20W day-to-day (hydration, glycogen, temperature)
    # Gronwald et al. 2024 meta-analysis confirms VT/LT correspondence
    # but inherent measurement uncertainty exists
    vt1_penalty = result.get("vt1_confidence_penalty", 0.0)
    vt2_penalty = result.get("vt2_confidence_penalty", 0.0)

    # Base confidence from detection method
    base_confidence = 0.65

    # A threshold can never be located more precisely than the protocol resolves
    # it: with 30W steps the true breakpoint lies anywhere within +/- half a step.
    step_resolution_w = _step_resolution_watts(df_steps)

    for t, penalty in (("vt1", vt1_penalty), ("vt2", vt2_penalty)):
        if result[f"{t}_watts"] is None:
            continue

        if result.get(f"{t}_is_estimate"):
            # Heuristic value (Pmax ratio / percentile) — not a measurement.
            conf = min(ESTIMATE_MAX_CONFIDENCE, max(0.1, base_confidence - penalty))
            margin = max(step_resolution_w / 2, pmax * ESTIMATE_MARGIN_PMAX_RATIO)
        else:
            conf = max(0.3, base_confidence - penalty)
            # Margin: high confidence = +/-5W, low = +/-20W
            margin = max(5 + (1 - conf) * 25, step_resolution_w / 2)

        result[f"{t}_confidence"] = round(conf, 2)
        result[f"{t}_range_low"] = math.floor(result[f"{t}_watts"] - margin)
        result[f"{t}_range_high"] = math.ceil(result[f"{t}_watts"] + margin)

    _populate_threshold_side_metrics(df_steps, result)

    if result["vt1_step"] and result["vt2_step"]:
        result["validation"]["vt1_before_vt2"] = result["vt1_step"] < result["vt2_step"]

    # 6. [Issue #2] VT2 vs Pmax sanity check
    if result["vt2_watts"] is not None and pmax > 0:
        validation = validate_threshold_vs_pmax(result["vt2_watts"], pmax, "VT2", max_ratio=0.95)
        if not validation["is_valid"]:
            result["analysis_notes"].append(validation["message"])
            result["vt2_confidence_penalty"] = validation["confidence_penalty"]
            result["vt2_unreliable"] = True

    return result


def _populate_threshold_side_metrics(df_steps, result: dict) -> None:
    """
    Fill vt1_hr/vt2_hr/vt1_ve/... by interpolating the step table at the
    threshold power.

    Detection paths set these only when they find a breakpoint; every fallback
    path leaves them None, which is why LTHR (= HR at VT2) never reached the
    report.
    """
    if df_steps is None or len(df_steps) < 2:
        return

    ordered = df_steps.sort_values("power")
    powers = ordered["power"].values

    for t in ("vt1", "vt2"):
        watts = result.get(f"{t}_watts")
        if watts is None:
            continue
        for metric, column in (("hr", "hr"), ("ve", "ve"), ("br", "br")):
            key = f"{t}_{metric}"
            if result.get(key) is not None or column not in ordered.columns:
                continue
            series = ordered[column]
            if series.notna().sum() < 2:
                continue
            value = float(np.interp(watts, powers, series.values))
            result[key] = round(value, 1)
            result[f"{key}_is_interpolated"] = True
