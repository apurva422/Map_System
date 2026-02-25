import streamlit as st
from components.dashboard_charts import render_hrbp_dashboard
from components.action_plan_form import render_action_plan_form

def render():
    st.title("HRBP Dashboard")

    tab1, tab2, tab3 = st.tabs(["All Action Plans", "Review Plans", "Analytics"])

    with tab1:
        render_hrbp_dashboard()

    with tab2:
        render_action_plan_form(role="hrbp")

    with tab3:
        st.info("Analytics charts coming soon.")
