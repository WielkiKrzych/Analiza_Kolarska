"""
HRV / DFA alpha-1 (3.5) and core-skin temperature gradient (4.4) pages.

Extracted verbatim from layout.py. Self-contained: depends only on shared
leaf helpers, styles and reportlab — no other page builder.
"""

from __future__ import annotations

from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .styles import is_compact, section_no


def build_page_hrv(hrv_data: Dict[str, Any], styles: Dict) -> List:
    """Build HRV / DFA Alpha-1 analysis page.

    Displays DFA Alpha-1 zone classification, RMSSD/SDNN metrics,
    and autonomic fitness interpretation with literature references.
    """

    elements = []

    elements.append(
        Paragraph(
            f"<font size='14'>{section_no('3.5')} ZMIENNOŚĆ RYTMU SERCA (HRV / DFA Alpha-1)</font>", styles["center"]
        )
    )
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Analiza fraktalna RR — klasyfikacja stref, fitness autonomiczny</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    # Intro
    elements.append(
        Paragraph(
            "DFA Alpha-1 to wskaźnik fraktalnej korelacji odstępów R-R serca. "
            "Wartość Alpha-1 ≈ 0.75 odpowiada progowi aerobowemu (HRVT1), "
            "a Alpha-1 ≈ 0.50 progowi anaerobowemu (HRVT2). "
            "Metoda jest niezależna od progów wentylacyjnych i SmO₂ — pozwala na krzyżową walidację.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 4 * mm))

    # Extract data
    summary = hrv_data.get("summary", {})
    quality = hrv_data.get("quality", {})
    hrv_data.get("zone_classification", {})

    mean_alpha1 = summary.get("mean_alpha1")
    mean_rmssd = summary.get("mean_rmssd")
    mean_sdnn = summary.get("mean_sdnn")
    windows_count = summary.get("windows_analyzed", 0)
    quality_grade = quality.get("grade", "n/a")
    is_uncertain = quality.get("is_uncertain", True)
    quality_reasons = quality.get("reasons", [])

    # === METRIC CARDS ===
    elements.append(Paragraph("<b>KLUCZOWE METRYKI HRV</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    def _hrv_card(title, value, unit, color, subtitle=""):
        card_content = [
            Paragraph(f"<font size='8' color='#7F8C8D'>{title}</font>", styles["center"]),
            Paragraph(f"<font size='14' color='{color}'><b>{value}</b></font>", styles["center"]),
            Paragraph(f"<font size='9'>{unit}</font>", styles["center"]),
        ]
        if subtitle:
            card_content.append(
                Paragraph(f"<font size='7' color='#95A5A6'>{subtitle}</font>", styles["center"])
            )
        card_table = Table([[card_content]], colWidths=[42 * mm])
        card_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8F9FA")),
                    ("BOX", (0, 0), (-1, -1), 1, HexColor(color)),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return card_table

    # Alpha-1 classification
    if mean_alpha1 is not None:
        if mean_alpha1 > 0.75:
            a1_color = "#27AE60"
            a1_zone = "Aerobowa (Z1-Z2)"
        elif mean_alpha1 > 0.5:
            a1_color = "#F39C12"
            a1_zone = "Przejściowa (Z3)"
        else:
            a1_color = "#E74C3C"
            a1_zone = "Anaerobowa (Z4-Z5)"
        a1_val = f"{mean_alpha1:.2f}"
    else:
        a1_color = "#808080"
        a1_zone = "brak danych"
        a1_val = "n/a"

    # RMSSD classification
    if mean_rmssd is not None:
        if mean_rmssd > 50:
            rmssd_color = "#27AE60"
            rmssd_interp = "Wysoka"
        elif mean_rmssd > 20:
            rmssd_color = "#F39C12"
            rmssd_interp = "Umiarkowana"
        else:
            rmssd_color = "#E74C3C"
            rmssd_interp = "Niska"
        rmssd_val = f"{mean_rmssd:.0f}"
    else:
        rmssd_color = "#808080"
        rmssd_interp = "brak"
        rmssd_val = "n/a"

    # SDNN
    sdnn_val = f"{mean_sdnn:.0f}" if mean_sdnn is not None else "n/a"
    sdnn_color = "#3498DB"

    # Quality grade color
    grade_colors = {"A": "#27AE60", "B": "#2ECC71", "C": "#F39C12", "D": "#E74C3C", "F": "#C0392B"}
    grade_color = grade_colors.get(quality_grade, "#808080")

    card1 = _hrv_card("DFA Alpha-1", a1_val, "fraktalny", a1_color, a1_zone)
    card2 = _hrv_card("RMSSD", rmssd_val, "ms", rmssd_color, rmssd_interp)
    card3 = _hrv_card("SDNN", sdnn_val, "ms", sdnn_color, "zmienność ogólna")
    card4 = _hrv_card(
        "JAKOŚĆ",
        quality_grade,
        f"({windows_count} okien)",
        grade_color,
        "niepewny" if is_uncertain else "wiarygodny",
    )

    cards_row = Table([[card1, card2, card3, card4]], colWidths=[44 * mm] * 4)
    cards_row.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(cards_row)
    elements.append(Spacer(1, 6 * mm))

    # === ZONE CLASSIFICATION TABLE ===
    elements.append(Paragraph("<b>KLASYFIKACJA STREF DFA</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    zone_table_data = [
        ["Strefa", "Alpha-1", "Opis fizjologiczny", "Zastosowanie treningowe"],
        [
            "Z1-Z2 Aerobowa",
            "> 0.75",
            "Korelacje fraktalne zachowane, dominacja parasympatyczna",
            "Treningi bazowe, recovery, długie Z2",
        ],
        [
            "Z3 Przejściowa",
            "0.50 - 0.75",
            "Utrata korelacji, równowaga sympatyczna/parasympatyczna",
            "Tempo, Sweet Spot — strefa 'szarego pola'",
        ],
        [
            "Z4-Z5 Anaerobowa",
            "< 0.50",
            "Korelacje antypersystentne, dominacja sympatyczna",
            "VO₂max interwały, powtórzenia ponadprogowe",
        ],
    ]

    zt = Table(zone_table_data, colWidths=[30 * mm, 22 * mm, 55 * mm, 55 * mm])
    zt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1F77B4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
                ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
                ("ROWHEIGHT", (0, 0), (-1, -1), 12 * mm),
                ("BACKGROUND", (0, 1), (-1, 1), HexColor("#d5f5e3")),
                ("BACKGROUND", (0, 2), (-1, 2), HexColor("#fdebd0")),
                ("BACKGROUND", (0, 3), (-1, 3), HexColor("#fadbd8")),
            ]
        )
    )
    elements.append(zt)
    elements.append(Spacer(1, 6 * mm))

    # === QUALITY WARNINGS ===
    if quality_reasons:
        elements.append(Paragraph("<b>UWAGI DOTYCZĄCE JAKOŚCI</b>", styles["subheading"]))
        elements.append(Spacer(1, 2 * mm))
        for reason in quality_reasons[:4]:
            elements.append(
                Paragraph(f"<font size='8' color='#E74C3C'>• {reason}</font>", styles["body"])
            )
        elements.append(Spacer(1, 4 * mm))

    # === INTERPRETATION ===
    if mean_alpha1 is not None:
        if mean_alpha1 > 0.75:
            interp_text = (
                "<b>DOMINACJA AEROBOWA (Alpha-1 > 0.75)</b><br/>"
                "Przeciętna wartość Alpha-1 wskazuje na dominację metabolizmu tlenowego. "
                "Układ autonomiczny jest dobrze zbalansowany. Trening bazowy (Z1-Z2) jest optymalny — "
                "moment na budowanie objętości i gęstości mitochondriów."
            )
            interp_color = "#27AE60"
        elif mean_alpha1 > 0.5:
            interp_text = (
                "<b>STREFA PRZEJŚCIOWA (Alpha-1 0.50-0.75)</b><br/>"
                "Przeciętna wartość Alpha-1 odpowiada strefie progu aerobowego (HRVT1). "
                "Jest to 'szare pole' — system glikolizowy jest aktywny, ale nie dominuje. "
                "Odpowiada to pracy Tempo/Sweet Spot."
            )
            interp_color = "#F39C12"
        else:
            interp_text = (
                "<b>DOMINACJA ANAEROBOWA (Alpha-1 < 0.50)</b><br/>"
                "Przeciętna wartość Alpha-1 wskazuje na intensywność powyżej HRVT2. "
                "Układ sympatyczny dominuje. Ten zakres odpowiada pracy VO₂max / Z4-Z5."
            )
            interp_color = "#E74C3C"

        white_style = ParagraphStyle(
            "hrv_interp", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9
        )
        interp_box = Table([[Paragraph(interp_text, white_style)]], colWidths=[165 * mm])
        interp_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor(interp_color)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(interp_box)
        elements.append(Spacer(1, 6 * mm))

    # === REFERENCES ===
    elements.append(
        Paragraph(
            "<font size='7' color='#95A5A6'><i>"
            "Ref: Mateo-March et al. 2024 — HRVT1 ICC=0.87, HRVT2 ICC=0.97. "
            "Iannetta et al. 2024 — DFA-a1 reliability ICC=0.76-0.86. "
            "Rogers et al. 2023 — validated in female cyclists. "
            "Cassirame et al. 2025 — SNR and motion artifact concerns."
            "</i></font>",
            styles["body"],
        )
    )

    return elements


# ============================================================================
# PAGE: SKIN TEMPERATURE GRADIENT (CORE − SKIN)
# ============================================================================


def build_page_skin_temp(
    thermo_data: Dict[str, Any], time_series: Dict[str, Any], styles: Dict
) -> List:
    """Build Skin Temperature Gradient analysis section.

    Displays core-skin temperature gradient as indicator of
    thermoregulatory efficiency (Périard et al. 2021).
    """

    elements = []

    elements.append(
        Paragraph(
            f"<font size='14'>{section_no('4.4')} GRADIENT TEMPERATURY (RDZEŃ − SKÓRA)</font>", styles["center"]
        )
    )
    elements.append(
        Paragraph(
            "<font size='10' color='#7F8C8D'>Efektywność chłodzenia — Périard et al. 2021</font>",
            styles["center"],
        )
    )
    elements.append(Spacer(1, 6 * mm))

    elements.append(
        Paragraph(
            "Gradient core-skin (ΔT = T<sub>core</sub> − T<sub>skin</sub>) jest wskaźnikiem "
            "efektywności termoregulacji. Wysoki gradient (>3°C) oznacza skuteczne chłodzenie — "
            "ciepło jest efektywnie odprowadzane z rdzenia do skóry. Spadek gradientu poniżej 2°C "
            "sygnalizuje, że skóra nie nadąża z chłodzeniem lub warunki otoczenia ograniczają konwekcję.",
            styles["body"],
        )
    )
    elements.append(Spacer(1, 4 * mm))

    # Extract time series data
    core_temps = time_series.get("core_temp", [])
    skin_temps = time_series.get("skin_temp", [])

    if not core_temps or not skin_temps or len(core_temps) < 10:
        elements.append(
            Paragraph(
                "<font color='#E74C3C'><b>Brak wystarczających danych temperatury skóry i/lub rdzenia.</b></font>",
                styles["body"],
            )
        )
        return elements

    import numpy as np

    core_arr = np.array(core_temps, dtype=float)
    skin_arr = np.array(skin_temps, dtype=float)

    # Filter valid values
    valid_mask = (core_arr > 35) & (core_arr < 42) & (skin_arr > 25) & (skin_arr < 40)
    if np.sum(valid_mask) < 10:
        elements.append(
            Paragraph(
                "<font color='#E74C3C'><b>Zbyt mało prawidłowych pomiarów temperatury.</b></font>",
                styles["body"],
            )
        )
        return elements

    core_valid = core_arr[valid_mask]
    skin_valid = skin_arr[valid_mask]
    gradient = core_valid - skin_valid

    # Metrics
    grad_start = float(np.mean(gradient[:30])) if len(gradient) > 30 else float(gradient[0])
    grad_end = float(np.mean(gradient[-30:])) if len(gradient) > 30 else float(gradient[-1])
    grad_min = float(np.min(gradient))
    float(np.max(gradient))
    grad_mean = float(np.mean(gradient))
    grad_delta = grad_end - grad_start

    # Classification
    if grad_mean > 3.0:
        class_label = "EFEKTYWNE CHŁODZENIE"
        class_color = "#27AE60"
        class_desc = (
            "Gradient >3°C — termoregulacja skuteczna. Ciepło jest efektywnie "
            "odprowadzane z rdzenia do skóry i dalej do otoczenia."
        )
    elif grad_mean > 2.0:
        class_label = "UMIARKOWANE CHŁODZENIE"
        class_color = "#F39C12"
        class_desc = (
            "Gradient 2-3°C — chłodzenie obecne, ale nie optymalne. "
            "W warunkach ciepłych (>28°C) może dojść do kumulacji ciepła."
        )
    else:
        class_label = "OGRANICZONE CHŁODZENIE"
        class_color = "#E74C3C"
        class_desc = (
            "Gradient <2°C — chłodzenie niewystarczające. Skóra jest blisko temperatury "
            "rdzenia, co ogranicza odprowadzanie ciepła. Ryzyko przegrzania."
        )

    # === KEY METRICS TABLE ===
    elements.append(Paragraph("<b>KLUCZOWE METRYKI</b>", styles["subheading"]))
    elements.append(Spacer(1, 2 * mm))

    metrics_data = [
        ["Metryka", "Wartość", "Interpretacja"],
        ["Gradient start", f"{grad_start:.1f} °C", "Początkowy gradient (pierwsze 30s)"],
        ["Gradient koniec", f"{grad_end:.1f} °C", "Końcowy gradient (ostatnie 30s)"],
        ["Gradient średni", f"{grad_mean:.1f} °C", class_label],
        ["Gradient min", f"{grad_min:.1f} °C", "Najwęższy punkt chłodzenia"],
        ["Zmiana gradientu", f"{grad_delta:+.1f} °C", "Spadek = pogorszenie chłodzenia"],
    ]

    mt = Table(metrics_data, colWidths=[40 * mm, 30 * mm, 95 * mm])
    mt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1F77B4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
                ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "DejaVuSans-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#555555")),
                ("ROWHEIGHT", (0, 0), (-1, -1), 10 * mm),
                ("BACKGROUND", (0, 3), (-1, 3), HexColor(class_color)),
                ("TEXTCOLOR", (0, 3), (-1, 3), HexColor("#FFFFFF")),
            ]
        )
    )
    elements.append(mt)
    elements.append(Spacer(1, 6 * mm))

    # === CLASSIFICATION VERDICT ===
    white_style = ParagraphStyle(
        "skin_verdict", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9
    )
    verdict_box = Table(
        [[Paragraph(f"<b>{class_label}</b><br/>{class_desc}", white_style)]], colWidths=[165 * mm]
    )
    verdict_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(class_color)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(verdict_box)
    elements.append(Spacer(1, 6 * mm))

    # === TRAINING IMPLICATIONS (folded into consolidated plan when compact) ===
    show_implications = not is_compact()
    if show_implications:
        elements.append(Paragraph("<b>IMPLIKACJE TRENINGOWE</b>", styles["subheading"]))
        elements.append(Spacer(1, 2 * mm))

    if grad_mean > 3.0:
        recs = [
            "Termoregulacja nie jest limiterem — kontynuuj intensywny trening w normalnych warunkach",
            "Przy starcie w gorącu (>30°C): pre-cooling kamizelka + zimny napój jako dodatkowe zabezpieczenie",
            "Monitoruj gradient w treningach >2h — nawet dobra termoregulacja może się wyczerpać",
        ]
    elif grad_mean > 2.0:
        recs = [
            "Heat acclimation: 7-10 dni, 60min @ Z2 w ubraniu izolacyjnym lub temp. >28°C",
            "Chłodzenie aktywne: woda na kark/głowę co 10-15min w treningach >90min",
            "Preferuj poranne sesje (6-9) latem — niższa temperatura otoczenia = lepszy gradient",
            "Nawodnienie: 500-750ml/h + 500mg Na+/h — odwodnienie pogarsza gradient",
        ]
    else:
        recs = [
            "PILNE: Heat acclimation 10-14 dni, 60-90min @ Z2 w kontrolowanym cieple",
            "Pre-cooling obowiązkowe: kamizelka lodowa 20min + 500ml zimnego napoju przed startem",
            "Unikaj intensywnych sesji (>Z3) w temp. >25°C do czasu poprawy gradientu",
            "Diagnostyka: sprawdź nawodnienie (waga przed/po), sprawdź odzież treningową (wentylacja)",
            "Sauna post-trening: 15-20min × 3-4×/tydz. — wspomaganie adaptacji cieplnej",
        ]

    white_rec_style = ParagraphStyle(
        "rec_skin", parent=styles["body"], textColor=HexColor("#FFFFFF"), fontSize=9
    )
    rec_data = [[Paragraph(f"• {rec}", white_rec_style)] for rec in recs]
    rec_table = Table(rec_data, colWidths=[165 * mm])
    rec_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#16213e")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    if show_implications:
        elements.append(rec_table)
        elements.append(Spacer(1, 6 * mm))

    # === REFERENCE ===
    elements.append(
        Paragraph(
            "<font size='7' color='#95A5A6'><i>"
            "Ref: Périard et al. 2021 — Core-skin gradient as thermoregulatory efficiency marker. "
            "Racinais et al. 2019 — Heat acclimation improves gradient by 0.5-1.0°C. "
            "Tyler et al. 2015 — Pre-cooling effects on core-skin differential."
            "</i></font>",
            styles["body"],
        )
    )

    return elements


# ============================================================================
# PAGE: ALTITUDE / ENVIRONMENTAL ADJUSTMENT
# ============================================================================
