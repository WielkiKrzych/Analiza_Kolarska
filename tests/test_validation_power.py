"""Files without a power column cannot be analysed and must be rejected."""

import pandas as pd

from services.data_validation import validate_dataframe


def test_csv_without_power_is_rejected():
    df = pd.DataFrame({"time": range(50), "heartrate": [140] * 50})

    is_valid, message = validate_dataframe(df)

    assert not is_valid
    assert "kolumnę mocy" in message


def test_power_column_still_accepted():
    df = pd.DataFrame({"time": range(50), "watts": [200] * 50})

    is_valid, message = validate_dataframe(df)

    assert is_valid
    assert message == ""
