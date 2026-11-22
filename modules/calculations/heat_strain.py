"""Heat Strain Index analysis based on the CORE sensor's recorded index.

The CORE sensor reports HSI on a 0-10 scale, computed from estimated mean body
temperature (core + skin); 10 corresponds to 40 °C core and 37 °C skin. This
module only reads that recorded series — it never re-derives HSI from core
temperature and heart rate, because such a substitute is not the CORE index.
"""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .common import ensure_pandas

CORE_HSI_COLUMN = "heat_strain_index"
CORE_HSI_ALIASES = (
    "heat_strain_index",
    "HeatStrainIndex",
    "heat strain index",
    "hsi",
)

# CORE producer zones: below 1 no/limited strain, 1-2.9 adaptation begins,
# 3-6.9 heat-training zone, 7+ high strain.
HSI_ZONE_BOUNDS = (1.0, 3.0, 7.0)
HSI_ZONE_LABELS = (
    "Brak/niski (0–0.9)",
    "Niski-umiarkowany (1–2.9)",
    "Umiarkowany-wysoki (3–6.9)",
    "Wysoki (7+)",
)
HSI_ZONE_COLORS = ("#2ECC71", "#F1C40F", "#E67E22", "#E74C3C")

# A pause in recording is not time spent in a zone.
MAX_SAMPLE_GAP_SECONDS = 30.0
SPARSE_SAMPLE_INTERVAL_SECONDS = 2.0


def find_hsi_column(df: pd.DataFrame) -> Optional[str]:
    """Return the Heat Strain Index column name, preferring the recorded one."""
    if df is None:
        return None
    for name in CORE_HSI_ALIASES:
        if name in df.columns:
            return name
    lower = {str(c).lower().strip(): c for c in df.columns}
    for name in CORE_HSI_ALIASES:
        match = lower.get(name.lower())
        if match is not None:
            return match
    return None


def validated_hsi_series(df: pd.DataFrame) -> Optional[pd.Series]:
    """Recorded CORE HSI with everything outside 0-10 and NaN dropped.

    Invalid samples do not become zeros and are not clipped: they are unknown,
    so they must not contribute to peak, mean or zone time.
    """
    df = ensure_pandas(df)
    if df is None:
        return None

    hsi_col = find_hsi_column(df)
    if hsi_col is None:
        return None

    values = pd.to_numeric(df[hsi_col], errors="coerce")
    values = values.where(values.between(0.0, 10.0))
    return values if values.notna().any() else None


def assign_hsi_zones(hsi: pd.Series) -> pd.Series:
    """Assign each valid sample to exactly one CORE zone (bounds: 1, 3, 7)."""
    values = pd.to_numeric(hsi, errors="coerce")
    values = values.where(values.between(0.0, 10.0))
    return pd.cut(
        values,
        bins=[-np.inf, *HSI_ZONE_BOUNDS, np.inf],
        right=False,
        labels=list(HSI_ZONE_LABELS),
    )


def _sample_weights(
    df: pd.DataFrame, valid_positions: np.ndarray
) -> tuple[np.ndarray, float]:
    """Time until the next valid sample; recording pauses do not count.

    Returns per-sample weights and the median sampling interval.
    """
    if "time" not in df.columns:
        return np.ones(len(valid_positions), dtype=float), 1.0

    times = pd.to_numeric(df["time"], errors="coerce").to_numpy(dtype=float)
    deltas = np.diff(times[valid_positions])
    deltas = np.where(np.isfinite(deltas), deltas, 0.0)
    # A gap longer than the limit is a recording pause: it counts as zero time.
    deltas = np.where((deltas > 0) & (deltas <= MAX_SAMPLE_GAP_SECONDS), deltas, 0.0)

    positive = deltas[deltas > 0]
    interval = float(np.median(positive)) if positive.size else 1.0
    # The last valid sample has no successor; assume one typical interval.
    return np.append(deltas, interval), interval


def calculate_heat_strain_summary(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Summarize the recorded CORE HSI: peak, mean and exclusive zone times.

    Weights come from real timestamps, so zone percentages add up to 100 % of
    the measured time even when sampling is not 1 Hz. Returns None when the
    file has no HSI column or no valid (0-10) samples.
    """
    if df is None or df.empty:
        return None

    validated = validated_hsi_series(df)
    if validated is None:
        return None

    valid_mask = validated.notna()
    hsi = validated[valid_mask]
    positions = np.flatnonzero(valid_mask.to_numpy())
    weights, interval = _sample_weights(df, positions)

    zones = assign_hsi_zones(hsi).astype(object).to_numpy()
    zone_seconds = {
        label: float(weights[zones == label].sum()) for label in HSI_ZONE_LABELS
    }
    total_seconds = float(weights.sum())
    if total_seconds <= 0:
        return None

    values = hsi.to_numpy()
    time_above_1 = float(weights[values >= 1.0].sum())
    time_high = float(weights[values >= HSI_ZONE_BOUNDS[-1]].sum())

    return {
        "peak_hsi": round(float(hsi.max()), 1),
        "mean_hsi": round(float(hsi.mean()), 1),
        "total_seconds": total_seconds,
        "sample_interval_sec": interval,
        "zone_seconds": zone_seconds,
        "zone_pct": {
            label: round(seconds / total_seconds * 100.0, 1)
            for label, seconds in zone_seconds.items()
        },
        "time_above_1_seconds": time_above_1,
        "time_above_1_pct": round(time_above_1 / total_seconds * 100.0, 1),
        "time_high_seconds": time_high,
        "time_high_pct": round(time_high / total_seconds * 100.0, 1),
    }


def generate_heat_strain_recommendations(summary: Dict[str, Any]) -> List[str]:
    """State what the recorded HSI means; makes no safety guarantees."""
    if not summary:
        return [
            "Brak Heat Strain Index z CORE w pliku — nie można ocenić obciążenia cieplnego."
        ]

    recommendations: List[str] = []
    above_one_pct = summary.get("time_above_1_pct", 0.0)
    above_one_min = summary.get("time_above_1_seconds", 0.0) / 60.0

    if above_one_pct <= 0:
        recommendations.append(
            "HSI nie osiągnął 1 — sesja nie dostarczyła bodźca adaptacji cieplnej."
        )
    else:
        recommendations.append(
            f"HSI ≥ 1 przez {above_one_pct:.1f}% sesji ({above_one_min:.0f} min) "
            "— bodziec adaptacji cieplnej."
        )

    if summary.get("time_high_pct", 0.0) > 0:
        recommendations.append(
            f"{summary['time_high_pct']:.1f}% czasu w strefie wysokiej (HSI ≥ 7). "
            "Sprawdź nawodnienie i harmonogram chłodzenia."
        )
    if summary.get("peak_hsi", 0.0) >= 7:
        recommendations.append(
            "Szczyt HSI ≥ 7 — według skali CORE organizm pracował w strefie wysokiej."
        )
    return recommendations


def get_heat_strain_color_mapping() -> Dict[str, str]:
    """Map CORE zone labels to chart colors."""
    return dict(zip(HSI_ZONE_LABELS, HSI_ZONE_COLORS, strict=True))
