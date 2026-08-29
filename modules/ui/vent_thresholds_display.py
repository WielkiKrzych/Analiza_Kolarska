"""
Vent Thresholds — 4-threshold cards, metabolic zones table, analysis notes, theory section.
"""

import pandas as pd
import streamlit as st

from modules.calculations.thresholds import (
    detect_smo2_ramp_breakpoints,
    estimate_ftp_from_ramp,
)


def render_threshold_cards(cpet_result: dict, target_df: pd.DataFrame, cp_input: float) -> None:  # noqa: C901
    """
    Render method badge, 4 threshold cards (VT1_onset, VT1_steady, RCP_onset, RCP_steady),
    metabolic zones table, and analysis notes.
    """
    st.info(
        "ℹ️ **Tryb VE-only**: 4-punktowa analiza CPET (VT1_onset, VT1_steady, RCP_onset, RCP_steady)"
    )

    _render_estimate_warning(cpet_result)

    def get_metric_with_fallback(result_key, power_val, col_map):  # noqa: C901
        val = cpet_result.get(result_key)
        if val is None and power_val:
            mask = (target_df["watts"] >= power_val - 10) & (target_df["watts"] <= power_val + 10)
            if mask.any():
                try:
                    for src_col in col_map:
                        if src_col in target_df.columns:
                            v = target_df.loc[mask, src_col].mean()
                            if pd.notna(v) and v > 0:
                                return (
                                    int(v)
                                    if "hr" in result_key or "br" in result_key
                                    else round(v, 1)
                                )
                except Exception:
                    return val
        return val

    # Row 1: VT1_onset and VT1_steady
    col1, col2 = st.columns(2)

    with col1:
        vt1_onset_w = cpet_result.get("vt1_onset_watts") or cpet_result.get("vt1_watts")
        vt1_hr = get_metric_with_fallback("vt1_hr", vt1_onset_w, ["hr"])
        vt1_ve = get_metric_with_fallback("vt1_ve", vt1_onset_w, ["tymeventilation"])
        vt1_br = get_metric_with_fallback("vt1_br", vt1_onset_w, ["tymebreathrate"])

        if vt1_onset_w:
            hr_line = (
                f'<p style="margin:0; color:#aaa;"><b>HR:</b> {int(vt1_hr)} bpm</p>'
                if vt1_hr
                else ""
            )
            ve_line = (
                f'<p style="margin:0; color:#aaa;"><b>VE:</b> {vt1_ve} L/min</p>' if vt1_ve else ""
            )
            br_line = (
                f'<p style="margin:0; color:#aaa;"><b>BR:</b> {int(vt1_br)} oddech/min</p>'
                if (vt1_br and vt1_br > 0)
                else ""
            )
            st.markdown(
                f"""
            <div style="padding:12px; border-radius:8px; border:2px solid #ffa15a; background-color: #222;">
                <h4 style="margin:0; color: #ffa15a; font-size:0.9em;">VT1_onset</h4>
                <p style="margin:0; color:#888; font-size:0.75em;">GET / LT1 Onset</p>
                <h2 style="margin:5px 0; font-size:2em;">{int(vt1_onset_w)} W</h2>
                {hr_line}{ve_line}{br_line}
            </div>
            """,
                unsafe_allow_html=True,
            )
            if cp_input > 0:
                st.caption(f"~{(vt1_onset_w / cp_input) * 100:.0f}% CP")
        else:
            st.warning("VT1_onset: Nie wykryto")

    with col2:
        vt1_steady_w = cpet_result.get("vt1_steady_watts")
        vt1_steady_hr = get_metric_with_fallback("vt1_steady_hr", vt1_steady_w, ["hr"])
        vt1_steady_ve = cpet_result.get("vt1_steady_ve")
        vt1_steady_br = cpet_result.get("vt1_steady_br")
        is_interpolated = cpet_result.get("vt1_steady_is_interpolated", False)

        if vt1_steady_w:
            hr_line = (
                f'<p style="margin:0; color:#aaa;"><b>HR:</b> {int(vt1_steady_hr)} bpm</p>'
                if vt1_steady_hr
                else ""
            )
            ve_line = (
                f'<p style="margin:0; color:#aaa;"><b>VE:</b> {vt1_steady_ve} L/min</p>'
                if vt1_steady_ve
                else ""
            )
            br_line = (
                f'<p style="margin:0; color:#aaa;"><b>BR:</b> {int(vt1_steady_br)} oddech/min</p>'
                if (vt1_steady_br and vt1_steady_br > 0)
                else ""
            )
            if is_interpolated:
                st.markdown(
                    f"""
                <div style="padding:12px; border-radius:8px; border:2px dashed #888; background-color: #1a1a1a;">
                    <h4 style="margin:0; color: #888; font-size:0.9em;">VT1_steady (Interpolated)</h4>
                    <p style="margin:0; color:#666; font-size:0.7em;">⚠️ No physiological plateau detected</p>
                    <h2 style="margin:5px 0; font-size:2em; color:#aaa;">{int(vt1_steady_w)} W</h2>
                    {hr_line}{ve_line}{br_line}
                </div>
                """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                <div style="padding:12px; border-radius:8px; border:2px solid #00cc96; background-color: #222;">
                    <h4 style="margin:0; color: #00cc96; font-size:0.9em;">VT1_steady</h4>
                    <p style="margin:0; color:#888; font-size:0.75em;">LT1 Steady (Upper Aerobic Ceiling) ✓plateau</p>
                    <h2 style="margin:5px 0; font-size:2em;">{int(vt1_steady_w)} W</h2>
                    {hr_line}{ve_line}{br_line}
                </div>
                """,
                    unsafe_allow_html=True,
                )
            if cp_input > 0:
                st.caption(f"~{(vt1_steady_w / cp_input) * 100:.0f}% CP")
        else:
            st.warning("VT1_steady: Nie wykryto")

    # Row 2: RCP_onset and RCP_steady
    col3, col4 = st.columns(2)

    with col3:
        rcp_onset_w = cpet_result.get("rcp_onset_watts") or cpet_result.get("vt2_watts")
        vt2_hr = get_metric_with_fallback("vt2_hr", rcp_onset_w, ["hr"])
        vt2_ve = cpet_result.get("vt2_ve")
        vt2_br = get_metric_with_fallback("vt2_br", rcp_onset_w, ["tymebreathrate"])

        if rcp_onset_w:
            hr_line = (
                f'<p style="margin:0; color:#aaa;"><b>HR:</b> {int(vt2_hr)} bpm</p>'
                if vt2_hr
                else ""
            )
            ve_line = (
                f'<p style="margin:0; color:#aaa;"><b>VE:</b> {vt2_ve} L/min</p>' if vt2_ve else ""
            )
            br_line = (
                f'<p style="margin:0; color:#aaa;"><b>BR:</b> {int(vt2_br)} oddech/min</p>'
                if (vt2_br and vt2_br > 0)
                else ""
            )
            st.markdown(
                f"""
            <div style="padding:12px; border-radius:8px; border:2px solid #ef553b; background-color: #222;">
                <h4 style="margin:0; color: #ef553b; font-size:0.9em;">RCP_onset</h4>
                <p style="margin:0; color:#888; font-size:0.75em;">VT2 / LT2 Onset (Respiratory Compensation Point)</p>
                <h2 style="margin:5px 0; font-size:2em;">{int(rcp_onset_w)} W</h2>
                {hr_line}{ve_line}{br_line}
            </div>
            """,
                unsafe_allow_html=True,
            )
            if cp_input > 0:
                st.caption(f"~{(rcp_onset_w / cp_input) * 100:.0f}% CP")
        else:
            st.warning("RCP_onset: Nie wykryto")

    with col4:
        rcp_steady_w = cpet_result.get("rcp_steady_watts")
        rcp_steady_hr = cpet_result.get("rcp_steady_hr")
        rcp_steady_ve = cpet_result.get("rcp_steady_ve")
        rcp_steady_br = cpet_result.get("rcp_steady_br")

        if rcp_steady_w:
            hr_line = (
                f'<p style="margin:0; color:#aaa;"><b>HR:</b> {int(rcp_steady_hr)} bpm</p>'
                if rcp_steady_hr
                else ""
            )
            ve_line = (
                f'<p style="margin:0; color:#aaa;"><b>VE:</b> {rcp_steady_ve} L/min</p>'
                if rcp_steady_ve
                else ""
            )
            br_line = (
                f'<p style="margin:0; color:#aaa;"><b>BR:</b> {int(rcp_steady_br)} oddech/min</p>'
                if (rcp_steady_br and rcp_steady_br > 0)
                else ""
            )
            st.markdown(
                f"""
            <div style="padding:12px; border-radius:8px; border:2px solid #ab63fa; background-color: #222;">
                <h4 style="margin:0; color: #ab63fa; font-size:0.9em;">RCP_steady</h4>
                <p style="margin:0; color:#888; font-size:0.75em;">Full RCP (Severe Domain Entry)</p>
                <h2 style="margin:5px 0; font-size:2em;">{int(rcp_steady_w)} W</h2>
                {hr_line}{ve_line}{br_line}
            </div>
            """,
                unsafe_allow_html=True,
            )
            if cp_input > 0:
                st.caption(f"~{(rcp_steady_w / cp_input) * 100:.0f}% CP")
        else:
            st.info("RCP_steady: Nie wykryto (za mało danych)")

    # Metabolic zones table
    zones = cpet_result.get("metabolic_zones", [])
    if zones and len(zones) >= 4:
        st.markdown("---")
        st.subheader("🎯 Strefy Metaboliczne")

        zone_data = []
        for z in zones:
            hr_range = ""
            if z.get("hr_min") and z.get("hr_max"):
                hr_range = f"{z['hr_min']} - {z['hr_max']}"
            elif z.get("hr_max"):
                hr_range = f"< {z['hr_max']}"
            elif z.get("hr_min"):
                hr_range = f"> {z['hr_min']}"

            zone_name = z["name"]
            if z.get("is_interpolated"):
                zone_name += " ⚠️"

            zone_data.append(
                {
                    "Strefa": f"Z{z['zone']}",
                    "Nazwa": zone_name,
                    "Moc (W)": f"{z['power_min']} - {z['power_max']}",
                    "HR (bpm)": hr_range,
                    "Trening": z["training"],
                    "Domena": z.get("domain", ""),
                }
            )

            if z.get("subzones") and isinstance(z["subzones"], list):
                for sz in z["subzones"]:
                    zone_data.append(
                        {
                            "Strefa": "",
                            "Nazwa": f"  └ {sz['name']}",
                            "Moc (W)": f"{sz['power_min']} - {sz['power_max']}",
                            "HR (bpm)": "",
                            "Trening": "",
                            "Domena": "",
                        }
                    )

        st.dataframe(pd.DataFrame(zone_data), width="stretch", hide_index=True)

        interp = cpet_result.get("no_steady_state_interpretation")
        if interp:
            st.warning(f"📋 **Interpretacja:** {interp}")

    # Analysis notes
    analysis_notes = cpet_result.get("analysis_notes", [])
    if analysis_notes:
        with st.expander("📋 Notatki z analizy CPET", expanded=False):
            for note in analysis_notes:
                if note.startswith("⚠️"):
                    st.warning(note)
                else:
                    st.info(note)


def render_theory_section() -> None:
    """Render the collapsible theory/help section."""
    with st.expander("🫁 TEORIA: Progi Wentylacyjne (VT1 / VT2)", expanded=False):
        st.markdown("""
        ## Co to są progi wentylacyjne?

        **Progi wentylacyjne** to punkty, w których wentylacja (VE) zaczyna rosnąć nieliniowo względem mocy.

        | Próg | Inna nazwa | Fizjologia | % VO2max |
        |------|-----------|------------|----------|
        | **VT1** | Próg tlenowy, LT1 | Początek akumulacji mleczanu | ~50-60% |
        | **VT2** | Próg beztlenowy, LT2, OBLA | Maksymalny laktat steady-state | ~75-85% |

        ---

        ## Jak działa detekcja?

        System stosuje:
        1. **Sliding Window Analysis**: Skanuje okno po oknie, żeby znaleźć przejścia w nachyleniu (slope)
        2. **Breakpoint Detection**: Szuka punktów załamania krzywej VE vs Power
        3. **Sensitivity Analysis**: Uruchamia algorytm kilkukrotnie z różnymi parametrami

        ---

        ## Zastosowanie progów

        | Strefa | Zakres | Cel treningowy |
        |--------|--------|----------------|
        | **Z1 (Recovery)** | < VT1 | Regeneracja, rozgrzewka |
        | **Z2 (Endurance)** | VT1 - środek | Baza tlenowa |
        | **Z3 (Tempo)** | środek - VT2 | Sweet Spot |
        | **Z4 (Threshold)** | VT2 ± 5% | FTP, próg |
        | **Z5+ (VO2max)** | > VT2 | Interwały, moc szczytowa |

        ---

        ## Reliability Score (Niezawodność)

        * **HIGH**: Wynik jest stabilny niezależnie od wygładzania
        * **MEDIUM**: Wynik zależy nieco od parametrów
        * **LOW**: Duża zmienność (>15W różnicy) - sugeruje "szumiący" sygnał

        ---

        ## Wymagania testu

        ⚠️ **Dla wiarygodnych wyników potrzebujesz:**
        - Test stopniowany (Ramp Test) z liniowym wzrostem mocy
        - Minimum 10-15 minut narastającego obciążenia
        - Czysty sygnał wentylacji (stabilny sensor)
        - Brak przerw i wahań mocy
        """)


def _render_estimate_warning(cpet_result: dict) -> None:
    """
    Warn when a threshold was not detected and the displayed number is a
    heuristic (Pmax ratio / power percentile) rather than a measurement.

    Without this the cards look identical whether the breakpoint was found or
    guessed, which is how a 60%-of-Pmax estimate ended up being read as a
    lab-grade VT1.
    """
    estimated = [
        label
        for key, label in (("vt1_is_estimate", "VT1"), ("vt2_is_estimate", "VT2/RCP"))
        if cpet_result.get(key)
    ]
    if not estimated:
        return

    st.error(
        f"🚫 **{' i '.join(estimated)} NIE ZOSTAŁ WYKRYTY.** Poniżej widać szacunek "
        f"z heurystyki (odsetek Pmax / percentyl mocy), a nie zmierzony próg — "
        f"nie używaj tej wartości do wyznaczania stref ani do oceny zawodnika. "
        f"Metoda: `{cpet_result.get('method', 'nieznana')}`. "
        f"Sprawdź jakość danych VE i zakres mocy w teście."
    )


def render_ramp_summary(cpet_result: dict, target_df: pd.DataFrame) -> None:
    """
    One table with every threshold the ramp produces: VT1, VT2, SmO₂ BP1/BP2,
    FTP and LTHR, each labelled with the method that produced it and whether it
    is a measurement or an estimate.

    VT2 and SmO₂ BP2 are listed as separate rows on purpose. They answer different
    questions — one systemic (respiratory compensation), one local (muscle
    deoxygenation) — and averaging them would invent a number neither method
    measured. Where they disagree, the divergence is stated below the table.
    """
    df_steps = cpet_result.get("df_steps")
    if df_steps is None or len(df_steps) == 0:
        return

    st.markdown("---")
    st.subheader("📊 Podsumowanie testu — wszystkie progi")

    ftp = estimate_ftp_from_ramp(df_steps)
    smo2 = detect_smo2_ramp_breakpoints(target_df, ftp["map_watts"] or 0)

    def fmt(value, unit="W"):
        return f"{value} {unit}" if value is not None else "—"

    vt1_w = cpet_result.get("vt1_watts")
    vt2_w = cpet_result.get("vt2_watts")

    rows = [
        {
            "Próg": "VT1 (GET)",
            "Moc": fmt(vt1_w),
            "HR": fmt(cpet_result.get("vt1_hr"), "bpm"),
            "Metoda": "minimum ekwiwalentu VE/moc",
            "Typ": "szacunek" if cpet_result.get("vt1_is_estimate") else "pomiar",
        },
        {
            "Próg": "VT2 (RCP)",
            "Moc": fmt(vt2_w),
            "HR": fmt(cpet_result.get("vt2_hr"), "bpm"),
            "Metoda": "maks. przyspieszenie VE w oknie dopuszczalnym",
            "Typ": "szacunek" if cpet_result.get("vt2_is_estimate") else "pomiar",
        },
        {
            "Próg": "SmO₂ BP1",
            "Moc": fmt(smo2["bp1_watts"]),
            "HR": "—",
            "Metoda": "regresja 2-segmentowa",
            "Typ": "pomiar",
        },
        {
            "Próg": "SmO₂ BP2",
            "Moc": fmt(smo2["bp2_watts"]),
            "HR": "—",
            "Metoda": "regresja 3-segmentowa",
            "Typ": "pomiar",
        },
        {
            "Próg": "FTP",
            "Moc": fmt(ftp["ftp_watts"]),
            "HR": "—",
            "Metoda": ftp["model"],
            "Typ": "szacunek",
        },
        {
            "Próg": "LTHR",
            "Moc": "—",
            "HR": fmt(cpet_result.get("vt2_hr"), "bpm"),
            "Metoda": "tętno zmierzone na VT2",
            "Typ": "pomiar",
        },
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    if vt2_w is not None and smo2["bp2_watts"] is not None:
        gap = smo2["bp2_watts"] - vt2_w
        if abs(gap) >= 15:
            st.warning(
                f"⚠️ **VT2 i SmO₂ BP2 się rozjeżdżają: {gap:+d} W** "
                f"(VT2 {vt2_w} W, BP2 {smo2['bp2_watts']} W). To nie jest błąd pomiaru — "
                "próg oddechowy i próg mięśniowy to dwa różne zjawiska. "
                "BP2 wyżej niż VT2 oznacza mięsień odporniejszy niż układ oddechowy."
            )
        else:
            st.success(
                f"✅ VT2 i SmO₂ BP2 zgodne ({vt2_w} W vs {smo2['bp2_watts']} W, "
                f"różnica {gap:+d} W)."
            )

    for note in smo2["notes"]:
        st.info(note)
