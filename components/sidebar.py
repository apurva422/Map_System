import streamlit as st
from auth import logout

ROLE_MENU = {
    "manager": ["Dashboard", "My Action Plans", "Create Plan"],
    "hrbp": ["Dashboard", "All Plans", "Review", "Analytics"],
    "admin": ["User Management", "Settings"],
    "ceo": ["Overview", "Analytics"],
}

def render_sidebar():
    user = st.session_state.get("user", {})
    role = user.get("role", "").lower()

    with st.sidebar:
        st.image("assets/logo.png", use_column_width=True) if False else None
        st.markdown(f"### 👤 {user.get('email', 'User')}")
        st.caption(f"Role: **{role.upper()}**")
        st.divider()

        menu_items = ROLE_MENU.get(role, [])
        for item in menu_items:
            st.button(item, key=f"nav_{item}", use_container_width=True)

        st.divider()
        if st.button("🔒 Logout", use_container_width=True):
            logout()
