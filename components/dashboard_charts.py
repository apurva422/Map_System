import streamlit as st
import pandas as pd
from database.supabase_client import get_supabase_client

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_plans(filters: dict | None = None) -> pd.DataFrame:
    supabase = get_supabase_client()
    query = supabase.table("action_plans").select("*")
    if filters:
        for col, val in filters.items():
            query = query.eq(col, val)
    res = query.execute()
    return pd.DataFrame(res.data or [])

# ── Role-specific dashboards ──────────────────────────────────────────────────

def render_manager_dashboard():
    user = st.session_state.get("user", {})
    df = _load_plans({"created_by": user.get("id")})
    _status_bar_chart(df, title="My Plans by Status")

def render_hrbp_dashboard():
    df = _load_plans()
    col1, col2 = st.columns(2)
    with col1:
        _status_bar_chart(df, title="All Plans by Status")
    with col2:
        _plans_over_time(df)

def render_ceo_dashboard():
    df = _load_plans()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Plans", len(df))
    col2.metric("Approved", len(df[df["status"] == "Approved"]) if not df.empty else 0)
    col3.metric("Pending Review", len(df[df["status"] == "Under Review"]) if not df.empty else 0)
    _status_bar_chart(df, title="Company-wide Plan Status")

# ── Chart primitives ──────────────────────────────────────────────────────────

def _status_bar_chart(df: pd.DataFrame, title: str = "Plans by Status"):
    st.subheader(title)
    if df.empty:
        st.info("No data available.")
        return
    counts = df["status"].value_counts().reset_index()
    counts.columns = ["Status", "Count"]
    st.bar_chart(counts.set_index("Status"))

def _plans_over_time(df: pd.DataFrame):
    st.subheader("Plans Over Time")
    if df.empty or "created_at" not in df.columns:
        st.info("No timeline data available.")
        return
    df["created_at"] = pd.to_datetime(df["created_at"])
    timeline = df.groupby(df["created_at"].dt.date).size().reset_index(name="Count")
    st.line_chart(timeline.set_index("created_at"))
