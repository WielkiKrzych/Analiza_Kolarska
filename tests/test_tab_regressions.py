"""Regression tests for tab renderers that crashed or halted the whole app."""

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from modules.calculations.thermal import calculate_heat_strain_index


@pytest.fixture
def non_ramp_vent_df(sample_power_df):
    """Steady training ride with ventilation data — not a valid step test."""
    df = sample_power_df.copy()
    rng = np.random.default_rng(0)
    df["tymeventilation"] = rng.normal(60, 5, len(df))
    df["heartrate"] = df["heartrate"].round()
    return df


def test_heat_strain_index_reads_recorded_core_index_without_mutating_input():
    n = 600
    df = pd.DataFrame(
        {
            "time": np.arange(n, dtype=float),
            "core_temperature_smooth": np.linspace(37.0, 38.8, n),
            "heartrate_smooth": np.linspace(95, 175, n),
            # HSI is computed by the CORE sensor; the app must only read it.
            "heat_strain_index": np.linspace(0.0, 8.0, n),
        }
    )
    original_columns = list(df.columns)

    out = calculate_heat_strain_index(df)

    assert out["hsi"].equals(df["heat_strain_index"])
    assert list(df.columns) == original_columns


def _render_tab_then_marker(tab_name, args):
    import streamlit as st

    from modules.ui.tab_config import render_tab_content

    render_tab_content(tab_name, *args)
    st.markdown("AFTER_TAB")


def test_non_step_data_does_not_stop_rest_of_app(non_ramp_vent_df):
    from modules.notes import TrainingNotes

    args = (non_ramp_vent_df, TrainingNotes(), "ride.csv")
    at = AppTest.from_function(_render_tab_then_marker, args=("vent", args), default_timeout=30)
    at.run()

    assert not at.exception
    assert not [e.value for e in at.error if "Error loading tab" in e.value]
    assert any(m.value == "AFTER_TAB" for m in at.markdown)


def _box_selection_script():
    import streamlit as st

    from modules.ui.smo2 import _new_box_range

    def box(x0, x1):
        return {"selection": {"box": [{"x": [x1, x0]}]}}

    smo2_fresh = _new_box_range(box(100, 200), "smo2_seen")
    thb_fresh = _new_box_range(box(300, 400), "thb_seen")
    smo2_stale = _new_box_range(box(100, 200), "smo2_seen")  # still shown on SmO2 chart
    for result in (smo2_fresh, thb_fresh, smo2_stale, _new_box_range({"selection": {"box": []}}, "x")):
        st.text(str(result))


def test_stale_box_on_one_chart_does_not_override_new_box_on_other():
    at = AppTest.from_function(_box_selection_script).run()

    assert not at.exception
    assert [t.value for t in at.text] == ["(100, 200)", "(300, 400)", "None", "None"]
