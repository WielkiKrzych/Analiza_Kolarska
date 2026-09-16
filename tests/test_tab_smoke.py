"""Every dashboard tab renders a synthetic step-test session without raising."""

import logging

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

from modules.config import Config
from modules.ui.tab_config import render_tab_content
from modules.ui.tab_layout import TAB_GROUPS, SessionContext
from services.session_orchestrator import process_uploaded_session

# Same keys as modules/frontend/layout.py:render_sidebar — no hr_max / hr_rest there.
PARAMS = {
    "rider_weight": 75.0, "rider_height": 180, "rider_age": 35, "is_male": True,
    "vt1_watts": 220, "vt2_watts": 290, "vt1_vent": 50, "vt2_vent": 80,
    "cp": 280, "w_prime": 20000, "crank_length": 172.5,
}

# Intervals.icu tab talks to the live API when a key is configured — not a unit-test concern.
OFFLINE_TABS = [
    pytest.param(tab, id=tab.name)
    for group in TAB_GROUPS
    for tab in group.tabs
    if tab.name != "intervals_icu"
]


def build_context(df_raw) -> SessionContext:
    from modules.notes import TrainingNotes

    df_plot, df_resampled, metrics, error = process_uploaded_session(
        df_raw, PARAMS["cp"], PARAMS["w_prime"], PARAMS["rider_weight"],
        PARAMS["vt1_watts"], PARAMS["vt2_watts"],
    )
    assert error is None
    return SessionContext(
        df_raw=df_raw,
        df_plot=df_plot,
        df_plot_resampled=df_resampled,
        metrics=metrics,
        training_notes=TrainingNotes(),
        file_name="synthetic_ramp.csv",
        params=PARAMS,
        decoupling_percent=metrics.pop("_decoupling_percent", 0.0),
        drift_z2=metrics.pop("_drift_z2", 0.0),
    )


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "DB_PATH", tmp_path / "training_history.db")
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


@pytest.mark.parametrize("tab", OFFLINE_TABS)
def test_tab_renders_without_error(tab, synthetic_ramp_df, isolated_db, caplog):
    ctx = build_context(synthetic_ramp_df)

    with caplog.at_level(logging.ERROR, logger="modules.ui.tab_config"):
        render_tab_content(tab.name, *tab.args(ctx))

    assert not caplog.records, caplog.records[0].getMessage() if caplog.records else ""


def _dashboard_script(df_raw, params, db_path):
    from modules.config import Config
    from modules.frontend.state import MANUAL_INPUT_KEYS, StateManager
    from modules.ui.tab_layout import NAV_WIDGET_KEYS, SessionContext, render_selected_tab
    from services.session_orchestrator import process_uploaded_session

    Config.DB_PATH = db_path
    StateManager().preserve_widget_state(MANUAL_INPUT_KEYS + NAV_WIDGET_KEYS)
    df_plot, df_resampled, metrics, _ = process_uploaded_session(
        df_raw, params["cp"], params["w_prime"], params["rider_weight"],
        params["vt1_watts"], params["vt2_watts"],
    )
    render_selected_tab(
        SessionContext(df_raw, df_plot, df_resampled, metrics, None, "ramp.csv", params, 0.0, 0.0)
    )


def _single_select_indices(self):
    """AppTest 1.54 iterates a single-select value's characters; treat it as one option."""
    values = self.value if isinstance(self.value, list) else [self.value]
    return [self.options.index(self.format_func(v)) for v in values if v is not None]


def navigate(at, group_label, tab_label=None):
    group_idx = [g.label for g in TAB_GROUPS].index(group_label)
    at.button_group(key="nav_group").set_value(group_label).run()
    if tab_label:
        at.button_group(key=f"nav_tab_{group_idx}").set_value(tab_label).run()


def test_only_selected_tab_renders_and_manual_threshold_survives_navigation(
    synthetic_ramp_df, tmp_path, monkeypatch
):
    monkeypatch.setattr(Config, "DB_PATH", tmp_path / "training_history.db")
    monkeypatch.setattr(ButtonGroup, "indices", property(_single_select_indices))
    at = AppTest.from_function(
        _dashboard_script,
        args=(synthetic_ramp_df, PARAMS, tmp_path / "training_history.db"),
        default_timeout=60,
    )
    at.run()
    assert not at.exception
    assert not at.number_input  # Overview → KPI report has no manual inputs

    navigate(at, "🔬 Fizjologia (TD)", "🛠️ Manual Thresholds")
    assert not at.exception
    at.number_input(key="manual_vt1_watts").set_value(255).run()

    navigate(at, "⚡ Performance")
    assert not at.exception
    assert "manual_vt1_watts" not in [w.key for w in at.number_input]

    navigate(at, "🔬 Fizjologia (TD)")
    assert not at.exception
    assert at.button_group(key="nav_tab_5").value == "🛠️ Manual Thresholds"
    assert at.number_input(key="manual_vt1_watts").value == 255  # auto-detected VT1 is ~334 W


@pytest.mark.parametrize("tab_name", ["summary", "limiters"])
def test_tab_does_not_rename_columns_of_shared_frame(tab_name, synthetic_ramp_df, isolated_db):
    ctx = build_context(synthetic_ramp_df)
    ctx.df_plot["Lap Marker "] = 1
    tab = next(t for group in TAB_GROUPS for t in group.tabs if t.name == tab_name)

    render_tab_content(tab.name, *tab.args(ctx))

    assert "Lap Marker " in ctx.df_plot.columns
