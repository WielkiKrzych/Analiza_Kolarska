"""Regression tests for CSV reading and column alias normalization (modules.utils)."""

import io

import pandas as pd
import pytest

from modules.utils import _read_raw_file, normalize_columns_pandas


@pytest.mark.unit
def test_fit_export_suffixed_columns_map_to_canonical() -> None:
    """FIT/intervals-style exports use unit suffixes: power_w, cadence_rpm, ...

    Regression: 'power_w' was not an alias, so df['watts'] raised KeyError
    downstream (app.py "Praca [kJ]" metric).
    """
    df = pd.DataFrame(
        {
            "timestamp": ["2026-09-08T14:54:41Z"],
            "distance_m": [0.0],
            "heart_rate_bpm": [93],
            "cadence_rpm": [38],
            "power_w": [86],
        }
    )

    out = normalize_columns_pandas(df)

    assert "watts" in out.columns
    assert "cadence" in out.columns
    assert "heartrate" in out.columns
    assert "distance" in out.columns
    assert out["watts"].iloc[0] == 86


@pytest.mark.unit
def test_existing_canonical_column_wins_over_alias() -> None:
    """A file with both 'watts' and 'power_w' keeps 'watts' untouched."""
    df = pd.DataFrame({"watts": [200], "power_w": [999]})

    out = normalize_columns_pandas(df)

    assert out["watts"].iloc[0] == 200
    assert "power_w" in out.columns


@pytest.mark.unit
@pytest.mark.parametrize("sep", [",", ";", "\t"])
def test_reader_detects_separator(sep: str) -> None:
    """Regression: a ';' file parsed with the comma default does not raise —
    it yields one glued column, so the separator must be sniffed up front.
    """
    header = sep.join(["timestamp", "heart_rate_bpm", "power_w"])
    row = sep.join(["2026-08-05T15:13:44Z", "105", "206"])
    buf = io.BytesIO(f"{header}\n{row}\n".encode())

    df = _read_raw_file(buf)

    assert list(df.columns) == ["timestamp", "heart_rate_bpm", "power_w"]
    assert df["power_w"].iloc[0] == 206
