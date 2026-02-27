"""
utils/export_utils.py
=====================
Single export function called identically from HRBP, Admin, and CEO views.

generate_report(df, export_format, filename, filters=None)
  → returns bytes (CSV / Excel / PDF)

Adding a new export format = one elif in generate_report() only.
"""

from __future__ import annotations

import io
import os
import tempfile
from datetime import datetime

import pandas as pd
from fpdf import FPDF


# ── Unicode → Latin-1 sanitizer ───────────────────────────────────────────────

def _sanitize(text: str) -> str:
    """
    Replace Unicode characters unsupported by fpdf2's built-in Helvetica
    (Latin-1 only) with safe ASCII equivalents, then hard-drop anything
    that still falls outside Latin-1.
    """
    replacements = {
        "\u2014": "-",    # em dash         —  → -
        "\u2013": "-",    # en dash         –  → -
        "\u2018": "'",    # left s-quote    '  → '
        "\u2019": "'",    # right s-quote   '  → '
        "\u201C": '"',    # left d-quote    "  → "
        "\u201D": '"',    # right d-quote   "  → "
        "\u2026": "...",  # ellipsis        …  → ...
        "\u00A0": " ",    # non-break space    → space
        "\u2022": "*",    # bullet          •  → *
        "\u00B7": ".",    # middle dot      ·  → .
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Final fallback: encode to Latin-1, replacing anything still unsupported
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ── PDF renderer ──────────────────────────────────────────────────────────────

class _ReportPDF(FPDF):
    """Custom FPDF subclass with MAP System header and footer."""

    def __init__(self, title: str = "Action Plans Report", *args, **kwargs):
        super().__init__(orientation="L", unit="mm", format="A4", *args, **kwargs)
        self._report_title = title
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(left=12, top=12, right=12)

    def header(self) -> None:
        # Orange accent bar
        self.set_fill_color(197, 90, 17)   # #C55A11
        self.rect(x=0, y=0, w=self.w, h=4, style="F")

        self.set_y(7)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(50, 50, 50)
        self.cell(
            0, 8,
            _sanitize(f"MAP System  |  {self._report_title}"),
            align="L",
        )
        self.ln(4)

        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 6,
            _sanitize(
                f"Generated: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}"
                f"  |  XYZ Industries - HR CoE"
            ),
            align="L",
        )
        self.ln(6)

        # Thin divider line
        self.set_draw_color(220, 220, 220)
        self.line(12, self.get_y(), self.w - 12, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(160, 160, 160)
        self.cell(0, 6, f"Page {self.page_no()} of {{nb}}", align="C")


# ── Column config for PDF table ───────────────────────────────────────────────

# (display_name, df_column, width_mm, align)
_PDF_COLUMNS: list[tuple[str, str, float, str]] = [
    ("Manager",  "manager_name", 35, "L"),
    ("Zone",     "zone",         25, "L"),
    ("Function", "function",     28, "L"),
    ("Q#",       "wef_element",  10, "C"),
    ("Title",    "title",        50, "L"),
    ("Status",   "status",       22, "C"),
    ("Start",    "start_date",   22, "C"),
    ("Target",   "target_date",  22, "C"),
]

_STATUS_COLOURS: dict[str, tuple[int, int, int]] = {
    "Initiated": (158, 158, 158),
    "Ongoing":   (255, 193,   7),
    "Closed":    ( 76, 175,  80),
}


def _build_pdf(df: pd.DataFrame, title: str) -> bytes:
    """Render a DataFrame as a formatted PDF table and return bytes."""
    pdf = _ReportPDF(title=_sanitize(title))
    pdf.alias_nb_pages()
    pdf.add_page()

    # Only render columns that actually exist in the DataFrame
    available = [col for col in _PDF_COLUMNS if col[1] in df.columns]

    # ── Table header row ───────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_text_color(50, 50, 50)
    pdf.set_draw_color(200, 200, 200)

    for display_name, _, width, align in available:
        pdf.cell(width, 7, _sanitize(display_name), border=1, align=align, fill=True)
    pdf.ln()

    # ── Data rows ──────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 7.5)
    fill = False

    for _, row in df.iterrows():
        # Manual page break check so rows are never split mid-row
        if pdf.get_y() + 7 > pdf.h - pdf.b_margin:
            pdf.add_page()

        for _, col_key, width, align in available:
            val  = row.get(col_key, "")
            val  = "" if val is None else val
            text = _sanitize(str(val))[:40]   # sanitize + truncate for column fit

            if col_key == "status":
                r, g, b = _STATUS_COLOURS.get(text, (200, 200, 200))
                pdf.set_text_color(r, g, b)
                pdf.set_font("Helvetica", "B", 7.5)
            else:
                pdf.set_text_color(50, 50, 50)
                pdf.set_font("Helvetica", "", 7.5)

            if fill:
                pdf.set_fill_color(248, 248, 248)
            else:
                pdf.set_fill_color(255, 255, 255)

            pdf.cell(width, 6.5, text, border=1, align=align, fill=True)

        fill = not fill
        pdf.ln()

    # ── Summary block ──────────────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Total Records: {len(df)}", align="L")

    if "status" in df.columns:
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 8)
        for status in ["Initiated", "Ongoing", "Closed"]:
            count = len(df[df["status"] == status])
            r, g, b = _STATUS_COLOURS.get(status, (100, 100, 100))
            pdf.set_text_color(r, g, b)
            pdf.cell(50, 5, f"{status}: {count}", align="L")

    return bytes(pdf.output())


# ── Public API ────────────────────────────────────────────────────────────────

def generate_report(
    df: pd.DataFrame,
    export_format: str,      # "CSV" | "Excel" | "PDF"
    filename: str,
    filters: dict | None = None,
) -> bytes | None:
    """
    Generate a report in the requested format.

    Parameters
    ----------
    df            : DataFrame to export (already filtered by caller)
    export_format : "CSV" | "Excel" | "PDF"
    filename      : used as the PDF report title and Excel sheet name
    filters       : optional metadata dict (not applied here — caller filters df)

    Returns
    -------
    bytes  for CSV, Excel, and PDF
    None   if an unsupported format is requested
    """

    if export_format == "CSV":
        return df.to_csv(index=False).encode("utf-8")

    if export_format == "Excel":
        buf   = io.BytesIO()
        sheet = (filename or "Action Plans")[:31]   # Excel sheet name limit = 31 chars
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet)
        return buf.getvalue()

    if export_format == "PDF":
        title = filename or "Action Plans Report"
        try:
            return _build_pdf(df, title)
        except Exception as exc:
            raise RuntimeError(f"PDF generation failed: {exc}") from exc

    return None


def save_temp_file(content: bytes, suffix: str) -> str:
    """
    Write bytes to a named temp file and return its path.
    Used by email_service when attaching an exported file.
    The caller is responsible for deleting the file after sending.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return tmp.name