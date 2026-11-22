"""Sidebar values must survive the Streamlit rerun triggered by Enter."""

from types import SimpleNamespace

import modules.frontend.state as state_module


def _fake_streamlit() -> SimpleNamespace:
    return SimpleNamespace(session_state={})


def test_sidebar_value_survives_second_init(monkeypatch):
    fake_st = _fake_streamlit()
    monkeypatch.setattr(state_module, "st", fake_st)
    manager = state_module.StateManager()

    manager.init_session_state()
    assert fake_st.session_state["weight"] == 97.0  # default on a fresh session

    fake_st.session_state["weight"] = 80.0
    manager.init_session_state()

    assert fake_st.session_state["weight"] == 80.0


def test_missing_keys_are_seeded(monkeypatch):
    fake_st = _fake_streamlit()
    monkeypatch.setattr(state_module, "st", fake_st)
    manager = state_module.StateManager()

    manager.init_session_state()

    assert fake_st.session_state["cp_in"] == 380
    assert fake_st.session_state["report_generation_requested"] is False
