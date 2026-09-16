"""Analiza #1: Wellness → Wydajność — korelacja snu, HRV i samopoczucia z wynikami treningów."""

import logging
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


def compute(client) -> dict:  # noqa: C901
    """Oblicz korelacje między danymi wellness a wydajnością treningową.

    Returns:
        dict z kluczami: df, correlations, sleep_comparison, weekly_trend
    """
    try:
        wellness_df = client.get_wellness(days_back=90)
        activities_df = client.get_activities(days_back=90)
    except Exception as e:
        logger.warning("Failed to fetch data: %s", e)
        return {"error": str(e)}

    if wellness_df.empty or activities_df.empty:
        return {"error": "Brak danych wellness lub aktywności"}

    # Przygotowanie danych
    if "date" not in activities_df.columns:
        return {"error": "Brak kolumny date w aktywnościach"}
    if "date" not in wellness_df.columns:
        return {"error": "Brak kolumny date w wellness"}

    activities_df["date"] = pd.to_datetime(activities_df["date"])
    wellness_df["date"] = pd.to_datetime(wellness_df["date"])

    # Dla każdego treningu znajdź wellness z dnia POPRZEDNIEGO
    merged = []
    for _, act in activities_df.iterrows():
        act_date = act["date"]
        prev_date = act_date - timedelta(days=1)
        prev_wellness = wellness_df[wellness_df["date"].dt.date == prev_date.date()]
        if not prev_wellness.empty:
            row = {
                "activity_date": act_date,
                "activity_name": act.get("name", ""),
                "type": act.get("type", ""),
                "icu_training_load": act.get("icu_training_load"),
                "icu_intensity": act.get("icu_intensity"),
                "moving_time": act.get("moving_time"),
                "distance": act.get("distance"),
            }
            w = prev_wellness.iloc[0]
            row.update(
                {
                    "sleep_secs": w.get("sleepSecs"),
                    "sleep_quality": w.get("sleepQuality"),
                    "resting_hr": w.get("restingHR"),
                    "hrv": w.get("hrv"),
                    "weight": w.get("weight"),
                    "fatigue": w.get("fatigue"),
                    "soreness": w.get("soreness"),
                    "stress": w.get("stress"),
                    "mood": w.get("mood"),
                    "motivation": w.get("motivation"),
                }
            )
            merged.append(row)

    if not merged:
        return {"error": "Brak dopasowanych danych wellness↔trening"}

    df = pd.DataFrame(merged)

    # Konwersje
    for col in [
        "sleep_secs",
        "resting_hr",
        "hrv",
        "weight",
        "fatigue",
        "soreness",
        "stress",
        "mood",
        "motivation",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "sleep_secs" in df.columns:
        df["sleep_hours"] = df["sleep_secs"] / 3600

    # Korelacje
    has_if = "icu_intensity" in df.columns and df["icu_intensity"].notna().any()
    has_tss = "icu_training_load" in df.columns and df["icu_training_load"].notna().any()

    correlations = {}
    if has_if:
        for metric in ["sleep_hours", "sleep_quality", "resting_hr", "hrv", "fatigue", "soreness"]:
            if metric in df.columns and df[metric].notna().sum() >= 5:
                corr = df[metric].corr(df["icu_intensity"])
                correlations[f"{metric}_vs_IF"] = round(corr, 3)

    if has_tss:
        for metric in ["sleep_hours", "fatigue", "motivation"]:
            if metric in df.columns and df[metric].notna().sum() >= 5:
                corr = df[metric].corr(df["icu_training_load"])
                correlations[f"{metric}_vs_TSS"] = round(corr, 3)

    # Porównanie: sen <6h vs sen >7h
    sleep_comparison = {}
    if "sleep_hours" in df.columns and has_if:
        bad_sleep = df[df["sleep_hours"] < 6]
        good_sleep = df[df["sleep_hours"] > 7]
        if not bad_sleep.empty and not good_sleep.empty:
            sleep_comparison = {
                "bad_sleep_avg_if": round(bad_sleep["icu_intensity"].mean(), 3),
                "bad_sleep_count": len(bad_sleep),
                "good_sleep_avg_if": round(good_sleep["icu_intensity"].mean(), 3),
                "good_sleep_count": len(good_sleep),
                "if_drop_pct": round(
                    (1 - bad_sleep["icu_intensity"].mean() / good_sleep["icu_intensity"].mean())
                    * 100,
                    1,
                )
                if good_sleep["icu_intensity"].mean() > 0
                else 0,
            }

    # Weekly trend
    df["week"] = pd.to_datetime(df["activity_date"]).dt.isocalendar().week
    weekly = (
        df.groupby("week")
        .agg(
            avg_if=("icu_intensity", "mean"),
            avg_tss=("icu_training_load", "mean"),
            avg_sleep=("sleep_hours", "mean"),
            count=("activity_date", "count"),
        )
        .reset_index()
    )

    return {
        "df": df,
        "correlations": correlations,
        "sleep_comparison": sleep_comparison,
        "weekly_trend": weekly,
        "has_data": True,
    }


def render(result: dict):  # noqa: C901
    """Renderuj zakładkę Wellness → Wydajność w Streamlit."""
    import streamlit as st

    if result.get("error"):
        st.warning(f"⚠️ {result['error']}")
        return

    if not result.get("has_data"):
        st.info("Brak wystarczających danych do analizy.")
        return

    st.subheader("🏥 Wellness → Wydajność Treningowa")
    st.caption("Korelacja danych wellness z dnia POPRZEDNIEGO z wynikami treningu")

    corr = result.get("correlations", {})
    if corr:
        st.markdown("### 📊 Korelacje (Pearson r)")
        corr_items = []
        for k, v in corr.items():
            emoji = "🟢" if abs(v) > 0.3 else "🟡" if abs(v) > 0.1 else "⚪"
            corr_items.append(f"{emoji} **{k}**: {v:+.3f}")
        st.markdown("\n\n".join(corr_items))

    sleep_cmp = result.get("sleep_comparison", {})
    if sleep_cmp:
        st.markdown("### 😴 Wpływ snu na intensywność")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "IF przy śnie <6h",
                f"{sleep_cmp['bad_sleep_avg_if']:.2f}",
                f"n={sleep_cmp['bad_sleep_count']}",
            )
        with col2:
            st.metric(
                "IF przy śnie >7h",
                f"{sleep_cmp['good_sleep_avg_if']:.2f}",
                f"n={sleep_cmp['good_sleep_count']}",
            )
        with col3:
            drop = sleep_cmp.get("if_drop_pct", 0)
            st.metric(
                "Spadek wydajności",
                f"{drop}%",
                delta=f"{'-' if drop > 0 else '+'}{abs(drop)}%",
                delta_color="inverse",
            )

    # Weekly trend chart
    weekly = result.get("weekly_trend")
    if weekly is not None and not weekly.empty:
        st.markdown("### 📈 Trend tygodniowy: Sen vs Intensywność")
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=weekly["week"],
                y=weekly["avg_sleep"],
                name="Sen (h)",
                marker_color="rgba(100, 149, 237, 0.6)",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=weekly["week"],
                y=weekly["avg_if"],
                name="Średnia IF",
                mode="lines+markers",
                line=dict(color="#FF6B6B", width=2),
            ),
            secondary_y=True,
        )
        fig.update_layout(
            template="plotly_dark",
            height=350,
            margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(orientation="h", y=1.1),
        )
        fig.update_xaxes(title_text="Tydzień")
        fig.update_yaxes(title_text="Sen (h)", secondary_y=False)
        fig.update_yaxes(title_text="Intensity Factor", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

    # Raw data
    with st.expander("📋 Dane szczegółowe"):
        df = result.get("df")
        if df is not None:
            cols = [
                c
                for c in [
                    "activity_date",
                    "type",
                    "sleep_hours",
                    "hrv",
                    "resting_hr",
                    "icu_intensity",
                    "icu_training_load",
                ]
                if c in df.columns
            ]
            st.dataframe(df[cols].tail(30), use_container_width=True)
