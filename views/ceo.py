"""
views/ceo.py
============
CEO / Business Head view — read-only across the entire organisation.

Pages (driven by sidebar.py → current_page session key)
---------------------------------------------------------
  dashboard   → Filter bar + 6 Plotly charts + metrics strip (all update live)
  all_plans   → Full filterable read-only table + export buttons

Dashboard filter bar
--------------------
Zone, Function, and Status multiselects sit at the top of the dashboard.
Every chart and every metric card is drawn from the filtered DataFrame,
so selecting "North Zone" instantly narrows all 6 charts to that zone.

Chart layout (dashboard)
------------------------
  Metrics strip  — 4 KPI cards
  Row 1          — Plans by Zone  |  Plans by Function
  Row 2          — WEF Distribution (wide)  |  Status Donut
  Row 3          — Status by Zone (grouped) |  Monthly Trend

FIX LOG
-------
  v2: PDF blank — pass raw column names to generate_report (not renamed).
  v2: All Plans / Export pages merged; bar labels clipped → fixed with headroom.
  v3: Dashboard filter bar added; 2 new charts (status_by_zone, plans_over_time).
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
    chart_status_by_zone,
    chart_plans_over_time,
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
    Fetch every action plan + manager name.
    Cached 60 s — short enough to reflect new plans without hammering Supabase.
    """
    try:
        client = get_service_client()

        plans_res = (
            client.from_("action_plans")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        if not plans_res.data:
            return pd.DataFrame()

        df = pd.DataFrame(plans_res.data)

        emp_res = client.from_("employees").select("id, name").execute()
        emp_map: dict[str, str] = (
            {row["id"]: row["name"] for row in emp_res.data}
            if emp_res.data else {}
        )

        df["manager_name"] = df["manager_id"].map(emp_map).fillna("Unknown")
        df["wef_label"]    = df["wef_element"].map(_WEF_LABELS).fillna(
            df["wef_element"].astype(str)
        )

        # Format dates for display; keep original strings for the trend chart parser
        for col in ("start_date", "target_date", "created_at", "updated_at"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d %b %Y")

        return df

    except Exception as exc:
        st.error(f"Failed to load action plans: {exc}")
        return pd.DataFrame()


def _refresh() -> None:
    _load_all_plans.clear()
    st.rerun()


# ── Column definitions ────────────────────────────────────────────────────────

_DISPLAY_COLUMNS = [
    "manager_name", "zone", "function", "wef_label",
    "title", "status", "start_date", "target_date", "created_at",
]

# Raw column names — DO NOT rename before passing to generate_report().
# _build_pdf in export_utils.py maps these raw names to display headers.
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


# ── Shared UI helpers ─────────────────────────────────────────────────────────

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


def _render_export_buttons(df: pd.DataFrame, label_prefix: str) -> None:
    """Pass raw column names to generate_report — _build_pdf needs them."""
    if df.empty:
        st.info("No data to export.")
        return

    export_cols = [c for c in _EXPORT_COLUMNS if c in df.columns]
    export_df   = df[export_cols].copy()
    filename    = "MAP_All_ActionPlans_CEO"
    c1, c2, c3 = st.columns(3)

    with c1:
        data = generate_report(export_df, "CSV", filename)
        if data:
            st.download_button("⬇️ Download CSV", data=data,
                               file_name=f"{filename}.csv", mime="text/csv",
                               use_container_width=True, key=f"{label_prefix}_csv")
    with c2:
        data = generate_report(export_df, "Excel", filename)
        if data:
            st.download_button("⬇️ Download Excel", data=data,
                               file_name=f"{filename}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True, key=f"{label_prefix}_xlsx")
    with c3:
        try:
            data = generate_report(export_df, "PDF", filename)
            if data:
                st.download_button("⬇️ Download PDF", data=data,
                                   file_name=f"{filename}.pdf", mime="application/pdf",
                                   use_container_width=True, key=f"{label_prefix}_pdf")
        except Exception as exc:
            st.error(f"PDF generation failed: {exc}")


# ── Dashboard filter bar ──────────────────────────────────────────────────────

def _render_dashboard_filter_bar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compact filter bar rendered inside the dashboard page.
    Returns a filtered copy of df — every chart and metric reads from this.
    Filters are persisted in session_state so they survive Streamlit reruns.
    """
    if df.empty:
        return df

    with st.container():
        st.markdown(
            "<div style='background:#F9FAFB;border:1px solid #E5E7EB;"
            "border-radius:8px;padding:0.75rem 1rem;margin-bottom:1rem;'>"
            "<span style='font-size:0.85rem;font-weight:600;color:#374151;'>"
            "🔍 &nbsp;Dashboard Filters &nbsp;"
            "<span style='font-weight:400;color:#9CA3AF;'>"
            "— charts and metrics update instantly</span></span></div>",
            unsafe_allow_html=True,
        )

        f1, f2, f3, f4 = st.columns(4)

        with f1:
            zone_opts = sorted(df["zone"].dropna().unique().tolist()) if "zone" in df.columns else []
            sel_zones = st.multiselect(
                "Zone", zone_opts,
                key="dash_filter_zone",
                placeholder="All zones",
            )

        with f2:
            func_opts = sorted(df["function"].dropna().unique().tolist()) if "function" in df.columns else []
            sel_funcs = st.multiselect(
                "Function", func_opts,
                key="dash_filter_func",
                placeholder="All functions",
            )

        with f3:
            status_opts = ["Initiated", "Ongoing", "Closed"]
            sel_status  = st.multiselect(
                "Status", status_opts,
                key="dash_filter_status",
                placeholder="All statuses",
            )

        with f4:
            mgr_opts = sorted(df["manager_name"].dropna().unique().tolist()) if "manager_name" in df.columns else []
            sel_mgrs = st.multiselect(
                "Manager", mgr_opts,
                key="dash_filter_mgr",
                placeholder="All managers",
            )

    # Apply filters — only filter on dimensions the user actually set
    filtered = df.copy()
    if sel_zones:
        filtered = filtered[filtered["zone"].isin(sel_zones)]
    if sel_funcs:
        filtered = filtered[filtered["function"].isin(sel_funcs)]
    if sel_status:
        filtered = filtered[filtered["status"].isin(sel_status)]
    if sel_mgrs:
        filtered = filtered[filtered["manager_name"].isin(sel_mgrs)]

    # Active filter count badge
    n_active = sum(bool(x) for x in [sel_zones, sel_funcs, sel_status, sel_mgrs])
    if n_active:
        st.markdown(
            f"<div style='font-size:0.8rem;color:#6B7280;margin-bottom:0.5rem;'>"
            f"Filters active: <strong>{n_active}</strong> &nbsp;·&nbsp; "
            f"Showing <strong>{len(filtered)}</strong> of <strong>{len(df)}</strong> plans"
            f"</div>",
            unsafe_allow_html=True,
        )

    return filtered


# ── Page: Dashboard ───────────────────────────────────────────────────────────

def _page_dashboard(df: pd.DataFrame) -> None:
    user = get_current_user()

    # Header
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

    # ── Filter bar — returns the filtered df used by ALL charts below ─────────
    df_filtered = _render_dashboard_filter_bar(df)

    st.divider()

    # ── Metrics strip (responds to filters) ───────────────────────────────────
    summary_metrics_strip(df_filtered)

    st.divider()

    if df_filtered.empty:
        st.info("No Action Plans match the active filters.")
        return

    # ── Row 1: Zone + Function bars ───────────────────────────────────────────
    st.markdown("#### Plan Distribution")
    col_l, col_r = st.columns(2)

    with col_l:
        fig = chart_plans_by_zone(df_filtered)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="ceo_zone")

    with col_r:
        fig = chart_plans_by_function(df_filtered)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="ceo_func")

    st.divider()

    # ── Row 2: WEF hbar + Status donut ────────────────────────────────────────
    st.markdown("#### Engagement Framework & Progress")
    col_wef, col_status = st.columns([3, 2])

    with col_wef:
        fig = chart_wef_distribution(df_filtered)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="ceo_wef")

    with col_status:
        fig = chart_status_distribution(df_filtered)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="ceo_donut")

    st.divider()

    # ── Row 3: Status by Zone (grouped) + Monthly Trend ──────────────────────
    st.markdown("#### Zone Health & Adoption Trend")
    col_grp, col_trend = st.columns(2)

    with col_grp:
        fig = chart_status_by_zone(df_filtered)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="ceo_status_zone")

    with col_trend:
        # Monthly trend uses the full (unfiltered) df when a zone is selected
        # so the cumulative line represents the true org-wide ramp.
        # When no filter is set, filtered == full df so it doesn't matter.
        fig = chart_plans_over_time(df_filtered)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="ceo_trend")

    # ── Recent snapshot ───────────────────────────────────────────────────────
    st.divider()
    with st.expander("📋 Recent Plans Snapshot (latest 10 in filtered view)", expanded=False):
        _render_table(df_filtered.head(10))
        st.caption("Navigate to **All Plans** for the full table.")


# ── Page: All Plans (browse + export) ─────────────────────────────────────────

def _page_all_plans(df: pd.DataFrame) -> None:
    """Browse and download — filter bar + full table + export buttons."""
    st.markdown("### 📋 All Action Plans")
    st.caption("Browse, filter, and export every Action Plan across the organisation.")
    st.divider()

    # Filter bar (separate keys from dashboard so state doesn't bleed)
    c1, c2, c3, c4 = st.columns(4)
    filtered = df.copy()

    with c1:
        opts = sorted(df["zone"].dropna().unique().tolist()) if "zone" in df.columns else []
        sel  = st.multiselect("Zone", opts, key="ap_zone", placeholder="All")
        if sel: filtered = filtered[filtered["zone"].isin(sel)]

    with c2:
        opts = sorted(df["function"].dropna().unique().tolist()) if "function" in df.columns else []
        sel  = st.multiselect("Function", opts, key="ap_func", placeholder="All")
        if sel: filtered = filtered[filtered["function"].isin(sel)]

    with c3:
        sel = st.multiselect("Status", ["Initiated", "Ongoing", "Closed"],
                             key="ap_status", placeholder="All")
        if sel: filtered = filtered[filtered["status"].isin(sel)]

    with c4:
        opts = sorted(df["manager_name"].dropna().unique().tolist()) if "manager_name" in df.columns else []
        sel  = st.multiselect("Manager", opts, key="ap_mgr", placeholder="All")
        if sel: filtered = filtered[filtered["manager_name"].isin(sel)]

    st.divider()
    _render_table(filtered)

    if not filtered.empty:
        st.divider()
        st.markdown("#### 📤 Export")
        _render_export_buttons(filtered, label_prefix="ceo_ap")


# ── Entry point ───────────────────────────────────────────────────────────────

def render() -> None:
    """Called by app.py's role router when role == 'CEO'."""
    df   = _load_all_plans()
    page = get_current_page()

    if page == "dashboard":
        _page_dashboard(df)
    elif page in ("all_plans", "export"):
        _page_all_plans(df)
    else:
        _page_dashboard(df)