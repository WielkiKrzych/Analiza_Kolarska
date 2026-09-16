import hashlib
import streamlit as st
import os
import logging

# --- FRONTEND IMPORTS ---
from modules.frontend.theme import ThemeManager
from modules.frontend.state import MANUAL_INPUT_KEYS, StateManager
from modules.frontend.layout import AppLayout
from modules.frontend.components import UIComponents

logger = logging.getLogger(__name__)

# --- MODULE IMPORTS ---
from modules.utils import load_data
from modules.ml_logic import MLX_AVAILABLE, predict_only, MODEL_FILE
from modules.notes import TrainingNotes
from modules.db import SessionRecord
from modules.cache_utils import get_session_store
from modules.reporting.persistence import check_git_tracking
from modules.domain import SessionType, classify_session_type, classify_ramp_test

# --- SERVICES IMPORTS ---
from services import calculate_header_metrics, prepare_session_record, prepare_sticky_header_data
from modules.ui.tab_layout import NAV_WIDGET_KEYS, SessionContext, Tab, render_selected_tab

# --- CONSTANTS ---
MIN_POWER_SAMPLES_FOR_RAMP = 300


def _render_summary_pdf_export(tab: Tab, ctx: SessionContext) -> None:
    """PDF export panel shown under the Summary tab."""
    if tab.name != "summary":
        return
    st.divider()
    with st.expander("📄 Eksport raportu PDF"):
        if st.button("Generuj raport PDF", key="btn_gen_pdf"):
            with st.spinner("Generowanie PDF…"):
                try:
                    from modules.cache_utils import cached_generate_summary_pdf
                    from modules.ui.summary import detect_session_thresholds

                    threshold_result, smo2_result = detect_session_thresholds(ctx.df_plot, ctx.cp)
                    pdf_bytes = cached_generate_summary_pdf(
                        ctx.df_plot,
                        ctx.metrics,
                        ctx.cp,
                        ctx.w_prime,
                        ctx.rider_weight,
                        ctx.vt1_watts,
                        ctx.vt2_watts,
                        ctx.vt1_watts,  # lt1 proxy
                        ctx.vt2_watts,  # lt2 proxy
                        threshold_result,
                        smo2_result,
                        ctx.file_name,
                    )
                    st.session_state["summary_pdf_bytes"] = pdf_bytes
                except Exception as e:
                    logger.warning(f"PDF generation failed: {e}")
                    st.error(f"Nie udało się wygenerować PDF: {e}")
        if st.session_state.get("summary_pdf_bytes"):
            st.download_button(
                "⬇️ Pobierz PDF",
                data=st.session_state["summary_pdf_bytes"],
                file_name=f"raport_{ctx.file_name}.pdf",
                mime="application/pdf",
                key="dl_summary_pdf",
            )


# --- INIT ---
ThemeManager.set_page_config()
ThemeManager.load_css()

state = StateManager()
state.init_session_state()
state.preserve_widget_state(MANUAL_INPUT_KEYS + NAV_WIDGET_KEYS)

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
w_prime_input = params.get("w_prime", 20000)

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
                state.reset_manual_inputs()
                st.session_state.pop("summary_pdf_bytes", None)  # previous file's PDF
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

    # Auto-save — once per file and parameter set, not on every widget click
    autosave_key = (current_file_hash, cp_input, w_prime_input, rider_weight, vt1_watts, vt2_watts)
    if st.session_state.get("autosaved_key") != autosave_key:
        try:
            session_data = prepare_session_record(
                uploaded_file.name, df_plot, metrics, np_header, if_header, tss_header
            )
            get_session_store().add_session(SessionRecord(**session_data))
            st.session_state["autosaved_key"] = autosave_key
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

    ctx = SessionContext(
        df_raw=df_clean_pl,
        df_plot=df_plot,
        df_plot_resampled=df_plot_resampled,
        metrics=metrics,
        training_notes=training_notes,
        file_name=uploaded_file.name,
        params=params,
        decoupling_percent=decoupling_percent,
        drift_z2=drift_z2,
    )
    render_selected_tab(ctx, after_render=lambda tab: _render_summary_pdf_export(tab, ctx))

else:
    st.sidebar.info("Wgraj plik.")
