"""
components/dashboard_charts.py
===============================
Reusable Plotly chart functions consumed by ceo.py (and optionally admin.py).

All functions accept a pre-filtered DataFrame and return a Plotly figure,
or call st.info() if there is no data to display.

Functions
---------
chart_plans_by_zone(df)         → Plotly bar  — Action Plans by Zone
chart_plans_by_function(df)     → Plotly bar  — Action Plans by Function
chart_wef_distribution(df)      → Plotly hbar — Distribution by WEF Element
chart_status_distribution(df)   → Plotly donut — Status Distribution
summary_metrics_strip(df)       → Renders four st.metric cards inline
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st


# ── Design tokens (match style.css palette) ───────────────────────────────────

_BRAND_BLUE    = "#2E75B6"
_BRAND_GREEN   = "#375623"
_BRAND_ORANGE  = "#C55A11"
_BRAND_PURPLE  = "#7030A0"
_BRAND_GREY    = "#E5E7EB"

_STATUS_COLOURS = {
    "Initiated": "#9CA3AF",   # grey
    "Ongoing":   "#F59E0B",   # amber
    "Closed":    "#10B981",   # green
}

# Colour sequence for zone / function bars
_BAR_PALETTE = [
    "#2E75B6", "#7030A0", "#C55A11", "#375623",
    "#0891B2", "#DB2777", "#16A34A", "#D97706",
]

# Short WEF labels for axis readability
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

_CHART_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="sans-serif", size=12, color="#374151"),
)


# ── 1. Plans by Zone ──────────────────────────────────────────────────────────

def chart_plans_by_zone(df: pd.DataFrame) -> go.Figure | None:
    """Vertical bar chart — total Action Plans per Zone."""
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

    fig = go.Figure(
        go.Bar(
            x=counts["Zone"],
            y=counts["Plans"],
            marker_color=_BAR_PALETTE[: len(counts)],
            marker_line_width=0,
            text=counts["Plans"],
            textposition="outside",
            textfont=dict(size=12, color="#374151"),
        )
    )
    fig.update_layout(
        **_CHART_LAYOUT_DEFAULTS,
        title=dict(text="Action Plans by Zone", font=dict(size=14, color="#1A1A2E"), x=0),
        xaxis=dict(title="", tickfont=dict(size=11)),
        yaxis=dict(title="No. of Plans", gridcolor="#F3F4F6", zeroline=False),
        showlegend=False,
        height=320,
        margin=dict(l=16, r=16, t=40, b=16),
    )
    return fig


# ── 2. Plans by Function ──────────────────────────────────────────────────────

def chart_plans_by_function(df: pd.DataFrame) -> go.Figure | None:
    """Vertical bar chart — total Action Plans per Function."""
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

    # Cycle through palette if more functions than colours
    colours = (_BAR_PALETTE * ((len(counts) // len(_BAR_PALETTE)) + 1))[: len(counts)]

    fig = go.Figure(
        go.Bar(
            x=counts["Function"],
            y=counts["Plans"],
            marker_color=colours,
            marker_line_width=0,
            text=counts["Plans"],
            textposition="outside",
            textfont=dict(size=12, color="#374151"),
        )
    )
    fig.update_layout(
        **_CHART_LAYOUT_DEFAULTS,
        title=dict(text="Action Plans by Function", font=dict(size=14, color="#1A1A2E"), x=0),
        xaxis=dict(title="", tickangle=-30, tickfont=dict(size=10)),
        yaxis=dict(title="No. of Plans", gridcolor="#F3F4F6", zeroline=False),
        showlegend=False,
        height=320,
        margin=dict(l=16, r=16, t=40, b=16),
    )
    return fig


# ── 3. WEF Element Distribution ───────────────────────────────────────────────

def chart_wef_distribution(df: pd.DataFrame) -> go.Figure | None:
    """Horizontal bar chart — plans per Workplace Engagement Framework element."""
    if df.empty or "wef_element" not in df.columns:
        st.info("No WEF data available.")
        return None

    # Ensure all 12 elements appear (even if count = 0)
    all_elements = pd.DataFrame({"wef_element": list(range(1, 13))})
    counts_raw = (
        df["wef_element"]
        .value_counts()
        .reset_index()
        .rename(columns={"wef_element": "wef_element", "count": "Plans"})
    )
    counts = (
        all_elements
        .merge(counts_raw, on="wef_element", how="left")
        .fillna(0)
        .astype({"Plans": int})
        .sort_values("wef_element")
    )
    counts["Label"] = counts["wef_element"].map(_WEF_LABELS)

    # Colour bars: highlight elements with plans
    bar_colours = [
        _BRAND_BLUE if v > 0 else _BRAND_GREY
        for v in counts["Plans"]
    ]

    fig = go.Figure(
        go.Bar(
            y=counts["Label"],
            x=counts["Plans"],
            orientation="h",
            marker_color=bar_colours,
            marker_line_width=0,
            text=counts["Plans"].apply(lambda v: str(v) if v > 0 else ""),
            textposition="outside",
            textfont=dict(size=11, color="#374151"),
        )
    )
    fig.update_layout(
        **_CHART_LAYOUT_DEFAULTS,
        title=dict(
            text="Distribution by WEF Element",
            font=dict(size=14, color="#1A1A2E"),
            x=0,
        ),
        xaxis=dict(
            title="No. of Plans",
            gridcolor="#F3F4F6",
            zeroline=False,
            dtick=1,
        ),
        yaxis=dict(
            title="",
            tickfont=dict(size=10),
            autorange="reversed",
        ),
        showlegend=False,
        height=480,
        margin=dict(l=220, r=40, t=40, b=16),
    )
    return fig


# ── 4. Status Distribution ────────────────────────────────────────────────────

def chart_status_distribution(df: pd.DataFrame) -> go.Figure | None:
    """Donut chart — Initiated / Ongoing / Closed breakdown."""
    if df.empty or "status" not in df.columns:
        st.info("No status data available.")
        return None

    # Preserve canonical order
    order   = ["Initiated", "Ongoing", "Closed"]
    counts  = df["status"].value_counts()
    labels  = [s for s in order if s in counts.index]
    values  = [counts[s] for s in labels]
    colours = [_STATUS_COLOURS[s] for s in labels]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker=dict(colors=colours, line=dict(color="#FFFFFF", width=3)),
            textinfo="label+percent",
            textfont=dict(size=12),
            hovertemplate="%{label}: %{value} plans (%{percent})<extra></extra>",
        )
    )

    total = sum(values)
    fig.add_annotation(
        text=f"<b>{total}</b><br><span style='font-size:11px'>Total</span>",
        x=0.5, y=0.5,
        font=dict(size=18, color="#1A1A2E"),
        showarrow=False,
    )
    fig.update_layout(
        **_CHART_LAYOUT_DEFAULTS,
        title=dict(
            text="Status Distribution",
            font=dict(size=14, color="#1A1A2E"),
            x=0,
        ),
        showlegend=True,
        legend=dict(
            orientation="v",
            x=1.02, y=0.5,
            font=dict(size=11),
        ),
        height=320,
        margin=dict(l=16, r=16, t=40, b=16),
    )
    return fig


# ── Summary metrics strip ─────────────────────────────────────────────────────

def summary_metrics_strip(df: pd.DataFrame) -> None:
    """
    Render four key metric cards in a single row.
    Uses st.metric for native Streamlit styling.
    """
    if df.empty:
        total          = 0
        pct_closed     = 0
        active_zones   = 0
        active_managers = 0
    else:
        total           = len(df)
        closed_count    = len(df[df["status"] == "Closed"])
        pct_closed      = round((closed_count / total) * 100) if total else 0
        active_zones    = df["zone"].nunique() if "zone" in df.columns else 0
        active_managers = df["manager_id"].nunique() if "manager_id" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Total Action Plans",    total)
    c2.metric("✅ Plans Closed",          f"{pct_closed}%")
    c3.metric("🗺️  Zones with Plans",      active_zones)
    c4.metric("👤 Managers Participating", active_managers)