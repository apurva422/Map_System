import streamlit as st
from components.sidebar import render_sidebar
from components.dashboard_charts import render_ceo_dashboard

def render():
    render_sidebar()
    st.title("CEO Overview")
    render_ceo_dashboard()
