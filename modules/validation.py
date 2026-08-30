"""
Input CSV validation — fail loudly and clearly, never silently.

This is a private clinical/coaching tool: a file that loads but is quietly
wrong is worse than a file that's rejected with a clear reason. This module
inspects an uploaded ride/test CSV and returns a structured report the UI can
render as a diagnostic panel:

- errors  → block analysis (nothing usable can come out)
- warnings → analysis proceeds, but something looks off and results may suffer
- info     → neutral notes (which optional signals are present/missing)

The function is pure (no Streamlit, no I/O) so it is fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from modules.calculations.column_aliases import (
    HR_ALIASES,
    POWER_ALIASES,
)

# Physiologically plausible ranges. Values outside these are flagged (warning),
# not rejected — real data has spikes, but a whole column in the wrong unit is
# what we want to catch (e.g. power recorded in kW, HR in a raw ADC value).
_PLAUSIBLE = {
    "watts": (5, 2000, "W"),  # median <5 W over a file → power likely in kW (unit error)
    "hr": (20, 240, "bpm"),
    "smo2": (0, 100, "%"),
    "cadence": (0, 250, "rpm"),
    "core_temperature": (30, 43, "°C"),
    "skin_temperature": (20, 45, "°C"),
}

# Minimum rows to attempt any analysis at all (≈1 min at 1 Hz).
_MIN_ROWS_HARD = 60
# Below this, ramp-test / threshold analysis is unreliable (≈5 min at 1 Hz).
_MIN_ROWS_SOFT = 300


@dataclass
class ValidationReport:
    """Structured result of validating an input CSV."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    columns: Dict[str, Optional[str]] = field(default_factory=dict)
    n_rows: int = 0

    @property
    def ok(self) -> bool:
        """True when nothing blocks analysis (warnings are allowed)."""
        return not self.errors

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_info(self, msg: str) -> None:
        self.info.append(msg)


def _find_column(cols: set[str], canonical: str, aliases) -> Optional[str]:
    """Return the actual column name matching canonical or any alias, else None."""
    if canonical in cols:
        return canonical
    for alias in aliases:
        if alias in cols:
            return alias
    return None


def validate_input(df: Optional[pd.DataFrame]) -> ValidationReport:  # noqa: C901
    """Validate a raw uploaded ride/test DataFrame.

    Returns a ValidationReport. Callers should block on `not report.ok` and
    surface every message so the user knows exactly what to fix.
    """
    report = ValidationReport()

    # --- Structural checks ---------------------------------------------------
    if df is None or not isinstance(df, pd.DataFrame):
        report.add_error("Nie udało się wczytać pliku (brak danych tabelarycznych).")
        return report

    report.n_rows = len(df)

    if df.empty or len(df.columns) == 0:
        report.add_error("Plik jest pusty — brak wierszy lub kolumn.")
        return report

    # Work on a normalized, lowercase view of the column names.
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    cols = set(lower_map.keys())

    power_col = _find_column(cols, "watts", POWER_ALIASES)
    hr_col = _find_column(cols, "hr", HR_ALIASES)
    smo2_col = _find_column(cols, "smo2", ("smo2_pct", "muscle_o2", "moxy_smo2"))
    time_col = _find_column(cols, "time", ("seconds", "timestamp", "elapsed", "secs"))

    report.columns = {
        "watts": power_col,
        "hr": hr_col,
        "smo2": smo2_col,
        "time": time_col,
    }

    # --- Row-count checks ----------------------------------------------------
    if report.n_rows < _MIN_ROWS_HARD:
        report.add_error(
            f"Za mało danych: {report.n_rows} wierszy (min. {_MIN_ROWS_HARD}). "
            "Plik jest zbyt krótki lub źle sparsowany (sprawdź separator / nagłówek)."
        )
        return report
    if report.n_rows < _MIN_ROWS_SOFT:
        report.add_warning(
            f"Krótka sesja: {report.n_rows} wierszy (<{_MIN_ROWS_SOFT}). "
            "Analiza progów / ramp testu może być niewiarygodna."
        )

    # --- Power is the backbone of this app -----------------------------------
    if not power_col:
        report.add_error(
            "Brak kolumny z mocą. Oczekiwano 'watts' lub 'power'. "
            f"Znalezione kolumny: {', '.join(sorted(cols)) or '(brak)'}."
        )
        return report

    power = pd.to_numeric(df[lower_map[power_col]], errors="coerce")
    if power.notna().sum() == 0:
        report.add_error(
            f"Kolumna mocy ('{power_col}') nie zawiera żadnych liczb — "
            "prawdopodobnie zły format lub separator dziesiętny (przecinek vs kropka)."
        )
        return report

    # --- Optional signals: note presence/absence -----------------------------
    for _canon, actual, label in [
        ("hr", hr_col, "tętno (HR)"),
        ("smo2", smo2_col, "oksygenacja mięśniowa (SmO₂)"),
    ]:
        if actual:
            report.add_info(f"Wykryto {label}: kolumna '{actual}'.")
        else:
            report.add_warning(f"Brak sygnału: {label}. Część analiz zostanie pominięta.")

    # --- Missing-data gaps in present numeric columns ------------------------
    _check_gaps(df, lower_map, power_col, "moc", report)
    if hr_col:
        _check_gaps(df, lower_map, hr_col, "HR", report)
    if smo2_col:
        _check_gaps(df, lower_map, smo2_col, "SmO₂", report)

    # --- Unit / plausibility sanity ------------------------------------------
    for canon, (lo, hi, unit) in _PLAUSIBLE.items():
        actual = lower_map.get(canon) or lower_map.get(
            {"watts": power_col, "hr": hr_col, "smo2": smo2_col}.get(canon, "")
        )
        if not actual:
            continue
        series = pd.to_numeric(df[actual], errors="coerce").dropna()
        if series.empty:
            continue
        med = float(series.median())
        if med < lo or med > hi:
            report.add_warning(
                f"Podejrzane jednostki w '{actual}': mediana {med:.1f} poza "
                f"typowym zakresem {lo}–{hi} {unit}. Sprawdź jednostki."
            )

    # --- Time monotonicity ---------------------------------------------------
    if time_col:
        t = pd.to_numeric(df[lower_map[time_col]], errors="coerce").dropna()
        if len(t) >= 2 and not t.is_monotonic_increasing:
            report.add_warning(
                f"Kolumna czasu ('{time_col}') nie jest rosnąca — możliwe "
                "przestawione wiersze lub restart licznika."
            )

    return report


def _check_gaps(
    df: pd.DataFrame,
    lower_map: Dict[str, str],
    col: str,
    label: str,
    report: ValidationReport,
) -> None:
    """Warn if a present column is mostly empty."""
    series = pd.to_numeric(df[lower_map[col]], errors="coerce")
    n = len(series)
    if n == 0:
        return
    missing_frac = series.isna().sum() / n
    if missing_frac >= 0.30:
        report.add_warning(
            f"Sygnał {label} ma {missing_frac * 100:.0f}% braków — "
            "wyniki oparte na nim mogą być niepełne."
        )
