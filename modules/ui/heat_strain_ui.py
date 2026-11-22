"""Heat Strain Index tab — the HSI recorded by the CORE sensor."""

from typing import Any, Dict, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.calculations.heat_strain import (
    HSI_ZONE_BOUNDS,
    HSI_ZONE_COLORS,
    HSI_ZONE_LABELS,
    SPARSE_SAMPLE_INTERVAL_SECONDS,
    calculate_heat_strain_summary,
    find_hsi_column,
    generate_heat_strain_recommendations,
    validated_hsi_series,
)
from modules.plots import CHART_HEIGHT_MAIN
from modules.ui.shared import chart, require_data


def _time_minutes(df: pd.DataFrame) -> pd.Series:
    """Session time in minutes, from 'time_min' or 'time' (seconds)."""
    if "time_min" in df.columns:
        return df["time_min"]
    if "time" in df.columns:
        return pd.to_numeric(df["time"], errors="coerce") / 60.0
    return pd.Series(range(len(df)), index=df.index, dtype=float) / 60.0


def _temperature_column(df: pd.DataFrame, base: str) -> Optional[str]:
    for name in (f"{base}_smooth", base):
        if name in df.columns:
            return name
    return None


def _render_temperature_only(df: pd.DataFrame) -> None:
    """Fallback view: core/skin temperature without a recorded HSI."""
    core_col = _temperature_column(df, "core_temperature")
    skin_col = _temperature_column(df, "skin_temperature")
    if core_col is None and skin_col is None:
        st.caption("Brak temperatury rdzenia i skóry w pliku.")
        return

    fig = go.Figure()
    if core_col:
        fig.add_trace(
            go.Scatter(
                x=_time_minutes(df),
                y=df[core_col],
                mode="lines",
                name="Temperatura rdzenia",
                line=dict(color="#ff7f0e", width=2),
                hovertemplate="%{y:.2f} °C<extra></extra>",
            )
        )
    if skin_col:
        fig.add_trace(
            go.Scatter(
                x=_time_minutes(df),
                y=df[skin_col],
                mode="lines",
                name="Temperatura skóry",
                line=dict(color="#f5b041", width=2, dash="dot"),
                hovertemplate="%{y:.2f} °C<extra></extra>",
            )
        )
    fig.update_layout(
        template="plotly_dark",
        title="Temperatura rdzenia i skóry",
        xaxis_title="Czas [min]",
        yaxis_title="Temperatura [°C]",
        height=CHART_HEIGHT_MAIN,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=50, b=10),
    )
    chart(fig, key="hsi_temperature_only")


def _render_hsi_chart(df: pd.DataFrame, sample_interval_sec: float) -> None:
    """HSI over session time with CORE zones and core/skin temperature."""
    fig = go.Figure()
    # Sparse recordings need visible points, otherwise a few samples vanish.
    hsi_mode = (
        "lines+markers"
        if sample_interval_sec > SPARSE_SAMPLE_INTERVAL_SECONDS
        else "lines"
    )

    edges = (0.0, *HSI_ZONE_BOUNDS, 10.0)
    for low, high, color in zip(edges[:-1], edges[1:], HSI_ZONE_COLORS, strict=True):
        fig.add_hrect(
            y0=low,
            y1=high,
            fillcolor=color,
            opacity=0.07,
            line_width=0,
            layer="below",
        )

    fig.add_trace(
        go.Scatter(
            x=_time_minutes(df),
            y=validated_hsi_series(df),
            mode=hsi_mode,
            name="Heat Strain Index (CORE)",
            line=dict(color="#d62728", width=2),
            hovertemplate="HSI: %{y:.1f}<extra></extra>",
        )
    )

    for base, label, color, dash in (
        ("core_temperature", "Temperatura rdzenia", "#ff7f0e", "solid"),
        ("skin_temperature", "Temperatura skóry", "#f5b041", "dot"),
    ):
        column = _temperature_column(df, base)
        if column:
            fig.add_trace(
                go.Scatter(
                    x=_time_minutes(df),
                    y=df[column],
                    mode="lines",
                    name=label,
                    yaxis="y2",
                    line=dict(color=color, width=1.5, dash=dash),
                    hovertemplate="%{y:.2f} °C<extra></extra>",
                )
            )

    fig.update_layout(
        template="plotly_dark",
        title="Heat Strain Index z CORE na tle temperatur",
        xaxis_title="Czas [min]",
        yaxis=dict(title="HSI (0–10)", range=[0, 10]),
        yaxis2=dict(title="Temperatura [°C]", overlaying="y", side="right", showgrid=False),
        height=CHART_HEIGHT_MAIN,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    chart(fig, key="hsi_timeline")


def _render_zone_table(summary: Dict[str, Any]) -> None:
    rows = []
    for label in HSI_ZONE_LABELS:
        seconds = summary.get("zone_seconds", {}).get(label, 0.0)
        pct = summary.get("zone_pct", {}).get(label, 0.0)
        rows.append(
            {
                "Strefa CORE": label,
                "Czas [min]": round(seconds / 60.0, 1),
                "Udział [%]": pct,
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_heat_strain_tab(
    df: Optional[pd.DataFrame] = None,
    df_resampled: Optional[pd.DataFrame] = None,
    metrics: Optional[Dict[str, Any]] = None,
    rider_weight: float = 75.0,
    cp_input: int = 280,
    w_prime_input: int = 20000,
    hr_max: Optional[int] = None,
    hr_rest: Optional[int] = None,
    rider_age: int = 30,
    is_male: bool = True,
    **kwargs,
) -> None:
    """Render the Heat Strain Index analysis tab."""
    if not require_data(df):
        return

    st.header("🌡️ Heat Strain Index (CORE)")
    st.markdown(
        """
        Heat Strain Index (HSI) to wskaźnik 0–10 liczony przez sensor CORE
        z szacowanej średniej temperatury ciała (rdzeń + skóra).
        Wartość 10 odpowiada rdzeniowi 40 °C i skórze 37 °C.
        """
    )

    hsi_col = find_hsi_column(df)
    if hsi_col is None:
        st.info("Brak Heat Strain Index z CORE w pliku. Nie wyliczam zastępczego wskaźnika.")
        _render_temperature_only(df)
        return

    summary = calculate_heat_strain_summary(df)
    if not summary:
        st.info("Kolumna Heat Strain Index z CORE nie zawiera ważnych pomiarów.")
        _render_temperature_only(df)
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Maks. HSI",
        f"{summary['peak_hsi']:.1f}/10",
        help="Najwyższy zarejestrowany Heat Strain Index z CORE.",
    )
    col2.metric(
        "Średni HSI",
        f"{summary['mean_hsi']:.1f}/10",
        help="Średnia z zarejestrowanych pomiarów HSI.",
    )
    col3.metric(
        "Czas HSI ≥ 1",
        f"{summary['time_above_1_seconds'] / 60.0:.1f} min ({summary['time_above_1_pct']:.1f}%)",
        help="Czas w strefie, w której zaczyna się adaptacja cieplna.",
    )
    col4.metric(
        "Czas HSI ≥ 7",
        f"{summary['time_high_seconds'] / 60.0:.1f} min ({summary['time_high_pct']:.1f}%)",
        help="Czas w strefie wysokiej według skali CORE.",
    )

    st.subheader("📈 HSI w czasie sesji")
    _render_hsi_chart(df, summary["sample_interval_sec"])

    st.subheader("📊 Czas w strefach CORE")
    st.caption("Strefy rozłączne — suma udziałów to 100% czasu ważnych pomiarów.")
    _render_zone_table(summary)

    st.subheader("💡 Interpretacja")
    for recommendation in generate_heat_strain_recommendations(summary):
        st.markdown(f"- {recommendation}")

    with st.expander("📖 Skala CORE", expanded=False):
        st.markdown(
            """
            | HSI | Strefa | Znaczenie |
            | --- | --- | --- |
            | 0–0.9 | Brak/niski | Brak bodźca adaptacji cieplnej |
            | 1–2.9 | Niski-umiarkowany | Początek adaptacji cieplnej |
            | 3–6.9 | Umiarkowany-wysoki | Strefa treningu cieplnego |
            | 7+ | Wysoki | Wysokie obciążenie cieplne |

            HSI liczy sensor CORE; nie da się go odtworzyć wyłącznie z temperatury
            rdzenia i tętna. Wykres korzysta z wartości zarejestrowanej w pliku,
            a kolumna `temp` to temperatura otoczenia, nie rdzenia.
            """
        )
