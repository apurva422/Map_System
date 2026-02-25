"""
app.py
======
Entry point for the MAP System Streamlit application.

Responsibilities:
  1. Load global CSS
  2. Render the shared sidebar (nav + logout)
  3. Read the authenticated user's role
  4. Route to the correct view module
"""

import streamlit as st

from auth import require_auth, logout, get_current_user
from config import APP_TITLE, APP_ICON, ROLE_COLOURS

# ── View imports (each is a module with a render() function) ──────────────────
from views import manager, hrbp, admin, ceo
from components import sidebar as sidebar_component


# ── Global page config (must be the very first Streamlit call) ────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_css() -> None:
    """Inject global stylesheet from assets/style.css."""
    try:
        with open("assets/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass  # CSS file not yet created — silently skip during early phases


def _route(role: str) -> None:
    """
    Central role router.
    Adding a new role = one elif + one view module.
    """
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _load_css()

    # Gate: renders login page + st.stop() if not authenticated
    user = require_auth()

    role   = user["role"]
    name   = user["name"]
    colour = ROLE_COLOURS.get(role, "#2E75B6")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        # Role-coloured accent bar at the top of the sidebar
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

        # Role-aware navigation links rendered by sidebar component
        sidebar_component.render_nav(role)

        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()

    # ── Main content area ─────────────────────────────────────────────────────
    _route(role)


if __name__ == "__main__":
    main()