"""
Cardiovascular (3.2) and ventilation (3.1) diagnostic pages.

Extracted verbatim from layout.py. Self-contained: depends only on shared
leaf helpers, styles, cards and reportlab — no other page builder.
"""

from __future__ import annotations

from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ._helpers import (
    _signal_quality_label,
    get_confidence_prefix,
    get_confidence_suffix,
)
from .cards import build_metric_card
from .styles import COLORS, FONT_FAMILY, FONT_FAMILY_BOLD, is_compact, section_no


def build_page_cardiovascular(cardio_data: Dict[str, Any], styles: Dict) -> List:
    """Build Cardiovascular Cost Diagnostic page - PREMIUM."""

    elements = []

    # ==========================================================================
    # HEADER
    # ==========================================================================
    elements.append(
        Paragraph(f"<font size='14'>{section_no('3.2')} UKŁAD SERCOWO-NACZYNIOWY</font>", styles["center"])
    )
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Diagnostyka kosztu sercowego generowania mocy</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # Extract metrics
    pp = cardio_data.get("pulse_power", 0)
    ef = cardio_data.get("efficiency_factor", 0)
    drift = cardio_data.get("hr_drift_pct", 0)
    recovery = cardio_data.get("hr_recovery_1min")
    cci = cardio_data.get("cci_avg", 0)
    cci_bp = cardio_data.get("cci_breakpoint_watts")
    status = cardio_data.get("efficiency_status", "unknown")
    confidence = cardio_data.get("efficiency_confidence", 0)
    interpretation = cardio_data.get("interpretation", "")
    recommendations = cardio_data.get("recommendations", [])

    # ==========================================================================
    # 1. METRIC CARDS
    # ==========================================================================

    # Pulse Power
    pp_color = "#2ECC71" if pp > 2.0 else ("#F39C12" if pp > 1.5 else "#E74C3C")
    pp_interp = "Efektywny" if pp > 2.0 else ("Umiarkowany" if pp > 1.5 else "Niski")
    card1 = build_metric_card(
        "MOC PULSOWA",
        f"{pp:.2f}",
        "W/bpm",
        pp_color,
        interpretation=pp_interp,
        value_font_size=16,
        interp_font_size=8,
        styles=styles,
    )

    # Efficiency Factor
    ef_color = "#2ECC71" if ef > 1.8 else ("#F39C12" if ef > 1.4 else "#E74C3C")
    ef_interp = "Wysoki" if ef > 1.8 else ("Średni" if ef > 1.4 else "Niski")
    card2 = build_metric_card(
        "WSP. EFEKTYWNOŚCI",
        f"{ef:.2f}",
        "W/bpm",
        ef_color,
        interpretation=ef_interp,
        value_font_size=16,
        interp_font_size=8,
        styles=styles,
    )

    # HR Drift
    drift_color = "#2ECC71" if drift < 3 else ("#F39C12" if drift < 6 else "#E74C3C")
    drift_interp = "Stabilny" if drift < 3 else ("Drift" if drift < 6 else "Wysoki Drift")
    card3 = build_metric_card(
        "DRYF HR",
        f"{drift:.1f}",
        "%",
        drift_color,
        interpretation=drift_interp,
        value_font_size=16,
        interp_font_size=8,
        styles=styles,
    )

    # HR Recovery or CCI
    if recovery and recovery > 0:
        rec_color = "#2ECC71" if recovery > 25 else ("#F39C12" if recovery > 15 else "#E74C3C")
        rec_interp = "Szybki" if recovery > 25 else ("Średni" if recovery > 15 else "Wolny")
        card4 = build_metric_card(
            "REGENERACJA HR",
            f"{recovery:.0f}",
            "bpm/min",
            rec_color,
            interpretation=rec_interp,
            value_font_size=16,
            interp_font_size=8,
            styles=styles,
        )
    else:
        cci_color = "#2ECC71" if cci < 0.15 else ("#F39C12" if cci < 0.25 else "#E74C3C")
        cci_interp = "Efektywny" if cci < 0.15 else ("Średni" if cci < 0.25 else "Wysoki koszt")
        card4 = build_metric_card(
            "CCI (avg)",
            f"{cci:.3f}",
            "bpm/W",
            cci_color,
            interpretation=cci_interp,
            value_font_size=16,
            interp_font_size=8,
            styles=styles,
        )

    cards_row = Table([[card1, card2, card3, card4]], colWidths=[44 * mm] * 4)
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 4 * mm))

    # ==========================================================================
    # 2. CCI METRIC PANEL
    # ==========================================================================

    elements.append(
        Paragraph("<b>INDEKS KOSZTU SERCOWO-NACZYNIOWEGO (CCI)</b>", styles["subheading"])
    )
    elements.append(Spacer(1, 2 * mm))

    cci_text = f"<b>CCI = {cci:.4f}</b> bpm/W – koszt tętna na jednostkę mocy."
    if cci_bp:
        cci_text += f" <b>Breakpoint</b> przy {cci_bp:.0f}W – punkt załamania efektywności."
    elements.append(Paragraph(cci_text, styles["body"]))
    elements.append(Spacer(1, 3 * mm))

    # ==========================================================================
    # 3. EFFICIENCY VERDICT PANEL
    # ==========================================================================

    elements.append(
        Paragraph("<b>WERDYKT EFEKTYWNOŚCI SERCOWO-NACZYNIOWEJ</b>", styles["subheading"])
    )
    elements.append(Spacer(1, 2 * mm))

    status_colors = {
        "efficient": "#2ECC71",
        "compensating": "#F39C12",
        "decompensating": "#E74C3C",
        "unknown": "#7F8C8D",
    }
    status_names = {
        "efficient": "EFEKTYWNY",
        "compensating": "KOMPENSUJĄCY",
        "decompensating": "DEKOMPENSUJĄCY",
        "unknown": "NIEOKREŚLONY",
    }
    status_icons = {"efficient": "✓", "compensating": "⚠", "decompensating": "✗", "unknown": "?"}

    st_color = HexColor(status_colors.get(status, "#7F8C8D"))
    st_name = status_names.get(status, "NIEOKREŚLONY")
    st_icon = status_icons.get(status, "?")

    verdict_content = [
        Paragraph(f"<font color='white'><b>{st_icon} {st_name}</b></font>", styles["center"]),
        Paragraph(
            f"<font size='10' color='white'>jakość sygnału: {_signal_quality_label(confidence)}</font>",
            styles["center"],
        ),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), st_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(verdict_table)
    elements.append(Spacer(1, 2 * mm))

    # Interpretation
    if interpretation:
        for line in interpretation.split("\n")[:2]:
            line_with_confidence = (
                get_confidence_prefix(confidence) + line + get_confidence_suffix(confidence)
            )
            elements.append(Paragraph(line_with_confidence, styles["body"]))
    elements.append(Spacer(1, 3 * mm))

    # ==========================================================================
    # 4. DECISION CARDS
    # ==========================================================================

    if recommendations and not is_compact():
        elements.append(Paragraph("<b>DECYZJE TRENINGOWE I ŚRODOWISKOWE</b>", styles["subheading"]))
        elements.append(Spacer(1, 2 * mm))

        type_colors = {
            "TRENINGOWA": "#3498DB",
            "ŚRODOWISKOWA": "#9B59B6",
            "REGENERACJA": "#1ABC9C",
            "WYDAJNOŚĆ": "#2ECC71",
            "DIAGNOSTYCZNA": "#E74C3C",
        }

        for rec in recommendations[:4]:
            rec_type = rec.get("type", "TRENINGOWA")
            action = rec.get("action", "---")
            expected = rec.get("expected", "---")
            risk = rec.get("risk", "low")

            type_color = type_colors.get(rec_type, "#7F8C8D")
            risk_color = (
                "#2ECC71" if risk == "low" else ("#F39C12" if risk == "medium" else "#E74C3C")
            )
            risk_label = (
                "NISKIE" if risk == "low" else ("ŚREDNIE" if risk == "medium" else "WYSOKIE")
            )

            card_content = [
                Paragraph(
                    f"<font size='9' color='{type_color}'><b>[{rec_type}]</b></font> {action}",
                    styles["body"],
                ),
                Paragraph(
                    f"<font size='8' color='#27AE60'>Spodziewany efekt: {expected}</font> | <font size='8' color='{risk_color}'>Ryzyko: {risk_label}</font>",
                    styles["body"],
                ),
            ]
            card_table = Table([[card_content]], colWidths=[170 * mm])
            card_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                        ("BOX", (0, 0), (-1, -1), 0.5, COLORS["border"]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(card_table)
            elements.append(Spacer(1, 1.5 * mm))

    # ==========================================================================
    # 5. HR RECOVERY KINETICS
    # ==========================================================================
    if recovery and recovery > 0:
        elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph("<b>KINETYKA REGENERACJI HR</b>", styles["subheading"]))
        elements.append(Spacer(1, 2 * mm))

        # Classify recovery quality (Daanen et al. 2012; Buchheit 2014)
        if recovery > 30:
            rec_class = "DOSKONAŁA"
            rec_color = "#2ECC71"
            rec_note = (
                "Szybki powrót HR po wysiłku wskazuje na dobrą reaktywność "
                "parasympatyczną i wysoki poziom wytrenowania aerobowego."
            )
        elif recovery > 20:
            rec_class = "DOBRA"
            rec_color = "#27AE60"
            rec_note = (
                "Regeneracja HR w normie dla wytrenowanego zawodnika. "
                "Układ autonomiczny dobrze reaguje na zaprzestanie wysiłku."
            )
        elif recovery > 12:
            rec_class = "ŚREDNIA"
            rec_color = "#F39C12"
            rec_note = (
                "Umiarkowana regeneracja HR może wskazywać na niedobór treningu "
                "aerobowego lub skumulowane zmęczenie. Monitoruj HRV w kolejnych dniach."
            )
        else:
            rec_class = "WOLNA"
            rec_color = "#E74C3C"
            rec_note = (
                "Wolna regeneracja HR (<12 bpm/min) może sygnalizować overreaching, "
                "odwodnienie lub niedostateczną bazę aerobową. Rozważ dodatkowy odpoczynek."
            )

        rec_box_style = ParagraphStyle(
            "rec_box", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9
        )
        rec_content = (
            f"<b>HR Recovery 1 min: {recovery:.0f} bpm/min → {rec_class}</b><br/>"
            f"{rec_note}<br/>"
            f"<font size='7'><i>Ref: Buchheit 2014 — HRR1 >25 bpm = bardzo dobra fitness aerobowa; "
            f"<12 bpm = ryzyko overreaching/niedostatecznej bazy Z2.</i></font>"
        )
        rec_box = Table([[Paragraph(rec_content, rec_box_style)]], colWidths=[170 * mm])
        rec_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor(rec_color)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(rec_box)

    return elements


# ============================================================================
# PAGE: BREATHING & METABOLIC CONTROL DIAGNOSTIC (PREMIUM)
# ============================================================================


def build_page_ventilation(vent_data: Dict[str, Any], styles: Dict) -> List:
    """Build Breathing & Metabolic Control Diagnostic page - PREMIUM."""

    elements = []

    # ==========================================================================
    # HEADER
    # ==========================================================================
    elements.append(Paragraph("3. DIAGNOSTYKA UKŁADÓW", styles["title"]))
    elements.append(Paragraph(f"<font size='14'>{section_no('3.1')} KONTROLA ODDYCHANIA</font>", styles["center"]))
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Diagnostyka wentylacji i kontroli metabolicznej</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # Extract metrics
    ve_avg = vent_data.get("ve_avg", 0)
    ve_max = vent_data.get("ve_max", 0)
    rr_avg = vent_data.get("rr_avg", 0)
    rr_max = vent_data.get("rr_max", 0)
    ve_rr = vent_data.get("ve_rr_ratio", 0)
    ve_slope = vent_data.get("ve_slope", 0)
    ve_bp = vent_data.get("ve_breakpoint_watts")
    pattern = vent_data.get("breathing_pattern", "unknown")
    status = vent_data.get("control_status", "unknown")
    confidence = vent_data.get("control_confidence", 0)
    interpretation = vent_data.get("interpretation", "")
    recommendations = vent_data.get("recommendations", [])

    # ==========================================================================
    # 1. METRIC CARDS
    # ==========================================================================

    # VE
    ve_color = "#2ECC71" if ve_max < 120 else ("#F39C12" if ve_max < 150 else "#E74C3C")
    card1 = build_metric_card(
        "VE MAX",
        f"{ve_max:.0f}",
        "L/min",
        ve_color,
        interpretation=f"avg: {ve_avg:.0f}",
        interp_font_size=7,
        styles=styles,
    )

    # RR
    rr_color = "#2ECC71" if rr_max < 45 else ("#F39C12" if rr_max < 55 else "#E74C3C")
    rr_interp = "Ekonomiczny" if rr_max < 45 else ("Podwyższony" if rr_max < 55 else "Wysoki")
    card2 = build_metric_card(
        "RR MAX",
        f"{rr_max:.0f}",
        "/min",
        rr_color,
        interpretation=rr_interp,
        interp_font_size=7,
        styles=styles,
    )

    # VE/RR
    verr_color = "#2ECC71" if ve_rr > 2.5 else ("#F39C12" if ve_rr > 1.5 else "#E74C3C")
    verr_interp = "Głęboki oddech" if ve_rr > 2.5 else ("Średni" if ve_rr > 1.5 else "Płytki")
    card3 = build_metric_card(
        "VE/RR RATIO",
        f"{ve_rr:.2f}",
        "L/breath",
        verr_color,
        interpretation=verr_interp,
        interp_font_size=7,
        styles=styles,
    )

    # VE Slope
    slope_color = "#2ECC71" if ve_slope < 0.25 else ("#F39C12" if ve_slope < 0.4 else "#E74C3C")
    slope_interp = "Stabilny" if ve_slope < 0.25 else ("Rosnący" if ve_slope < 0.4 else "Stromy")
    card4 = build_metric_card(
        "VE SLOPE",
        f"{ve_slope:.2f}",
        "L/min/100W",
        slope_color,
        interpretation=slope_interp,
        interp_font_size=7,
        styles=styles,
    )

    cards_row = Table([[card1, card2, card3, card4]], colWidths=[44 * mm] * 4)
    cards_row.setStyle(
        TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")])
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 2 * mm))

    # Ramp test context note for peak ventilatory values
    elements.append(
        Paragraph(
            "<font size='8' color='#7F8C8D'><i>Uwaga: wartości szczytowe (VE max, RR max) dotyczą "
            "końcowej fazy rampy — przy wyczerpaniu. Nie należy ich porównywać z normami "
            "dla wysiłku stacjonarnego. Kluczowa jest dynamika wzrostu (VE slope) i stosunek "
            "VE/RR (głębokość oddechu), które lepiej odzwierciedlają ekonomię wentylacyjną.</i></font>",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 4 * mm))

    # ==========================================================================
    # 2. BREATHING PATTERN
    # ==========================================================================

    pattern_colors = {
        "efficient": "#2ECC71",
        "shallow": "#E74C3C",
        "hyperventilation": "#F39C12",
        "mixed": "#7F8C8D",
        "unknown": "#7F8C8D",
    }
    pattern_names = {
        "efficient": "EFEKTYWNY ODDECH",
        "shallow": "PŁYTKI/PANIKA",
        "hyperventilation": "HIPERWENTYLACJA",
        "mixed": "WZÓR MIESZANY",
        "unknown": "NIEOKREŚLONY",
    }

    elements.append(Paragraph("<b>WYKRYWANIE WZORCA ODDECHOWEGO</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    pattern_badge = Paragraph(
        f"<font color='white'><b>{pattern_names.get(pattern, 'UNDEFINED')}</b></font>",
        styles["center"],
    )
    pattern_table = Table([[pattern_badge]], colWidths=[170 * mm])
    pattern_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(pattern_colors.get(pattern, "#7F8C8D"))),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(pattern_table)
    elements.append(Spacer(1, 4 * mm))

    # ==========================================================================
    # 3. CONTROL VERDICT
    # ==========================================================================

    elements.append(Paragraph("<b>WERDYKT KONTROLI WENTYLACJI</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    status_colors = {
        "controlled": "#2ECC71",
        "compensatory": "#F39C12",
        "unstable": "#E74C3C",
        "unknown": "#7F8C8D",
    }
    status_names = {
        "controlled": "KONTROLOWANY",
        "compensatory": "KOMPENSACYJNY",
        "unstable": "NIESTABILNY",
        "unknown": "NIEOKREŚLONY",
    }
    status_icons = {"controlled": "✓", "compensatory": "⚠", "unstable": "✗", "unknown": "?"}

    st_color = HexColor(status_colors.get(status, "#7F8C8D"))
    st_name = status_names.get(status, "NIEOKREŚLONY")
    st_icon = status_icons.get(status, "?")

    verdict_content = [
        Paragraph(f"<font color='white'><b>{st_icon} {st_name}</b></font>", styles["center"]),
        Paragraph(
            f"<font size='10' color='white'>jakość sygnału: {_signal_quality_label(confidence)}</font>",
            styles["center"],
        ),
    ]
    verdict_table = Table([[verdict_content]], colWidths=[170 * mm])
    verdict_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), st_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(verdict_table)
    elements.append(Spacer(1, 3 * mm))

    if interpretation:
        for line in interpretation.split("\n")[:2]:
            line_with_confidence = (
                get_confidence_prefix(confidence) + line + get_confidence_suffix(confidence)
            )
            elements.append(Paragraph(line_with_confidence, styles["body"]))

    if ve_bp:
        elements.append(
            Paragraph(
                f"<b>VE Breakpoint:</b> {ve_bp:.0f}W – punkt załamania kontroli wentylacyjnej",
                styles["body"],
            )
        )

    elements.append(Spacer(1, 4 * mm))

    # ==========================================================================
    # 3b. TIDAL VOLUME DECOMPOSITION (VE = TV × RR)
    # ==========================================================================
    elements.append(
        Paragraph("<b>DEKOMPOZYCJA WENTYLACJI (VE = TV × RR)</b>", styles["subheading"])
    )
    elements.append(Spacer(1, 2 * mm))

    # TV = VE/RR at different intensities
    tv_avg = ve_avg / rr_avg if rr_avg > 0 else 0
    tv_max = ve_max / rr_max if rr_max > 0 else 0

    if tv_avg > 0:
        # Determine breathing strategy
        if tv_max < tv_avg * 0.85:
            strategy = "PŁYTKI-SZYBKI"
            strategy_color = "#E74C3C"
            strategy_note = (
                "Przy wysokiej intensywności VE rośnie głównie przez RR (częstotliwość), "
                "nie TV (głębokość). Wskazuje na limit mechaniczny klatki piersiowej lub "
                "nieefektywny wzorzec oddechowy."
            )
        elif tv_max > tv_avg * 1.15:
            strategy = "GŁĘBOKI-WOLNY"
            strategy_color = "#27AE60"
            strategy_note = (
                "Przy wysokiej intensywności TV rośnie proporcjonalnie do RR — "
                "efektywny wzorzec oddechowy z dobrą mechaniką klatki piersiowej."
            )
        else:
            strategy = "ZBALANSOWANY"
            strategy_color = "#3498DB"
            strategy_note = (
                "TV i RR rosną proporcjonalnie. Typowy wzorzec dla umiarkowanie "
                "wytrenowanych zawodników."
            )

        tv_data = [
            ["Parametr", "Średnia", "Szczyt", "Interpretacja"],
            [
                "Objętość oddechowa (TV)",
                f"{tv_avg:.2f} L",
                f"{tv_max:.2f} L",
                f"{'↑' if tv_max > tv_avg else '↓'} {abs(tv_max - tv_avg) / tv_avg * 100:.0f}% zmiana",
            ],
            [
                "Częstość (RR)",
                f"{rr_avg:.0f} /min",
                f"{rr_max:.0f} /min",
                f"↑ {(rr_max - rr_avg) / rr_avg * 100:.0f}% wzrost",
            ],
            ["Strategia oddechowa", "", "", strategy],
        ]

        tv_table = Table(tv_data, colWidths=[45 * mm, 30 * mm, 30 * mm, 60 * mm])
        tv_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2C3E50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                    ("FONTNAME", (0, 0), (-1, -1), FONT_FAMILY),
                    ("FONTNAME", (0, 0), (-1, 0), FONT_FAMILY_BOLD),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (2, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#555555")),
                    ("ROWHEIGHT", (0, 0), (-1, -1), 10 * mm),
                    ("BACKGROUND", (0, 1), (-1, -1), HexColor("#f8f9fa")),
                    ("BACKGROUND", (3, 3), (3, 3), HexColor(strategy_color)),
                    ("TEXTCOLOR", (3, 3), (3, 3), HexColor("#FFFFFF")),
                    ("FONTNAME", (3, 3), (3, 3), FONT_FAMILY_BOLD),
                ]
            )
        )
        elements.append(tv_table)
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(f"<font size='8'><i>{strategy_note}</i></font>", styles["body"]))

    elements.append(Spacer(1, 4 * mm))

    # ==========================================================================
    # 3c. VENTILATORY RESERVE
    # ==========================================================================
    # MVV (Maximal Voluntary Ventilation) estimation: MVV ≈ FEV1 × 40
    # Without FEV1, use population estimate: MVV ≈ 200 L/min (trained male)
    # Breathing reserve = (1 - VEmax/MVV) × 100
    mvv_estimated = 200.0  # Conservative estimate for trained male cyclist
    breathing_reserve = (1 - ve_max / mvv_estimated) * 100 if ve_max > 0 else 100
    br_color = (
        "#27AE60"
        if breathing_reserve > 30
        else ("#F39C12" if breathing_reserve > 15 else "#E74C3C")
    )
    br_label = (
        "Wystarczająca"
        if breathing_reserve > 30
        else ("Ograniczona" if breathing_reserve > 15 else "Wyczerpana")
    )

    elements.append(
        Paragraph(
            f"<b>REZERWA WENTYLACYJNA:</b> <font color='{br_color}'><b>{breathing_reserve:.0f}%</b> ({br_label})</font>"
            f" — VE max {ve_max:.0f} L/min vs szacowane MVV ~{mvv_estimated:.0f} L/min. "
            f"{'Płuca NIE są czynnikiem limitującym.' if breathing_reserve > 30 else 'Płuca MOGĄ być czynnikiem limitującym — rozważ spirometrię.'}"
            f" <font size='7' color='#95A5A6'>(MVV szacowane; do precyzyjnej oceny wymagana spirometria)</font>",
            styles["body"],
        )
    )

    elements.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # 4. DECISION CARDS
    # ==========================================================================

    if recommendations and not is_compact():
        elements.append(Paragraph("<b>DECYZJE TRENINGOWE WENTYLACJI</b>", styles["subheading"]))
        elements.append(Spacer(1, 3 * mm))

        type_colors = {
            "TRENINGOWA": "#3498DB",
            "TECHNICZNA": "#9B59B6",
            "WYDAJNOŚĆ": "#2ECC71",
            "INTENSYWNOŚĆ": "#1ABC9C",
            "PILNA": "#E74C3C",
            "DIAGNOSTYKA": "#F39C12",
            "MEDYCZNA": "#E74C3C",
        }

        for rec in recommendations[:5]:
            rec_type = rec.get("type", "TRENINGOWA")
            action = rec.get("action", "---")
            expected = rec.get("expected", "---")
            risk = rec.get("risk", "low")

            type_color = type_colors.get(rec_type, "#7F8C8D")
            risk_color = (
                "#2ECC71" if risk == "low" else ("#F39C12" if risk == "medium" else "#E74C3C")
            )
            risk_label = (
                "NISKIE" if risk == "low" else ("ŚREDNIE" if risk == "medium" else "WYSOKIE")
            )

            card_content = [
                Paragraph(
                    f"<font size='9' color='{type_color}'><b>[{rec_type}]</b></font> {action}",
                    styles["body"],
                ),
                Paragraph(
                    f"<font size='8' color='#27AE60'>Spodziewany efekt: {expected}</font> | <font size='8' color='{risk_color}'>Ryzyko: {risk_label}</font>",
                    styles["body"],
                ),
            ]
            card_table = Table([[card_content]], colWidths=[170 * mm])
            card_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), COLORS["background"]),
                        ("BOX", (0, 0), (-1, -1), 0.5, COLORS["border"]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            elements.append(card_table)
            elements.append(Spacer(1, 2 * mm))

    return elements


# ============================================================================
# PAGE: METABOLIC ENGINE & TRAINING STRATEGY (PREMIUM)
# Moved to metabolic.py — re-exported for backward compatibility.
# ============================================================================


# ============================================================================
# PAGE: LIMITER RADAR (20 MIN FTP ANALYSIS)
# ============================================================================
