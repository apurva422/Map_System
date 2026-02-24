import streamlit as st
from components.sidebar import render_sidebar
from database.supabase_client import get_supabase_client

def render():
    render_sidebar()
    st.title("Admin Panel")

    tab1, tab2 = st.tabs(["User Management", "System Settings"])

    with tab1:
        _render_user_management()

    with tab2:
        st.info("System settings coming soon.")

def _render_user_management():
    supabase = get_supabase_client()
    st.subheader("All Users")
    try:
        profiles = supabase.table("profiles").select("*").execute()
        if profiles.data:
            import pandas as pd
            st.dataframe(pd.DataFrame(profiles.data), use_container_width=True)
        else:
            st.info("No users found.")
    except Exception as e:
        st.error(f"Error loading users: {e}")
