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
        "heart_rate": ("modules.ui.heart_rate", "render_hr_tab"),
        "summary": ("modules.ui.summary", "render_summary_tab"),
        "drift_maps": ("modules.ui.drift_maps_ui", "render_drift_maps_tab"),
        # --- Cycling features migrated from Tri_Dashboard ---
        "tte": ("modules.ui.tte_ui", "render_tte_tab"),
        "training_distribution": (
            "modules.ui.training_distribution_ui",
            "render_training_distribution_tab",
        ),
        "heat_strain": ("modules.ui.heat_strain_ui", "render_heat_strain_tab"),
        # --- Cycling analytics migrated from Tri_Dashboard (Phase 5) ---
        "aerobic_efficiency": (
            "modules.ui.aerobic_efficiency_ui",
            "render_aerobic_efficiency_tab",
        ),
        "intervals": ("modules.ui.intervals_ui", "render_intervals_tab"),
        "power_trends": ("modules.ui.power_trends_ui", "render_power_trends_tab"),
        # Ported cycling physiology tabs (ws6)
        "fueling": ("modules.ui.fueling_ui", "render_fueling_tab"),
        "ai_coach": ("modules.ui.ai_coach", "render_ai_coach_tab"),
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
