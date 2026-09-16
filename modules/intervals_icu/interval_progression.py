"""Analiza #5: Cross-Activity Interval Progression — śledzenie progresji interwałów."""

import logging
from collections import defaultdict

import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


def compute(client) -> dict:  # noqa: C901
    """Śledź progresję interwałów między aktywnościami.

    Pobiera interwały z ostatnich aktywności i grupuje je według wzorca.
    """
    try:
        activities_df = client.get_activities(days_back=90)
    except Exception as e:
        logger.warning("Failed to fetch activities: %s", e)
        return {"error": str(e)}

    if activities_df.empty:
        return {"error": "Brak aktywności"}

    # Pobierz interwały dla aktywności rowerowych
    ride_activities = activities_df[activities_df["type"].isin(["Ride", "VirtualRide"])].copy()
    if ride_activities.empty:
        return {"error": "Brak aktywności rowerowych"}

    # Grupuj interwały wg wzorca (power + duration combo)
    interval_patterns = defaultdict(list)

    for _, act in ride_activities.iterrows():
        act_id = act.get("id")
        if not act_id:
            continue
        try:
            details = client.get_activity_details(str(act_id))
        except Exception:
            continue

        intervals = details.get("icu_intervals", [])
        for interval in intervals:
            itype = interval.get("type", "")
            if itype not in ("WORK", "ACTIVE"):
                continue
            avg_w = interval.get("average_watts", 0)
            dur = interval.get("moving_time", 0)
            avg_hr = interval.get("average_heartrate", 0)

            if avg_w > 50 and dur > 10:
                # Stwórz klucz wzorca: round(duration, nearest 30s) + round(watts, nearest 10)
                dur_key = round(dur / 30) * 30
                watt_key = round(avg_w / 10) * 10
                pattern_key = f"{dur_key}s@{watt_key}w"

                interval_patterns[pattern_key].append(
                    {
                        "activity_id": str(act_id),
                        "date": act.get("date"),
                        "avg_watts": avg_w,
                        "avg_hr": avg_hr,
                        "duration": dur,
                        "type": itype,
                    }
                )

    # Wybierz top 3 wzorce (najczęściej występujące)
    top_patterns = sorted(interval_patterns.items(), key=lambda x: len(x[1]), reverse=True)[:3]

    pattern_data = {}
    for key, records in top_patterns:
        df = pd.DataFrame(records)
        if "date" in df.columns:
            df = df.sort_values("date")
        if len(df) >= 3:
            pattern_data[key] = df

    return {
        "patterns": pattern_data,
        "top_patterns": [k for k, _ in top_patterns],
        "has_data": bool(pattern_data),
    }


def render(result: dict):  # noqa: C901
    """Renderuj zakładkę Progresja Interwałów."""
    import streamlit as st

    if result.get("error"):
        st.warning(f"⚠️ {result['error']}")
        return
    if not result.get("has_data"):
        st.info(
            "Brak wystarczających danych interwałowych (potrzeba min. 3 sesje z danym wzorcem)."
        )
        return

    st.subheader("🔍 Progresja Interwałów")
    st.caption("Te same wzorce interwałowe na przestrzeni czasu — czy rośnie moc? Czy spada tętno?")

    patterns = result.get("patterns", {})

    for key, df in patterns.items():
        # Parse key: "300s@280w" -> parts[0]="300s" (sekundy z sufiksem), parts[1]="280w"
        parts = key.split("@")
        if len(parts) == 2:
            try:
                secs = int(parts[0].rstrip("s"))
                dur_txt = f"{secs // 60}min" if secs >= 60 else f"{secs}s"
                label = f"Interwały {dur_txt} @ ~{parts[1]}"
            except ValueError:
                label = key
        else:
            label = key

        st.markdown(f"### {label}")
        st.caption(f"Liczba wystąpień: {len(df)}")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["avg_watts"],
                mode="lines+markers",
                name="Moc (W)",
                line=dict(color="#3498DB", width=2),
                yaxis="y1",
            )
        )
        if "avg_hr" in df.columns and df["avg_hr"].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=df["date"],
                    y=df["avg_hr"],
                    mode="lines+markers",
                    name="HR (bpm)",
                    line=dict(color="#E74C3C", width=2, dash="dot"),
                    yaxis="y2",
                )
            )

        fig.update_layout(
            template="plotly_dark",
            height=300,
            margin=dict(l=20, r=20, t=10, b=20),
            yaxis=dict(title="Moc (W)"),
            yaxis2=dict(title="HR (bpm)", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Podsumowanie
        if len(df) >= 4:
            first_half = df.head(len(df) // 2)["avg_watts"].mean()
            last_half = df.tail(len(df) // 2)["avg_watts"].mean()
            delta_w = last_half - first_half
            st.metric("Zmiana mocy", f"{last_half:.0f} W", delta=f"{delta_w:+.0f} W")

    with st.expander("📋 Wszystkie dane interwałowe"):
        for key, df in patterns.items():
            st.markdown(f"**{key}**")
            st.dataframe(df, use_container_width=True)
