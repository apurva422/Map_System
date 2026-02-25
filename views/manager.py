import streamlit as st
from components.dashboard_charts import render_manager_dashboard
from components.action_plan_form import render_action_plan_form
from database.supabase_client import supabase

def render():
    st.title("Manager Dashboard")

    tab1, tab2 = st.tabs(["My Action Plans", "Create / Edit Plan"])

    with tab1:
        render_manager_dashboard()

    with tab2:
        render_action_plan_form(role="manager")
