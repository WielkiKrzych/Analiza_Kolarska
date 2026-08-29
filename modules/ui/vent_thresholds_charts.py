"""
Vent Thresholds — CPET chart panels (VE-only) using Matplotlib.
"""

import pandas as pd
import streamlit as st


def render_cpet_charts(cpet_result: dict) -> None:
    """
    Render the "📊 Wykresy CPET" expander with all chart panels.

    Draws the VE vs Power chart, the secondary metabolic zones table and the raw
    step data expander.
    """
    st.markdown("---")
    with st.expander("📊 Wykresy CPET", expanded=True):
        import matplotlib.pyplot as plt

        df_s = cpet_result.get("df_steps")
        v1_w = cpet_result.get("vt1_watts")
        v2_w = cpet_result.get("vt2_watts")

        if df_s is None or len(df_s) == 0:
            st.warning("Brak danych schodków do wyświetlenia wykresów")
            return

        # VE-only: no gas-exchange panels — the hardware is a TymeWear VitalPro.
        st.markdown("### Wykres VE vs Power")

        fig, ax1 = plt.subplots(figsize=(10, 5))
        plt.style.use("dark_background")
        fig.patch.set_facecolor("#0E1117")
        ax1.set_facecolor("#0E1117")

        if "ve" in df_s.columns:
            ax1.plot(df_s["power"], df_s["ve"], "b-o", linewidth=2, label="VE (L/min)")
        elif "ve_smooth" in df_s.columns:
            ax1.plot(df_s["power"], df_s["ve_smooth"], "b-o", linewidth=2, label="VE (L/min)")

        ax1.set_xlabel("Moc [W]", color="white")
        ax1.set_ylabel("Wentylacja [L/min]", color="#5da5da")

        if v1_w:
            ax1.axvline(
                v1_w, color="#ffa15a", linestyle="--", linewidth=2, label=f"VT1: {v1_w}W"
            )
        if v2_w:
            ax1.axvline(
                v2_w, color="#ef553b", linestyle="--", linewidth=2, label=f"VT2: {v2_w}W"
            )

        ax1.set_title("VE vs Power z Progami VT1/VT2", color="white", pad=10)
        ax1.grid(True, alpha=0.2)
        ax1.legend(loc="upper left")

        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
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
