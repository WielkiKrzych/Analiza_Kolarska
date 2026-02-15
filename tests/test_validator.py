"""Tests for TestValidator module."""

import pytest
import pandas as pd
import numpy as np
from modules.calculations.test_validator import (
    validate_ramp_test,
    _detect_power_steps,
    _calculate_monotonicity,
    _detect_max_gap,
    _calculate_quality_score,
)
from modules.calculations.threshold_types import TestValidityReport


class TestValidateRampTest:
    
    def test_valid_ramp_test(self):
        df = _create_synthetic_ramp(duration_sec=600, steps=5)
        result = validate_ramp_test(df)
        
        assert result.status == "valid"
        assert result.quality_score >= 80
        assert all(result.criteria.values())
    
    def test_too_short_test(self):
        df = _create_synthetic_ramp(duration_sec=180, steps=2)
        result = validate_ramp_test(df)
        
        assert result.status in ["conditional", "invalid"]
        assert result.criteria["duration"] == False
    
    def test_missing_power_column(self):
        df = pd.DataFrame({
            "time": range(600),
            "cadence": [80] * 600
        })
        result = validate_ramp_test(df)
        
        assert result.criteria["steps_count"] == False
        assert result.criteria["monotonicity"] == False
    
    def test_with_data_gaps(self):
        df = _create_synthetic_ramp_with_gaps(duration_sec=600, gap_size=10)
        result = validate_ramp_test(df)
        
        assert result.has_warnings == True
        assert result.criteria["data_gaps"] == False
    
    def test_conditional_status(self):
        df = _create_synthetic_ramp(duration_sec=400, steps=3)
        df.loc[100:110, "watts"] = np.nan
        
        result = validate_ramp_test(df)
        
        assert result.status in ["valid", "conditional"]
    
    def test_returns_test_validity_report(self):
        df = _create_synthetic_ramp(duration_sec=600, steps=5)
        result = validate_ramp_test(df)
        
        assert isinstance(result, TestValidityReport)
        assert hasattr(result, "status")
        assert hasattr(result, "quality_score")
        assert hasattr(result, "criteria")
    
    def test_quality_label_high(self):
        df = _create_synthetic_ramp(duration_sec=600, steps=6)
        result = validate_ramp_test(df)
        
        if result.quality_score >= 80:
            assert result.quality_label == "Wysoka"
    
    def test_quality_label_medium(self):
        df = _create_synthetic_ramp(duration_sec=350, steps=3)
        df.loc[50:70, "watts"] = df["watts"].iloc[50:70] * 0.5
        result = validate_ramp_test(df)
        
        if 50 <= result.quality_score < 80:
            assert result.quality_label == "Średnia"


class TestDetectPowerSteps:
    
    def test_detects_multiple_steps(self):
        power = _create_power_steps_array(steps=5)
        steps = _detect_power_steps(power)
        
        assert len(steps) >= 3
    
    def test_empty_power_returns_empty(self):
        steps = _detect_power_steps(np.array([]))
        assert steps == []
    
    def test_short_power_returns_empty(self):
        steps = _detect_power_steps(np.ones(20))
        assert steps == []


class TestCalculateMonotonicity:
    
    def test_perfect_monotonic_increase(self):
        power = np.linspace(100, 400, 600)
        mono = _calculate_monotonicity(power)
        
        assert mono >= 0.9
    
    def test_non_monotonic(self):
        power = np.concatenate([
            np.linspace(100, 250, 200),
            np.linspace(250, 100, 150),
            np.linspace(100, 300, 150)
        ])
        mono = _calculate_monotonicity(power)
        
        assert mono < 1.0
    
    def test_constant_power(self):
        power = np.ones(600) * 200
        mono = _calculate_monotonicity(power)
        
        assert mono == 1.0


class TestDetectMaxGap:
    
    def test_no_gap(self):
        time = np.arange(600)
        gap = _detect_max_gap(time)
        
        assert gap == 0
    
    def test_with_gap(self):
        time = np.concatenate([np.arange(100), np.arange(110, 600)])
        gap = _detect_max_gap(time)
        
        assert gap >= 9


class TestCalculateQualityScore:
    
    def test_all_passed(self):
        criteria = {"duration": True, "steps_count": True, "monotonicity": True}
        details = {}
        score = _calculate_quality_score(criteria, details)
        
        assert score == 100.0
    
    def test_some_failed(self):
        criteria = {"duration": True, "steps_count": False, "monotonicity": True}
        details = {}
        score = _calculate_quality_score(criteria, details)
        
        assert score < 100.0


class TestValidityReportProperties:
    """Tests for TestValidityReport dataclass properties."""
    
    def test_is_valid_property(self):
        report = TestValidityReport(status="valid", quality_score=90)
        assert report.is_valid == True
        
        report = TestValidityReport(status="invalid", quality_score=30)
        assert report.is_valid == False
    
    def test_has_warnings_property(self):
        report = TestValidityReport(status="valid", warnings=["Test warning"])
        assert report.has_warnings == True
        
        report = TestValidityReport(status="valid")
        assert report.has_warnings == False
    
    def test_quality_label_property(self):
        report = TestValidityReport(status="valid", quality_score=85)
        assert report.quality_label == "Wysoka"
        
        report = TestValidityReport(status="conditional", quality_score=65)
        assert report.quality_label == "Średnia"
        
        report = TestValidityReport(status="invalid", quality_score=30)
        assert report.quality_label == "Niska"


def _create_synthetic_ramp(duration_sec: int, steps: int) -> pd.DataFrame:
    step_duration = duration_sec // steps
    power_values = []
    
    for i in range(steps):
        base_power = 100 + i * 50
        step_power = np.random.normal(base_power, 5, step_duration)
        power_values.extend(step_power)
    
    while len(power_values) < duration_sec:
        power_values.append(power_values[-1])
    
    return pd.DataFrame({
        "time": range(duration_sec),
        "watts": power_values,
        "cadence": [85] * duration_sec
    })


def _create_synthetic_ramp_with_gaps(duration_sec: int, gap_size: int = 10) -> pd.DataFrame:
    df = _create_synthetic_ramp(duration_sec + gap_size, steps=5)
    df = df.drop(range(100, 100 + gap_size))
    df = df.reset_index(drop=True)
    return df


def _create_power_steps_array(steps: int) -> np.ndarray:
    step_duration = 60
    power = np.array([])
    
    for i in range(steps):
        base = 100 + i * 40
        step_power = np.random.normal(base, 3, step_duration)
        power = np.concatenate([power, step_power])
    
    return power
