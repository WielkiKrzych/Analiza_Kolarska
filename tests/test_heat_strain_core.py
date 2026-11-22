"""Heat Strain Index must come from the CORE sensor column, not a local formula."""

import numpy as np
import pandas as pd

from modules.calculations.data_processing import process_data
from modules.calculations.heat_strain import (
    HSI_ZONE_LABELS,
    calculate_heat_strain_summary,
    find_hsi_column,
    validated_hsi_series,
)
from modules.calculations.thermal import calculate_heat_strain_index
from modules.utils import normalize_columns_pandas


def test_zone_time_is_exclusive_and_sums_to_100_percent():
    df = pd.DataFrame(
        {
            "time": np.arange(5, dtype=float),
            "heat_strain_index": [0.0, 0.5, 1.2, 3.5, 7.2],
        }
    )

    summary = calculate_heat_strain_summary(df)

    assert abs(sum(summary["zone_pct"].values()) - 100.0) < 0.1
    assert summary["zone_pct"][HSI_ZONE_LABELS[0]] == 40.0
    assert summary["zone_pct"][HSI_ZONE_LABELS[1]] == 20.0
    assert summary["zone_pct"][HSI_ZONE_LABELS[2]] == 20.0
    assert summary["zone_pct"][HSI_ZONE_LABELS[3]] == 20.0
    assert summary["peak_hsi"] == 7.2
    assert summary["time_above_1_pct"] == 60.0


def test_zone_time_uses_measured_intervals():
    df = pd.DataFrame(
        {
            "time": [0.0, 5.0, 10.0, 15.0],
            "heat_strain_index": [0.0, 8.0, 8.0, 0.0],
        }
    )

    summary = calculate_heat_strain_summary(df)

    assert summary["time_high_seconds"] == 10.0
    assert abs(sum(summary["zone_pct"].values()) - 100.0) < 0.1


def test_out_of_range_values_are_dropped():
    df = pd.DataFrame({"time": [0.0, 1.0, 2.0], "heat_strain_index": [0.0, 70.0, 8.0]})

    summary = calculate_heat_strain_summary(df)

    assert summary["peak_hsi"] == 8.0
    assert summary["mean_hsi"] == 4.0


def test_file_without_hsi_does_not_raise_or_invent_one():
    df = pd.DataFrame(
        {
            "time": np.arange(10, dtype=float),
            "watts": np.full(10, 200.0),
            "core_temperature": np.full(10, 37.5),
            "skin_temperature": np.full(10, 33.0),
        }
    )

    assert calculate_heat_strain_summary(df) is None
    assert validated_hsi_series(df) is None
    out = calculate_heat_strain_index(df)
    assert "hsi" not in out.columns


def test_all_invalid_values_return_none():
    df = pd.DataFrame({"time": [0.0, 1.0, 2.0], "heat_strain_index": [70.0, -3.0, np.nan]})

    assert calculate_heat_strain_summary(df) is None


def test_recorded_column_wins_over_legacy_hsi():
    df = pd.DataFrame(
        {
            "time": np.arange(2, dtype=float),
            "heat_strain_index": [1.0, 2.0],
            "hsi": [9.0, 9.0],
        }
    )

    assert find_hsi_column(df) == "heat_strain_index"
    summary = calculate_heat_strain_summary(df)
    assert summary["peak_hsi"] == 2.0

    out = calculate_heat_strain_index(df)
    assert out["hsi"].tolist() == [1.0, 2.0]


def test_legacy_hsi_alias_is_normalized_to_recorded_column():
    raw = pd.DataFrame({"time": [0], "HeatStrainIndex": [1.5]})

    normalized = normalize_columns_pandas(raw)

    assert "heat_strain_index" in normalized.columns


def test_alias_priority_is_deterministic():
    raw = pd.DataFrame(
        {"time": [0, 1], "HeatStrainIndex": [1.0, 2.0], "hsi": [9.0, 9.0]}
    )

    normalized = normalize_columns_pandas(raw)

    assert normalized["heat_strain_index"].tolist() == [1.0, 2.0]


def test_ambient_temp_is_not_mapped_to_core_temperature():
    raw = pd.DataFrame({"time": [0], "temp": [30.0]})

    normalized = normalize_columns_pandas(raw)

    assert "temp" in normalized.columns
    assert "core_temperature" not in normalized.columns


def test_processing_keeps_zero_and_does_not_interpolate_hsi_gap():
    raw = pd.DataFrame(
        {
            "time": [0.0, 1.0, 2.0, 3.0],
            "watts": [200.0] * 4,
            "heat_strain_index": [0.0, np.nan, 2.0, 0.0],
        }
    )

    processed = process_data(raw)

    assert processed.loc[0, "heat_strain_index"] == 0.0
    assert pd.isna(processed.loc[1, "heat_strain_index"])
    assert processed.loc[2, "heat_strain_index"] == 2.0
