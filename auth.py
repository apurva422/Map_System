"""
auth.py
=======
Centralised authentication layer for the MAP System.

Public API
----------
login()             →  renders the login form; populates session on success
logout()            →  clears session state
require_auth()      →  call at the top of every view; stops unauthenticated access
get_current_user()  →  returns the user dict from session (or None)

Session state schema (st.session_state["user"])
------------------------------------------------
{
    "auth_uid": str,   # Supabase Auth UID
    "emp_id":   str,   # employee record ID
    "db_id":    str,   # UUID primary key in employees table
    "name":     str,
    "role":     str,   # "Manager" | "HRBP" | "Admin" | "CEO"
    "zone":     str,
    "email":    str,
}
"""

import streamlit as st
from database.supabase_client import supabase, get_service_client
from config import APP_ICON, ROLE_COLOURS


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_employee_profile(auth_uid: str) -> dict | None:
    """
    Join auth_users → employees to build the full session user dict.

    Uses the service client for BOTH queries so RLS never blocks the
    login profile fetch — the anon client's session hasn't fully
    propagated at the moment this runs, so RLS would return 0 rows.
    The service client is the correct tool for this internal bootstrap.
    """
    try:
        client = get_service_client()

        # 1. Get the bridge row (auth_uid → emp_id, role, zone)
        auth_row = (
            client
            .from_("auth_users")
            .select("emp_id, role, zone")
            .eq("auth_uid", auth_uid)
            .single()
            .execute()
        )
        if not auth_row.data:
            return None

        emp_id = auth_row.data["emp_id"]
        role   = auth_row.data["role"]
        zone   = auth_row.data["zone"]

        # 2. Get display name and email from employees
        emp_row = (
            client
            .from_("employees")
            .select("id, name, email")
            .eq("emp_id", emp_id)
            .single()
            .execute()
        )
        if not emp_row.data:
            return None

        return {
            "auth_uid": auth_uid,
            "emp_id":   emp_id,
            "db_id":    emp_row.data["id"],   # UUID PK in employees table
            "name":     emp_row.data["name"],
            "email":    emp_row.data["email"],
            "role":     role,
            "zone":     zone or "",
        }

    except Exception as exc:
        st.error(f"Profile fetch error: {exc}")
        return None


def _set_session(user: dict) -> None:
    st.session_state["user"]          = user
    st.session_state["authenticated"] = True


def _clear_session() -> None:
    for key in ["user", "authenticated"]:
        st.session_state.pop(key, None)


# ── Public API ────────────────────────────────────────────────────────────────

def get_current_user() -> dict | None:
    """Return the logged-in user dict, or None if not authenticated."""
    return st.session_state.get("user")


def require_auth() -> dict:
    """
    Guard function — place at the top of every view render function.
    If the user is not authenticated, renders the login page and stops
    execution via st.stop().
    Returns the user dict when authenticated.
    """
    if not st.session_state.get("authenticated"):
        login()
        st.stop()
    return get_current_user()


def logout() -> None:
    """Sign out of Supabase Auth and clear local session."""
    try:
        supabase.auth.sign_out()
    except Exception:
        pass  # even if the server call fails, clear local state
    _clear_session()
    st.rerun()


def login() -> None:
    """
    Render the login page.
    On successful Supabase Auth sign-in, fetches the employee profile
    using the service client and stores it in session state, then calls
    st.rerun() so the role router in app.py takes over.
    """
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
            <div class="login-card">
                <div class="login-title">{APP_ICON} MAP System</div>
                <div class="login-sub">Manager Action Planning — XYZ Industries</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Sign in to your account")

        with st.form("login_form", clear_on_submit=False):
            email     = st.text_input(
                "Email address",
                placeholder="you@xyzindustries.com",
            )
            password  = st.text_input(
                "Password",
                type="password",
                placeholder="••••••••",
            )
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
                return

            with st.spinner("Signing in…"):
                try:
                    resp = supabase.auth.sign_in_with_password(
                        {"email": email.strip(), "password": password}
                    )
                except Exception as exc:
                    st.error(f"Sign-in failed: {exc}")
                    return

            if not resp or not resp.user:
                st.error("Invalid email or password. Please try again.")
                return

            auth_uid = resp.user.id
            profile  = _fetch_employee_profile(auth_uid)

            if profile is None:
                st.error(
                    "Your account exists in Supabase Auth but has no matching "
                    "employee profile. Please contact the HR Administrator to "
                    "ensure your Auth UID is correctly linked in the auth_users table."
                )
                return

            _set_session(profile)

            role   = profile["role"]
            colour = ROLE_COLOURS.get(role, "#2E75B6")
            st.success(f"Welcome, {profile['name']}! Logged in as **{role}**.")
            st.markdown(
                f"<div style='height:4px;background:{colour};border-radius:2px;'></div>",
                unsafe_allow_html=True,
            )
            st.rerun()