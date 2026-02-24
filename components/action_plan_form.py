import streamlit as st
from database.supabase_client import get_supabase_client
from config import AP_STATUSES
from utils.validators import check_eligibility

def render_action_plan_form(role: str, plan_id: str | None = None):
    """Reusable create / edit action plan form."""
    supabase = get_supabase_client()
    st.subheader("📝 Action Plan Form")

    existing = {}
    if plan_id:
        res = supabase.table("action_plans").select("*").eq("id", plan_id).single().execute()
        existing = res.data or {}

    with st.form("action_plan_form"):
        title       = st.text_input("Title", value=existing.get("title", ""))
        description = st.text_area("Description", value=existing.get("description", ""))
        due_date    = st.date_input("Due Date")
        status      = st.selectbox("Status", AP_STATUSES,
                                   index=AP_STATUSES.index(existing.get("status", "Draft")))

        submitted = st.form_submit_button("Save Action Plan")

    if submitted:
        if not title:
            st.warning("Title is required.")
            return

        user = st.session_state.get("user", {})
        payload = {
            "title": title,
            "description": description,
            "due_date": str(due_date),
            "status": status,
            "created_by": user.get("id"),
        }

        try:
            if plan_id:
                supabase.table("action_plans").update(payload).eq("id", plan_id).execute()
                st.success("Action plan updated successfully!")
            else:
                supabase.table("action_plans").insert(payload).execute()
                st.success("Action plan created successfully!")
        except Exception as e:
            st.error(f"Error saving action plan: {e}")
