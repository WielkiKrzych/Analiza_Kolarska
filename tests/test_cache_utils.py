"""Disk cache keys must depend on argument content, not just shape."""

import numpy as np
import pandas as pd
import pytest

import modules.cache_utils as cache_utils

diskcache = pytest.importorskip("diskcache")


def _two_rides_same_shape():
    a = pd.DataFrame({"time": np.arange(600.0), "watts": np.full(600, 200.0)})
    b = a.assign(watts=np.full(600, 310.0))
    return a, b


def test_same_shape_dataframes_with_different_data_get_different_keys():
    a, b = _two_rides_same_shape()

    assert cache_utils._generate_cache_key("f", (a,), {}) != cache_utils._generate_cache_key("f", (b,), {})


def test_dicts_with_same_length_but_different_values_get_different_keys():
    key_a = cache_utils._generate_cache_key("f", ({"np": 250.0, "tss": 80.0},), {})
    key_b = cache_utils._generate_cache_key("f", ({"np": 300.0, "tss": 95.0},), {})

    assert key_a != key_b


def test_equal_content_gets_equal_keys():
    a, _ = _two_rides_same_shape()
    args = (a, {"np": 250.0, "zones": [1, 2]}, np.arange(5), 280, "ride.csv")
    copy_args = (a.copy(), {"zones": [1, 2], "np": 250.0}, np.arange(5), 280, "ride.csv")

    assert cache_utils._generate_cache_key("f", args, {}) == cache_utils._generate_cache_key(
        "f", copy_args, {}
    )


def test_cached_function_does_not_return_other_sessions_result(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_utils, "_cache", diskcache.Cache(str(tmp_path)))

    @cache_utils.cache_result(ttl=60)
    def mean_power(df, metrics):
        return float(df["watts"].mean())

    a, b = _two_rides_same_shape()

    assert mean_power(a, {"tss": 1.0}) == 200.0
    assert mean_power(b, {"tss": 2.0}) == 310.0
