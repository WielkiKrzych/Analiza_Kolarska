"""
CPET VE-Only Detection — 4-point CPET detection, zone construction, and breakpoint helpers.
"""

from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

# Physiological admissibility window for RCP (Binder 2008, Meyer 2005):
# RCP sits at 85-92% HRmax and 75-90% of peak ramp power. Anything above is
# terminal hyperventilation, not respiratory compensation.
RCP_MAX_PMAX_RATIO = 0.90
RCP_MAX_HRMAX_RATIO = 0.90

# Basin tolerance is 1%, not 2%: on a shallow pre-VT1 limb the equivalent falls
# by under 2% per step, so a 2% band reaches back across steps that are still
# genuinely declining and reports VT1 an entire step or two too low.
# VT1 search starts at 50% of peak ramp power and stops three steps from the top
# (the ventilatory equivalent turns up again past RCP). The lower cut-off is a
# hard physiological floor, not a step count: below half of Pmax the athlete is
# still warming up, VE is driven by thermoregulation and breathing pattern rather
# than by metabolic demand, and a trained cyclist's VT1 does not sit there.
# Expressed as a ratio it is protocol-independent — it behaves the same on a step
# test and on a continuous ramp, unlike "skip the first N steps".
VT1_SEARCH_MIN_PMAX_RATIO = 0.50
VT1_SEARCH_TAIL_STEPS = 3
VT1_EQUIV_BASIN_TOLERANCE = 0.01


def detect_ve_only_thresholds(  # noqa: C901
    df_steps: pd.DataFrame,
    data: pd.DataFrame,
    cols: dict,
    result: dict,
) -> dict:
    """
    VE-only 4-point CPET detection (VT1_onset, VT1_steady, RCP_onset, RCP_steady).

    Returns new result dict with detected thresholds, zones, and notes.
    """
    from scipy.signal import savgol_filter

    result = {**result}
    result["analysis_notes"] = list(result.get("analysis_notes", []))
    result["analysis_notes"].append("VE-only mode: 4-point CPET detection")
    result["method"] = "ve_only_4point_cpet"

    df_steps = df_steps.copy()

    try:
        window = min(5, len(df_steps) if len(df_steps) % 2 == 1 else len(df_steps) - 1)
        if window < 3:
            window = 3
        df_steps["ve_smooth"] = savgol_filter(
            df_steps["ve"].values, window_length=window, polyorder=2
        )
    except Exception:
        df_steps["ve_smooth"] = df_steps["ve"].rolling(3, center=True, min_periods=1).mean()

    has_hr = "hr" in df_steps.columns and df_steps["hr"].notna().sum() > 3
    has_br = "br" in df_steps.columns and df_steps["br"].notna().sum() > 3

    if has_br:
        df_steps["br_smooth"] = df_steps["br"].rolling(3, center=True, min_periods=1).mean()
        df_steps["vt_calc"] = df_steps["ve_smooth"] / df_steps["br_smooth"].replace(0, np.nan)
        df_steps["vt_smooth"] = df_steps["vt_calc"].rolling(3, center=True, min_periods=1).mean()

    # Ventilatory equivalent VE/power — proxy for VE/VO2 when no gas exchange.
    # Its nadir marks VT1. Because VO2 has a power-independent intercept, the
    # VE/power nadir is a *lower* bound on the true VE/VO2 nadir.
    # Built from raw step VE: smoothing is for derivatives, and across only ten
    # steps it blurs a level-based criterion enough to move the nadir a step.
    df_steps["ve_equiv"] = df_steps["ve"] / df_steps["power"].replace(0, np.nan)

    ve_slope = np.gradient(df_steps["ve_smooth"].values, df_steps["power"].values)
    df_steps["ve_slope"] = ve_slope

    ve_accel = np.gradient(ve_slope, df_steps["power"].values)
    df_steps["ve_accel"] = ve_accel
    df_steps["ve_accel_smooth"] = df_steps["ve_accel"].rolling(3, center=True, min_periods=1).mean()

    if has_br:
        br_slope = np.gradient(df_steps["br_smooth"].values, df_steps["power"].values)
        df_steps["br_slope"] = br_slope
        df_steps["br_slope_smooth"] = (
            df_steps["br_slope"].rolling(3, center=True, min_periods=1).mean()
        )

        vt_slope = np.gradient(df_steps["vt_smooth"].ffill().values, df_steps["power"].values)
        df_steps["vt_slope"] = vt_slope
        df_steps["vt_slope_smooth"] = (
            df_steps["vt_slope"].rolling(3, center=True, min_periods=1).mean()
        )

    if has_hr:
        hr_slope = np.gradient(df_steps["hr"].values, df_steps["power"].values)
        df_steps["hr_slope"] = hr_slope
        baseline_hr_slope = np.mean(hr_slope[: min(4, len(hr_slope))])
        if baseline_hr_slope > 0:
            df_steps["hr_drift"] = hr_slope / baseline_hr_slope
        else:
            df_steps["hr_drift"] = np.ones(len(hr_slope))

    baseline_ve_slope = np.mean(df_steps["ve_slope"].iloc[: min(4, len(df_steps))])
    baseline_ve_accel = np.mean(df_steps["ve_accel_smooth"].iloc[: min(4, len(df_steps))])
    baseline_br_slope = 0
    if has_br:
        baseline_br_slope = np.mean(df_steps["br_slope_smooth"].iloc[: min(4, len(df_steps))])

    vt1_onset_idx = _find_vt1_onset(
        df_steps, baseline_ve_slope, baseline_ve_accel, baseline_br_slope, has_br
    )
    vt1_steady_idx, vt1_steady_is_real = _find_vt1_steady(
        df_steps, vt1_onset_idx, baseline_ve_slope, baseline_ve_accel, baseline_br_slope, has_br
    )
    result["vt1_steady_is_real"] = vt1_steady_is_real

    search_start = vt1_steady_idx if vt1_steady_idx else (vt1_onset_idx + 2 if vt1_onset_idx else 4)
    rcp_onset_idx = _find_rcp_onset(
        df_steps, search_start, baseline_ve_accel, baseline_br_slope, has_br, has_hr
    )
    rcp_steady_idx = _find_rcp_steady(df_steps, rcp_onset_idx, baseline_ve_accel, has_br, has_hr)

    def get_point_data(idx, point_name):
        if idx is None:
            return None
        row = (
            df_steps.loc[idx]
            if isinstance(idx, (int, np.integer)) and idx in df_steps.index
            else df_steps.iloc[idx]
        )
        data_pt = {
            "watts": int(row["power"]),
            "ve": round(row["ve"], 1),
            "step": int(row["step"]),
            "time": row.get("time", 0),
        }
        if "hr" in row and pd.notna(row["hr"]):
            data_pt["hr"] = int(row["hr"])
        if "br" in row and pd.notna(row["br"]):
            data_pt["br"] = int(row["br"])
        if "vt_smooth" in row and pd.notna(row["vt_smooth"]):
            data_pt["vt"] = round(row["vt_smooth"], 2)
        return data_pt

    if vt1_onset_idx is not None:
        pt = get_point_data(vt1_onset_idx, "vt1_onset")
        result["vt1_onset_watts"] = pt["watts"]
        result["vt1_watts"] = pt["watts"]
        result["vt1_ve"] = pt["ve"]
        result["vt1_step"] = pt["step"]
        result["vt1_hr"] = pt.get("hr")
        result["vt1_br"] = pt.get("br")
        result["vt1_vt"] = pt.get("vt")
        result["vt1_onset_time"] = pt.get("time")
        result["analysis_notes"].append(f"VT1_onset (GET/LT1): {pt['watts']}W @ step {pt['step']}")

    if vt1_steady_idx is not None and result.get("vt1_steady_is_real", False):
        pt = get_point_data(vt1_steady_idx, "vt1_steady")
        result["vt1_steady_watts"] = pt["watts"]
        result["vt1_steady_ve"] = pt["ve"]
        result["vt1_steady_hr"] = pt.get("hr")
        result["vt1_steady_br"] = pt.get("br")
        result["vt1_steady_vt"] = pt.get("vt")
        result["vt1_steady_time"] = pt.get("time")
        result["vt1_steady_is_interpolated"] = False
        result["analysis_notes"].append(
            f"VT1_steady (LT1 steady): {pt['watts']}W @ step {pt['step']} ✓plateau"
        )
    elif result.get("vt1_onset_watts") and result.get("rcp_onset_watts"):
        vt1_onset_w = result["vt1_onset_watts"]
        rcp_onset_w = result["rcp_onset_watts"]
        vt1_steady_virtual_w = int((vt1_onset_w + rcp_onset_w) / 2)

        virtual_mask = (df_steps["power"] >= vt1_steady_virtual_w - 15) & (
            df_steps["power"] <= vt1_steady_virtual_w + 15
        )
        if virtual_mask.any():
            closest_idx = (
                df_steps.loc[virtual_mask, "power"].sub(vt1_steady_virtual_w).abs().idxmin()
            )
            pt = get_point_data(closest_idx, "vt1_steady_virtual")
            result["vt1_steady_watts"] = pt["watts"]
            result["vt1_steady_ve"] = pt["ve"]
            result["vt1_steady_hr"] = pt.get("hr")
            result["vt1_steady_br"] = pt.get("br")
            result["vt1_steady_time"] = pt.get("time")
        else:
            result["vt1_steady_watts"] = vt1_steady_virtual_w

        result["vt1_steady_is_interpolated"] = True
        result["analysis_notes"].append(
            f"VT1_steady (interpolated): {result['vt1_steady_watts']}W - no physiological plateau detected"
        )
        result["no_steady_state_interpretation"] = (
            "Pomiędzy VT1_onset a RCP_onset nie występuje stabilny stan ustalony wentylacji. "
            "Krzywa VE wykazuje ciągłe przyspieszanie, co wskazuje na: "
            "wąską strefę przejściową, szybkie narastanie buforowania H⁺, "
            "wczesne wejście w domenę heavy. "
            "Profil typowy dla sportowca o wysokiej pojemności tlenowej i stromym przejściu do kompensacji oddechowej."
        )

    if rcp_onset_idx is not None:
        pt = get_point_data(rcp_onset_idx, "rcp_onset")
        result["rcp_onset_watts"] = pt["watts"]
        result["vt2_watts"] = pt["watts"]
        result["vt2_ve"] = pt["ve"]
        result["vt2_step"] = pt["step"]
        result["vt2_hr"] = pt.get("hr")
        result["vt2_br"] = pt.get("br")
        result["rcp_onset_vt"] = pt.get("vt")
        result["rcp_onset_time"] = pt.get("time")
        result["analysis_notes"].append(f"RCP_onset (VT2/LT2): {pt['watts']}W @ step {pt['step']}")

    if rcp_steady_idx is not None:
        pt = get_point_data(rcp_steady_idx, "rcp_steady")
        result["rcp_steady_watts"] = pt["watts"]
        result["rcp_steady_ve"] = pt["ve"]
        result["rcp_steady_hr"] = pt.get("hr")
        result["rcp_steady_br"] = pt.get("br")
        result["rcp_steady_vt"] = pt.get("vt")
        result["rcp_steady_time"] = pt.get("time")
        result["analysis_notes"].append(f"RCP_steady (Full RCP): {pt['watts']}W")

    result = _apply_ve_only_fallbacks(df_steps, data, cols, result)
    result = _build_metabolic_zones(df_steps, result)

    return result


def _find_vt1_onset(df_steps, baseline_ve_slope, baseline_ve_accel, baseline_br_slope, has_br):
    """
    Find VT1_onset — nadir of the ventilatory equivalent, falling back to the
    VE acceleration sign change.

    The nadir is the primary rule because it is the classical VT1 criterion and
    it survives noise: it needs the *level* of VE/power, not its second
    derivative. The slope-based search below only fires on a clean sign change,
    which a real ramp rarely gives — on a 10-step test it returned nothing at
    all and handed VT1 to the 60th-percentile fallback.
    """
    nadir_idx = _find_ventilatory_equivalent_nadir(df_steps)
    if nadir_idx is not None:
        return nadir_idx

    for i in range(3, len(df_steps) - 4):
        accel_prev = df_steps["ve_accel_smooth"].iloc[i - 1]
        accel_curr = df_steps["ve_accel_smooth"].iloc[i]
        sign_change = (accel_prev <= 0 and accel_curr > 0) or (accel_curr > baseline_ve_accel * 2)

        slope_rising = (
            df_steps["ve_slope"].iloc[i] > baseline_ve_slope * 1.15
            and df_steps["ve_slope"].iloc[i + 1] > baseline_ve_slope * 1.10
        )

        br_not_spiking = True
        if has_br and baseline_br_slope > 0:
            br_not_spiking = df_steps["br_slope_smooth"].iloc[i] < baseline_br_slope * 2.0

        if (sign_change or slope_rising) and br_not_spiking:
            if df_steps["ve_slope"].iloc[i + 2] > baseline_ve_slope * 1.05:
                return i

    return None


def _find_vt1_steady(
    df_steps, vt1_onset_idx, baseline_ve_slope, baseline_ve_accel, baseline_br_slope, has_br
):
    """Find VT1_steady index — stable elevated VE slope plateau."""
    if vt1_onset_idx is None:
        return None, False

    for i in range(vt1_onset_idx + 2, len(df_steps) - 3):
        curr_slope = df_steps["ve_slope"].iloc[i]
        next_slope = df_steps["ve_slope"].iloc[i + 1]
        next2_slope = df_steps["ve_slope"].iloc[i + 2]

        elevated = curr_slope > baseline_ve_slope * 1.15

        delta_1 = abs(next_slope - curr_slope) / max(abs(curr_slope), 0.01)
        delta_2 = abs(next2_slope - curr_slope) / max(abs(curr_slope), 0.01)
        slope_stable = delta_1 < 0.12 and delta_2 < 0.15

        br_ok = True
        if has_br and baseline_br_slope > 0:
            br_at_i = df_steps["br_slope_smooth"].iloc[i]
            br_ok = br_at_i < baseline_br_slope * 1.5

        ve_accel_at_i = df_steps["ve_accel_smooth"].iloc[i]
        no_exponential = ve_accel_at_i < baseline_ve_accel * 2.5

        if elevated and slope_stable and br_ok and no_exponential:
            return i, True

    return None, False


def _find_rcp_onset(
    df_steps, search_start, baseline_ve_accel, baseline_br_slope, has_br, has_hr=False
):
    """
    Find RCP_onset — strongest VE acceleration *inside the physiologically
    admissible window* (see _rcp_admissible_index), plus BR spike and VT plateau.

    Restricting the window before taking the maximum is the whole point: VE
    acceleration in a ramp-to-exhaustion peaks at the final step by
    construction, so an unrestricted argmax reports terminal hyperventilation
    as RCP.
    """
    if not search_start or search_start >= len(df_steps) - 3:
        return None

    admissible = _rcp_admissible_index(df_steps, has_hr)
    if len(admissible) == 0:
        return None

    # search_start comes from VT1 and can overshoot the admissible window on a
    # test where VT1 sits high. Clamp rather than give up, otherwise RCP falls
    # through to the power-percentile estimate.
    last_admissible = df_steps.index.get_loc(admissible[-1])
    search_df = df_steps.iloc[min(search_start, last_admissible) :]
    search_df = search_df.loc[search_df.index.intersection(admissible)]
    if search_df.empty:
        return None

    max_accel_idx = search_df["ve_accel_smooth"].idxmax()
    max_accel_val = df_steps.loc[max_accel_idx, "ve_accel_smooth"]

    rcp_candidates = []

    for idx in search_df.index:
        ve_accel_high = df_steps.loc[idx, "ve_accel_smooth"] > max_accel_val * 0.6

        br_spike = True
        vt_plateau = True

        if has_br:
            br_slope_val = df_steps.loc[idx, "br_slope_smooth"]
            br_spike = (
                br_slope_val > baseline_br_slope * 2.0
                if baseline_br_slope > 0
                else br_slope_val > 0.1
            )

            vt_slope_val = abs(df_steps.loc[idx, "vt_slope_smooth"])
            baseline_vt_slope = abs(
                np.mean(df_steps["vt_slope_smooth"].iloc[: min(4, len(df_steps))])
            )
            vt_plateau = vt_slope_val < baseline_vt_slope * 0.7 if baseline_vt_slope > 0 else True

        if ve_accel_high and br_spike and vt_plateau:
            rcp_candidates.append((idx, df_steps.loc[idx, "ve_accel_smooth"]))

    if rcp_candidates:
        return max(rcp_candidates, key=lambda x: x[1])[0]
    else:
        return max_accel_idx


def _find_ventilatory_equivalent_nadir(df_steps):
    """Index of the minimum VE/power, searched away from both ends of the ramp."""
    if "ve_equiv" not in df_steps.columns:
        return None

    power_floor = df_steps["power"].max() * VT1_SEARCH_MIN_PMAX_RATIO
    above_floor = np.flatnonzero(df_steps["power"].values >= power_floor)
    if len(above_floor) == 0:
        return None
    lo, hi = int(above_floor[0]), len(df_steps) - VT1_SEARCH_TAIL_STEPS
    if hi - lo < 2:
        return None

    window = df_steps["ve_equiv"].iloc[lo:hi]
    if window.isna().all():
        return None

    # The nadir is a flat basin, not a spike — two neighbouring steps routinely
    # sit within 1% of each other, so a bare idxmin() flips between them on
    # noise. VT1_*onset* is the entry into that basin: the first step that gets
    # within tolerance of the minimum.
    floor = window.min() * (1 + VT1_EQUIV_BASIN_TOLERANCE)
    within = window[window <= floor]
    return within.index[0] if len(within) else window.idxmin()


def _rcp_admissible_index(df_steps, has_hr):
    """
    Steps that could physiologically be RCP.

    Without this the search runs to the end of the ramp, where VE acceleration
    is always largest — terminal hyperventilation. Any argmax over the full
    range therefore reports the last step as RCP regardless of the athlete.
    """
    power_ok = df_steps["power"] <= df_steps["power"].max() * RCP_MAX_PMAX_RATIO

    if has_hr and "hr" in df_steps.columns and df_steps["hr"].notna().any():
        hr_ok = df_steps["hr"] <= df_steps["hr"].max() * RCP_MAX_HRMAX_RATIO
    else:
        hr_ok = True

    return df_steps.index[power_ok & hr_ok]


def _find_rcp_steady(df_steps, rcp_onset_idx, baseline_ve_accel, has_br, has_hr):
    """Find RCP_steady index — high VE acceleration + BR dominates + HR drift."""
    if rcp_onset_idx is None:
        return None

    rcp_onset_loc = df_steps.index.get_loc(rcp_onset_idx)

    for i in range(rcp_onset_loc + 1, len(df_steps) - 1):
        idx = df_steps.index[i]

        ve_accel_high = df_steps.loc[idx, "ve_accel_smooth"] > baseline_ve_accel * 3

        br_dominates = True
        if has_br:
            br_slope_val = df_steps.loc[idx, "br_slope_smooth"]
            vt_slope_val = df_steps.loc[idx, "vt_slope_smooth"]
            br_dominates = (
                abs(br_slope_val) > abs(vt_slope_val) * 1.5 if vt_slope_val != 0 else True
            )

        hr_drift_strong = True
        if has_hr:
            hr_drift_strong = df_steps.loc[idx, "hr_drift"] > 1.5

        if ve_accel_high and br_dominates and hr_drift_strong:
            return idx

    if rcp_onset_loc + 1 < len(df_steps):
        return df_steps.index[min(rcp_onset_loc + 1, len(df_steps) - 1)]

    return None


def _apply_ve_only_fallbacks(df_steps, data, cols, result):  # noqa: C901
    """Apply fallback estimates and enforce monotonic zone boundaries."""
    max_power = int(df_steps["power"].max())

    vt1_onset_w = result.get("vt1_onset_watts")
    vt1_steady_w = result.get("vt1_steady_watts")
    rcp_onset_w = result.get("rcp_onset_watts") or result.get("vt2_watts")
    rcp_steady_w = result.get("rcp_steady_watts")
    is_vt1_steady_interpolated = result.get("vt1_steady_is_interpolated", False)  # noqa: F841

    raw_power = data[data[cols["power"]] >= 100][cols["power"]].values
    power_60th_raw = int(np.percentile(raw_power, 60))
    power_80th_raw = int(np.percentile(raw_power, 80))

    if vt1_onset_w is None:
        vt1_onset_w = power_60th_raw
        result["vt1_onset_watts"] = vt1_onset_w
        result["vt1_watts"] = vt1_onset_w
        result["vt1_is_estimate"] = True
        result["analysis_notes"].append(
            f"⚠️ VT1 NIE WYKRYTY — szacunek 60 percentyl mocy ({vt1_onset_w}W). "
            f"To nie jest zmierzony próg."
        )

    if rcp_onset_w is None:
        rcp_onset_w = power_80th_raw
        result["rcp_onset_watts"] = rcp_onset_w
        result["vt2_watts"] = rcp_onset_w
        result["vt2_is_estimate"] = True
        result["analysis_notes"].append(
            f"⚠️ VT2/RCP NIE WYKRYTY — szacunek 80 percentyl mocy ({rcp_onset_w}W). "
            f"To nie jest zmierzony próg."
        )

    if vt1_steady_w is None:
        vt1_steady_w = int((vt1_onset_w + rcp_onset_w) / 2)
        result["vt1_steady_watts"] = vt1_steady_w
        result["vt1_steady_is_interpolated"] = True
        is_vt1_steady_interpolated = True  # noqa: F841
        result["analysis_notes"].append(
            f"⚠️ VT1_steady interpolowany: {vt1_steady_w}W = (VT1_onset + RCP_onset) / 2"
        )
        result["no_steady_state_interpretation"] = (
            "Nie wykryto stabilnego LT1 steady-state pomiędzy VT1_onset a RCP_onset. "
            "Wentylacja wykazuje ciągłe przyspieszanie, co wskazuje na wąską strefę przejściową "
            "i szybkie wejście w domenę heavy. "
            "Zastosowano interpolowany VT1_steady jako punkt referencyjny dla stref treningowych."
        )

    if rcp_steady_w is None:
        rcp_steady_w = int(rcp_onset_w + (max_power - rcp_onset_w) * 0.4)
        result["rcp_steady_watts"] = rcp_steady_w

    # Percentile guard — estimates only. The 60th percentile of the raw power
    # samples is a property of the protocol, not of the athlete; applying it to
    # a detected breakpoint silently replaces a measurement with an artefact.
    if result.get("vt1_is_estimate") and vt1_onset_w < power_60th_raw:
        result["analysis_notes"].append(
            f"⚠️ VT1_onset ({vt1_onset_w}W) poniżej 60 percentyla ({power_60th_raw}W) - korekta"
        )
        vt1_onset_w = power_60th_raw
        result["vt1_onset_watts"] = vt1_onset_w
        result["vt1_watts"] = vt1_onset_w
        result["vt1_is_estimate"] = True

    if result.get("vt2_is_estimate") and rcp_onset_w < power_80th_raw:
        result["analysis_notes"].append(
            f"⚠️ RCP_onset ({rcp_onset_w}W) poniżej 80 percentyla ({power_80th_raw}W) - korekta"
        )
        rcp_onset_w = power_80th_raw
        result["rcp_onset_watts"] = rcp_onset_w
        result["vt2_watts"] = rcp_onset_w
        result["vt2_is_estimate"] = True

    # Enforce monotonicity
    boundaries_valid = vt1_onset_w < vt1_steady_w < rcp_onset_w < rcp_steady_w <= max_power

    if not boundaries_valid:
        result["analysis_notes"].append("⚠️ Korekta granic: wymuszenie monotoniczności")

        if vt1_steady_w <= vt1_onset_w:
            vt1_steady_w = vt1_onset_w + int((rcp_onset_w - vt1_onset_w) * 0.4)
            result["vt1_steady_watts"] = vt1_steady_w

        if rcp_onset_w <= vt1_steady_w:
            rcp_onset_w = vt1_steady_w + int((max_power - vt1_steady_w) * 0.5)
            result["rcp_onset_watts"] = rcp_onset_w
            result["vt2_watts"] = rcp_onset_w
            result["vt2_is_estimate"] = True

        if rcp_steady_w <= rcp_onset_w:
            rcp_steady_w = rcp_onset_w + 15
            result["rcp_steady_watts"] = rcp_steady_w

    if vt1_steady_w <= vt1_onset_w:
        vt1_steady_w = int((vt1_onset_w + rcp_onset_w) / 2)
        result["vt1_steady_watts"] = vt1_steady_w
        result["vt1_steady_is_interpolated"] = True

    result["boundaries_valid"] = vt1_onset_w < vt1_steady_w < rcp_onset_w < rcp_steady_w

    return result


def _build_metabolic_zones(df_steps, result):
    """Construct 4-domain metabolic zones from boundary values."""
    vt1_onset_w = result.get("vt1_onset_watts")
    vt1_steady_w = result.get("vt1_steady_watts")
    rcp_onset_w = result.get("rcp_onset_watts") or result.get("vt2_watts")
    rcp_steady_w = result.get("rcp_steady_watts")
    max_power = int(df_steps["power"].max())
    is_vt1_steady_interpolated = result.get("vt1_steady_is_interpolated", False)

    zones = []

    zones.append(
        {
            "zone": 1,
            "name": "Pure Aerobic",
            "power_min": 0,
            "power_max": vt1_onset_w,
            "hr_min": None,
            "hr_max": result.get("vt1_hr"),
            "description": "Full homeostasis, linear VE, no H⁺ buffering",
            "training": "Recovery / Endurance Base",
            "domain": "Moderate",
        }
    )

    zone2_name = "Upper Aerobic (Unstable)" if is_vt1_steady_interpolated else "Upper Aerobic"
    zone2_desc = (
        "Strefa niestabilna - brak plateau VE, ciągłe przyspieszanie"
        if is_vt1_steady_interpolated
        else "Buffering onset, rising VE, stable metabolism"
    )
    zones.append(
        {
            "zone": 2,
            "name": zone2_name,
            "power_min": vt1_onset_w,
            "power_max": vt1_steady_w,
            "hr_min": result.get("vt1_hr"),
            "hr_max": result.get("vt1_steady_hr"),
            "description": zone2_desc,
            "training": "Tempo / Sweet Spot",
            "domain": "Moderate-Heavy Transition",
            "is_interpolated": is_vt1_steady_interpolated,
        }
    )

    zones.append(
        {
            "zone": 3,
            "name": "Heavy Domain",
            "power_min": vt1_steady_w,
            "power_max": rcp_onset_w,
            "hr_min": result.get("vt1_steady_hr"),
            "hr_max": result.get("vt2_hr"),
            "description": "Building acidosis, VE > VO₂, pre-compensation",
            "training": "Threshold / FTP Work",
            "domain": "Heavy",
        }
    )

    zones.append(
        {
            "zone": 4,
            "name": "Severe Domain",
            "power_min": rcp_onset_w,
            "power_max": max_power,
            "hr_min": result.get("vt2_hr"),
            "hr_max": None,
            "description": "Compensatory hyperventilation, no steady-state possible",
            "training": "VO₂max / Anaerobic",
            "domain": "Severe",
            "subzones": [
                {
                    "name": "4a - Severe Onset",
                    "power_min": rcp_onset_w,
                    "power_max": rcp_steady_w,
                    "description": "RCP onset → full RCP transition",
                },
                {
                    "name": "4b - Full Severe",
                    "power_min": rcp_steady_w,
                    "power_max": max_power,
                    "description": "Full respiratory compensation, exhaustion imminent",
                },
            ],
        }
    )

    if len(zones) != 4:
        result["analysis_notes"].append(f"❌ BŁĄD: Wygenerowano {len(zones)} stref zamiast 4!")
    else:
        result["analysis_notes"].append("✓ 4 strefy wygenerowane poprawnie")

    result["metabolic_zones"] = zones
    return result


def _find_breakpoint_segmented(
    x: np.ndarray, y: np.ndarray, min_segment_size: int = 3
) -> Optional[int]:
    """
    Find optimal breakpoint using piecewise linear regression.

    [Issue #6] Uses adaptive slope ratio threshold based on signal variance:
    - Low CV (stable athletes): threshold = 1.05 + 0.02 * CV
    - This allows detection in fit athletes with subtle transitions

    Args:
        x: Independent variable (power)
        y: Dependent variable (VE/VO2 or VE/VCO2)
        min_segment_size: Minimum points in each segment

    Returns:
        Index of optimal breakpoint, or None if not found
    """
    if len(x) < 2 * min_segment_size:
        return None

    mask = ~(np.isnan(x) | np.isnan(y))
    x = x[mask]
    y = y[mask]

    if len(x) < 2 * min_segment_size:
        return None

    # Calculate coefficient of variation for adaptive threshold [Issue #6]
    y_mean = np.mean(y)
    y_std = np.std(y)
    cv = y_std / y_mean if y_mean != 0 else 0

    # Adaptive threshold: base 1.05 + 0.02 * CV
    # - Low CV (0.1): threshold = 1.07 (sensitive)
    # - High CV (0.5): threshold = 1.15 (conservative)
    adaptive_slope_threshold = 1.05 + 0.02 * cv

    best_idx = None
    best_sse = np.inf

    for i in range(min_segment_size, len(x) - min_segment_size):
        x1, y1 = x[:i], y[:i]
        x2, y2 = x[i:], y[i:]

        try:
            slope1, intercept1, _, _, _ = stats.linregress(x1, y1)
            pred1 = slope1 * x1 + intercept1
            sse1 = np.sum((y1 - pred1) ** 2)

            slope2, intercept2, _, _, _ = stats.linregress(x2, y2)
            pred2 = slope2 * x2 + intercept2
            sse2 = np.sum((y2 - pred2) ** 2)

            total_sse = sse1 + sse2

            slope_ratio = slope2 / slope1 if slope1 != 0 else slope2

            if total_sse < best_sse and slope_ratio > adaptive_slope_threshold:
                best_sse = total_sse
                best_idx = i

        except Exception:
            continue

    return best_idx


def _calculate_segment_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Calculate slope of a segment using linear regression."""
    if len(x) < 2:
        return 0.0

    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 2:
        return 0.0

    try:
        slope, _, _, _, _ = stats.linregress(x[mask], y[mask])
        return slope
    except Exception:
        return 0.0
