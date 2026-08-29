"""
DFA alpha1 longitudinal tab — non-invasive lactate curve tracking.
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from modules.plots import CHART_HEIGHT_MAIN, CHART_HEIGHT_SUB
from modules.ui.shared import chart, metric, require_data


def render_dfa_longitudinal_tab(df_plot):
    st.header("🔬 DFA alpha1 — Żywa Krzywa Mleczanowa")

    if not require_data(df_plot):
        return

    has_dfa = "alpha1" in df_plot.columns or "dfa_alpha1" in df_plot.columns
    has_power = "watts" in df_plot.columns

    if not has_dfa:
        st.info(
            "ℹ️ Brak danych DFA alpha1 w tym pliku. Wgraj dane z czujnika HRV (np. Polar H10, Garmin HRM-Pro)."
        )
        return

    alpha1_col = "alpha1" if "alpha1" in df_plot.columns else "dfa_alpha1"
    hr_col = (
        "heart_rate"
        if "heart_rate" in df_plot.columns
        else ("hr" if "hr" in df_plot.columns else None)
    )

    alpha1 = df_plot[alpha1_col].to_numpy(dtype=float)
    time_arr = (
        df_plot["time"].to_numpy(dtype=float)
        if "time" in df_plot.columns
        else np.arange(len(alpha1), dtype=float)
    )
    power = df_plot["watts"].to_numpy(dtype=float) if has_power else np.full(len(alpha1), np.nan)
    hr = df_plot[hr_col].to_numpy(dtype=float) if hr_col else np.full(len(alpha1), np.nan)

    time_min = time_arr / 60.0

    # DFA alpha1 chart with threshold line
    fig_dfa = go.Figure()
    fig_dfa.add_trace(
        go.Scatter(
            x=time_min,
            y=alpha1,
            name="DFA α1",
            line=dict(color="#636efa", width=1.5),
            hovertemplate="Czas: %{x:.1f} min<br>α1: %{y:.3f}<extra></extra>",
        )
    )
    fig_dfa.add_hline(
        y=0.75,
        line_dash="dash",
        line_color="#ef553b",
        annotation_text="Próg HT (α1=0.75)",
        annotation_position="top right",
    )
    fig_dfa.add_hline(
        y=0.50,
        line_dash="dot",
        line_color="#ffa15a",
        annotation_text="Próg HRVT2 (α1=0.50)",
        annotation_position="bottom right",
    )
    fig_dfa.add_hrect(
        y0=0.45, y1=0.75, fillcolor="red", opacity=0.05, annotation_text="Strefa ciężka/beztlenowa"
    )
    fig_dfa.update_layout(
        template="plotly_dark",
        title="DFA Alpha1 w czasie",
        xaxis_title="Czas [min]",
        yaxis_title="DFA Alpha1",
        hovermode="x unified",
        height=CHART_HEIGHT_MAIN,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    chart(fig_dfa, key="dfa_long_chart")

    # Extract both thresholds (HRVT1 @0.75 aerobic, HRVT2 @0.50 anaerobic)
    from modules.calculations.dfa_longitudinal import (
        cross_validate_with_vt,
        extract_dfa_thresholds_both,
    )

    both = extract_dfa_thresholds_both(time_arr, alpha1, power, hr)
    hrvt1, hrvt2 = both["hrvt1"], both["hrvt2"]
    # Keep HRVT1 as the primary threshold for downstream VT cross-validation.
    threshold_result = (hrvt1["power"], hrvt1["hr"]) if hrvt1 else None

    if hrvt1 or hrvt2:
        quality = _assess_quality(alpha1)
        quality_label = {
            "A": "🟢 Doskonała",
            "B": "🟡 Dobra",
            "C": "🟠 Umiarkowana",
            "D": "🔴 Słaba",
        }
        st.markdown("#### Progi DFA α1")
        c1, c2, c3, c4, c5 = st.columns(5)
        metric(
            "HRVT1 moc (tlenowy)", f"{hrvt1['power']:.0f}" if hrvt1 else "—", suffix=" W", column=c1
        )
        metric(
            "HRVT1 HR",
            f"{hrvt1['hr']:.0f}" if hrvt1 and hrvt1["hr"] > 0 else "—",
            suffix=" bpm",
            column=c2,
        )
        metric(
            "HRVT2 moc (beztlenowy)",
            f"{hrvt2['power']:.0f}" if hrvt2 else "—",
            suffix=" W",
            column=c3,
        )
        metric(
            "HRVT2 HR",
            f"{hrvt2['hr']:.0f}" if hrvt2 and hrvt2["hr"] > 0 else "—",
            suffix=" bpm",
            column=c4,
        )
        metric("Jakość sygnału", quality_label.get(quality, "❓"), column=c5)
        if hrvt1 and hrvt2 and hrvt2["power"] > hrvt1["power"]:
            st.caption(
                f"Strefy: tlenowa < {hrvt1['power']:.0f} W · ciężka {hrvt1['power']:.0f}–{hrvt2['power']:.0f} W "
                f"· ekstremalna > {hrvt2['power']:.0f} W"
            )
    else:
        st.info(
            "Nie wykryto przejścia DFA α1 przez próg 0.75 ani 0.50. "
            "Może to oznaczać brak progresji intensywności."
        )

    # Power vs alpha1 scatter
    if has_power:
        fig_scatter = go.Figure()
        fig_scatter.add_trace(
            go.Scatter(
                x=power,
                y=alpha1,
                mode="markers",
                marker=dict(
                    size=3,
                    color=time_min,
                    colorscale="Viridis",
                    showscale=True,
                    colorbar=dict(title="Czas [min]"),
                ),
                hovertemplate="Moc: %{x:.0f} W<br>α1: %{y:.3f}<extra></extra>",
            )
        )
        fig_scatter.add_hline(y=0.75, line_dash="dash", line_color="#ef553b")
        fig_scatter.update_layout(
            template="plotly_dark",
            title="DFA α1 vs Moc",
            xaxis_title="Moc [W]",
            yaxis_title="DFA Alpha1",
            height=CHART_HEIGHT_SUB,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False,
        )
        chart(fig_scatter, key="dfa_power_scatter")

    # Cross-validation with VT (if stored in session state)
    vt1 = st.session_state.get("vt1_watts", 0)
    vt2 = st.session_state.get("vt2_watts", 0)
    if threshold_result and vt1 > 0 and vt2 > 0:
        cv = cross_validate_with_vt(threshold_result[0], vt1, vt2)
        st.subheader("🔍 Krzyżowa walidacja z VT")
        m4, m5, m6 = st.columns(3)
        metric("DFA Próg", f"{cv['dfa_power']:.0f}", suffix=" W", column=m4)
        metric("VT1", f"{cv['vt1_power']:.0f}", suffix=" W", column=m5)
        metric("VT2", f"{cv['vt2_power']:.0f}", suffix=" W", column=m6)
        if cv["within_range"]:
            st.success("✅ Próg DFA jest spójny z progami wentylacyjnymi (VT1-VT2).")
        else:
            st.warning(
                f"⚠️ Próg DFA odchyla o {cv['deviation_pct']:.1f}% od VT1. Sprawdź jakość sygnału."
            )

    with st.expander("📖 Teoria — DFA Alpha1 jako marker progu"):
        st.markdown("""
        **DFA Alpha1** (Detrended Fluctuation Analysis) to korelacyjny wskaźnik
        zmienności rytmu zatokowego (HRV), który zmienia się z intensywnością wysiłku.

        **Próg DFA α1 = 0.75** odpowiada w przybliżeniu przejściu tlenowemu (LT1/VT1).
        - α1 > 0.75: dominująca regulacja przywspółczulna (strefa tlenowa)
        - α1 < 0.75: dominująca regulacja współczulna (strefa beztlenowa)
        - α1 ~ 0.5: silny stres współczulny (intensywność VO2max+)

        **Zastosowanie:**
        - Nieinwazyjna ocena progu mleczanowego z danych HRV
        - Monitorowanie adaptacji treningowej (przesunięcie progu w górę = poprawa)
        - Planowanie intensywności bez testów laboratoryjnych

        **Bibliografia:**
        - Rogers SA, Gronwald T (2022). Physiological markers of HT via DFA.
        - Mateo-March M et al. (2024). HRVT1 ICC=0.87, HRVT2 ICC=0.97.
        """)


def _assess_quality(alpha1: np.ndarray) -> str:
    """Assess DFA signal quality."""
    valid = np.isfinite(alpha1)
    pct_valid = np.sum(valid) / max(len(alpha1), 1)
    if pct_valid < 0.5:
        return "D"
    mean_val = np.nanmean(alpha1)
    if mean_val < 0.3 or mean_val > 1.5:
        return "D"
    if pct_valid > 0.95 and 0.4 < mean_val < 1.2:
        return "A"
    if pct_valid > 0.9:
        return "B"
    return "C"
