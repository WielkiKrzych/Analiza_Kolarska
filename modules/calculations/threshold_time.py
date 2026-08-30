"""Canonical helper: locate time at which ramp power reaches a target.

Single source of truth for VT/LT/SmO₂ threshold markers across ALL tabs.
Rule (DOMAIN_MODEL ramp semantics): search ONLY the ascending phase up to
peak power — post-exhaustion decline points must not shadow the true match.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def find_time_for_power(
    df: pd.DataFrame,
    power: float,
    *,
    ascending_only: bool = True,
) -> Optional[float]:
    """Return the ``time`` value where smoothed power is closest to ``power``.

    Column preference: ``watts_smooth_5s`` -> ``watts``.
    ``ascending_only=True`` restricts the window to indices <= argmax(power):
    every metabolic threshold occurs BEFORE exhaustion in a ramp test.
    Fallback: without a ``time`` column, returns the integer index (charts
    plotted against index use it directly as x-axis).
    """
    if df is None or df.empty or power is None or power <= 0:
        return None
    col = (
        "watts_smooth_5s"
        if "watts_smooth_5s" in df.columns
        else ("watts" if "watts" in df.columns else None)
    )
    if col is None:
        return None
    search_df = df
    if ascending_only:
        peak_idx = df[col].idxmax()
        search_df = df.loc[:peak_idx]
        if search_df.empty:
            return None
    idx = (search_df[col] - power).abs().idxmin()
    return search_df.loc[idx, "time"] if "time" in df.columns else idx
