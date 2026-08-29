"""
CPET Step Aggregation — builds steady-state step data from raw time-series.
"""

from typing import Optional

import pandas as pd

from modules.config import Config

# Step segmentation for the no-step_range fallback path.
BLOCK_WINDOW_S = 30
BLOCK_POWER_TOLERANCE_W = 10.0
MIN_BLOCK_DURATION_S = 60
OVERLONG_BLOCK_RATIO = 2.0


def aggregate_step_data(
    data: pd.DataFrame,
    cols: dict,
    step_range,
    min_power_watts: Optional[int],
    has_hr: bool,
    result: dict,
) -> Optional[pd.DataFrame]:
    """
    Aggregate raw CPET data into per-step steady-state values.

    Args:
        data: Preprocessed DataFrame (from preprocess_cpet_data)
        cols: Column mapping dict
        step_range: Optional detected step ranges (with .steps attribute)
        min_power_watts: Manual override — minimum power to start VT search
        has_hr: Data availability flag
        result: Result dict — modified in place for analysis_notes

    Returns:
        Sorted df_steps DataFrame, or None if fewer than 5 steps found.
    """
    step_data = []

    br_col = None
    for col in ["tymebreathrate", "br", "resprate", "breathing_rate", "rf", "rr"]:
        if col in data.columns:
            br_col = col
            break

    if step_range and hasattr(step_range, "steps") and step_range.steps:
        for i, step in enumerate(step_range.steps):
            mask = (data[cols["time"]] >= step.start_time) & (data[cols["time"]] <= step.end_time)
            step_df = data[mask]

            if len(step_df) < 30:
                continue

            step_duration = step.end_time - step.start_time
            ss_start_ratio = max(0.5, 1 - (90 / step_duration)) if step_duration > 90 else 0.5
            cutoff = int(len(step_df) * ss_start_ratio)
            ss_df = step_df.iloc[cutoff:]

            row = {
                "step": i + 1,
                "power": step.avg_power,
                "ve": ss_df["ve_smooth"].mean(),
                "time": step.start_time,
                "duration": step_duration,
            }

            if has_hr and cols["hr"] in ss_df.columns:
                row["hr"] = ss_df[cols["hr"]].mean()
            if br_col and br_col in ss_df.columns:
                row["br"] = ss_df[br_col].mean()

            step_data.append(row)
    else:
        step_data = _aggregate_from_time_blocks(
            data, cols, min_power_watts, has_hr, br_col, result
        )

    if len(step_data) < 5:
        result["error"] = f"Insufficient steps ({len(step_data)}). Need at least 5."
        result["analysis_notes"].append("Not enough steps for reliable analysis")
        return None

    return pd.DataFrame(step_data).sort_values("power").reset_index(drop=True)


def _aggregate_from_time_blocks(
    data: pd.DataFrame,
    cols: dict,
    min_power_watts: Optional[int],
    has_hr: bool,
    br_col: Optional[str],
    result: dict,
) -> list:
    """
    Auto-detect steps when no step_range is provided, by walking the file in
    time order and cutting a new block whenever power leaves the current level.

    Binning by power *value* (the previous approach) merged every sample that
    ever hit a given wattage, so warmup and cool-down landed in the same bin as
    a real step — a 60W "step" spanning 2536s, and VE running backwards against
    power. Blocks are contiguous in time, so that cannot happen.
    """
    blocks = _split_into_power_blocks(data, cols)

    raw_steps = []
    for start_time, end_time, block in blocks:
        duration = end_time - start_time
        if duration < MIN_BLOCK_DURATION_S or len(block) < 30:
            continue

        ss_start_ratio = max(0.5, 1 - (90 / duration)) if duration > 90 else 0.5
        ss_df = block.iloc[int(len(block) * ss_start_ratio):]

        row = {
            "power": round(block[cols["power"]].mean()),
            "ve": ss_df["ve_smooth"].mean(),
            "time": start_time,
            "duration": duration,
        }

        if has_hr and cols["hr"] in ss_df.columns:
            row["hr"] = ss_df[cols["hr"]].mean()
        if br_col and br_col in ss_df.columns:
            row["br"] = ss_df[br_col].mean()

        raw_steps.append(row)

    raw_steps = _drop_cooldown(raw_steps, result)
    raw_steps = _drop_overlong_blocks(raw_steps, result)
    raw_steps = sorted(raw_steps, key=lambda x: x["power"])

    ramp_start_idx = _find_ramp_start(raw_steps, min_power_watts, result)

    if ramp_start_idx > 0:
        result["analysis_notes"].append(f"Skipping first {ramp_start_idx} warmup steps")

    step_data = []
    for i, step in enumerate(raw_steps[ramp_start_idx:]):
        step["step"] = i + 1
        step_data.append(step)

    return step_data


def _split_into_power_blocks(data: pd.DataFrame, cols: dict) -> list:
    """
    Cut the ride into contiguous constant-power blocks.

    Power is averaged over fixed windows first — raw second-by-second power is
    far too noisy to chain directly, and a single spike would split a step.
    """
    data = data.sort_values(cols["time"])
    time = data[cols["time"]]
    window_start = time.iloc[0]

    windows = []
    for w_start in range(int(window_start), int(time.iloc[-1]) + 1, BLOCK_WINDOW_S):
        w = data[(time >= w_start) & (time < w_start + BLOCK_WINDOW_S)]
        if len(w) >= 5:
            windows.append((w_start, w_start + BLOCK_WINDOW_S, w[cols["power"]].mean()))

    if not windows:
        return []

    blocks = []
    current = [windows[0]]
    for w in windows[1:]:
        level = sum(c[2] for c in current) / len(current)
        if abs(w[2] - level) <= BLOCK_POWER_TOLERANCE_W:
            current.append(w)
        else:
            blocks.append(current)
            current = [w]
    blocks.append(current)

    out = []
    for b in blocks:
        start, end = b[0][0], b[-1][1]
        out.append((start, end, data[(time >= start) & (time < end)]))
    return out


def _drop_overlong_blocks(raw_steps: list, result: dict) -> list:
    """
    A block far longer than the protocol's step length is a warmup hold, not a
    step. Left in, it passes _find_ramp_start()'s increment test (80W -> 100W
    looks like a legal step) and drags the whole analysis down one level.
    """
    if len(raw_steps) < 3:
        return raw_steps

    durations = sorted(s["duration"] for s in raw_steps)
    median = durations[len(durations) // 2]
    kept = [s for s in raw_steps if s["duration"] <= median * OVERLONG_BLOCK_RATIO]

    if len(kept) < len(raw_steps):
        result["analysis_notes"].append(
            f"Dropping {len(raw_steps) - len(kept)} over-long block(s) (warmup hold)"
        )
    return kept


def _drop_cooldown(raw_steps: list, result: dict) -> list:
    """
    Everything after the peak-power block is cool-down, not a step.

    Without this the ~90W cool-down comes back as a low-power step and corrupts
    both the VE curve and the warmup detection below it.
    """
    if not raw_steps:
        return raw_steps

    peak = max(range(len(raw_steps)), key=lambda i: raw_steps[i]["power"])
    dropped = len(raw_steps) - peak - 1
    if dropped > 0:
        result["analysis_notes"].append(f"Dropping {dropped} block(s) after peak power (cool-down)")
    return raw_steps[: peak + 1]


def _find_ramp_start(raw_steps: list, min_power_watts: Optional[int], result: dict) -> int:
    """Find the index where the ramp test starts (skip warmup)."""
    if min_power_watts is not None and min_power_watts > 0:
        for i, step in enumerate(raw_steps):
            if step["power"] >= min_power_watts:
                result["ramp_start_step"] = i + 1
                result["analysis_notes"].append(
                    f"Manual override: Starting analysis from {int(min_power_watts)}W (step {i + 1})"
                )
                return i
        return 0

    min_step_duration = Config.RAMP_MIN_STEP_DURATION
    power_increment_range = (Config.RAMP_POWER_INCREMENT_MIN, Config.RAMP_POWER_INCREMENT_MAX)

    for i in range(len(raw_steps) - 2):
        step1 = raw_steps[i]
        step2 = raw_steps[i + 1]
        step3 = raw_steps[i + 2]

        dur_ok = all(s["duration"] >= min_step_duration for s in [step1, step2, step3])

        inc1 = step2["power"] - step1["power"]
        inc2 = step3["power"] - step2["power"]
        inc_ok = (
            power_increment_range[0] <= inc1 <= power_increment_range[1]
            and power_increment_range[0] <= inc2 <= power_increment_range[1]
        )

        if dur_ok and inc_ok:
            result["ramp_start_step"] = i + 1
            result["analysis_notes"].append(
                f"Ramp test detected starting at step {i + 1} ({int(step1['power'])}W)"
            )
            return i

    return 0
