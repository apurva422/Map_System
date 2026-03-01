"""Auth layer — login, logout, require_auth, get_current_user."""

import streamlit as st
from database.supabase_client import supabase, get_service_client
from config import APP_ICON, ROLE_COLOURS


# Internal helpers

def _fetch_employee_profile(auth_uid: str) -> dict | None:
    """Build session user dict from auth_users + employees (service client)."""
    try:
        client = get_service_client()

        # Bridge row: auth_uid → emp_id, role, zone
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

        # Employee details
        emp_row = (
            client
            .from_("employees")
            .select("id, name, email, function")
            .eq("emp_id", emp_id)
            .single()
            .execute()
        )
        if not emp_row.data:
            return None

        return {
            "auth_uid":  auth_uid,
            "emp_id":    emp_id,
            "db_id":     emp_row.data["id"],
            "name":      emp_row.data["name"],
            "email":     emp_row.data["email"],
            "role":      role,
            "zone":      zone or "",
            "function":  emp_row.data.get("function", ""),
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


# Public API

def get_current_user() -> dict | None:
    """Return logged-in user dict or None."""
    return st.session_state.get("user")


def require_auth() -> dict:
    """Guard — renders login + st.stop() if unauthenticated, else returns user."""
    if not st.session_state.get("authenticated"):
        login()
        st.stop()
    return get_current_user()


def logout() -> None:
    """Sign out and clear session."""
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    _clear_session()
    st.rerun()


def login() -> None:
    """Render login page; on success, store profile and rerun."""
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