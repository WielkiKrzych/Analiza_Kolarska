"""
Shared PDF layout primitives.

Leaf helpers used by every page builder — colour constants, signal-quality
language, coloured boxes, chart embedding and education blocks. Extracted from
the monolithic layout.py so page-builder modules can depend on this small file
instead of importing from (or living inside) the 5000-line layout module.

This module must stay a leaf: it may import from .styles and reportlab, but
never from .layout or any page-builder module, to keep the dependency graph
acyclic.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .styles import COLORS, MARGIN, PAGE_WIDTH, is_compact

logger = logging.getLogger("Tri_Dashboard.PDFHelpers")

# Premium color constants
PREMIUM_COLORS = {
    "navy": HexColor("#1A5276"),  # Recommendations/training
    "dark_glass": HexColor("#17252A"),  # Title page background
    "red": HexColor("#C0392B"),  # Warnings/limitations
    "green": HexColor("#27AE60"),  # Positives/strengths
    "white": HexColor("#FFFFFF"),
    "light_gray": HexColor("#BDC3C7"),
}


# ==============================================================================
# SIGNAL QUALITY LANGUAGE HELPERS
# ==============================================================================


def get_confidence_prefix(confidence: float) -> str:
    """Return empty prefix - interpretation text is self-sufficient.

    Previously added qualifiers like 'Analiza wskazuje:' but these looked
    mechanical when repeated before every line. Kept for API compatibility.
    """
    return ""


def get_confidence_suffix(confidence: float) -> str:
    """Get methodology note based on signal quality level.

    Professional phrasing - no numeric confidence exposed to end users.
    """
    return ""


def _signal_quality_label(confidence: float) -> str:
    """Convert numeric confidence to professional signal quality label."""
    if confidence >= 0.85:
        return "bardzo dobra"
    elif confidence >= 0.7:
        return "dobra"
    elif confidence >= 0.5:
        return "wystarczająca"
    else:
        return "podstawowa"


def _signal_quality_stars(confidence: float) -> str:
    """Convert numeric confidence to star rating (1-5)."""
    if confidence >= 0.9:
        stars = 5
    elif confidence >= 0.75:
        stars = 4
    elif confidence >= 0.6:
        stars = 3
    elif confidence >= 0.4:
        stars = 2
    else:
        stars = 1
    return "★" * stars + "☆" * (5 - stars)


# ==============================================================================
# PREMIUM HELPER FUNCTIONS
# ==============================================================================


def build_colored_box(text: str, styles: Dict, bg_color: str = "navy") -> List:
    """Create a colored box with text for recommendations/warnings/positives.

    Args:
        text: Text content
        styles: PDF styles dict
        bg_color: "navy", "red", or "green"

    Returns:
        List of flowables
    """
    color_map = {
        "navy": PREMIUM_COLORS["navy"],
        "red": PREMIUM_COLORS["red"],
        "green": PREMIUM_COLORS["green"],
    }
    bg = color_map.get(bg_color, PREMIUM_COLORS["navy"])

    table_data = [[Paragraph(f"<font color='white'><b>{text}</b></font>", styles["center"])]]

    box_table = Table(table_data, colWidths=[170 * mm])
    box_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 15),
                ("RIGHTPADDING", (0, 0), (-1, -1), 15),
            ]
        )
    )

    return [box_table, Spacer(1, 4 * mm)]


def build_section_description(text: str, styles: Dict) -> List:
    """Add 10pt italic description under section header.

    Args:
        text: Description text (1-2 sentences)
        styles: PDF styles dict

    Returns:
        List of flowables
    """
    desc_style = ParagraphStyle(
        "SectionDescription",
        fontName="DejaVuSans-Oblique"
        if "DejaVuSans" in str(styles.get("body", {}))
        else "Helvetica-Oblique",
        fontSize=10,
        textColor=HexColor("#7F8C8D"),
        leading=12,
        spaceAfter=4 * mm,
    )
    return [Paragraph(text, desc_style)]


def build_chapter_header(chapter_num: str, chapter_title: str, styles: Dict) -> List:
    """Build a prominent chapter header with Roman numeral.

    Args:
        chapter_num: Roman numeral (I, II, III, IV, V)
        chapter_title: Chapter title text
        styles: PDF styles dict

    Returns:
        List of flowables
    """
    elements = []

    # Chapter header with navy background
    header_content = [
        [
            Paragraph(
                f"<font color='white' size='16'><b>{chapter_num}. {chapter_title}</b></font>",
                styles["center"],
            )
        ]
    ]

    header_table = Table(header_content, colWidths=[170 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PREMIUM_COLORS["navy"]),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 6 * mm))

    return elements


def _build_chart(chart_path: str, title: str, styles: Dict, max_height_mm: int = 90) -> List:
    """Build a chart section with image.

    Args:
        chart_path: Path to chart PNG file
        title: Section title
        styles: Paragraph styles dictionary
        max_height_mm: Maximum image height in mm (default 90)

    Returns:
        List of flowables
    """
    chart_elements = []

    # Title for the chart
    chart_elements.append(Paragraph(title, styles["subheading"]))

    # 1. Check if file exists
    if not chart_path or not os.path.exists(chart_path):
        logger.warning("PDF Layout: Chart file missing for '%s' at path: %s", title, chart_path)
        chart_elements.append(Paragraph("Wykres niedostępny", styles["small"]))
        return [KeepTogether(chart_elements)]

    # 2. Embed image
    try:
        available_width = PAGE_WIDTH - 2 * MARGIN
        img = Image(chart_path)

        # Scale to fit width
        aspect = img.imageHeight / img.imageWidth
        img_width = min(available_width, 150 * mm)
        img_height = img_width * aspect

        # Limit height
        if img_height > max_height_mm * mm:
            img_height = max_height_mm * mm
            img_width = img_height / aspect

        img.drawWidth = img_width
        img.drawHeight = img_height

        chart_elements.append(img)
    except Exception as e:
        logger.error("PDF Layout: Error embedding chart '%s' from %s: %s", title, chart_path, e)

    # Wrap in KeepTogether to prevent title/chart separation across pages
    return [KeepTogether(chart_elements)]


def _build_education_block(title: str, content: str, styles: Dict) -> List:
    """Helper to build a consistent education block with 'Dlaczego to ma znaczenie?'."""
    if is_compact():
        return []
    elements = []

    # Label
    label = Paragraph("", styles["small"])  # Removed educational label
    elements.append(label)

    # Title & Text in a subtle box
    inner_story = [
        Paragraph(f"<b>{title}</b>", styles["heading"]),
        Spacer(1, 1 * mm),
        Paragraph(content, styles["body_italic"]),
    ]

    table = Table([[inner_story]], colWidths=[170 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLORS["light_grey"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, COLORS["grey"]),
                ("BOX", (0, 0), (-1, -1), 0.25, COLORS["grey"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )

    elements.append(table)
    return elements
