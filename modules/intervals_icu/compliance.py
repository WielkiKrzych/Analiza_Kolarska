"""Analiza #3: Workout Compliance — porównanie zaplanowanych treningów z wykonanymi."""

import logging
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


def compute(client) -> dict:  # noqa: C901
    """Porównaj zaplanowane eventy kalendarza z wykonanymi aktywnościami.

    Returns:
        dict z compliance_df, weekly_compliance, missed_workouts
    """
    try:
        events_df = client.get_calendar_events(days_ahead=0, days_back=30)
        activities_df = client.get_activities(days_back=30)
    except Exception as e:
        logger.warning("Failed to fetch compliance data: %s", e)
        return {"error": str(e)}

    if events_df.empty:
        return {"error": "Brak zaplanowanych treningów w kalendarzu"}
    if activities_df.empty:
        return {"error": "Brak wykonanych aktywności"}

    # Filtruj tylko WORKOUT eventy
    if "category" in events_df.columns:
        planned = events_df[events_df["category"] == "WORKOUT"].copy()
    else:
        planned = events_df.copy()

    if planned.empty:
        return {"error": "Brak zaplanowanych WORKOUTÓW w kalendarzu"}

    # Normalizuj daty
    if "date" in planned.columns:
        planned["date"] = pd.to_datetime(planned["date"])
    if "date" in activities_df.columns:
        activities_df["date"] = pd.to_datetime(activities_df["date"])

    # Matching: planned date ±1 day + same sport type
    matched = []
    missed = []

    for _, plan in planned.iterrows():
        plan_date = plan.get("date")
        plan_type = plan.get("type", "")
        plan_name = plan.get("name", "")
        plan_tss = plan.get("icu_training_load") or 0

        # Szukaj aktywności w oknie ±1 dzień
        if plan_date:
            date_mask = (activities_df["date"] >= plan_date - timedelta(days=1)) & (
                activities_df["date"] <= plan_date + timedelta(days=1)
            )
            candidates = activities_df[date_mask]

            # Dopasuj po typie sportu
            if plan_type and "type" in candidates.columns:
                candidates = candidates[candidates["type"] == plan_type]

            if not candidates.empty:
                actual = candidates.iloc[0]
                matched.append(
                    {
                        "plan_date": plan_date,
                        "plan_name": plan_name,
                        "plan_type": plan_type,
                        "plan_tss": plan_tss,
                        "plan_duration": plan.get("moving_time", 0),
                        "actual_date": actual.get("date"),
                        "actual_tss": actual.get("icu_training_load") or 0,
                        "actual_duration": actual.get("moving_time", 0),
                        "actual_if": actual.get("icu_intensity"),
                        "compliance_tss": min(
                            100, round((actual.get("icu_training_load") or 0) / plan_tss * 100, 1)
                        )
                        if plan_tss > 0
                        else 100,
                    }
                )
            else:
                missed.append(
                    {
                        "plan_date": plan_date,
                        "plan_name": plan_name,
                        "plan_type": plan_type,
                        "plan_tss": plan_tss,
                    }
                )

    compliance_df = pd.DataFrame(matched) if matched else pd.DataFrame()
    missed_df = pd.DataFrame(missed) if missed else pd.DataFrame()

    # Weekly compliance
    if not compliance_df.empty:
        compliance_df["week"] = pd.to_datetime(compliance_df["plan_date"]).dt.isocalendar().week
        weekly = (
            compliance_df.groupby("week")
            .agg(
                completed=("plan_name", "count"),
                avg_compliance=("compliance_tss", "mean"),
            )
            .reset_index()
        )
    else:
        weekly = pd.DataFrame()

    total_planned = len(planned)
    total_completed = len(matched)
    total_missed = len(missed)
    overall_pct = round(total_completed / total_planned * 100, 1) if total_planned > 0 else 0

    return {
        "compliance_df": compliance_df,
        "missed_df": missed_df,
        "weekly": weekly,
        "total_planned": total_planned,
        "total_completed": total_completed,
        "total_missed": total_missed,
        "overall_pct": overall_pct,
        "has_data": True,
    }


def render(result: dict):  # noqa: C901
    """Renderuj zakładkę Compliance Treningowy."""
    import streamlit as st

    if result.get("error"):
        st.warning(f"⚠️ {result['error']}")
        return
    if not result.get("has_data"):
        st.info("Brak danych compliance.")
        return

    st.subheader("📋 Compliance Treningowy")
    st.caption("Porównanie zaplanowanych treningów z wykonanymi (ostatnie 30 dni)")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Zaplanowane", result["total_planned"])
    with col2:
        st.metric("Wykonane", result["total_completed"])
    with col3:
        st.metric(
            "Opuszczone",
            result["total_missed"],
            delta=-result["total_missed"],
            delta_color="inverse",
        )
    with col4:
        pct = result["overall_pct"]
        st.metric("Compliance", f"{pct}%", delta="✅" if pct > 80 else "⚠️" if pct > 60 else "🔴")

    # Weekly chart
    weekly = result.get("weekly")
    if weekly is not None and not weekly.empty:
        st.markdown("### 📊 Compliance tygodniowe")
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=weekly["week"],
                y=weekly["avg_compliance"],
                marker_color=[
                    "#2ECC71" if v > 80 else "#F39C12" if v > 60 else "#E74C3C"
                    for v in weekly["avg_compliance"]
                ],
                text=[f"{v:.0f}%" for v in weekly["avg_compliance"]],
                textposition="outside",
            )
        )
        fig.add_hline(y=80, line_dash="dash", line_color="green", annotation_text="Cel: 80%")
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=20, r=20, t=10, b=20))
        fig.update_yaxes(range=[0, 105])
        st.plotly_chart(fig, use_container_width=True)

    # Missed workouts
    missed = result.get("missed_df")
    if missed is not None and not missed.empty:
        st.markdown("### ⚠️ Opuszczone treningi")
        st.dataframe(
            missed[["plan_date", "plan_name", "plan_type", "plan_tss"]], use_container_width=True
        )

    # Detailed compliance
    compliance = result.get("compliance_df")
    if compliance is not None and not compliance.empty:
        with st.expander("📋 Szczegóły compliance"):
            cols = [
                c
                for c in [
                    "plan_date",
                    "plan_name",
                    "plan_type",
                    "plan_tss",
                    "actual_tss",
                    "compliance_tss",
                ]
                if c in compliance.columns
            ]
            st.dataframe(compliance[cols], use_container_width=True)
