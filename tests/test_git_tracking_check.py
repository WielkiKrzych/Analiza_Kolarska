"""check_git_tracking runs git once per directory, but still warns on every rerun."""

import streamlit as st

from modules.reporting import persistence


class _Completed:
    returncode = 0
    stdout = "reports/ramp_tests/athlete.json\n"


def test_git_runs_once_and_warning_repeats(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    calls, errors = [], []
    monkeypatch.setattr(persistence.subprocess, "run", lambda *a, **k: calls.append(a) or _Completed())
    monkeypatch.setattr(st, "error", errors.append)
    st.cache_data.clear()

    for _ in range(3):
        persistence.check_git_tracking("reports/ramp_tests")

    assert len(calls) == 1
    assert len(errors) == 3
    st.cache_data.clear()
