"""Entry point — loads CSS, renders sidebar, routes by role."""

import streamlit as st

from auth import require_auth, logout, get_current_user
from config import APP_TITLE, APP_ICON, ROLE_COLOURS

# View imports
from views import manager, hrbp, admin, ceo
from components import sidebar as sidebar_component


# Page config (must be first Streamlit call)
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_css() -> None:
    """Inject global CSS."""
    try:
        with open("assets/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass  # CSS file missing — skip


def _route(role: str) -> None:
    """Route to the view module for the given role."""
    if role == "Manager":
        manager.render()
    elif role == "HRBP":
        hrbp.render()
    elif role == "Admin":
        admin.render()
    elif role == "CEO":
        ceo.render()
    else:
        st.error(
            f"Unknown role **{role}**. "
            "Please contact the HR Administrator to correct your account."
        )


# Main

def main() -> None:
    _load_css()

    # Auth gate
    user = require_auth()

    role   = user["role"]
    name   = user["name"]
    colour = ROLE_COLOURS.get(role, "#2E75B6")

    # Sidebar
    with st.sidebar:
        # Accent bar
        st.markdown(
            f"""
            <div style="
                background:{colour};
                height:6px;
                border-radius:3px;
                margin-bottom:1rem;
            "></div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(f"### {APP_ICON} MAP System")
        st.markdown(
            f"<small style='color:#6B7280;'>Logged in as <strong>{role}</strong></small>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**{name}**")
        st.divider()

        # Nav links
        sidebar_component.render_nav(role)

        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()

    # Main content
    _route(role)


if __name__ == "__main__":
    main()