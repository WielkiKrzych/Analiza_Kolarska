"""calculate_w_prime_balance returns the input frame plus a balance column, untouched otherwise."""

import numpy as np
import pandas as pd

from modules.calculations.w_prime import calculate_w_prime_balance, calculate_w_prime_fast


def _ride():
    n = 600
    return pd.DataFrame(
        {
            "time": np.arange(n, dtype=float),
            "watts": np.where(np.arange(n) % 120 < 40, 380.0, 180.0),
            "heartrate": np.arange(n) % 60 + 120,
            "lap": pd.Categorical(np.arange(n) // 200),
            "note": ["x"] * n,
        },
        index=np.arange(1000, 1000 + n),
    )


def test_keeps_other_columns_and_resets_index():
    df = _ride()

    result = calculate_w_prime_balance(df, cp=250.0, w_prime=20000.0)

    pd.testing.assert_frame_equal(
        result.drop(columns="w_prime_balance"), df.reset_index(drop=True)
    )
    expected = calculate_w_prime_fast(df["watts"].to_numpy(), df["time"].to_numpy(), 250.0, 20000.0)
    np.testing.assert_array_equal(result["w_prime_balance"].to_numpy(), expected)


def test_does_not_mutate_input():
    df = _ride()
    before = df.copy()

    calculate_w_prime_balance(df.drop(columns="time"), cp=250.0, w_prime=20000.0)
    calculate_w_prime_balance(df, cp=250.0, w_prime=20000.0)

    pd.testing.assert_frame_equal(df, before)


def test_unconvertible_power_falls_back_to_zero_balance():
    df = _ride().assign(watts="n/a")

    result = calculate_w_prime_balance(df, cp=250.0, w_prime=20000.0)

    assert (result["w_prime_balance"] == 0.0).all()
