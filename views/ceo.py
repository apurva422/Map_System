"""
views/ceo.py
============
CEO / Business Head view — read-only across the entire organisation.

Pages (driven by sidebar.py → current_page session key)
---------------------------------------------------------
  dashboard   → Summary metrics + 4 Plotly charts (Critical)
  all_plans   → Full filterable read-only table — browse only, no downloads
  export      → Format selector + download buttons (CSV / Excel / PDF)

FIX LOG
-------
  v2: PDF was blank because export_df columns were renamed before being
      passed to generate_report(). _build_pdf in export_utils.py maps raw
      column names (e.g. "manager_name") to display headers internally.
      Renaming before the call meant no columns matched → blank table.
      Fix: pass raw column names to generate_report; rename only for display.

  v2: All Plans and Export pages were functionally identical.
      All Plans is now a pure browse-only page (no download buttons).
      Export is a focused Step 1/2/3 download flow with a compact preview.

  v2: Bar chart value labels were clipped by chart boundary.
      Fixed in dashboard_charts.py by adding y-axis range headroom.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from auth import get_current_user
from database.supabase_client import get_service_client
from components.sidebar import get_current_page
from components.dashboard_charts import (
    chart_plans_by_zone,
    chart_plans_by_function,
    chart_wef_distribution,
    chart_status_distribution,
    summary_metrics_strip,
)
from utils.export_utils import generate_report


# ── WEF element lookup ────────────────────────────────────────────────────────

_WEF_LABELS: dict[int, str] = {
    1:  "Q1 · Clear Expectations",
    2:  "Q2 · Right Materials & Equipment",
    3:  "Q3 · Do Best Work Daily",
    4:  "Q4 · Recognition & Praise",
    5:  "Q5 · Manager Cares",
    6:  "Q6 · Development Encouraged",
    7:  "Q7 · Opinions Count",
    8:  "Q8 · Mission & Purpose",
    9:  "Q9 · Quality Colleagues",
    10: "Q10 · Best Friend at Work",
    11: "Q11 · Progress Conversations",
    12: "Q12 · Learn & Grow",
}


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _load_all_plans() -> pd.DataFrame:
    """
    Fetch every action plan + the corresponding manager name.
    Cached for 60 s to avoid hammering Supabase on every rerun.
    """
    try:
        client = get_service_client()

        plans_res = (
            client
            .from_("action_plans")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        if not plans_res.data:
            return pd.DataFrame()

        df = pd.DataFrame(plans_res.data)

        emp_res = (
            client
            .from_("employees")
            .select("id, name")
            .execute()
        )
        emp_map: dict[str, str] = {}
        if emp_res.data:
            emp_map = {row["id"]: row["name"] for row in emp_res.data}

        df["manager_name"] = df["manager_id"].map(emp_map).fillna("Unknown")
        df["wef_label"]    = df["wef_element"].map(_WEF_LABELS).fillna(
            df["wef_element"].astype(str)
        )

        for col in ("start_date", "target_date", "created_at", "updated_at"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime(
                    "%d %b %Y"
                )

        return df

    except Exception as exc:
        st.error(f"Failed to load action plans: {exc}")
        return pd.DataFrame()


def _refresh() -> None:
    _load_all_plans.clear()
    st.rerun()


# ── Filter helpers ────────────────────────────────────────────────────────────

def _multiselect_filter(
    df: pd.DataFrame, col: str, label: str, key: str,
) -> pd.DataFrame:
    if col not in df.columns or df.empty:
        return df
    options = sorted(df[col].dropna().unique().tolist())
    chosen  = st.multiselect(label, options, key=key)
    if chosen:
        df = df[df[col].isin(chosen)]
    return df


def _build_filter_bar(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        df = _multiselect_filter(df, "zone",        "Zone",            f"{prefix}_zone")
    with c2:
        df = _multiselect_filter(df, "function",    "Function",        f"{prefix}_func")
    with c3:
        df = _multiselect_filter(df, "status",      "Status",          f"{prefix}_status")
    with c4:
        df = _multiselect_filter(df, "wef_element", "WEF Element (#)", f"{prefix}_wef")
    return df


# ── Column definitions ────────────────────────────────────────────────────────

# Screen display uses wef_label (human-readable); export uses wef_element (int)
_DISPLAY_COLUMNS = [
    "manager_name", "zone", "function", "wef_label",
    "title", "status", "start_date", "target_date", "created_at",
]

# CRITICAL: these must match the raw DB column names that _build_pdf in
# export_utils.py expects. Do NOT rename before passing to generate_report().
_EXPORT_COLUMNS = [
    "manager_name", "zone", "function", "wef_element",
    "title", "status", "start_date", "target_date",
]

_DISPLAY_HEADERS = {
    "manager_name": "Manager",
    "zone":         "Zone",
    "function":     "Function",
    "wef_label":    "WEF Element",
    "title":        "Title",
    "status":       "Status",
    "start_date":   "Start",
    "target_date":  "Target",
    "created_at":   "Created",
}


# ── Table renderer (screen only) ──────────────────────────────────────────────

def _render_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No action plans match the selected filters.")
        return

    cols_avail = [c for c in _DISPLAY_COLUMNS if c in df.columns]
    display_df = df[cols_avail].rename(columns=_DISPLAY_HEADERS)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status":      st.column_config.TextColumn(width="small"),
            "WEF Element": st.column_config.TextColumn(width="medium"),
            "Title":       st.column_config.TextColumn(width="large"),
        },
    )
    st.caption(f"Showing **{len(df)}** record(s)")


# ── Export buttons ────────────────────────────────────────────────────────────

def _render_export_buttons(df: pd.DataFrame, label_prefix: str = "ceo") -> None:
    """
    Render CSV / Excel / PDF download buttons.

    IMPORTANT: raw column names (e.g. "manager_name") are passed to
    generate_report() so that _build_pdf can match them against _PDF_COLUMNS.
    Renaming before this call causes the PDF table to be blank because
    _build_pdf iterates over _PDF_COLUMNS looking for "manager_name" etc.
    """
    if df.empty:
        st.info("No data to export.")
        return

    export_cols = [c for c in _EXPORT_COLUMNS if c in df.columns]
    export_df   = df[export_cols].copy()   # raw column names — do NOT rename

    filename = "MAP_All_ActionPlans_CEO"

    c1, c2, c3 = st.columns(3)

    with c1:
        csv_bytes = generate_report(export_df, "CSV", filename)
        if csv_bytes:
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_bytes,
                file_name=f"{filename}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"{label_prefix}_csv",
            )

    with c2:
        xlsx_bytes = generate_report(export_df, "Excel", filename)
        if xlsx_bytes:
            st.download_button(
                label="⬇️ Download Excel",
                data=xlsx_bytes,
                file_name=f"{filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"{label_prefix}_xlsx",
            )

    with c3:
        try:
            pdf_bytes = generate_report(export_df, "PDF", filename)
            if pdf_bytes:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"{filename}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"{label_prefix}_pdf",
                )
        except Exception as exc:
            st.error(f"PDF generation failed: {exc}")


# ── Page: Dashboard ───────────────────────────────────────────────────────────

def _page_dashboard(df: pd.DataFrame) -> None:
    user = get_current_user()
    st.markdown(
        f"### 📊 Leadership Dashboard"
        f"<span style='font-size:0.85rem;color:#6B7280;margin-left:1rem;'>"
        f"Welcome, {user.get('name', '')} · Organisation-wide view"
        f"</span>",
        unsafe_allow_html=True,
    )

    col_refresh, _ = st.columns([1, 8])
    with col_refresh:
        if st.button("🔄 Refresh", key="ceo_refresh"):
            _refresh()

    st.divider()
    summary_metrics_strip(df)
    st.divider()

    if df.empty:
        st.info(
            "No Action Plans found yet. "
            "Once managers create plans, the charts will populate here."
        )
        return

    # Row 1 — Zone + Function
    st.markdown("#### Plan Distribution")
    col_left, col_right = st.columns(2)
    with col_left:
        fig_zone = chart_plans_by_zone(df)
        if fig_zone:
            st.plotly_chart(fig_zone, use_container_width=True, key="ceo_zone_chart")
    with col_right:
        fig_func = chart_plans_by_function(df)
        if fig_func:
            st.plotly_chart(fig_func, use_container_width=True, key="ceo_func_chart")

    st.divider()

    # Row 2 — WEF + Status donut
    st.markdown("#### Engagement Framework & Progress")
    col_wef, col_status = st.columns([3, 2])
    with col_wef:
        fig_wef = chart_wef_distribution(df)
        if fig_wef:
            st.plotly_chart(fig_wef, use_container_width=True, key="ceo_wef_chart")
    with col_status:
        fig_status = chart_status_distribution(df)
        if fig_status:
            st.plotly_chart(fig_status, use_container_width=True, key="ceo_status_chart")

    st.divider()
    with st.expander("📋 Recent Plans Snapshot (latest 10)", expanded=False):
        _render_table(df.head(10))
        st.caption("Navigate to **All Plans** for the full filterable table.")


# ── Page: All Plans (browse-only — no download buttons) ───────────────────────

def _page_all_plans(df: pd.DataFrame) -> None:
    """
    Pure read-only browse page.
    No download buttons — use the Export page for that.
    This keeps the two pages distinct: browse here, download there.
    """
    st.markdown("### 📋 All Action Plans — Read Only")
    st.caption(
        "Browse and filter every Action Plan across the organisation. "
        "To download data, use **📤 Export** in the sidebar."
    )
    st.divider()

    df_filtered = _build_filter_bar(df, prefix="ceo_all")
    st.divider()
    _render_table(df_filtered)

    if not df_filtered.empty:
        st.markdown(
            "<div style='text-align:right;margin-top:0.5rem;'>"
            "<small style='color:#6B7280;'>Need to download? "
            "Use 📤 <strong>Export</strong> in the sidebar.</small></div>",
            unsafe_allow_html=True,
        )


# ── Page: Export (step-by-step download flow) ─────────────────────────────────

def _page_export(df: pd.DataFrame) -> None:
    """
    Focused download page — filter → compact preview → download.
    No full table browser (that's All Plans).
    """
    st.markdown("### 📤 Export Action Plans")
    st.caption(
        "Filter the dataset, confirm the preview, then download in your format."
    )
    st.divider()

    # Step 1 — Filter
    st.markdown("**Step 1 — Filter** *(optional)*")
    df_filtered = _build_filter_bar(df, prefix="ceo_export")

    st.divider()

    # Step 2 — Preview (5 rows max)
    record_count = len(df_filtered)
    st.markdown(
        f"**Step 2 — Preview** &nbsp;"
        f"<span style='color:#6B7280;font-size:0.85rem;'>"
        f"{record_count} record(s) will be exported</span>",
        unsafe_allow_html=True,
    )

    if df_filtered.empty:
        st.info("No records match the selected filters. Adjust the filters above.")
        return

    preview_cols = [c for c in _DISPLAY_COLUMNS if c in df_filtered.columns]
    preview_df   = df_filtered[preview_cols].head(5).rename(columns=_DISPLAY_HEADERS)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)
    if record_count > 5:
        st.caption(
            f"_Showing first 5 of {record_count} rows. "
            "All rows are included in the downloaded file._"
        )

    st.divider()

    # Step 3 — Download
    st.markdown("**Step 3 — Download**")
    _render_export_buttons(df_filtered, label_prefix="ceo_export_dl")


# ── Entry point ───────────────────────────────────────────────────────────────

def render() -> None:
    """Called by app.py's role router when role == 'CEO'."""
    df   = _load_all_plans()
    page = get_current_page()

    if page == "dashboard":
        _page_dashboard(df)
    elif page == "all_plans":
        _page_all_plans(df)
    elif page == "export":
        _page_export(df)
    else:
        _page_dashboard(df)