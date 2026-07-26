import hashlib
import streamlit as st
import os
import logging

# --- FRONTEND IMPORTS ---
from modules.frontend.theme import ThemeManager
from modules.frontend.state import StateManager
from modules.frontend.layout import AppLayout
from modules.frontend.components import UIComponents

logger = logging.getLogger(__name__)

# --- MODULE IMPORTS ---
from modules.utils import load_data
from modules.ml_logic import MLX_AVAILABLE, predict_only, MODEL_FILE
from modules.notes import TrainingNotes
from modules.db import SessionStore, SessionRecord
from modules.reporting.persistence import check_git_tracking
from modules.domain import SessionType, classify_session_type, classify_ramp_test

# --- SERVICES IMPORTS ---
from services import calculate_header_metrics, prepare_session_record, prepare_sticky_header_data

# --- CONSTANTS ---
MIN_POWER_SAMPLES_FOR_RAMP = 300


# --- TAB REGISTRY (OCP) ---
class TabRegistry:
    """Registry for UI tabs to support Open/Closed Principle."""

    _tabs = {
        "report": ("modules.ui.report", "render_report_tab"),
        "power": ("modules.ui.power", "render_power_tab"),
        "biomech": ("modules.ui.biomech", "render_biomech_tab"),
        "model": ("modules.ui.model", "render_model_tab"),
        "hrv": ("modules.ui.hrv", "render_hrv_tab"),
        "smo2": ("modules.ui.smo2", "render_smo2_tab"),
        "hemo": ("modules.ui.hemo", "render_hemo_tab"),
        "vent": ("modules.ui.vent", "render_vent_tab"),
        "thermal": ("modules.ui.thermal", "render_thermal_tab"),
        "nutrition": ("modules.ui.nutrition", "render_nutrition_tab"),
        "limiters": ("modules.ui.limiters", "render_limiters_tab"),
        "thresholds": ("modules.ui.threshold_analysis_ui", "render_threshold_analysis_tab"),
        "history": ("modules.ui.trends_history", "render_trends_history_tab"),
        "community": ("modules.ui.community", "render_community_tab"),
        "import": ("modules.ui.history_import_ui", "render_history_import_tab"),
        "heart_rate": ("modules.ui.heart_rate", "render_hr_tab"),
        "summary": ("modules.ui.summary", "render_summary_tab"),
        "drift_maps": ("modules.ui.drift_maps_ui", "render_drift_maps_tab"),
        # --- Cycling features migrated from Tri_Dashboard ---
        "tte": ("modules.ui.tte_ui", "render_tte_tab"),
        "race_predictor": ("modules.ui.race_predictor_ui", "render_race_predictor_tab"),
        "training_distribution": (
            "modules.ui.training_distribution_ui",
            "render_training_distribution_tab",
        ),
        "durability": ("modules.ui.durability_ui", "render_durability_tab"),
        "w_prime_reconstitution": (
            "modules.ui.w_prime_reconstitution_ui",
            "render_w_prime_reconstitution_tab",
        ),
        "heat_strain": ("modules.ui.heat_strain_ui", "render_heat_strain_tab"),
        # --- Cycling analytics migrated from Tri_Dashboard (Phase 5) ---
        "mpa": ("modules.ui.mpa_ui", "render_mpa_tab"),
        "vlamax": ("modules.ui.vlamax_ui", "render_vlamax_tab"),
        "aerobic_efficiency": (
            "modules.ui.aerobic_efficiency_ui",
            "render_aerobic_efficiency_tab",
        ),
        "training_impact": ("modules.ui.training_impact_ui", "render_training_impact_tab"),
        "banister": ("modules.ui.banister_ui", "render_banister_tab"),
        "periodization": ("modules.ui.periodization_ui", "render_periodization_tab"),
        # --- Longitudinal / whole-athlete analysis ---
        "load": ("modules.ui.training_load_ui", "render_training_load_tab"),
        "compare": ("modules.ui.compare", "render_comparison_tab"),
        "alerts": ("modules.ui.alerts", "render_alerts_tab"),
        "smo2_thresholds": ("modules.ui.smo2_thresholds", "render_smo2_thresholds_tab"),
        "intervals": ("modules.ui.intervals_ui", "render_intervals_tab"),
        "power_trends": ("modules.ui.power_trends_ui", "render_power_trends_tab"),
    }

    @classmethod
    def render(cls, tab_name, *args, **kwargs):
        """Dynamic dispatcher for tab rendering (Lazy loading)."""
        if tab_name not in cls._tabs:
            st.error(f"Unknown tab: {tab_name}")
            return

        module_path, func_name = cls._tabs[tab_name]
        try:
            import importlib

            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            return func(*args, **kwargs)
        except Exception as e:
            st.error(f"Error loading tab {tab_name}: {e}")


def render_tab_content(tab_name, *args, **kwargs):
    """Facade for TabRegistry."""
    return TabRegistry.render(tab_name, *args, **kwargs)


# --- INIT ---
ThemeManager.set_page_config()
ThemeManager.load_css()

state = StateManager()
state.init_session_state()

# Safety Check: Git Tracking of sensitive data (reports & raw CSVs)
check_git_tracking("reports/ramp_tests")
check_git_tracking("treningi_csv")

layout = AppLayout(state)
uploaded_file, params = layout.render_sidebar()

# Parameters shorthand
rider_weight = params.get("rider_weight", 75.0)
cp_input = params.get("cp", 280)
vt1_watts = params.get("vt1_watts", 0)
vt2_watts = params.get("vt2_watts", 0)
vt1_vent = params.get("vt1_vent", 0)
vt2_vent = params.get("vt2_vent", 0)
w_prime_input = params.get("w_prime", 20000)
rider_age = params.get("rider_age", 30)
is_male = params.get("is_male", True)

layout.render_header()


if rider_weight <= 0 or cp_input <= 0:
    st.error("Błąd: Waga i CP muszą być większe od zera.")
    st.stop()

if uploaded_file is not None:
    state.cleanup_old_data()
    training_notes = TrainingNotes()

    with st.spinner("Przetwarzanie danych..."):
        try:
            df_raw = load_data(uploaded_file)

            # --- SESSION TYPE CLASSIFICATION (MUST run first) ---

            # Check if we already processed this file (content-based hash)
            uploaded_file.seek(0)
            current_file_hash = hashlib.md5(uploaded_file.read()).hexdigest()
            uploaded_file.seek(0)
            cached_hash = st.session_state.get("current_file_hash")
            
            if cached_hash != current_file_hash:
                # New file - process and cache
                session_type = classify_session_type(df_raw, uploaded_file.name)
                st.session_state["session_type"] = session_type
                st.session_state["current_file_hash"] = current_file_hash
                
                # Store detailed ramp classification for gating decisions
                ramp_classification = None
                if "watts" in df_raw.columns or "power" in df_raw.columns:
                    power_col = "watts" if "watts" in df_raw.columns else "power"
                    power = df_raw[power_col].dropna()
                    if len(power) >= MIN_POWER_SAMPLES_FOR_RAMP:
                        ramp_classification = classify_ramp_test(power)
                        st.session_state["ramp_classification"] = ramp_classification
            else:
                # Use cached values
                session_type = st.session_state.get("session_type")
                ramp_classification = st.session_state.get("ramp_classification")

            # --- PROCESSING PIPELINE (SRP/DIP) ---
            from services.session_orchestrator import process_uploaded_session

            df_plot, df_plot_resampled, metrics, error_msg = process_uploaded_session(
                df_raw, cp_input, w_prime_input, rider_weight, vt1_watts, vt2_watts
            )

            if error_msg:
                st.error(f"Błąd analizy: {error_msg}")
                st.stop()

            # Extract intermediate results from metrics (DIP: metrics acts as a container here)
            decoupling_percent = metrics.pop("_decoupling_percent", 0.0)
            drift_z2 = metrics.pop("_drift_z2", 0.0)
            # FIXED: _df_clean_pl removed from metrics - use df_raw directly
            df_clean_pl = df_raw

            state.set_data_loaded()

            # AI Section (Optional/Non-critical)
            if MLX_AVAILABLE and os.path.exists(MODEL_FILE):
                try:
                    auto_pred = predict_only(df_plot_resampled)
                    if auto_pred is not None:
                        df_plot_resampled["ai_hr"] = auto_pred
                except Exception as e:
                    logger.warning(f"AI prediction failed: {e}")

        except Exception as e:
            st.error(f"Błąd wczytywania pliku: {e}")
            st.stop()

    # --- RENDER DASHBOARD ---

    # 1. Header Metrics
    np_header, if_header, tss_header = calculate_header_metrics(df_plot, cp_input)

    # Auto-save
    try:
        session_data = prepare_session_record(
            uploaded_file.name, df_plot, metrics, np_header, if_header, tss_header
        )
        SessionStore().add_session(SessionRecord(**session_data))
    except Exception as e:
        logger.warning(f"Auto-save failed: {e}")

    # Sticky Header
    header_data = prepare_sticky_header_data(df_plot, metrics)
    UIComponents.render_sticky_header(header_data)

    m1, m2, m3 = st.columns(3)
    m1.metric("NP (Norm. Power)", f"{np_header:.0f} W")
    m2.metric("TSS", f"{tss_header:.0f}", help=f"IF: {if_header:.2f}")
    m3.metric("Praca [kJ]", f"{df_plot['watts'].sum() / 1000:.0f}")

    # Session Type Badge with Confidence
    session_type = st.session_state.get("session_type")
    ramp_classification = st.session_state.get("ramp_classification")

    if session_type:
        # Build display message based on session type
        if session_type == SessionType.RAMP_TEST and ramp_classification:
            confidence = ramp_classification.confidence
            bg_color = "rgba(46, 204, 113, 0.2)"
            msg = f"Rozpoznano: <b>Ramp Test</b> (confidence: {confidence:.2f})"
        elif session_type == SessionType.RAMP_TEST_CONDITIONAL and ramp_classification:
            confidence = ramp_classification.confidence
            bg_color = "rgba(241, 196, 15, 0.2)"
            msg = f"Rozpoznano: <b>Ramp Test (warunkowo)</b> (confidence: {confidence:.2f})"
        elif session_type == SessionType.TRAINING:
            bg_color = "rgba(52, 152, 219, 0.2)"
            if ramp_classification and not ramp_classification.is_ramp:
                msg = f"Sesja treningowa – analiza badawcza pominięta"
            else:
                msg = f"Rozpoznano: <b>Sesja treningowa</b>"
        else:
            bg_color = "rgba(149, 165, 166, 0.2)"
            msg = f"Typ sesji: <b>{session_type}</b>"

        # Escape msg for defense-in-depth (msg is built from trusted enum values,
        # but we sanitize to prevent any future XSS if inputs change)
        import html as html_lib
        safe_msg = html_lib.escape(msg).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        emoji_val = session_type.emoji if isinstance(session_type.emoji, str) else session_type.emoji()
        safe_emoji = html_lib.escape(emoji_val)

        st.markdown(
            f"""
        <div style="background: linear-gradient(90deg, {bg_color}, transparent);
                    padding: 10px 15px; border-radius: 8px; margin-bottom: 10px; display: inline-block;">
            <span style="font-size: 1.1em;">{safe_emoji} {safe_msg}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Physiological alert report (overtraining risk, cardiac drift, SmO2 crash, HRV)
    try:
        from modules.calculations.alert_engine import analyze_session_alerts

        _history = SessionStore().get_sessions(days=90)
        _session_history = [
            {
                "date": r.date,
                "avg_rmssd": r.avg_rmssd,
                "session_type": getattr(r, "session_type", None),
                "tss": r.tss,
            }
            for r in _history
        ]
        alert_report = analyze_session_alerts(df_plot, metrics, session_history=_session_history)
    except Exception as e:
        logger.warning(f"Alert engine failed: {e}")
        from modules.calculations.alert_engine import AlertReport

        alert_report = AlertReport()

    # Layout Tabs
    tab_overview, tab_performance, tab_intelligence, tab_physiology, tab_cycling = st.tabs(
        ["📊 Overview", "⚡ Performance", "🧠 Intelligence", "🫀 Physiology", "🚴 Cycling"]
    )

    with tab_overview:
        UIComponents.show_breadcrumb("📊 Overview")
        t1, t2, t3, t4, t5 = st.tabs(
            ["📋 Raport z KPI", "📊 Podsumowanie", "📅 Load (PMC)", "🔀 Compare", "📈 Moc w czasie"]
        )
        with t1:
            render_tab_content(
                "report",
                df_plot,
                df_plot_resampled,
                metrics,
                rider_weight,
                cp_input,
                decoupling_percent,
                drift_z2,
                vt1_vent,
                vt2_vent,
            )
        with t2:
            render_tab_content(
                "summary",
                df_plot,
                df_plot_resampled,
                metrics,
                training_notes,
                uploaded_file.name,
                cp_input,
                w_prime_input,
                rider_weight,
                vt1_watts,
                vt2_watts,
                vt1_watts,  # FIXED: lt1_watts - use VT1 as proxy (VT1 ≈ LT1)
                vt2_watts,  # FIXED: lt2_watts - use VT2 as proxy (VT2 ≈ LT2)
            )
            st.divider()
            with st.expander("📄 Eksport raportu PDF"):
                if st.button("Generuj raport PDF", key="btn_gen_pdf"):
                    with st.spinner("Generowanie PDF…"):
                        try:
                            from modules.cache_utils import cached_generate_summary_pdf

                            pdf_bytes = cached_generate_summary_pdf(
                                df_plot,
                                metrics,
                                cp_input,
                                w_prime_input,
                                rider_weight,
                                vt1_watts,
                                vt2_watts,
                                vt1_watts,  # lt1 proxy
                                vt2_watts,  # lt2 proxy
                                st.session_state.get("threshold_result"),
                                st.session_state.get("smo2_result"),
                                uploaded_file.name,
                            )
                            st.session_state["summary_pdf_bytes"] = pdf_bytes
                        except Exception as e:
                            logger.warning(f"PDF generation failed: {e}")
                            st.error(f"Nie udało się wygenerować PDF: {e}")
                if st.session_state.get("summary_pdf_bytes"):
                    st.download_button(
                        "⬇️ Pobierz PDF",
                        data=st.session_state["summary_pdf_bytes"],
                        file_name=f"raport_{uploaded_file.name}.pdf",
                        mime="application/pdf",
                        key="dl_summary_pdf",
                    )
        with t3:
            render_tab_content("load")
        with t4:
            render_tab_content("compare")
        with t5:
            render_tab_content("power_trends")

    with tab_performance:
        UIComponents.show_breadcrumb("⚡ Performance")
        t1, t2, t3, t4, t5, t6, t7, t8, t9 = st.tabs(
            [
                "🔋 Power",
                "🦵 Biomech",
                "📐 Model",
                "❤️ HR",
                "🧬 Hematology",
                "📈 Drift Maps",
                "⏱️ TTE",
                "🔗 W'bal Recon",
                "🛡️ Durability",
            ]
        )
        with t1:
            render_tab_content(
                "power",
                df_plot,
                df_plot_resampled,
                cp_input,
                w_prime_input,
                rider_weight,
                metrics.get("vo2_max_est", 0),
            )
        with t2:
            render_tab_content("biomech", df_plot, df_plot_resampled)
        with t3:
            render_tab_content("model", df_plot, cp_input, w_prime_input)
        with t4:
            render_tab_content("heart_rate", df_plot)
        with t5:
            render_tab_content("hemo", df_plot)
        with t6:
            render_tab_content("drift_maps", df_plot)
        with t7:
            render_tab_content("tte", df_plot, cp_input, uploaded_file.name)
        with t8:
            render_tab_content(
                "w_prime_reconstitution",
                df_plot,
                df_plot_resampled,
                metrics,
                rider_weight,
                cp_input,
                w_prime_input,
            )
        with t9:
            render_tab_content(
                "durability",
                df_plot,
                df_plot_resampled,
                metrics,
                rider_weight,
                cp_input,
                w_prime_input,
            )

    with tab_intelligence:
        UIComponents.show_breadcrumb("🧠 Intelligence")
        t1, t2, t3, t4, t5 = st.tabs(
            [
                "🍎 Nutrition",
                "🚧 Limiters",
                "🏁 Race Predictor",
                "📊 Training Distribution",
                "🔁 Intervals",
            ]
        )
        with t1:
            render_tab_content("nutrition", df_plot, cp_input, vt1_watts, vt2_watts)
        with t2:
            render_tab_content("limiters", df_plot, cp_input, vt2_vent)
        with t3:
            render_tab_content(
                "race_predictor",
                df_plot,
                df_plot_resampled,
                metrics,
                rider_weight,
                cp_input,
                w_prime_input,
            )
        with t4:
            render_tab_content(
                "training_distribution",
                df_plot,
                df_plot_resampled,
                metrics,
                rider_weight,
                cp_input,
                w_prime_input,
            )
        with t5:
            render_tab_content(
                "intervals",
                df_plot,
                df_plot_resampled,
                cp_input,
                rider_weight,
                rider_age,
                is_male,
            )

    with tab_physiology:
        UIComponents.show_breadcrumb("🫀 Physiology")
        t1, t2, t3, t4, t5, t6, t7 = st.tabs(
            [
                "💓 HRV",
                "🩸 SmO2",
                "🫁 Ventilation",
                "🌡️ Thermal",
                "🔥 Heat Strain",
                "🚨 Alerts",
                "🩸 Progi SmO2",
            ]
        )
        with t1:
            render_tab_content("hrv", df_clean_pl)
        with t2:
            render_tab_content("smo2", df_plot, training_notes, uploaded_file.name)
        with t3:
            render_tab_content("vent", df_plot, training_notes, uploaded_file.name)
        with t4:
            render_tab_content("thermal", df_plot)
        with t5:
            render_tab_content(
                "heat_strain",
                df_plot,
                df_plot_resampled,
                metrics,
                rider_weight,
                cp_input,
                w_prime_input,
                params.get("hr_max"),
                params.get("hr_rest"),
                rider_age,
                is_male,
            )
        with t6:
            render_tab_content("alerts", alert_report)
        with t7:
            render_tab_content(
                "smo2_thresholds",
                df_plot,
                training_notes,
                uploaded_file.name,
                cp_input,
            )

    with tab_cycling:
        UIComponents.show_breadcrumb("🚴 Cycling")
        t1, t2, t3, t4, t5, t6 = st.tabs(
            [
                "🎯 MPA",
                "🧪 VLaMax",
                "♻️ Aerobic Efficiency",
                "📈 Training Impact",
                "🗓️ Banister",
                "📅 Periodization",
            ]
        )
        with t1:
            render_tab_content("mpa", df_plot, cp_input, w_prime_input)
        with t2:
            render_tab_content("vlamax", df_plot, cp_input, w_prime_input, rider_weight)
        with t3:
            render_tab_content("aerobic_efficiency", df_plot, cp_input)
        with t4:
            render_tab_content("training_impact", df_plot, cp_input, w_prime_input)
        with t5:
            render_tab_content("banister")
        with t6:
            render_tab_content("periodization")

else:
    st.sidebar.info("Wgraj plik.")
