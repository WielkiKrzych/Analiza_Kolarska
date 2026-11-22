"""
Dashboard navigation: tab groups, per-tab render arguments, lazy rendering.

st.tabs computes the content of every tab on every rerun (Streamlit 1.54 docs), so the
dashboard selects a group and a tab with segmented controls and renders only that tab.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

import pandas as pd
import streamlit as st

from modules.frontend.components import UIComponents
from modules.ui.tab_config import render_tab_content


@dataclass(frozen=True)
class SessionContext:
    """Everything a tab renderer may need for the currently loaded session."""

    df_raw: pd.DataFrame
    df_plot: pd.DataFrame
    df_plot_resampled: pd.DataFrame
    metrics: dict
    training_notes: Any
    file_name: str
    params: dict
    decoupling_percent: float
    drift_z2: float

    @property
    def rider_weight(self) -> float:
        return self.params.get("rider_weight", 75.0)

    @property
    def cp(self) -> float:
        return self.params.get("cp", 280)

    @property
    def w_prime(self) -> float:
        return self.params.get("w_prime", 20000)

    @property
    def vt1_watts(self) -> float:
        return self.params.get("vt1_watts", 0)

    @property
    def vt2_watts(self) -> float:
        return self.params.get("vt2_watts", 0)

    @property
    def vt1_vent(self) -> float:
        return self.params.get("vt1_vent", 0)

    @property
    def vt2_vent(self) -> float:
        return self.params.get("vt2_vent", 0)

    @property
    def rider_age(self) -> int:
        return self.params.get("rider_age", 30)

    @property
    def is_male(self) -> bool:
        return self.params.get("is_male", True)


@dataclass(frozen=True)
class Tab:
    label: str
    name: str  # TabRegistry key
    args: Callable[[SessionContext], tuple] = lambda c: ()


@dataclass(frozen=True)
class TabGroup:
    label: str
    tabs: tuple


def _perf_args(c: SessionContext) -> tuple:
    return (c.df_plot, c.df_plot_resampled, c.metrics, c.rider_weight, c.cp, c.w_prime)


TAB_GROUPS = (
    TabGroup("📊 Overview", (
        Tab("📋 Raport z KPI", "report", lambda c: (
            c.df_plot, c.df_plot_resampled, c.metrics, c.rider_weight, c.cp,
            c.decoupling_percent, c.drift_z2, c.vt1_vent, c.vt2_vent,
        )),
        Tab("📊 Podsumowanie", "summary", lambda c: (
            c.df_plot, c.df_plot_resampled, c.metrics, c.training_notes, c.file_name,
            c.cp, c.w_prime, c.rider_weight, c.vt1_watts, c.vt2_watts,
            None, None,  # no LT1/LT2 input — Summary falls back to its own SmO2 detection
        )),
    )),
    TabGroup("⚡ Performance", (
        Tab("🔋 Power", "power", lambda c: (
            c.df_plot, c.df_plot_resampled, c.cp, c.w_prime, c.rider_weight,
            c.metrics.get("vo2_max_est", 0),
        )),
        Tab("🦵 Biomech", "biomech", lambda c: (c.df_plot, c.df_plot_resampled)),
        Tab("📐 Model", "model", lambda c: (c.df_plot, c.cp, c.w_prime)),
        Tab("❤️ HR", "heart_rate", lambda c: (c.df_plot,)),
        Tab("🧬 Hematology", "hemo", lambda c: (c.df_plot,)),
        Tab("📈 Drift Maps", "drift_maps", lambda c: (c.df_plot,)),
        Tab("⏱️ TTE", "tte", lambda c: (c.df_plot, c.cp, c.file_name)),
        Tab("📈 Moc w czasie", "power_trends"),
    )),
    TabGroup("🧠 Intelligence", (
        Tab("🍎 Nutrition", "nutrition", lambda c: (c.df_plot, c.cp, c.vt1_watts, c.vt2_watts)),
        Tab("📊 Training Distribution", "training_distribution", _perf_args),
        Tab("🔁 Intervals", "intervals", lambda c: (
            c.df_plot, c.df_plot_resampled, c.cp, c.rider_weight, c.rider_age, c.is_male,
        )),
        Tab("🍎 Fueling", "fueling", lambda c: (c.df_plot_resampled, c.cp)),
        Tab("🤖 AI Coach", "ai_coach", lambda c: (c.df_plot_resampled, c.cp)),
    )),
    TabGroup("🫀 Physiology", (
        Tab("💓 HRV", "hrv", lambda c: (c.df_raw,)),
        Tab("🩸 SmO2", "smo2", lambda c: (c.df_plot, c.training_notes, c.file_name)),
        Tab("🫁 Ventilation", "vent", lambda c: (c.df_plot, c.training_notes, c.file_name)),
        Tab("🌡️ Thermal", "thermal", lambda c: (c.df_plot,)),
        Tab("🔥 Heat Strain", "heat_strain", lambda c: (
            *_perf_args(c), c.params.get("hr_max"), c.params.get("hr_rest"),
            c.rider_age, c.is_male,
        )),
        Tab("♻️ Aerobic Efficiency", "aerobic_efficiency", lambda c: (c.df_plot, c.cp)),
    )),
)

NAV_WIDGET_KEYS = ("nav_group",) + tuple(f"nav_tab_{i}" for i in range(len(TAB_GROUPS)))


def _select(label: str, options: list, key: str) -> str:
    """Segmented control that always has a selection (clicking the active option deselects it)."""
    choice = st.segmented_control(
        label, options, default=options[0], key=key, label_visibility="collapsed"
    )
    return choice if choice in options else options[0]


def render_selected_tab(
    ctx: SessionContext, after_render: Optional[Callable[[Tab], None]] = None
) -> None:
    """Render the group/tab navigation and only the selected tab's content."""
    group_labels = [g.label for g in TAB_GROUPS]
    group_idx = group_labels.index(_select("Sekcja", group_labels, "nav_group"))
    group = TAB_GROUPS[group_idx]

    tab = group.tabs[0]
    if len(group.tabs) > 1:
        tab_labels = [t.label for t in group.tabs]
        tab = group.tabs[tab_labels.index(_select("Zakładka", tab_labels, f"nav_tab_{group_idx}"))]

    UIComponents.show_breadcrumb(group.label, tab.label if len(group.tabs) > 1 else None)
    render_tab_content(tab.name, *tab.args(ctx))
    if after_render:
        after_render(tab)
