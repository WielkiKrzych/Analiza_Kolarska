"""Analiza #2: Progresja krzywych mocy i tempa — miesiąc do miesiąca."""

import logging
import re
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _duration_to_seconds(dur) -> Optional[int]:
    """Convert an intervals.icu duration label to seconds.

    Handles plain numbers (300), unit suffixes ("300s", "5m", "1h") and
    mm:ss / hh:mm:ss strings ("5:00"). Returns None if it can't be parsed.
    """
    if dur is None:
        return None
    if isinstance(dur, (int, float)):
        return int(dur)
    s = str(dur).strip().lower()
    if not s:
        return None
    if ":" in s:  # mm:ss or hh:mm:ss
        try:
            parts = [int(p) for p in s.split(":")]
        except ValueError:
            return None
        total = 0
        for p in parts:
            total = total * 60 + p
        return total
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd]?)", s)
    if not m:
        return None
    return int(float(m.group(1)) * _UNIT_SECONDS.get(m.group(2) or "s", 1))


KEY_DURATIONS = [5, 30, 60, 300, 600, 1200, 2400, 3600]  # sekundy
DURATION_LABELS = {
    5: "5s",
    30: "30s",
    60: "1min",
    300: "5min",
    600: "10min",
    1200: "20min",
    3600: "1h",
}


def compute(client) -> dict:
    """Śledź progresję krzywych mocy miesiąc-do-miesiąca.

    Returns:
        dict z danymi do wizualizacji
    """
    try:
        power_data = client.get_power_curves(sport="Ride", days_back=180)
        pace_data = client.get_pace_curves(sport="Run", days_back=180)
    except Exception as e:
        logger.warning("Failed to fetch curves: %s", e)
        return {"error": str(e)}

    if not power_data and not pace_data:
        return {"error": "Brak danych krzywych mocy i tempa"}

    # Parsowanie power curves
    power_trends = _parse_curve_progression(power_data, "power") if power_data else None
    pace_trends = _parse_curve_progression(pace_data, "pace") if pace_data else None

    return {
        "power_trends": power_trends,
        "pace_trends": pace_trends,
        "has_data": bool(power_trends or pace_trends),
        "duration_labels": DURATION_LABELS,
    }


def _parse_curve_progression(curve_data: dict, metric: str) -> pd.DataFrame:  # noqa: C901
    """Parsuj dane krzywej w progression per duration."""
    if not isinstance(curve_data, (list, dict)):
        return None

    # Intervals.icu zwraca krzywe jako listę punktów lub dict duration→value
    records = []
    if isinstance(curve_data, list):
        for entry in curve_data:
            if not isinstance(entry, dict):
                continue
            secs_list = entry.get("secs")
            if isinstance(secs_list, list):
                # Realny kształt: obiekt krzywej z tablicami secs[] + wartości[].
                vals = (
                    entry.get("values")
                    or entry.get("watts")
                    or entry.get("y")
                    or entry.get("pace")
                    or []
                )
                grp = entry.get("start_date_local") or entry.get("name") or entry.get("id")
                for s, v in zip(secs_list, vals, strict=False):  # noqa: B905
                    sec = _duration_to_seconds(s)
                    if sec is not None and v is not None:
                        records.append({"duration": sec, "value": float(v), "date": grp})
            else:
                # Stary wariant: pojedynczy punkt na wpis.
                dur = entry.get("duration") or entry.get("secs")
                val = entry.get("value") or entry.get("watts") or entry.get("pace")
                date_str = entry.get("date") or entry.get("start_date")
                secs = _duration_to_seconds(dur)
                if secs is not None and val is not None:
                    records.append({"duration": secs, "value": float(val), "date": date_str})
    elif isinstance(curve_data, dict):
        for date_str, points in curve_data.items():
            if isinstance(points, dict):
                for dur, val in points.items():
                    secs = _duration_to_seconds(dur)
                    if secs is not None and val is not None:
                        records.append({"duration": secs, "value": float(val), "date": date_str})

    if not records:
        return None

    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["month"] = df["date"].dt.to_period("M")

    return df


def render(result: dict):  # noqa: C901
    """Renderuj zakładkę Progresja Mocy/Tempa."""
    import streamlit as st

    if result.get("error"):
        st.warning(f"⚠️ {result['error']}")
        return
    if not result.get("has_data"):
        st.info("Brak danych krzywych mocy/tempa.")
        return

    st.subheader("📈 Progresja Krzywych Mocy i Tempa")
    st.caption("Najlepsze wartości na kluczowych dystansach — miesiąc do miesiąca")

    duration_labels = result.get("duration_labels", DURATION_LABELS)

    # Power trends
    power_df = result.get("power_trends")
    if power_df is not None and not power_df.empty:
        st.markdown("### 🚴 Moc (Watts)")
        _render_curve_bars(power_df, duration_labels)

    # Pace trends
    pace_df = result.get("pace_trends")
    if pace_df is not None and not pace_df.empty:
        st.markdown("### 🏃 Tempo (min/km)")
        _render_curve_bars(pace_df, duration_labels)

    # Fitness progression score
    if power_df is not None and not power_df.empty and "month" in power_df.columns:
        months = sorted(power_df["month"].unique())
        if len(months) >= 2:
            first = power_df[power_df["month"] == months[0]]
            last = power_df[power_df["month"] == months[-1]]
            improvements = []
            for dur in KEY_DURATIONS:
                if dur in first["duration"].values and dur in last["duration"].values:
                    old_val = first[first["duration"] == dur]["value"].max()
                    new_val = last[last["duration"] == dur]["value"].max()
                    if old_val > 0:
                        improvements.append((new_val - old_val) / old_val * 100)
            if improvements:
                score = min(100, max(0, sum(improvements) / len(improvements) * 5 + 50))
                st.metric(
                    "📊 Fitness Progression Score",
                    f"{score:.0f}/100",
                    delta=f"{sum(improvements) / len(improvements):+.1f}%",
                )


def _render_curve_bars(df, duration_labels):
    """Renderuj wykres słupkowy progresji."""
    import streamlit as st

    if "month" not in df.columns or "duration" not in df.columns:
        return

    for dur in KEY_DURATIONS:
        dur_df = df[df["duration"] == dur].copy()
        if dur_df.empty:
            continue
        if "date" in dur_df.columns:
            dur_df = dur_df.sort_values("date")

        fig = go.Figure()
        months = [str(m) for m in dur_df["month"].unique()] if "month" in dur_df.columns else []
        values = []
        for m in months:
            month_data = dur_df[dur_df["month"].astype(str) == m]
            if not month_data.empty:
                values.append(month_data["value"].max())

        fig.add_trace(
            go.Bar(
                x=months,
                y=values,
                marker_color="rgba(52, 152, 219, 0.7)",
                text=[f"{v:.1f}" for v in values],
                textposition="outside",
                name=duration_labels.get(dur, f"{dur}s"),
            )
        )
        fig.update_layout(
            template="plotly_dark",
            height=200,
            margin=dict(l=20, r=20, t=30, b=20),
            title=f"{duration_labels.get(dur, f'{dur}s')} — najlepsza wartość",
        )
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Dane szczegółowe"):
        st.dataframe(df, use_container_width=True)
