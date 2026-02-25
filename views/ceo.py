import streamlit as st
from components.dashboard_charts import render_ceo_dashboard

def render():
    st.title("CEO Overview")
    render_ceo_dashboard()
