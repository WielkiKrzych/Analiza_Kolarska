"""
Tab configuration and dynamic dispatch (Open/Closed Principle).

Central registry mapping logical tab names to (module_path, render_func).
Extracted from app.py so adding a new tab only touches this file plus the
render call site — no more shotgun surgery in the main entry point.
"""
import importlib
import logging

import streamlit as st

logger = logging.getLogger(__name__)


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
        "smo2_thresholds": ("modules.ui.smo2_thresholds_tab", "render_smo2_thresholds_tab"),
        "smo2_manual": (
            "modules.ui.smo2_manual_thresholds",
            "render_smo2_manual_thresholds_tab",
        ),
        "intervals": ("modules.ui.intervals_ui", "render_intervals_tab"),
        "power_trends": ("modules.ui.power_trends_ui", "render_power_trends_tab"),
        # Pported cycling physiology tabs (ws6)
        "dfa_longitudinal": ("modules.ui.dfa_longitudinal_ui", "render_dfa_longitudinal_tab"),
        "fueling": ("modules.ui.fueling_ui", "render_fueling_tab"),
        "hrv_readiness": ("modules.ui.hrv_readiness_ui", "render_hrv_readiness_tab"),
        "sleep_recovery": ("modules.ui.sleep_recovery_ui", "render_sleep_recovery_tab"),
        "smo2_longitudinal": ("modules.ui.smo2_longitudinal_ui", "render_smo2_longitudinal_tab"),
        "manual_thresholds": ("modules.ui.manual_thresholds", "render_manual_thresholds_tab"),
        "vent_thresholds": ("modules.ui.vent_thresholds", "render_vent_thresholds_tab"),
        "ai_coach": ("modules.ui.ai_coach", "render_ai_coach_tab"),
        "intervals_icu": ("modules.ui.intervals_icu_ui", "render_intervals_icu_section"),
    }

    @classmethod
    def render(cls, tab_name, *args, **kwargs):
        """Dynamic dispatcher for tab rendering (Lazy loading)."""
        if tab_name not in cls._tabs:
            st.error(f"Unknown tab: {tab_name}")
            return

        module_path, func_name = cls._tabs[tab_name]
        try:
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Tab {tab_name} failed to render")
            st.error(f"Error loading tab {tab_name}: {e}")


def render_tab_content(tab_name, *args, **kwargs):
    """Facade for TabRegistry."""
    return TabRegistry.render(tab_name, *args, **kwargs)
