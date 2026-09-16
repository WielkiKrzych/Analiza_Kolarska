"""Summary PDF gets the same VT/SmO2 detections as the Summary tab (HR/VE were always '-')."""

import io

import pypdf

from modules.reporting.pdf.summary_pdf import generate_summary_pdf
from modules.ui.summary import detect_session_thresholds


def _vt1_row(pdf_bytes):
    """Cells after the VT1 label; pypdf puts every table cell on its own line."""
    text = "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)
    lines = text.splitlines()
    start = lines.index("VT1 (Próg Tlenowy)") + 1
    return lines[start : start + 5]


def test_pdf_threshold_table_has_heart_rate_and_ventilation(synthetic_ramp_df):
    df = synthetic_ramp_df
    threshold_result, smo2_result = detect_session_thresholds(df, cp_input=280)

    pdf = generate_summary_pdf(
        df, {}, 280, 20000, 75.0, 220, 290, 220, 290,
        threshold_result, smo2_result, "ramp.csv",
    )

    power, hr, ve, *_ = _vt1_row(pdf)
    assert power == "220 W"
    assert hr.endswith("bpm") and ve.endswith("L/min"), (hr, ve)
    assert smo2_result is not None
