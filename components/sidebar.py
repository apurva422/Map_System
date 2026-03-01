"""Role-aware sidebar navigation. Clears drill-down state on page change."""

import streamlit as st


# Nav items per role
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

# Keys cleared on page change (prevents stale drill-down state)
_DRILL_DOWN_KEYS = [
    "selected_plan_id",
    "selected_manager_id",
]


def render_nav(role: str) -> None:
    """Render nav links for the given role."""
    items = _NAV_ITEMS.get(role, [])
    if not items:
        st.caption("No navigation items for this role.")
        return

    # Init page state
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = items[0][2]

    st.markdown("**Navigation**")
    for icon, label, page_key in items:
        is_active = st.session_state.get("current_page") == page_key
        btn_label = f"{icon} **{label}**" if is_active else f"{icon} {label}"

        if st.button(btn_label, key=f"nav_{page_key}", use_container_width=True):
            # Clear drill-down state
            for key in _DRILL_DOWN_KEYS:
                st.session_state.pop(key, None)

            st.session_state["current_page"] = page_key
            st.rerun()


def get_current_page() -> str:
    """Return current page key."""
    return st.session_state.get("current_page", "dashboard")