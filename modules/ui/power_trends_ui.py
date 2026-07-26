"""Longitudinal power trends — Mean-Maximal Power (MMP) over the season.

Reads best efforts (5s / 1min / 5min / 20min) stored per session in the
SessionStore and plots how they evolve over time. Pure read-only view.
"""
from __future__ import annotations

import logging

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.plots import CHART_CONFIG, CHART_HEIGHT_MAIN, apply_chart_style

logger = logging.getLogger(__name__)

# (db field, label, colour)
_MMP_SERIES = [
    ("mmp_5s", "5 s (sprint)", "#FF6B6B"),
    ("mmp_1m", "1 min (VO₂)", "#FFC83D"),
    ("mmp_5m", "5 min (VO₂max)", "#4ECDC4"),
    ("mmp_20m", "20 min (FTP)", "#8A7DFF"),
]


def render_power_trends_tab() -> None:
    st.subheader("📈 Krzywa mocy w czasie (MMP)")
    st.caption(
        "Najlepsza średnia moc dla 5 s / 1 min / 5 min / 20 min z zapisanych sesji. "
        "Rosnące linie = poprawa formy w danym zakresie."
    )

    days = st.selectbox(
        "Zakres",
        options=[90, 180, 365, 3650],
        format_func=lambda d: {90: "90 dni", 180: "6 miesięcy", 365: "1 rok", 3650: "Całość"}[d],
        index=1,
    )

    try:
        from modules.cache_utils import get_session_store

        store = get_session_store()
    except Exception:
        from modules.db import SessionStore

        store = SessionStore()

    try:
        records = store.get_sessions(days=days)
    except Exception as e:
        logger.warning("Power trends: could not load sessions: %s", e)
        st.info("Brak dostępu do historii sesji.")
        return

    rows = []
    for r in records:
        rows.append(
            {
                "date": r.date,
                "mmp_5s": r.mmp_5s,
                "mmp_1m": r.mmp_1m,
                "mmp_5m": r.mmp_5m,
                "mmp_20m": r.mmp_20m,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty or df[["mmp_5s", "mmp_1m", "mmp_5m", "mmp_20m"]].dropna(how="all").empty:
        st.info(
            "Za mało danych. Wgraj co najmniej 2 sesje z mocą — najlepsze wysiłki "
            "(5 s / 1 / 5 / 20 min) zapisują się automatycznie i pojawią się tutaj."
        )
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    # --- Current + all-time bests ---
    cols = st.columns(4)
    for col, (field, label, _) in zip(cols, _MMP_SERIES):
        series = df[field].dropna()
        if series.empty:
            col.metric(label, "—")
            continue
        best = series.max()
        latest = series.iloc[-1]
        delta = latest - best if best else 0
        col.metric(
            label,
            f"{latest:.0f} W",
            delta=f"rekord {best:.0f} W" if abs(delta) > 1 else "rekord",
            delta_color="off",
        )

    # --- Trend chart ---
    fig = go.Figure()
    for field, label, colour in _MMP_SERIES:
        sub = df[["date", field]].dropna()
        if sub.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=sub["date"],
                y=sub[field],
                mode="lines+markers",
                name=label,
                line=dict(color=colour, width=2),
                marker=dict(size=6),
                hovertemplate=f"{label}: %{{y:.0f}} W<br>%{{x|%Y-%m-%d}}<extra></extra>",
            )
        )
    fig.update_layout(height=CHART_HEIGHT_MAIN, yaxis_title="Moc [W]", xaxis_title="Data")
    apply_chart_style(fig, "Mean-Maximal Power — trend sezonowy")
    st.plotly_chart(fig, width="stretch", config=CHART_CONFIG)

    with st.expander("ℹ️ Jak czytać"):
        st.markdown(
            "- **5 s** — moc neuromięśniowa / sprint.\n"
            "- **1 min** — pojemność beztlenowa.\n"
            "- **5 min** — VO₂max / moc tlenowa maksymalna.\n"
            "- **20 min** — proxy FTP (≈95% z 20-min).\n\n"
            "Rekord = najlepszy wynik w wybranym zakresie; wartość = ostatnia sesja."
        )
