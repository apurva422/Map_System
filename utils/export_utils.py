import io
import pandas as pd
import streamlit as st

# ── CSV ───────────────────────────────────────────────────────────────────────

def export_csv(df: pd.DataFrame, filename: str = "export.csv"):
    """Return a Streamlit download button for a CSV export."""
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv",
    )

# ── Excel ─────────────────────────────────────────────────────────────────────

def export_excel(df: pd.DataFrame, filename: str = "export.xlsx"):
    """Return a Streamlit download button for an Excel export."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    st.download_button(
        label="⬇ Download Excel",
        data=buffer.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ── PDF ───────────────────────────────────────────────────────────────────────

def export_pdf(df: pd.DataFrame, filename: str = "export.pdf", title: str = "Report"):
    """Return a Streamlit download button for a PDF export (requires reportlab)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = [Paragraph(title, styles["Title"])]

        data = [df.columns.tolist()] + df.astype(str).values.tolist()
        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ]))
        elements.append(table)
        doc.build(elements)

        st.download_button(
            label="⬇ Download PDF",
            data=buffer.getvalue(),
            file_name=filename,
            mime="application/pdf",
        )
    except ImportError:
        st.warning("PDF export requires the `reportlab` package. Run: pip install reportlab")
