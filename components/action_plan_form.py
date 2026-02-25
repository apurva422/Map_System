import streamlit as st
from database.supabase_client import supabase
from config import PLAN_STATUSES
from utils.validators import is_eligible_manager

def render_action_plan_form(role: str, plan_id: str | None = None):
    """Reusable create / edit action plan form."""

    st.subheader("📝 Action Plan Form")

    existing = {}
    if plan_id:
        res = supabase.table("action_plans").select("*").eq("id", plan_id).single().execute()
        existing = res.data or {}

    with st.form("action_plan_form"):
        title       = st.text_input("Title", value=existing.get("title", ""))
        description = st.text_area("Description", value=existing.get("description", ""))
        due_date    = st.date_input("Due Date")
        status      = st.selectbox("Status", PLAN_STATUSES,
                                   index=PLAN_STATUSES.index(existing.get("status", "Initiated")))

        submitted = st.form_submit_button("Save Action Plan")

    if submitted:
        if not title:
            st.warning("Title is required.")
            return

        payload = {
            "title": title,
            "description": description,
            "due_date": str(due_date),
            "status": status,
            # NOTE: add "created_by": user.get("id") once the column
            # is added to the action_plans table in Supabase.
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
