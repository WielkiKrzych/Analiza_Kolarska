"""Auto-saved sessions are dated by the ride, not by the upload day."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from services.session_orchestrator import prepare_session_record


@pytest.fixture
def ride():
    return pd.DataFrame({"watts": np.full(1300, 250.0), "heartrate": np.full(1300, 150.0)})


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("RampTest 27.02.2026.csv", "2026-02-27"),
        ("2025-11-03_endurance.csv", "2025-11-03"),
        ("session_20240615_071500.csv", "2024-06-15"),
    ],
)
def test_date_comes_from_filename(ride, filename, expected):
    record = prepare_session_record(filename, ride, {}, 250.0, 0.9, 60.0)

    assert record["date"] == expected


def test_falls_back_to_today_without_date_in_filename(ride):
    record = prepare_session_record("trening.csv", ride, {}, 250.0, 0.9, 60.0)

    assert record["date"] == date.today().isoformat()
