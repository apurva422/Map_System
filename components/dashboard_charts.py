"""Plotly chart functions for CEO dashboard (and optionally admin)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# Design tokens

_BRAND_BLUE   = "#2E75B6"
_BRAND_GREY   = "#E5E7EB"

_STATUS_COLOURS = {
    "Initiated": "#9CA3AF",
    "Ongoing":   "#F59E0B",
    "Closed":    "#10B981",
}

_BAR_PALETTE = [
    "#2E75B6", "#7030A0", "#C55A11", "#375623",
    "#0891B2", "#DB2777", "#16A34A", "#D97706",
]

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

# Shared layout
_BASE_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="sans-serif", size=12, color="#374151"),
)


# Helpers

def _y_max(series: pd.Series) -> float:
    """Y-axis ceiling with 25% headroom."""
    m = int(series.max()) if len(series) else 1
    return max(m * 1.25, m + 1)


# 1. Plans by Zone

def chart_plans_by_zone(df: pd.DataFrame) -> go.Figure | None:
    """Bar — plans per zone."""
    if df.empty or "zone" not in df.columns:
        st.info("No zone data available.")
        return None

    counts = (
        df["zone"]
        .value_counts()
        .reset_index()
        .rename(columns={"zone": "Zone", "count": "Plans"})
        .sort_values("Plans", ascending=False)
    )

    fig = go.Figure(go.Bar(
        x=counts["Zone"],
        y=counts["Plans"],
        marker_color=(_BAR_PALETTE * 4)[: len(counts)],
        marker_line_width=0,
        text=counts["Plans"],
        textposition="outside",
        textfont=dict(size=12, color="#374151"),
        cliponaxis=False,
    ))
    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Action Plans by Zone", font=dict(size=14, color="#1A1A2E"), x=0),
        xaxis=dict(title="", tickfont=dict(size=11)),
        yaxis=dict(title="No. of Plans", gridcolor="#F3F4F6", zeroline=False,
                   range=[0, _y_max(counts["Plans"])]),
        showlegend=False,
        height=300,
        margin=dict(l=16, r=16, t=44, b=16),
    )
    return fig


# 2. Plans by Function

def chart_plans_by_function(df: pd.DataFrame) -> go.Figure | None:
    """Bar — plans per function."""
    if df.empty or "function" not in df.columns:
        st.info("No function data available.")
        return None

    counts = (
        df["function"]
        .value_counts()
        .reset_index()
        .rename(columns={"function": "Function", "count": "Plans"})
        .sort_values("Plans", ascending=False)
    )
    colours = (_BAR_PALETTE * 4)[: len(counts)]

    fig = go.Figure(go.Bar(
        x=counts["Function"],
        y=counts["Plans"],
        marker_color=colours,
        marker_line_width=0,
        text=counts["Plans"],
        textposition="outside",
        textfont=dict(size=12, color="#374151"),
        cliponaxis=False,
    ))
    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Action Plans by Function", font=dict(size=14, color="#1A1A2E"), x=0),
        xaxis=dict(title="", tickangle=-30, tickfont=dict(size=10)),
        yaxis=dict(title="No. of Plans", gridcolor="#F3F4F6", zeroline=False,
                   range=[0, _y_max(counts["Plans"])]),
        showlegend=False,
        height=300,
        margin=dict(l=16, r=16, t=44, b=16),
    )
    return fig


# 3. WEF Distribution

def chart_wef_distribution(df: pd.DataFrame) -> go.Figure | None:
    """H-bar — plans per WEF element."""
    if df.empty or "wef_element" not in df.columns:
        st.info("No WEF data available.")
        return None

    all_q  = pd.DataFrame({"wef_element": list(range(1, 13))})
    raw    = (
        df["wef_element"]
        .value_counts()
        .reset_index()
        .rename(columns={"count": "Plans"})
    )
    counts = (
        all_q
        .merge(raw, on="wef_element", how="left")
        .fillna(0)
        .astype({"Plans": int})
        .sort_values("wef_element")
    )
    counts["Label"] = counts["wef_element"].map(_WEF_LABELS)
    colours = [_BRAND_BLUE if v > 0 else _BRAND_GREY for v in counts["Plans"]]

    fig = go.Figure(go.Bar(
        y=counts["Label"],
        x=counts["Plans"],
        orientation="h",
        marker_color=colours,
        marker_line_width=0,
        text=counts["Plans"].apply(lambda v: str(v) if v > 0 else ""),
        textposition="outside",
        textfont=dict(size=11, color="#374151"),
        cliponaxis=False,
    ))
    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Distribution by WEF Element", font=dict(size=14, color="#1A1A2E"), x=0),
        xaxis=dict(title="No. of Plans", gridcolor="#F3F4F6", zeroline=False, dtick=1),
        yaxis=dict(title="", tickfont=dict(size=10), autorange="reversed"),
        showlegend=False,
        height=480,
        margin=dict(l=220, r=50, t=44, b=16),
    )
    return fig


# 4. Status Distribution (donut)

def chart_status_distribution(df: pd.DataFrame) -> go.Figure | None:
    """Donut — status breakdown."""
    if df.empty or "status" not in df.columns:
        st.info("No status data available.")
        return None

    order   = ["Initiated", "Ongoing", "Closed"]
    counts  = df["status"].value_counts()
    labels  = [s for s in order if s in counts.index]
    values  = [counts[s] for s in labels]
    colours = [_STATUS_COLOURS[s] for s in labels]
    total   = sum(values)

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colours, line=dict(color="#FFFFFF", width=3)),
        textinfo="label+percent",
        textfont=dict(size=12),
        hovertemplate="%{label}: %{value} plans (%{percent})<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{total}</b><br><span style='font-size:11px'>Total</span>",
        x=0.5, y=0.5,
        font=dict(size=18, color="#1A1A2E"),
        showarrow=False,
    )
    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Status Distribution", font=dict(size=14, color="#1A1A2E"), x=0),
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=11)),
        height=300,
        margin=dict(l=16, r=80, t=44, b=16),
    )
    return fig


# 5. Status by Zone (grouped bar)

def chart_status_by_zone(df: pd.DataFrame) -> go.Figure | None:
    """
    Grouped bar — Initiated / Ongoing / Closed count per Zone.
    Reveals which zones are lagging (lots of Initiated) vs progressing well.
    """
    if df.empty or "zone" not in df.columns or "status" not in df.columns:
        st.info("No zone/status data available.")
        return None

    order  = ["Initiated", "Ongoing", "Closed"]
    pivot  = (
        df.groupby(["zone", "status"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    # Ensure all status columns exist even if a status has 0 plans
    for s in order:
        if s not in pivot.columns:
            pivot[s] = 0

    zones  = pivot["zone"].tolist()
    fig    = go.Figure()

    for status in order:
        vals = pivot[status].tolist()
        fig.add_trace(go.Bar(
            name=status,
            x=zones,
            y=vals,
            marker_color=_STATUS_COLOURS[status],
            marker_line_width=0,
            text=vals,
            textposition="outside",
            textfont=dict(size=10, color="#374151"),
            cliponaxis=False,
        ))

    all_counts = pivot[order].values
    y_max_val  = _y_max(pd.Series(all_counts.max(axis=0).tolist()))

    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(
            text="Status Breakdown by Zone",
            font=dict(size=14, color="#1A1A2E"),
            x=0,
        ),
        barmode="group",
        xaxis=dict(title="", tickfont=dict(size=11)),
        yaxis=dict(
            title="No. of Plans",
            gridcolor="#F3F4F6",
            zeroline=False,
            range=[0, y_max_val],
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            x=0, y=-0.18,
            font=dict(size=11),
        ),
        height=340,
        margin=dict(l=16, r=16, t=44, b=40),
    )
    return fig


# 6. Plans Created Over Time (monthly line) 

def chart_plans_over_time(df: pd.DataFrame) -> go.Figure | None:
    """
    Monthly line chart — shows adoption momentum (how many plans created each month).
    Uses the raw `created_at` column before date formatting, so it must be called
    on the df returned by _load_all_plans() which has created_at as a formatted
    string like '01 Mar 2026'. We parse it back to datetime here.
    """
    if df.empty or "created_at" not in df.columns:
        st.info("No timeline data available.")
        return None

    # Parse the formatted date string back to datetime for grouping
    parsed = pd.to_datetime(df["created_at"], format="%d %b %Y", errors="coerce")
    if parsed.isna().all():
        st.info("No parseable date data for trend chart.")
        return None

    monthly = (
        parsed
        .dt.to_period("M")
        .value_counts()
        .sort_index()
        .reset_index()
    )
    monthly.columns = ["Month", "Plans"]
    monthly["MonthStr"] = monthly["Month"].astype(str)
    monthly["Cumulative"] = monthly["Plans"].cumsum()

    fig = go.Figure()

    # Monthly bars (subtle background)
    fig.add_trace(go.Bar(
        x=monthly["MonthStr"],
        y=monthly["Plans"],
        name="New this month",
        marker_color=_BRAND_BLUE,
        marker_opacity=0.25,
        marker_line_width=0,
        hovertemplate="%{x}: %{y} new plans<extra></extra>",
    ))

    # Cumulative line (primary emphasis)
    fig.add_trace(go.Scatter(
        x=monthly["MonthStr"],
        y=monthly["Cumulative"],
        name="Cumulative",
        mode="lines+markers",
        line=dict(color=_BRAND_BLUE, width=2.5),
        marker=dict(size=7, color=_BRAND_BLUE, line=dict(color="#FFFFFF", width=2)),
        hovertemplate="%{x}: %{y} total plans<extra></extra>",
    ))

    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(
            text="Plan Creation Trend (Monthly)",
            font=dict(size=14, color="#1A1A2E"),
            x=0,
        ),
        xaxis=dict(title="", tickfont=dict(size=10)),
        yaxis=dict(
            title="Plans",
            gridcolor="#F3F4F6",
            zeroline=False,
        ),
        showlegend=True,
        legend=dict(orientation="h", x=0, y=-0.2, font=dict(size=11)),
        height=300,
        margin=dict(l=16, r=16, t=44, b=40),
        hovermode="x unified",
    )
    return fig


# ── Summary metrics strip ─────────────────────────────────────────────────────

def summary_metrics_strip(df: pd.DataFrame) -> None:
    """
    Four st.metric cards — fully responds to whatever filtered df is passed in.
    Calling this with a dashboard-filtered df makes the metrics update live.
    """
    if df.empty:
        total = closed_count = pct_closed = active_zones = active_managers = 0
    else:
        total           = len(df)
        closed_count    = len(df[df["status"] == "Closed"])
        pct_closed      = round((closed_count / total) * 100) if total else 0
        active_zones    = df["zone"].nunique()    if "zone"       in df.columns else 0
        active_managers = df["manager_id"].nunique() if "manager_id" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Total Action Plans",     total)
    c2.metric("✅ Plans Closed",           f"{pct_closed}%")
    c3.metric("🗺️  Zones with Plans",       active_zones)
    c4.metric("👤 Managers Participating", active_managers)