"""
utils/export_utils.py
=====================
Single export function called identically from HRBP, Admin, and CEO views.
Phase 8 implements the full bodies.

generate_report(df, export_format, filename, filters=None)
  → returns bytes (CSV/Excel) or file path (PDF)
"""

import io
import pandas as pd


def generate_report(
    df: pd.DataFrame,
    export_format: str,   # "CSV" | "Excel" | "PDF"
    filename: str,
    filters: dict | None = None,
) -> bytes | str | None:
    """
    Phase 8 will implement:
      CSV   → df.to_csv()
      Excel → df.to_excel() via openpyxl
      PDF   → fpdf2 table render
    """
    if export_format == "CSV":
        return df.to_csv(index=False).encode("utf-8")

    if export_format == "Excel":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Action Plans")
        return buf.getvalue()

    if export_format == "PDF":
        # Full fpdf2 implementation in Phase 8
        return None

    return None