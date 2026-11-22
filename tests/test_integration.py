"""
Integration tests for Tri_Dashboard.

Tests that verify end-to-end functionality with real-like data.
"""


class TestDataLoadingIntegration:
    """Integration tests for data loading and processing."""

    def test_load_and_process_data(self, sample_power_df):
        """Should process data without errors."""
        from modules.calculations import process_data

        df = process_data(sample_power_df)

        assert len(df) > 0
        assert "watts" in df.columns

    def test_calculate_all_metrics(self, sample_power_df_with_smooth, cp_value):
        """Should calculate all standard metrics."""
        from modules.calculations import (
            calculate_metrics,
            calculate_normalized_power,
            calculate_advanced_kpi,
            calculate_power_duration_curve,
        )

        metrics = calculate_metrics(sample_power_df_with_smooth, cp_value)
        np_val = calculate_normalized_power(sample_power_df_with_smooth)
        decoupling, ef = calculate_advanced_kpi(sample_power_df_with_smooth)
        pdc = calculate_power_duration_curve(sample_power_df_with_smooth)

        assert metrics["avg_watts"] > 0
        assert np_val > 0
        assert isinstance(decoupling, float)
        assert len(pdc) > 0


class TestPDCFullWorkflow:
    """Integration tests for complete PDC workflow."""

    def test_pdc_to_stamina_workflow(self, sample_long_ride_df, rider_params):
        """Test complete workflow from PDC to Stamina Score."""
        from modules.calculations import (
            calculate_power_duration_curve,
            calculate_fatigue_resistance_index,
            calculate_stamina_score,
            estimate_vlamax_from_pdc,
        )

        # Step 1: Calculate PDC
        pdc = calculate_power_duration_curve(sample_long_ride_df)
        assert len(pdc) > 0

        # Step 2: Get MMP values
        mmp_5min = pdc.get(300)
        mmp_20min = pdc.get(1200)

        # Step 3: Calculate FRI (may be None if not enough data)
        if mmp_5min and mmp_20min:
            fri = calculate_fatigue_resistance_index(mmp_5min, mmp_20min)
            assert 0 <= fri <= 2  # Allow some tolerance

            # Step 4: Calculate Stamina Score
            power_per_kg = mmp_5min / rider_params["weight"]
            vo2max = 16.61 + 8.87 * power_per_kg

            stamina = calculate_stamina_score(
                vo2max=vo2max,
                fri=fri,
                w_prime=rider_params["w_prime"],
                cp=rider_params["cp"],
                weight=rider_params["weight"],
            )

            assert 0 <= stamina <= 100

        # Step 5: Estimate VLamax
        vlamax = estimate_vlamax_from_pdc(pdc, rider_params["weight"])
        # May be None if not enough data, that's OK
