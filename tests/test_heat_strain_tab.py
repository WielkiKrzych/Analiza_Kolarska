"""Heat Strain tab: recorded CORE HSI renders, missing HSI degrades gracefully."""

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest


def _render_heat_strain(df):
    from modules.ui.heat_strain_ui import render_heat_strain_tab

    render_heat_strain_tab(df, df, {}, 75.0, 280, 20000, 190, 50, 30, True)


def _session_df(with_hsi: bool) -> pd.DataFrame:
    n = 300
    time = np.arange(n, dtype=float)
    data = {
        "time": time,
        "time_min": time / 60.0,
        "watts": np.full(n, 200.0),
        "core_temperature": np.linspace(37.0, 38.5, n),
        "skin_temperature": np.linspace(33.0, 35.0, n),
        "temp": np.full(n, 24.0),
    }
    if with_hsi:
        data["heat_strain_index"] = np.linspace(0.0, 8.0, n)
    return pd.DataFrame(data)


def test_tab_renders_recorded_hsi():
    at = AppTest.from_function(
        _render_heat_strain, args=(_session_df(True),), default_timeout=60
    ).run()

    assert not at.exception
    assert not [i.value for i in at.info if "Brak Heat Strain Index" in i.value]


def test_tab_without_hsi_shows_message_without_crashing():
    at = AppTest.from_function(
        _render_heat_strain, args=(_session_df(False),), default_timeout=60
    ).run()

    assert not at.exception
    assert any("Brak Heat Strain Index z CORE" in i.value for i in at.info)
