"""Analiza #6: Race Readiness Dashboard — gotowość startowa, TSB, taper effectiveness."""

import logging
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# Najbliższy start
RACE_DATE = datetime(2026, 7, 12)
RACE_NAME = "1/2 IM Bydgoszcz"


def compute(client) -> dict:
    """Analiza gotowości startowej przed zawodami.

    Returns:
        dict z fitness_data, taper_metrics, days_to_race
    """
    try:
        fitness = client.get_fitness()
        activities_df = client.get_activities(days_back=90)
    except Exception as e:
        logger.warning("Failed to fetch fitness data: %s", e)
        return {"error": str(e)}

    # Days to race
    today = datetime.now()
    days_to_race = (RACE_DATE - today).days if RACE_DATE > today else 0

    # Fitness metrics
    ctl = fitness.get("ctl", 0) if fitness else 0
    atl = fitness.get("atl", 0) if fitness else 0
    tsb = fitness.get("tsb", 0) if fitness else 0

    # Fitness history from activities
    fitness_history = []
    if not activities_df.empty:
        for _, act in activities_df.iterrows():
            act_date = act.get("date")
            if act_date and act.get("icu_fitness") and act.get("icu_fatigue"):
                try:
                    f = float(act["icu_fitness"])
                    g = float(act["icu_fatigue"])
                    fitness_history.append(
                        {
                            "date": pd.to_datetime(act_date),
                            "ctl": f,
                            "atl": g,
                            "tsb": f - g,
                        }
                    )
                except (ValueError, TypeError):
                    continue

    fitness_df = pd.DataFrame(fitness_history) if fitness_history else pd.DataFrame()

    # Taper analysis (last 21 days trend)
    taper_metrics = {}
    if not fitness_df.empty and len(fitness_df) >= 14:
        recent = fitness_df.tail(21)
        if len(recent) >= 7:
            ctl_trend = recent["ctl"].iloc[-1] - recent["ctl"].iloc[0]
            tsb_trend = recent["tsb"].iloc[-1] - recent["tsb"].iloc[0]
            taper_metrics = {
                "ctl_trend": round(ctl_trend, 1),
                "tsb_trend": round(tsb_trend, 1),
                "taper_quality": _taper_score(ctl_trend, tsb_trend, tsb),
            }

    return {
        "ctl": round(ctl, 1),
        "atl": round(atl, 1),
        "tsb": round(tsb, 1),
        "days_to_race": days_to_race,
        "race_name": RACE_NAME,
        "fitness_df": fitness_df,
        "taper_metrics": taper_metrics,
        "has_data": True,
    }


def _taper_score(ctl_trend: float, tsb_trend: float, current_tsb: float) -> dict:
    """Oblicz jakość taperu 0-100."""
    score = 50

    # CTL powinno spadać lub być stabilne w taperze
    if ctl_trend < -2:
        score += 20
    elif ctl_trend < 0:
        score += 10
    elif ctl_trend > 5:
        score -= 20

    # TSB powinno rosnąć
    if tsb_trend > 3:
        score += 20
    elif tsb_trend > 0:
        score += 10
    elif tsb_trend < -3:
        score -= 20

    # Aktualne TSB
    if 5 <= current_tsb <= 15:
        score += 10
    elif current_tsb > 15:
        score -= 5  # za duzo odpoczynku
    elif current_tsb < -10:
        score -= 15  # przetrenowanie

    score = max(0, min(100, score))
    quality = "✅ Idealny" if score >= 80 else "⚠️ OK" if score >= 50 else "🔴 Słaby"
    return {"score": score, "quality": quality}


def render(result: dict):  # noqa: C901
    """Renderuj zakładkę Race Readiness."""
    import streamlit as st

    if result.get("error"):
        st.warning(f"⚠️ {result['error']}")
        return
    if not result.get("has_data"):
        st.info("Brak danych fitness.")
        return

    st.subheader("🏁 Race Readiness Dashboard")

    # Countdown
    days = result.get("days_to_race", 0)
    race_name = result.get("race_name", "")
    st.markdown(f"### 🎯 {race_name}")
    st.metric("Dni do startu", f"{days} dni" if days > 0 else "START!")

    # Fitness gauges
    col1, col2, col3 = st.columns(3)
    with col1:
        ctl = result.get("ctl", 0)
        st.metric("CTL (Fitness)", f"{ctl}", delta=None)
    with col2:
        atl = result.get("atl", 0)
        st.metric("ATL (Zmęczenie)", f"{atl}")
    with col3:
        tsb = result.get("tsb", 0)
        st.metric(
            "TSB (Forma)", f"{tsb}", delta=f"{'🟢' if tsb > 0 else '🔴' if tsb < -10 else '🟡'}"
        )

    # TSB gauge
    st.markdown("### 🎚️ Wskaźnik Formy (TSB)")
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=tsb,
            domain={"x": [0, 1], "y": [0, 1]},
            gauge={
                "axis": {"range": [-30, 25]},
                "bar": {"color": "#2ECC71" if tsb > 0 else "#E74C3C"},
                "steps": [
                    {"range": [-30, -10], "color": "rgba(231, 76, 60, 0.3)"},
                    {"range": [-10, 0], "color": "rgba(243, 156, 18, 0.3)"},
                    {"range": [0, 15], "color": "rgba(46, 204, 113, 0.3)"},
                    {"range": [15, 25], "color": "rgba(41, 128, 185, 0.3)"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 2},
                    "thickness": 0.8,
                    "value": tsb,
                },
            },
        )
    )
    fig.update_layout(template="plotly_dark", height=250, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # Taper quality
    taper = result.get("taper_metrics", {})
    if taper:
        quality = taper.get("taper_quality", {})
        st.markdown("### 📉 Jakość Taperu")
        st.metric("Taper Score", f"{quality.get('score', 0)}/100")
        st.markdown(f"**{quality.get('quality', 'Brak danych')}**")
        st.caption(
            f"CTL trend: {taper.get('ctl_trend', 0):+.1f} | TSB trend: {taper.get('tsb_trend', 0):+.1f}"
        )

    # CTL/ATL/TSB timeline
    fitness_df = result.get("fitness_df")
    if fitness_df is not None and not fitness_df.empty:
        st.markdown("### 📈 Historia Formy (42 dni)")
        recent = fitness_df.tail(42)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=recent["date"], y=recent["ctl"], name="CTL", line=dict(color="#3498DB", width=2)
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=recent["date"], y=recent["atl"], name="ATL", line=dict(color="#E67E22", width=2)
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(
                x=recent["date"],
                y=recent["tsb"],
                name="TSB",
                marker_color=["#2ECC71" if v > 0 else "#E74C3C" for v in recent["tsb"]],
            ),
            secondary_y=True,
        )
        fig.update_layout(
            template="plotly_dark",
            height=350,
            margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(orientation="h", y=1.1),
        )
        fig.update_yaxes(title_text="CTL/ATL", secondary_y=False)
        fig.update_yaxes(title_text="TSB", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
