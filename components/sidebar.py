"""
components/sidebar.py
=====================
Role-aware navigation links rendered inside the sidebar.

render_nav(role) is called by app.py with the current user's role.
Each role sees only the pages relevant to them.

FIX: Every nav button click now clears `selected_plan_id` from
session state so navigating to "My Action Plans" from the sidebar
always lands on the list view, not the last-opened plan detail.
"""

import streamlit as st


# Navigation definitions per role
_NAV_ITEMS = {
    "Manager": [
        ("🏠", "Dashboard",         "dashboard"),
        ("➕", "Create Action Plan", "create_plan"),
        ("📝", "My Action Plans",   "my_plans"),
    ],
    "HRBP": [
        ("🏠", "Zone Dashboard",    "dashboard"),
        ("📋", "Zone Action Plans", "zone_plans"),
        ("📤", "Export / Email",    "export"),
    ],
    "Admin": [
        ("🏠", "Overview",          "dashboard"),
        ("📋", "All Action Plans",  "all_plans"),
        ("✉️",  "Send Feedback",    "feedback"),
        ("📤", "Export / Email",    "export"),
        ("👥", "Manager Onboarding","onboarding"),
        ("🔔", "Notifications",     "notifications"),
    ],
    "CEO": [
        ("📊", "Leadership Dashboard",  "dashboard"),
        ("📋", "All Plans",             "all_plans"),
    ],
}

# Session-state keys that represent drill-down state within a page.
# These are cleared whenever the user navigates to a different page
# so they always land on the list/overview, not a previously opened record.
_DRILL_DOWN_KEYS = [
    "selected_plan_id",   # Manager / HRBP plan detail
    "selected_manager_id",
]


def render_nav(role: str) -> None:
    """Render navigation links for the given role."""
    items = _NAV_ITEMS.get(role, [])
    if not items:
        st.caption("No navigation items for this role.")
        return

    # Initialise page state if not already set
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = items[0][2]

    st.markdown("**Navigation**")
    for icon, label, page_key in items:
        is_active = st.session_state.get("current_page") == page_key
        btn_label = f"{icon} **{label}**" if is_active else f"{icon} {label}"

        if st.button(btn_label, key=f"nav_{page_key}", use_container_width=True):
            # ── Clear all drill-down state before changing page ──────────────
            for key in _DRILL_DOWN_KEYS:
                st.session_state.pop(key, None)

            st.session_state["current_page"] = page_key
            st.rerun()


def get_current_page() -> str:
    """Return the currently selected page key."""
    return st.session_state.get("current_page", "dashboard")