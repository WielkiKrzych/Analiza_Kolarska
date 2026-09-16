"""
Vent Thresholds — CPET chart panels (VE-only), interactive Plotly.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_cpet_charts(cpet_result: dict) -> None:
    """
    Render the "📊 Wykresy CPET" expander with all chart panels.

    Draws the VE vs Power chart, the secondary metabolic zones table and the raw
    step data expander.
    """
    st.markdown("---")
    with st.expander("📊 Wykresy CPET", expanded=True):
        df_s = cpet_result.get("df_steps")
        v1_w = cpet_result.get("vt1_watts")
        v2_w = cpet_result.get("vt2_watts")

        if df_s is None or len(df_s) == 0:
            st.warning("Brak danych schodków do wyświetlenia wykresów")
            return

        # VE-only: no gas-exchange panels — the hardware is a TymeWear VitalPro.
        st.markdown("### Wykres VE vs Power")

        ve_col = next((c for c in ("ve", "ve_smooth") if c in df_s.columns), None)
        fig = go.Figure()
        if ve_col:
            fig.add_trace(
                go.Scatter(
                    x=df_s["power"],
                    y=df_s[ve_col],
                    mode="lines+markers",
                    name="VE (L/min)",
                    line=dict(color="#5da5da", width=2),
                    hovertemplate="<b>Moc:</b> %{x:.0f} W<br><b>VE:</b> %{y:.1f} L/min<extra></extra>",
                )
            )
        for watts, label, color in ((v1_w, "VT1", "#ffa15a"), (v2_w, "VT2", "#ef553b")):
            if watts:
                fig.add_vline(
                    x=watts,
                    line=dict(color=color, width=2, dash="dash"),
                    annotation_text=f"{label}: {watts}W",
                    annotation_position="top left",
                )
        fig.update_layout(
            title="VE vs Power z Progami VT1/VT2",
            xaxis_title="Moc [W]",
            yaxis=dict(title=dict(text="Wentylacja [L/min]", font=dict(color="#5da5da"))),
            legend=dict(x=0.01, y=0.99),
            height=450,
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode="closest",
        )
        st.plotly_chart(fig, width="stretch")
        # Secondary zones table
        st.markdown("### 🎯 Strefy Metaboliczne")
        if v1_w and v2_w:
            zones_data = [
                {
                    "Strefa": "Z1 (Recovery)",
                    "Zakres": f"< {v1_w} W",
                    "Opis": "Regeneracja, rozgrzewka",
                    "Metabolizm": "100% Tlenowy",
                },
                {
                    "Strefa": "Z2 (Endurance)",
                    "Zakres": f"{v1_w} - {int((v1_w + v2_w) / 2)} W",
                    "Opis": "Baza tlenowa",
                    "Metabolizm": "Dominująco tlenowy",
                },
                {
                    "Strefa": "Z3 (Tempo)",
                    "Zakres": f"{int((v1_w + v2_w) / 2)} - {v2_w} W",
                    "Opis": "Sweet Spot",
                    "Metabolizm": "Mieszany",
                },
                {
                    "Strefa": "Z4 (Threshold)",
                    "Zakres": f"{v2_w} - {int(v2_w * 1.05)} W",
                    "Opis": "FTP, MLSS",
                    "Metabolizm": "Glikolityczny",
                },
                {
                    "Strefa": "Z5 (VO2max)",
                    "Zakres": f"> {int(v2_w * 1.05)} W",
                    "Opis": "Interwały",
                    "Metabolizm": "Anaerobowy",
                },
            ]
            st.dataframe(pd.DataFrame(zones_data), hide_index=True, width="stretch")
        else:
            st.warning("Brak danych do wygenerowania stref metabolicznych")

        # Raw step data
        with st.expander("📝 Dane schodków (raw)", expanded=False):
            display_cols = ["step", "power", "ve"]
            for col in ["hr"]:
                if col in df_s.columns:
                    display_cols.append(col)

            available_cols = [c for c in display_cols if c in df_s.columns]
            st.dataframe(df_s[available_cols].round(2), width="stretch")
