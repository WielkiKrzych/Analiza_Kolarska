"""Training-ride PDF report generator.

Produces a multi-page PDF for a NORMAL training ride (not a ramp test),
styled like the ramp-test report but focused on the metrics that matter for
endurance/interval sessions: load (NP/IF/TSS), power-duration curve, time in
zones, aerobic decoupling & durability, muscle O2 / ventilation, thermal
strain and a short auto-summary.

Entry point: ``generate_training_report_pdf(...) -> bytes``.

Every section guards against missing signals so the report never crashes on a
file that lacks SmO2, core temperature, etc.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

# Emoji / pictographs the PDF font (DejaVuSans) can't render — strip them so
# interpretation strings don't show up as tofu boxes.
_EMOJI_RE = re.compile("[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f900-\U0001f9ff️]")


def _clean(text) -> str:
    return _EMOJI_RE.sub("", str(text)).strip()


import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (
    Image as RLImage,
)
from reportlab.platypus import (  # noqa: E402
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .pdf.styles import FONT_FAMILY, FONT_FAMILY_BOLD

logger = logging.getLogger(__name__)

PRIMARY = "#1F77B4"
GREEN = "#2ECC71"
RED = "#E74C3C"
ORANGE = "#F39C12"
GREY = "#7F8C8D"


# ─────────────────────────── helpers ───────────────────────────
def _num(x, default=0.0) -> float:
    try:
        v = float(x)
        return default if (v != v) else v  # NaN guard
    except (TypeError, ValueError):
        return default


def _col(df: pd.DataFrame, *names: str) -> Optional[str]:
    lc = {str(c).lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lc:
            return lc[n.lower()]
    return None


def _fig_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _fmt(v, unit="", nd=0):
    if v is None:
        return "—"
    try:
        f = float(v)
        if f != f:
            return "—"
        return f"{f:.{nd}f}{unit}"
    except (TypeError, ValueError):
        return str(v)


# ─────────────────────────── charts ───────────────────────────
def _chart_power_hr(df: pd.DataFrame, cp: float) -> Optional[bytes]:
    wcol = _col(df, "watts")
    if not wcol:
        return None
    t = (df[_col(df, "time")] / 60.0) if _col(df, "time") else np.arange(len(df)) / 60.0
    watts = pd.to_numeric(df[wcol], errors="coerce")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.fill_between(t, watts, color=PRIMARY, alpha=0.15)
    ax.plot(t, watts.rolling(30, min_periods=1).mean(), color=PRIMARY, lw=1.4, label="Moc (30s)")
    if cp > 0:
        ax.axhline(cp, color=RED, ls="--", lw=1, label=f"CP {cp:.0f} W")
    ax.set_xlabel("Czas [min]")
    ax.set_ylabel("Moc [W]", color=PRIMARY)
    ax.tick_params(axis="y", labelcolor=PRIMARY)
    hrcol = _col(df, "heartrate", "hr")
    if hrcol:
        ax2 = ax.twinx()
        ax2.plot(
            t,
            pd.to_numeric(df[hrcol], errors="coerce").rolling(30, min_periods=1).mean(),
            color=RED,
            lw=1.0,
            alpha=0.8,
            label="HR",
        )
        ax2.set_ylabel("HR [bpm]", color=RED)
        ax2.tick_params(axis="y", labelcolor=RED)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    return _fig_bytes(fig)


def _chart_zones(zone_names, zone_secs, palette) -> Optional[bytes]:
    if not zone_secs or sum(zone_secs) <= 0:
        return None
    mins = [s / 60.0 for s in zone_secs]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar(zone_names, mins, color=palette)
    total = sum(mins)
    for i, m in enumerate(mins):
        pct = (m / total * 100) if total else 0
        ax.text(i, m, f"{m:.0f}m\n{pct:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("Czas [min]")
    ax.margins(y=0.18)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return _fig_bytes(fig)


def _chart_pdc(pdc: Dict[int, float]) -> Optional[bytes]:
    pts = sorted((d, v) for d, v in pdc.items() if v)
    if len(pts) < 3:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(xs, ys, "-o", color=PRIMARY, ms=4, lw=1.6)
    ax.set_xscale("log")
    ax.set_xlabel("Czas [s] (skala log)")
    ax.set_ylabel("Najlepsza moc [W]")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    return _fig_bytes(fig)


def _chart_two_signals(df, sig_col, sig_label, sig_color, unit) -> Optional[bytes]:
    col = _col(df, sig_col)
    wcol = _col(df, "watts")
    if not col:
        return None
    t = (df[_col(df, "time")] / 60.0) if _col(df, "time") else np.arange(len(df)) / 60.0
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(
        t,
        pd.to_numeric(df[col], errors="coerce").rolling(15, min_periods=1).mean(),
        color=sig_color,
        lw=1.2,
        label=sig_label,
    )
    ax.set_xlabel("Czas [min]")
    ax.set_ylabel(f"{sig_label} [{unit}]", color=sig_color)
    ax.tick_params(axis="y", labelcolor=sig_color)
    if wcol:
        ax2 = ax.twinx()
        ax2.fill_between(t, pd.to_numeric(df[wcol], errors="coerce"), color=PRIMARY, alpha=0.10)
        ax2.set_ylabel("Moc [W]", color=PRIMARY)
        ax2.tick_params(axis="y", labelcolor=PRIMARY)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    return _fig_bytes(fig)


# ─────────────────────────── analytics ───────────────────────────
def _decoupling(df: pd.DataFrame) -> Optional[float]:
    wcol, hcol = _col(df, "watts"), _col(df, "heartrate", "hr")
    if not wcol or not hcol or len(df) < 600:
        return None
    w = pd.to_numeric(df[wcol], errors="coerce")
    h = pd.to_numeric(df[hcol], errors="coerce")
    mid = len(df) // 2
    m1 = (h.iloc[:mid] > 40) & (w.iloc[:mid] > 0)
    m2 = (h.iloc[mid:] > 40) & (w.iloc[mid:] > 0)
    if m1.sum() < 60 or m2.sum() < 60:
        return None
    r1 = w.iloc[:mid][m1].mean() / h.iloc[:mid][m1].mean()
    r2 = w.iloc[mid:][m2].mean() / h.iloc[mid:][m2].mean()
    if not r1 or r1 <= 0:
        return None
    return float((r1 - r2) / r1 * 100.0)


# ─────────────────────────── main ───────────────────────────
def generate_training_report_pdf(
    df_plot: pd.DataFrame,
    metrics: Dict[str, Any],
    cp_input: float,
    w_prime_input: float,
    rider_weight: float,
    vt1_watts: float = 0,
    vt2_watts: float = 0,
    filename: str = "trening",
    ride_date: Optional[str] = None,
    use_ai: bool = False,
) -> bytes:
    """Build the training-ride PDF and return it as bytes.

    use_ai: if True and DEEPSEEK_API_KEY is set, the closing comment is written by
    DeepSeek; otherwise the deterministic rule-based assessment is used.
    """
    df = df_plot
    metrics = metrics or {}
    cp = _num(cp_input)
    weight = _num(rider_weight, 1.0) or 1.0

    # ── derived values ──
    n = len(df)
    tcol = _col(df, "time")
    dur_sec = int(_num(df[tcol].iloc[-1]) - _num(df[tcol].iloc[0])) if tcol and n else n
    if dur_sec <= 0:
        dur_sec = n
    dur_min = dur_sec / 60.0
    dcol = _col(df, "distance")
    dist_km = (_num(df[dcol].max()) / 1000.0) if dcol else None

    wcol = _col(df, "watts")
    hcol = _col(df, "heartrate", "hr")
    watts = pd.to_numeric(df[wcol], errors="coerce") if wcol else pd.Series(dtype=float)

    np_w = _num(metrics.get("np"))
    avg_w = _num(metrics.get("avg_watts"))
    max_w = _num(watts.max()) if wcol else 0.0
    if_factor = (np_w / cp) if cp > 0 else 0.0
    tss = (dur_sec * np_w * if_factor) / (cp * 3600.0) * 100.0 if cp > 0 else 0.0
    work_kj = _num(metrics.get("work_kj"))
    work_cp = _num(metrics.get("work_above_cp_kj"))
    avg_hr = _num(metrics.get("avg_hr"))
    max_hr = _num(pd.to_numeric(df[hcol], errors="coerce").max()) if hcol else 0.0
    avg_cad = _num(metrics.get("avg_cadence"))
    wkg = (np_w / weight) if weight else 0.0
    ef = _num(metrics.get("ef_factor"))
    decoup = _decoupling(df)

    register_date = ride_date or datetime.now().strftime("%Y-%m-%d")

    # ── document ──
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="Raport treningowy",
        author="Tri_Dashboard",
    )
    base = getSampleStyleSheet()
    st_title = ParagraphStyle(
        "t",
        parent=base["Heading1"],
        fontName=FONT_FAMILY_BOLD,
        fontSize=22,
        textColor=colors.HexColor(PRIMARY),
        alignment=1,
        spaceAfter=6,
    )
    st_sub = ParagraphStyle(
        "su",
        parent=base["Normal"],
        fontName=FONT_FAMILY,
        fontSize=11,
        textColor=colors.HexColor(GREY),
        alignment=1,
        spaceAfter=2,
    )
    st_h = ParagraphStyle(
        "h",
        parent=base["Heading2"],
        fontName=FONT_FAMILY_BOLD,
        fontSize=15,
        textColor=colors.HexColor("#2C3E50"),
        spaceBefore=6,
        spaceAfter=8,
    )
    st_p = ParagraphStyle(
        "p",
        parent=base["Normal"],
        fontName=FONT_FAMILY,
        fontSize=10,
        textColor=colors.HexColor("#2C3E50"),
        spaceAfter=6,
        leading=14,
    )
    st_note = ParagraphStyle(
        "n",
        parent=base["Normal"],
        fontName=FONT_FAMILY,
        fontSize=8,
        textColor=colors.HexColor(GREY),
        spaceAfter=4,
    )

    st_klabel = ParagraphStyle(
        "kl",
        parent=base["Normal"],
        fontName=FONT_FAMILY_BOLD,
        fontSize=9.5,
        textColor=colors.HexColor(GREY),
        leading=12,
    )
    st_kval = ParagraphStyle(
        "kv",
        parent=base["Normal"],
        fontName=FONT_FAMILY,
        fontSize=10,
        textColor=colors.HexColor("#2C3E50"),
        leading=12,
    )

    story = []

    def kpi_table(rows):
        # Wrap every cell in a Paragraph so long labels/values wrap within the
        # column instead of overflowing into the neighbouring cell.
        data = []
        for r in range(0, len(rows), 2):
            pair = rows[r : r + 2]
            line = []
            for label, val in pair:
                line += [Paragraph(str(label), st_klabel), Paragraph(str(val), st_kval)]
            while len(line) < 4:
                line.append(Paragraph("", st_kval))
            data.append(line)
        tbl = Table(data, colWidths=[4.4 * cm, 2.8 * cm, 4.4 * cm, 2.8 * cm])
        tbl.setStyle(
            TableStyle(
                [
                    (
                        "ROWBACKGROUNDS",
                        (0, 0),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F4F7FA")],
                    ),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#ECF0F1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return tbl

    def img(b, w=16.5, h=6.0):
        return RLImage(io.BytesIO(b), width=w * cm, height=h * cm)

    st_cmh = ParagraphStyle(
        "cmh",
        parent=st_h,
        fontSize=12,
        spaceBefore=0,
        spaceAfter=2,
        textColor=colors.HexColor(PRIMARY),
    )
    st_verdict = ParagraphStyle(
        "cv",
        parent=st_p,
        fontName=FONT_FAMILY_BOLD,
        fontSize=10.5,
        textColor=colors.HexColor("#2C3E50"),
        spaceAfter=5,
    )

    def comment_box(verdict, paragraphs, source=""):
        """A visually distinct closing comment box that CAN split across pages.

        Built as a multi-row, single-column table: one row per whole paragraph.
        ReportLab breaks the box between rows across pages, so a long comment
        never gets clipped — while each paragraph stays intact and clean.
        """
        title = "Komentarz" + (f"  ({source})" if source else "")
        rows = [[Paragraph(title, st_cmh)]]
        if verdict:
            rows.append([Paragraph(verdict, st_verdict)])
        clean = [str(p).strip() for p in paragraphs if str(p).strip()] or ["—"]
        for para in clean:
            rows.append([Paragraph(para, st_p)])

        t = Table(rows, colWidths=[16.8 * cm], splitByRow=True, repeatRows=0)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7FA")),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(PRIMARY)),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 11),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, 0), 9),
                    ("TOPPADDING", (0, 1), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -2), 4),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
                ]
            )
        )
        return t

    def section(flowables):
        """Keep a whole section on one page; pack sections densely."""
        story.append(KeepTogether([f for f in flowables if f is not None]))
        story.append(Spacer(1, 0.45 * cm))

    def pdc_table(pdc):
        key_durs = [5, 15, 30, 60, 300, 600, 1200, 3600]
        labels = {
            5: "5 s",
            15: "15 s",
            30: "30 s",
            60: "1 min",
            300: "5 min",
            600: "10 min",
            1200: "20 min",
            3600: "60 min",
        }
        rows = [["Czas", "Moc [W]", "W/kg"]]
        for d in key_durs:
            v = pdc.get(d)
            if v:
                rows.append([labels[d], f"{v:.0f}", f"{v / weight:.1f}"])
        if len(rows) <= 1:
            return None
        t = Table(rows, colWidths=[4 * cm, 4 * cm, 4 * cm])
        t.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), FONT_FAMILY_BOLD),
                    ("FONTNAME", (0, 1), (-1, -1), FONT_FAMILY),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F4F7FA")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DEE2E6")),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return t

    # ── header + KPI + first chart (page 1) ──
    hh, mm = divmod(int(dur_min), 60)
    kpis = [
        ("Czas trwania", f"{hh}h {mm:02d}min" if hh else f"{mm} min"),
        ("Dystans", _fmt(dist_km, " km", 1) if dist_km else "—"),
        ("Śr. moc", _fmt(avg_w, " W")),
        ("Moc znorm. (NP)", _fmt(np_w, " W")),
        ("Intensywność (IF)", _fmt(if_factor, "", 2)),
        ("Obciążenie (TSS)", _fmt(tss, "")),
        ("Praca", _fmt(work_kj, " kJ")),
        ("Praca > CP", _fmt(work_cp, " kJ")),
        ("Max moc", _fmt(max_w, " W")),
        ("NP / kg", _fmt(wkg, " W/kg", 2)),
        ("Śr. / Max HR", f"{_fmt(avg_hr)} / {_fmt(max_hr)} bpm"),
        ("Śr. kadencja", _fmt(avg_cad, " rpm")),
    ]
    ref = Paragraph(
        f"Parametry referencyjne: CP {cp:.0f} W · W' {w_prime_input / 1000:.1f} kJ · "
        f"waga {weight:.0f} kg"
        + (f" · VT1 {vt1_watts:.0f} W · VT2 {vt2_watts:.0f} W" if vt1_watts and vt2_watts else ""),
        st_note,
    )
    b = _chart_power_hr(df, cp)
    header = [
        Paragraph("Raport Treningowy", st_title),
        Paragraph(f"{filename}", st_sub),
        Paragraph(f"Data raportu: {register_date}  ·  Tri_Dashboard", st_sub),
        Spacer(1, 0.35 * cm),
        kpi_table(kpis),
        Spacer(1, 0.15 * cm),
        ref,
    ]
    if b:
        header += [
            Spacer(1, 0.35 * cm),
            Paragraph("1. Przebieg treningu", st_h),
            img(b, h=6.2),
            Paragraph(
                "Moc (średnia krocząca 30 s) i tętno w czasie. "
                "Linia przerywana to moc krytyczna (CP).",
                st_note,
            ),
        ]
    section(header)

    # ── strefy mocy + krzywa mocy ──
    try:
        from modules.calculations.training_distribution import calculate_training_distribution

        dist = calculate_training_distribution(df, cp=cp) if cp > 0 else None
    except Exception as e:  # pragma: no cover
        logger.warning("zones failed: %s", e)
        dist = None
    pz = (dist or {}).get("power") if isinstance(dist, dict) else None
    zones = None
    if isinstance(pz, dict):
        zones = [(k, _num(v)) for k, v in pz.items() if k not in ("total_seconds", "cp_used")]
    if zones:
        names = [z[0] for z in zones]
        secs = [z[1] for z in zones]
        palette = ["#2ECC71", "#3498DB", "#F1C40F", "#E67E22", "#E74C3C", "#8E44AD", "#7F8C8D"][
            : len(names)
        ]
        cz = _chart_zones(names, secs, palette)
        if cz:
            section(
                [
                    Paragraph("2. Czas w strefach mocy", st_h),
                    img(cz, h=4.8),
                    Paragraph(
                        "Rozkład czasu wg stref mocy względem CP — charakter sesji "
                        "(tlenowa baza vs praca progowa/beztlenowa).",
                        st_note,
                    ),
                ]
            )

    try:
        from modules.calculations.power import calculate_power_duration_curve

        pdc = calculate_power_duration_curve(df) or {}
    except Exception as e:  # pragma: no cover
        logger.warning("pdc failed: %s", e)
        pdc = {}
    cpdc = _chart_pdc(pdc)
    if cpdc:
        section(
            [
                Paragraph("3. Krzywa mocy (najlepsze wysiłki)", st_h),
                img(cpdc, h=6.0),
                Spacer(1, 0.15 * cm),
                pdc_table(pdc),
            ]
        )

    # ── efektywność i odporność ──
    try:
        from modules.calculations.durability import (
            calculate_durability_index,
            get_decoupling_interpretation,
            get_durability_interpretation,
        )

        di, e1, e2 = calculate_durability_index(df, min_duration_min=20)
    except Exception as e:  # pragma: no cover
        logger.warning("durability failed: %s", e)
        di, e1, e2 = None, None, None
        get_durability_interpretation = get_decoupling_interpretation = lambda *_: ""
    eff = [
        Paragraph("4. Efektywność i odporność na zmęczenie", st_h),
        kpi_table(
            [
                ("Efektywność (moc/HR)", _fmt(ef, "", 2)),
                ("Decoupling moc:HR", _fmt(decoup, " %", 1) if decoup is not None else "—"),
                ("Indeks wytrzymałości", _fmt(di, " %", 1) if di is not None else "—"),
                ("Śr. moc 1. poł. / 2. poł.", f"{_fmt(e1)} / {_fmt(e2)} W" if e1 else "—"),
            ]
        ),
        Spacer(1, 0.15 * cm),
    ]
    if decoup is not None:
        eff.append(Paragraph(_clean(get_decoupling_interpretation(decoup)), st_p))
    if di is not None:
        eff.append(Paragraph(_clean(get_durability_interpretation(di)), st_p))
    section(eff)

    # ── fizjologia (SmO2 / wentylacja) ──
    scol = _col(df, "smo2")
    vent_col = _col(df, "tymeventilation", "ventilation")
    if scol or vent_col:
        phys = []
        if scol:
            s = pd.to_numeric(df[scol], errors="coerce").dropna()
            if len(s):
                phys += [
                    ("Śr. SmO₂", _fmt(s.mean(), " %", 1)),
                    ("Min SmO₂", _fmt(s.min(), " %", 1)),
                    (
                        "Desaturacja",
                        _fmt(s.iloc[: max(1, len(s) // 10)].mean() - s.min(), " pp", 1),
                    ),
                ]
        tcol2 = _col(df, "thb")
        if tcol2:
            phys.append(("Śr. THb", _fmt(pd.to_numeric(df[tcol2], errors="coerce").mean(), "", 1)))
        if vent_col:
            phys.append(("Śr. wentylacja", _fmt(metrics.get("avg_vent"), " L/min", 1)))
        rcol = _col(df, "tymebreathrate", "respiration")
        if rcol:
            phys.append(
                (
                    "Śr. częstość oddechu",
                    _fmt(
                        metrics.get("avg_rr") or pd.to_numeric(df[rcol], errors="coerce").mean(),
                        " /min",
                        0,
                    ),
                )
            )
        flow = [Paragraph("5. Fizjologia mięśniowa i oddechowa", st_h)]
        if phys:
            flow += [kpi_table(phys), Spacer(1, 0.15 * cm)]
        cs = _chart_two_signals(df, "smo2", "SmO₂", RED, "%") if scol else None
        if cs:
            flow += [
                img(cs, h=5.2),
                Paragraph(
                    "SmO₂ (mięśniowe wysycenie tlenem) na tle mocy — spadki wskazują "
                    "pracę powyżej progu tlenowego.",
                    st_note,
                ),
            ]
        section(flow)

    # ── termika ──
    corecol = _col(df, "core_temperature")
    if corecol:
        core = pd.to_numeric(df[corecol], errors="coerce").dropna()
        if len(core):
            th = [
                ("Śr. temp. rdzenia", _fmt(core.mean(), " °C", 1)),
                ("Max temp. rdzenia", _fmt(core.max(), " °C", 1)),
                ("Max Heat Strain Index", _fmt(metrics.get("max_hsi"), "", 1)),
            ]
            scin = _col(df, "skin_temperature")
            if scin:
                th.append(
                    (
                        "Śr. temp. skóry",
                        _fmt(pd.to_numeric(df[scin], errors="coerce").mean(), " °C", 1),
                    )
                )
            ct = _chart_two_signals(df, "core_temperature", "Temp. rdzenia", ORANGE, "°C")
            section(
                [
                    Paragraph("6. Obciążenie termiczne", st_h),
                    kpi_table(th),
                    Spacer(1, 0.15 * cm),
                    img(ct, h=5.2) if ct else None,
                ]
            )

    # ── estymaty ──
    section(
        [
            Paragraph("7. Estymaty metaboliczne", st_h),
            kpi_table(
                [
                    ("VO₂max (est.)", _fmt(metrics.get("vo2_max_est"), " ml/kg/min", 1)),
                    ("VLamax (est.)", _fmt(metrics.get("vlamax_est"), " mmol/l/s", 2)),
                    ("Węglowodany (est.)", _fmt(metrics.get("carbs_total"), " g")),
                    ("Praca / kg", _fmt(work_kj / weight if weight else 0, " kJ/kg", 1)),
                ]
            ),
            Spacer(1, 0.15 * cm),
            Paragraph(
                "Uwaga: VLamax i VO₂max z pojedynczej sesji to szacunki — wiarygodne dopiero "
                "przy odpowiednim bodźcu (maksymalne krótkie wysiłki / test rampowy).",
                st_note,
            ),
        ]
    )

    # ── komentarz końcowy ──
    # The closing comment must never sink the whole report: if the assessment or
    # the AI call fails for any reason, log it and skip the box.
    try:
        # Intensity distribution (% time per power zone) — the backbone of a full
        # training analysis. Built from the same data as the zones chart.
        _zone_pct = None
        if zones:
            _z_total = sum(s for _, s in zones) or 0
            if _z_total > 0:
                _zone_pct = {name: round(sec / _z_total * 100) for name, sec in zones if sec > 0}

        # Best efforts (peak 5- and 20-min power) from the power-duration curve.
        _best5 = _num((pdc or {}).get(300))
        _best20 = _num((pdc or {}).get(1200))

        # Aerobic fade: 2nd-half vs 1st-half average power (negative = power fell).
        _fade = None
        try:
            if wcol:
                _wv = pd.to_numeric(df[wcol], errors="coerce").dropna()
                if len(_wv) >= 120:
                    _h = len(_wv) // 2
                    _f1 = float(_wv.iloc[:_h].mean())
                    _f2 = float(_wv.iloc[_h:].mean())
                    if _f1 > 0:
                        _fade = (_f2 - _f1) / _f1 * 100.0
        except Exception:
            _fade = None
        _ctx = {
            "if_factor": if_factor,
            "tss": tss,
            "decoup": decoup,
            "dur_min": dur_min,
            "np": np_w,
            "wkg": wkg,
            "work_kj": work_kj,
            "work_cp": work_cp,
            "avg_cad": avg_cad,
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "dist_km": dist_km,
            "vi": (np_w / avg_w) if avg_w > 0 else None,
            "ef_factor": ef or None,
            "zones_pct": _zone_pct,
            "best_5min": _best5 or None,
            "best_20min": _best20 or None,
            "best_5min_wkg": (_best5 / weight) if (_best5 and weight) else None,
            "best_20min_wkg": (_best20 / weight) if (_best20 and weight) else None,
            "fade_pct": _fade,
            "vlamax_est": _num(metrics.get("vlamax_est")) or None,
            "vo2max_est": _num(metrics.get("vo2_max_est")) or None,
            "has_smo2": bool(scol),
            "max_hsi": _num(metrics.get("max_hsi")),
            "history": _history_context(register_date, _best20 or None),
        }
        _assessment = _session_assessment(_ctx)
        _ai = _ai_narrative(_ctx) if use_ai else None
        if _ai:
            _paras = _ai_paragraphs(_ai)
            _box = comment_box(_assessment["verdict"], _paras, source="AI")
        else:
            _paras = _assessment["paragraphs"]
            # Be transparent when AI was requested but unavailable.
            _src = "AI niedostępne" if use_ai else ""
            _box = comment_box(_assessment["verdict"], _paras, source=_src)
        # Short comment → keep whole box together (avoids an orphaned header at a
        # page break). Long comment → append raw so it can split across pages
        # instead of being clipped at the page bottom.
        _total_chars = len(_assessment["verdict"]) + sum(len(str(p)) for p in _paras)
        if _total_chars < 1400:
            story.append(KeepTogether([_box]))
        else:
            story.append(_box)
        story.append(Spacer(1, 0.45 * cm))
    except Exception as e:
        logger.warning("Closing comment skipped: %s", e, exc_info=True)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def _auto_summary(if_factor, tss, decoup, di, dur_min) -> str:
    parts = []
    if if_factor >= 0.95:
        parts.append(
            "Sesja o bardzo wysokiej intensywności (IF ≥ 0.95) — charakter wyścigowy/progowy."
        )
    elif if_factor >= 0.85:
        parts.append("Intensywność progowa (IF 0.85–0.95) — solidny bodziec tlenowo-progowy.")
    elif if_factor >= 0.7:
        parts.append("Intensywność tempo/sweet-spot (IF 0.70–0.85).")
    else:
        parts.append("Sesja o niskiej intensywności (IF < 0.70) — praca w bazie tlenowej Z1/Z2.")

    if tss >= 150:
        parts.append(f"Obciążenie bardzo wysokie (TSS {tss:.0f}) — wymaga solidnej regeneracji.")
    elif tss >= 80:
        parts.append(f"Umiarkowane-wysokie obciążenie (TSS {tss:.0f}).")
    else:
        parts.append(f"Niskie obciążenie (TSS {tss:.0f}).")

    if decoup is not None and dur_min >= 40:
        if decoup < 5:
            parts.append(
                f"Dobre sprzężenie moc:HR (decoupling {decoup:.1f} %) — silna baza tlenowa."
            )
        elif decoup < 10:
            parts.append(f"Umiarkowany dryf moc:HR ({decoup:.1f} %) — baza w budowie.")
        else:
            parts.append(
                f"Wysoki dryf moc:HR ({decoup:.1f} %) — rozważ więcej objętości Z2, "
                "kontrolę nawodnienia i termiki."
            )
    return " ".join(parts)


def _closing_comment(if_factor, tss, decoup, dur_min) -> str:
    """Short coach-style closing comment: what the session was + one takeaway."""
    summary = _auto_summary(if_factor, tss, decoup, if_factor, dur_min)

    # One forward-looking takeaway ("co dalej") from the strongest signal.
    if decoup is not None and dur_min >= 40 and decoup >= 10:
        takeaway = (
            "Co dalej: priorytetem spokojna objętość Z2 i kontrola nawodnienia/termiki — "
            "to obniży dryf i podniesie durability."
        )
    elif if_factor >= 0.9:
        takeaway = (
            "Co dalej: mocny bodziec — zadbaj o regenerację (sen, węglowodany) przed kolejnym "
            "twardym akcentem."
        )
    elif if_factor < 0.7:
        takeaway = (
            "Co dalej: dokładnie taki spokojny bodziec buduje ekonomię tlenową — utrzymuj "
            "regularną objętość."
        )
    else:
        takeaway = (
            "Co dalej: solidna praca tempo/sweet-spot — przeplataj ją dniami Z2, by uniknąć "
            "kumulacji zmęczenia."
        )
    return summary + " " + takeaway


def _history_context(
    ride_date: Optional[str] = None, current_best_20m: Optional[float] = None
) -> Optional[dict]:
    """Recent training-load context from the session store (best-effort).

    Returns CTL/ATL/TSB + form, 7-day load, and a personal-best flag so the
    comment can judge the session IN CONTEXT of the athlete's recent trend.
    Fully guarded: on any failure (no DB, too little history) returns None and
    the comment stays session-only.
    """
    try:
        import datetime

        from modules.calculations.pmc import calculate_pmc_history, get_form_interpretation
        from modules.db import SessionStore

        store = SessionStore()
        if store.get_session_count() < 5:
            return None  # not enough history to contextualize

        out: dict = {}
        pmc = calculate_pmc_history(store, days=120)
        if pmc:
            last = pmc[-1]
            out["CTL_forma_chroniczna"] = last.ctl
            out["ATL_zmeczenie_ostre"] = last.atl
            out["TSB_swiezosc"] = last.tsb
            out["status_formy"] = _clean(get_form_interpretation(last.tsb))

        recent = store.get_sessions(days=90)
        today = ride_date or datetime.date.today().isoformat()
        d7 = (datetime.date.fromisoformat(today[:10]) - datetime.timedelta(days=7)).isoformat()
        s7 = [s for s in recent if str(s.date) >= d7]
        out["TSS_ostatnie_7dni"] = round(sum(_num(s.tss) for s in s7))
        out["sesje_ostatnie_7dni"] = len(s7)

        # Personal best (20-min power) vs previous sessions (exclude today's).
        prev20 = [_num(s.mmp_20m) for s in recent if s.mmp_20m and str(s.date)[:10] != today[:10]]
        if prev20:
            out["poprzedni_best_20min_W_90dni"] = round(max(prev20))
            if current_best_20m and current_best_20m > max(prev20):
                out["rekord_20min"] = True
        return out or None
    except Exception as e:  # pragma: no cover
        logger.warning("History context unavailable: %s", e)
        return None


def _session_character(if_factor: float) -> str:
    if if_factor >= 0.95:
        return "Sesja wyścigowa/okołoprogowa"
    if if_factor >= 0.85:
        return "Sesja progowa"
    if if_factor >= 0.70:
        return "Sesja tempo / sweet-spot"
    return "Sesja bazowa (tlenowa Z1/Z2)"


def _execution_rating(ctx: dict) -> tuple[int, str]:
    """Rate how well the session was EXECUTED (1-5 stars) from durability + pacing.

    Not a judgement of the session's worth — a Z2 ride and a race effort are both
    valid. This grades control: holding power with a flat power:HR drift and even
    pacing scores high.
    """
    decoup = ctx.get("decoup")
    dur_min = ctx.get("dur_min", 0)
    vi = ctx.get("vi")  # variability index NP/avg
    if_factor = ctx.get("if_factor", 0)

    reasons = []
    if decoup is None or dur_min < 40:
        # Not enough signal to judge durability — rate steadiness only.
        rating = 3
        reasons.append("za krótka/brak HR, by ocenić durability")
    else:
        if decoup < 5:
            rating, r = 5, "bardzo niski dryf moc:HR"
        elif decoup < 8:
            rating, r = 4, "niski dryf moc:HR"
        elif decoup < 12:
            rating, r = 3, "umiarkowany dryf"
        else:
            rating, r = 2, "wysoki dryf — słabnąca durability"
        reasons.append(r)

    # Pacing: only meaningful for steady (non-interval) sessions.
    if vi is not None and if_factor < 0.85:
        if vi <= 1.05:
            rating = min(5, rating + 1)
            reasons.append("bardzo równa moc")
        elif vi >= 1.18:
            rating = max(1, rating - 1)
            reasons.append("moc poszarpana")

    rating = max(1, min(5, rating))
    return rating, ", ".join(reasons)


def _session_assessment(ctx: dict) -> dict:
    """Rich, data-driven closing assessment. Returns verdict + rating + paragraphs."""
    ifac = ctx.get("if_factor", 0)
    tss = ctx.get("tss", 0)
    decoup = ctx.get("decoup")
    dur_min = ctx.get("dur_min", 0)
    character = _session_character(ifac)
    stars, rating_reason = _execution_rating(ctx)
    star_str = "★" * stars + "☆" * (5 - stars)

    load = (
        "bardzo wysokie"
        if tss >= 150
        else "umiarkowane-wysokie"
        if tss >= 80
        else "niskie-umiarkowane"
        if tss >= 40
        else "niskie"
    )

    # P1 — intensity & load
    p1 = (
        f"{character}. Intensywność IF {ifac:.2f}, obciążenie TSS {tss:.0f} ({load}). "
        f"Moc znormalizowana {ctx.get('np', 0):.0f} W ({ctx.get('wkg', 0):.1f} W/kg), "
        f"praca {ctx.get('work_kj', 0):.0f} kJ"
    )
    if ctx.get("work_cp", 0) > 0:
        p1 += f" (z tego {ctx['work_cp']:.0f} kJ powyżej CP)"
    p1 += f", czas {dur_min:.0f} min"
    if ctx.get("dist_km"):
        p1 += f" / {ctx['dist_km']:.0f} km"
    p1 += "."

    # P2 — execution & physiology
    p2_bits = []
    zp = ctx.get("zones_pct")
    if isinstance(zp, dict) and zp:
        top = sorted(zp.items(), key=lambda kv: kv[1], reverse=True)[:3]
        dist_txt = ", ".join(f"{v}% {k}" for k, v in top if v)
        if dist_txt:
            p2_bits.append(f"rozkład intensywności: {dist_txt}")
    if ctx.get("ef_factor"):
        p2_bits.append(f"efektywność (EF) {ctx['ef_factor']:.2f}")
    if ctx.get("best_20min"):
        be = f"best 20 min {ctx['best_20min']:.0f} W"
        if ctx.get("best_5min"):
            be = f"best 5 min {ctx['best_5min']:.0f} W / " + be
        p2_bits.append(be)
    if ctx.get("fade_pct") is not None and dur_min >= 40:
        fp = ctx["fade_pct"]
        if fp <= -8:
            p2_bits.append(f"wyraźny spadek mocy w 2. połowie ({fp:.0f}%) — narastające zmęczenie")
        elif fp >= 5:
            p2_bits.append(f"negatywny split (+{fp:.0f}% w 2. połowie) — dobra rezerwa/rozgrzewka")
        else:
            _fv = round(fp)
            _sign = f"{_fv:+d}" if _fv != 0 else "0"
            p2_bits.append(f"równy split połówkowy ({_sign}%)")
    if decoup is not None and dur_min >= 40:
        if decoup < 5:
            p2_bits.append(
                f"Sprzężenie moc:HR bardzo dobre (dryf {decoup:.1f} %) — mocna baza tlenowa"
            )
        elif decoup < 10:
            p2_bits.append(f"Dryf moc:HR umiarkowany ({decoup:.1f} %) — durability w budowie")
        else:
            p2_bits.append(
                f"Dryf moc:HR wysoki ({decoup:.1f} %) — sygnał zmęczenia/odwodnienia lub zbyt wysokiej intensywności"
            )
    if ctx.get("avg_cad"):
        p2_bits.append(f"kadencja śr. {ctx['avg_cad']:.0f} rpm")
    if ctx.get("avg_hr"):
        hr_txt = f"HR śr. {ctx['avg_hr']:.0f}"
        if ctx.get("max_hr"):
            hr_txt += f" / max {ctx['max_hr']:.0f} bpm"
        p2_bits.append(hr_txt)
    if ctx.get("has_smo2"):
        p2_bits.append("dane SmO₂ obecne — sprawdź spadki wysycenia względem progu")
    if ctx.get("max_hsi") and ctx["max_hsi"] >= 4:
        p2_bits.append(f"obciążenie termiczne podwyższone (HSI {ctx['max_hsi']:.1f})")
    p2 = ". ".join(s[0].upper() + s[1:] for s in p2_bits) + "." if p2_bits else ""

    # P3 — takeaway
    if decoup is not None and dur_min >= 40 and decoup >= 10:
        p3 = (
            "Co dalej: priorytet spokojna objętość Z2 + kontrola nawodnienia/termiki — obniży "
            "dryf i podniesie durability."
        )
    elif ifac >= 0.9:
        p3 = (
            "Co dalej: mocny bodziec — zadbaj o regenerację (sen, węglowodany, łatwy dzień) "
            "przed kolejnym twardym akcentem."
        )
    elif ifac < 0.7:
        p3 = (
            "Co dalej: dokładnie taki spokojny bodziec buduje ekonomię tlenową i objętość "
            "mitochondrialną — utrzymuj regularność."
        )
    else:
        p3 = (
            "Co dalej: solidna praca tempo/sweet-spot — przeplataj dniami Z2, by nie kumulować "
            "zmęczenia."
        )

    # P_hist — recent-load context (only if history is available)
    h = ctx.get("history") or {}
    hb = []
    if h.get("status_formy") and h.get("TSB_swiezosc") is not None:
        hb.append(
            f"forma {h['status_formy']} (TSB {h['TSB_swiezosc']:+.0f}, "
            f"CTL {h.get('CTL_forma_chroniczna', 0):.0f})"
        )
    if h.get("TSS_ostatnie_7dni") is not None:
        hb.append(
            f"ostatnie 7 dni: TSS {h['TSS_ostatnie_7dni']} "
            f"w {h.get('sesje_ostatnie_7dni', 0)} sesjach"
        )
    if h.get("rekord_20min"):
        hb.append("nowy rekord mocy 20 min w ostatnich 90 dniach")
    p_hist = ("Kontekst formy: " + "; ".join(hb) + ".") if hb else ""

    verdict = f"{character} · Ocena wykonania: {star_str} ({rating_reason})"
    return {
        "verdict": verdict,
        "stars": stars,
        "paragraphs": [p for p in [p1, p2, p_hist, p3] if p],
    }


_ABBREV = {
    "śr",
    "np",
    "tj",
    "tzn",
    "itd",
    "itp",
    "ok",
    "min",
    "max",
    "godz",
    "por",
    "ang",
    "rys",
    "tab",
    "ww",
    "m.in",
    "tzw",
}


def _split_sentences(text: str) -> list:
    """Split text into sentences without breaking on abbreviations (śr., np., …)."""
    out, start = [], 0
    for m in re.finditer(r"[.!?]\s+(?=[A-ZŚŻŹĆĄĘŁÓŃ0-9])", text):
        before = text[: m.start()].split()
        token = before[-1].strip(".").lower() if before else ""
        if token in _ABBREV:
            continue
        out.append(text[start : m.start() + 1].strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return [s for s in out if s]


def _ai_paragraphs(text: str, max_len: int = 650) -> list:
    """Turn an AI blob into clean paragraph chunks for the comment box.

    Prefers the model's own paragraph breaks (blank lines / newlines); only if a
    paragraph is very long does it group whole sentences into ≤max_len chunks so
    the box can split across pages without clipping — never mid-abbreviation.
    """
    text = str(text or "").strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    out = []
    for p in paras:
        if len(p) <= max_len:
            out.append(p)
            continue
        buf = ""
        for s in _split_sentences(p):
            if buf and len(buf) + len(s) + 1 > max_len:
                out.append(buf.strip())
                buf = s
            else:
                buf = f"{buf} {s}".strip()
        if buf:
            out.append(buf.strip())
    return out or [text]


def _ai_narrative(ctx: dict) -> "Optional[str]":
    """Optional LLM-written narrative via DeepSeek (OpenAI-compatible API).

    Off unless DEEPSEEK_API_KEY is configured in .env (private, opt-in). Only the
    session metrics (numbers) are sent. Any failure → None, so the report
    silently falls back to the rule-based assessment. No key = never called.

    Config (env / .env):
      DEEPSEEK_API_KEY   — required to enable
      DEEPSEEK_BASE_URL  — default https://api.deepseek.com
      TRAINING_AI_MODEL  — default deepseek-chat (or deepseek-reasoner)
    """
    import os

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import json as _json

        import requests

        base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        model = os.environ.get("TRAINING_AI_MODEL", "deepseek-reasoner")

        def _clip(v):
            return v if v not in (0, None) else None

        facts = {
            "charakter_wg_IF": _session_character(ctx.get("if_factor", 0)),
            "IF_intensity_factor": round(ctx.get("if_factor", 0), 2) or None,
            "TSS": round(ctx.get("tss", 0)) or None,
            "NP_moc_znormalizowana_W": round(ctx.get("np", 0)) or None,
            "NP_W_per_kg": round(ctx.get("wkg", 0), 1) or None,
            "praca_calkowita_kJ": round(ctx.get("work_kj", 0)) or None,
            "praca_powyzej_CP_kJ": round(ctx.get("work_cp", 0)) or None,
            "decoupling_powerHR_proc": ctx.get("decoup"),
            "rozklad_intensywnosci_proc_czasu": ctx.get("zones_pct") or None,
            "efficiency_factor_EF": (round(ctx["ef_factor"], 2) if ctx.get("ef_factor") else None),
            "best_5min_W": round(ctx["best_5min"]) if ctx.get("best_5min") else None,
            "best_20min_W": round(ctx["best_20min"]) if ctx.get("best_20min") else None,
            "best_5min_W_per_kg": (
                round(ctx["best_5min_wkg"], 1) if ctx.get("best_5min_wkg") else None
            ),
            "best_20min_W_per_kg": (
                round(ctx["best_20min_wkg"], 1) if ctx.get("best_20min_wkg") else None
            ),
            "fade_2ga_vs_1sza_polowa_proc": (
                round(ctx["fade_pct"], 1) if ctx.get("fade_pct") is not None else None
            ),
            "VLamax_szacunek_mmol": ctx.get("vlamax_est"),
            "VO2max_szacunek_ml_kg_min": ctx.get("vo2max_est"),
            "kontekst_recent_forma_obciazenie": ctx.get("history") or None,
            "czas_min": round(ctx.get("dur_min", 0)) or None,
            "dystans_km": round(ctx.get("dist_km"), 1) if ctx.get("dist_km") else None,
            "kadencja_srednia_rpm": _clip(round(ctx.get("avg_cad", 0))),
            "HR_srednie_bpm": _clip(round(ctx.get("avg_hr", 0))),
            "HR_max_bpm": _clip(round(ctx.get("max_hr", 0))),
            "SmO2_dostepne": bool(ctx.get("has_smo2")),
            "max_HeatStrainIndex": ctx.get("max_hsi") or None,
        }

        system = (
            "Jesteś elitarnym trenerem kolarstwa i fizjologiem wysiłku na poziomie World Tour. "
            "Analizujesz dane jak połączenie Coggana (moc, TSS, IF, W'), Seilera (dystrybucja "
            "intensywności, polaryzacja) i San Millána (metabolizm, strefy). Rozumiesz znaczenie "
            "durability (decoupling power:HR jako marker odporności zmęczeniowej i nawodnienia), "
            "pracy powyżej CP (wydatek W'), oraz adekwatności bodźca do celu. Piszesz po polsku, "
            "rzeczowo i gęsto merytorycznie, bez marketingowego żargonu, coachingowych frazesów i "
            "lania wody. Nigdy nie zmyślasz danych, których nie ma."
        )
        user = (
            "Oceń JEDNĄ sesję treningową na podstawie metryk (JSON poniżej). Napisz zwartą, "
            "ekspercką analizę PO POLSKU w 2–3 krótkich akapitach rozdzielonych pustą linią "
            "(bez nagłówków, bez wypunktowań, bez emoji). Zawrzyj w tej kolejności, płynnie:\n"
            "1) Jednozdaniowy werdykt: jaki to był trening i czy został dobrze wykonany.\n"
            "2) Interpretacja fizjologiczna 2–3 najważniejszych sygnałów: co IF/TSS i rozkład "
            "intensywności (czas w strefach) mówią o charakterze bodźca i polaryzacji; co "
            "decoupling i EF mówią o durability/ekonomii; co oznacza udział pracy powyżej CP "
            "(obciążenie systemu beztlenowego W').\n"
            "3) Co konkretnie poszło dobrze, a co słabo — poparte danymi (np. best efforty "
            "5/20 min, fade między połowami, EF).\n"
            "4) Jedno najważniejsze, wykonalne zalecenie na kolejny krok (wykonanie lub "
            "periodyzacja), spójne z charakterem sesji ORAZ z kontekstem formy — jeśli podano "
            "TSB/CTL i obciążenie z ostatnich 7 dni, oceń tę sesję w kontekście trendu "
            "(świeżość vs zmęczenie, czy to kolejny twardy dzień z rzędu, ryzyko "
            "przeciążenia lub przestrzeń na bodziec). Jeśli padł rekord — odnotuj go.\n\n"
            "ZASADY: nie powtarzaj wszystkich liczb — wpleć tylko 2–3 kluczowe. Nie oceniaj "
            "sesji Z2/bazowej jako 'gorszej' od progowej — oceniaj adekwatność wykonania do typu "
            "bodźca. Jeśli pole jest null/false (np. brak HR, brak SmO2), NIE komentuj tego "
            "sygnału zamiast zmyślać — pomiń go milcząco lub zaznacz jednym słowem. VLamax i "
            "VO2max to SZACUNKI z jednej sesji — traktuj ostrożnie, nie wyciągaj mocnych "
            "wniosków. Decoupling interpretuj tylko dla sesji ≥40 min. Zachowaj proporcję: "
            "więcej analizy 'dlaczego', mniej wyliczania 'co'.\n\n"
            "Metryki (JSON):\n" + _json.dumps(facts, ensure_ascii=False, indent=None)
        )
        is_reasoner = "reasoner" in model
        # CRITICAL: deepseek-reasoner counts chain-of-thought tokens against
        # max_tokens. A small cap gets fully consumed by reasoning, leaving an
        # EMPTY final answer (finish_reason="length"). Give it ample room so the
        # actual comment survives after the reasoning.
        payload = {
            "model": model,
            "max_tokens": 4000 if is_reasoner else 900,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        # deepseek-reasoner ignores temperature; deepseek-chat benefits from it.
        if not is_reasoner:
            payload["temperature"] = 0.6
        # Reasoning model is slower (chain-of-thought).
        timeout = 120 if is_reasoner else 30
        resp = requests.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        return text or None
    except Exception as e:  # network, auth, quota, bad model — fall back silently
        logger.warning("AI narrative unavailable, using rule-based: %s", e)
        return None
