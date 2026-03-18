"""
SRP: Moduł odpowiedzialny za przetwarzanie surowych danych treningowych.
"""
import logging
from typing import Union, Any, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from .common import ensure_pandas, WINDOW_LONG, WINDOW_SHORT

# Gaps longer than this threshold (in seconds) are treated as recording pauses
# and will NOT be interpolated - they are preserved as NaN.
GAP_THRESHOLD_SECONDS = 30


def _detect_time_gaps(
    time_values: pd.Series, threshold: float = GAP_THRESHOLD_SECONDS
) -> List[Tuple[float, float]]:
    """Detect large time gaps in a sorted time series.

    Args:
        time_values: Sorted series of time values in seconds.
        threshold: Minimum gap size (seconds) to flag.

    Returns:
        List of (gap_start, gap_end) tuples marking recording pauses.
    """
    diffs = time_values.diff()
    gap_mask = diffs > threshold
    gap_indices = time_values.index[gap_mask]
    gaps: List[Tuple[float, float]] = []
    for idx in gap_indices:
        prev_idx = time_values.index[time_values.index.get_loc(idx) - 1]
        gap_start = float(time_values.loc[prev_idx])
        gap_end = float(time_values.loc[idx])
        gaps.append((gap_start, gap_end))
        logger.info(
            "Detected recording gap: %.0fs -> %.0fs (%.0fs pause)",
            gap_start, gap_end, gap_end - gap_start,
        )
    return gaps


def _mask_gaps_in_resampled(
    df: pd.DataFrame, gaps: List[Tuple[float, float]]
) -> pd.DataFrame:
    """Set all numeric columns to NaN for rows that fall inside detected gaps.

    Operates on a DataFrame whose 'time' column holds elapsed seconds.
    A small margin (1 s) on each side is kept so edge points remain valid.

    Args:
        df: Resampled DataFrame with a 'time' column.
        gaps: List of (gap_start, gap_end) from _detect_time_gaps.

    Returns:
        New DataFrame with gap regions set to NaN.
    """
    if not gaps:
        return df
    result = df.copy()
    num_cols = result.select_dtypes(include=[np.number]).columns.difference(['time', 'time_min'])
    for gap_start, gap_end in gaps:
        in_gap = (result['time'] > gap_start) & (result['time'] < gap_end)
        result.loc[in_gap, num_cols] = np.nan
    return result


def process_data(df: Union[pd.DataFrame, Any]) -> pd.DataFrame:
    """Process raw data: resample, smooth, and add time columns.

    This function:
    1. Ensures time column exists and is numeric
    2. Detects large recording gaps (pauses)
    3. Resamples to 1 second intervals
    4. Interpolates only small gaps (< GAP_THRESHOLD_SECONDS)
    5. Creates smoothed versions of key metrics

    Args:
        df: Raw DataFrame from CSV/file

    Returns:
        Processed DataFrame ready for analysis
    """
    df_pd = ensure_pandas(df)

    if 'time' not in df_pd.columns:
        df_pd['time'] = np.arange(len(df_pd)).astype(float)
    df_pd['time'] = pd.to_numeric(df_pd['time'], errors='coerce')

    # Remove rows with NaN time before creating index
    df_pd = df_pd.dropna(subset=['time'])

    # Fill missing time values sequentially if there are duplicates or gaps
    if df_pd['time'].isna().any() or len(df_pd) == 0:
        df_pd['time'] = np.arange(len(df_pd)).astype(float)

    df_pd = df_pd.sort_values('time').reset_index(drop=True)

    # Detect large recording gaps BEFORE resampling
    time_gaps = _detect_time_gaps(df_pd['time'])

    df_pd['time_dt'] = pd.to_timedelta(df_pd['time'], unit='s')

    # Ensure index has no NaN
    df_pd = df_pd[df_pd['time_dt'].notna()]
    df_pd = df_pd.set_index('time_dt')

    num_cols = df_pd.select_dtypes(include=['float64', 'int64']).columns.tolist()
    if num_cols:
        df_pd[num_cols] = df_pd[num_cols].interpolate(method='linear', limit=GAP_THRESHOLD_SECONDS).ffill().bfill()

    try:
        df_numeric = df_pd.select_dtypes(include=[np.number])
        df_resampled = df_numeric.resample('1s').mean()
        # Only interpolate small gaps — limit prevents bridging recording pauses
        df_resampled = df_resampled.interpolate(method='linear', limit=GAP_THRESHOLD_SECONDS)
        # Forward/backward fill only small remaining edge NaNs (up to 5s)
        df_resampled = df_resampled.ffill(limit=5).bfill(limit=5)
    except Exception as e:
        logger.warning(f"Resampling failed, using original data: {e}")
        df_resampled = df_pd

    df_resampled['time'] = df_resampled.index.total_seconds()
    df_resampled['time_min'] = df_resampled['time'] / 60.0

    # Restore NaN in detected gap regions so charts show breaks, not fake data
    df_resampled = _mask_gaps_in_resampled(df_resampled, time_gaps)

    # Create smoothed versions of key columns
    smooth_cols = [
        'watts', 'heartrate', 'cadence', 'smo2', 'torque', 'core_temperature',
        'skin_temperature', 'velocity_smooth', 'tymebreathrate', 'tymeventilation', 'thb'
    ]
    
    for col in smooth_cols:
        if col in df_resampled.columns:
            df_resampled[f'{col}_smooth'] = df_resampled[col].rolling(
                window=WINDOW_LONG, min_periods=1
            ).mean()
            df_resampled[f'{col}_smooth_5s'] = df_resampled[col].rolling(
                window=WINDOW_SHORT, min_periods=1
            ).mean()

    df_resampled = df_resampled.reset_index(drop=True)

    return df_resampled
