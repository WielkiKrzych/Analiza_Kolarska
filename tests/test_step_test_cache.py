"""analyze_step_test must not mutate its input and must be memoized for the UI."""

import modules.ui.shared as shared
from modules.calculations.thresholds import analyze_step_test

STEP_TEST_KWARGS = dict(
    power_column="watts",
    ve_column="tymeventilation",
    smo2_column="smo2",
    hr_column="heartrate",
    time_column="time",
)


def test_analyze_step_test_does_not_mutate_caller_columns(synthetic_ramp_df):
    df = synthetic_ramp_df.rename(columns={"watts": "Watts "})

    analyze_step_test(df, **STEP_TEST_KWARGS)

    assert "Watts " in df.columns


def test_cached_step_test_matches_direct_call_and_computes_once(synthetic_ramp_df, monkeypatch):
    calls = []

    def counting(df, **kwargs):
        calls.append(1)
        return analyze_step_test(df, **kwargs)

    monkeypatch.setattr(shared, "analyze_step_test", counting)
    shared.cached_analyze_step_test.clear()

    first = shared.cached_analyze_step_test(synthetic_ramp_df, **STEP_TEST_KWARGS)
    second = shared.cached_analyze_step_test(synthetic_ramp_df.copy(), **STEP_TEST_KWARGS)
    direct = analyze_step_test(synthetic_ramp_df.copy(), **STEP_TEST_KWARGS)

    assert len(calls) == 1
    for result in (first, second):
        assert result.vt1_watts == direct.vt1_watts
        assert result.vt2_watts == direct.vt2_watts
        assert result.smo2_1_watts == direct.smo2_1_watts
        assert result.analysis_notes == direct.analysis_notes
