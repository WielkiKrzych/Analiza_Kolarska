"""Analiza #7: Heat Adaptation — wpływ temperatury na wydajność treningową."""

import logging

import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

TEMP_BINS = [
    (-100, 15, "<15°C"),
    (15, 20, "15-20°C"),
    (20, 25, "20-25°C"),
    (25, 30, "25-30°C"),
    (30, 100, ">30°C"),
]


def compute(client) -> dict:  # noqa: C901
    """Analiza adaptacji do ciepła — korelacja temperatury z wydajnością.

    Returns:
        dict z heat_df, temp_bins_stats, heat_threshold
    """
    try:
        activities_df = client.get_activities(days_back=90)
    except Exception as e:
        logger.warning("Failed to fetch activities: %s", e)
        return {"error": str(e)}

    if activities_df.empty:
        return {"error": "Brak aktywności"}

    # Pobierz szczegóły aktywności z temperaturą
    heat_records = []
    for _, act in activities_df.iterrows():
        act_id = act.get("id")
        if not act_id:
            continue

        temp = act.get("icu_temperature") or act.get("temp")
        if temp is None:
            # Spróbuj pobrać szczegóły
            try:
                details = client.get_activity_details(str(act_id))
                temp = details.get("icu_temperature") or details.get("temp")
            except Exception:
                continue

        if temp is None:
            continue

        tss = act.get("icu_training_load") or 0
        intensity = act.get("icu_intensity") or 0
        hr_avg = act.get("icu_avg_heartrate") or act.get("average_heartrate") or 0

        heat_records.append(
            {
                "id": str(act_id),
                "date": act.get("date"),
                "type": act.get("type", ""),
                "temperature": float(temp),
                "tss": float(tss),
                "intensity": float(intensity),
                "hr_avg": float(hr_avg),
            }
        )

    if not heat_records:
        return {
            "error": "Brak danych temperatury w aktywnościach. Sprawdź czy pogoda jest włączona w Intervals.icu."
        }

    df = pd.DataFrame(heat_records)

    # Grupowanie po zakresach temperatur
    temp_stats = []
    for lo, hi, label in TEMP_BINS:
        mask = (df["temperature"] >= lo) & (df["temperature"] < hi)
        subset = df[mask]
        if not subset.empty:
            temp_stats.append(
                {
                    "range": label,
                    "count": len(subset),
                    "avg_intensity": round(subset["intensity"].mean(), 3),
                    "avg_tss": round(subset["tss"].mean(), 1),
                    "avg_hr": round(subset["hr_avg"].mean(), 1),
                }
            )
        else:
            temp_stats.append(
                {"range": label, "count": 0, "avg_intensity": 0, "avg_tss": 0, "avg_hr": 0}
            )

    # Heat threshold: temperatura przy której IF spada >5% vs optymalna
    heat_threshold = None
    baseline_if = None
    for stat in temp_stats:
        if stat["count"] > 0:
            if baseline_if is None:
                baseline_if = stat["avg_intensity"]
            elif baseline_if > 0 and heat_threshold is None:
                drop = (baseline_if - stat["avg_intensity"]) / baseline_if
                if drop > 0.05:
                    heat_threshold = stat["range"]

    return {
        "df": df,
        "temp_stats": temp_stats,
        "heat_threshold": heat_threshold,
        "has_data": True,
    }


def render(result: dict):  # noqa: C901
    """Renderuj zakładkę Heat Adaptation."""
    import streamlit as st

    if result.get("error"):
        st.warning(f"⚠️ {result['error']}")
        return
    if not result.get("has_data"):
        st.info("Brak danych temperatury.")
        return

    st.subheader("🌡️ Adaptacja do Ciepła")
    st.caption("Wpływ temperatury zewnętrznej na intensywność i wydajność treningową")

    # Temp bins table
    temp_stats = result.get("temp_stats", [])
    if temp_stats:
        st.markdown("### 📊 Wydajność wg temperatury")
        cols = st.columns(len(temp_stats))
        for i, stat in enumerate(temp_stats):
            with cols[i]:
                st.metric(
                    stat["range"],
                    f"IF: {stat['avg_intensity']:.2f}",
                    delta=f"n={stat['count']}" if stat["count"] > 0 else "brak danych",
                )

    # Scatter: temperature vs intensity
    df = result.get("df")
    if df is not None and not df.empty:
        st.markdown("### 📈 Temperatura vs Intensywność")
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df["temperature"],
                y=df["intensity"],
                mode="markers",
                marker=dict(
                    size=8,
                    color=df["temperature"],
                    colorscale="RdYlBu_r",
                    showscale=True,
                    colorbar=dict(title="°C"),
                ),
                text=df["date"].astype(str),
                hovertemplate="Data: %{text}<br>Temp: %{x}°C<br>IF: %{y:.2f}<extra></extra>",
            )
        )

        # Trend line
        if len(df) >= 5:
            try:
                import numpy as np

                z = np.polyfit(df["temperature"], df["intensity"], 1)
                p = np.poly1d(z)
                x_range = [df["temperature"].min(), df["temperature"].max()]
                fig.add_trace(
                    go.Scatter(
                        x=x_range,
                        y=[p(x) for x in x_range],
                        mode="lines",
                        name="Trend",
                        line=dict(color="white", dash="dash", width=1),
                    )
                )
            except Exception:
                pass

        fig.update_layout(template="plotly_dark", height=350, margin=dict(l=20, r=20, t=10, b=20))
        fig.update_xaxes(title_text="Temperatura (°C)")
        fig.update_yaxes(title_text="Intensity Factor (IF)")
        st.plotly_chart(fig, use_container_width=True)

        # HR by temp range
        st.markdown("### ❤️ Średnie tętno wg temperatury")
        hr_fig = go.Figure()
        ranges = [s["range"] for s in temp_stats if s["count"] > 0]
        hrs = [s["avg_hr"] for s in temp_stats if s["count"] > 0]
        hr_fig.add_trace(
            go.Bar(
                x=ranges,
                y=hrs,
                marker_color="rgba(231, 76, 60, 0.7)",
                text=[f"{h:.0f}" for h in hrs],
                textposition="outside",
            )
        )
        hr_fig.update_layout(
            template="plotly_dark", height=250, margin=dict(l=20, r=20, t=10, b=20)
        )
        hr_fig.update_yaxes(title_text="HR (bpm)")
        st.plotly_chart(hr_fig, use_container_width=True)

    # Heat threshold warning
    threshold = result.get("heat_threshold")
    if threshold:
        st.warning(
            f"⚠️ **Próg cieplny**: przy {threshold} wydajność spada o >5%. Rozważ obniżenie mocy docelowej w upały."
        )
    else:
        st.info("Nie wykryto znaczącego spadku wydajności w dostępnym zakresie temperatur.")

    with st.expander("📋 Dane szczegółowe"):
        if df is not None:
            st.dataframe(
                df[["date", "type", "temperature", "intensity", "hr_avg"]], use_container_width=True
            )
