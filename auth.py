import streamlit as st
from database.supabase_client import get_supabase_client

def login_page():
    st.title("MAP System — Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        authenticate(email, password)

def authenticate(email: str, password: str):
    supabase = get_supabase_client()
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_data = response.user
        if user_data:
            # Fetch role from profiles table
            profile = supabase.table("profiles").select("role").eq("id", user_data.id).single().execute()
            st.session_state.user = {
                "id": user_data.id,
                "email": user_data.email,
                "role": profile.data.get("role", ""),
            }
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")
    except Exception as e:
        st.error(f"Login failed: {e}")

def logout():
    supabase = get_supabase_client()
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()
