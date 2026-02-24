import streamlit as st
from auth import login_page, logout
from config import APP_TITLE
from views import manager, hrbp, admin, ceo

st.set_page_config(page_title=APP_TITLE, layout="wide")

def main():
    if "user" not in st.session_state or st.session_state.user is None:
        login_page()
        return

    user = st.session_state.user
    role = user.get("role", "").lower()

    if role == "manager":
        manager.render()
    elif role == "hrbp":
        hrbp.render()
    elif role == "admin":
        admin.render()
    elif role == "ceo":
        ceo.render()
    else:
        st.error("Unknown role. Please contact your administrator.")
        logout()

if __name__ == "__main__":
    main()
