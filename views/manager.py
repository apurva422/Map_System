"""
views/manager.py
================
Full Manager View for the MAP System.

Pages (routed via st.session_state["current_page"])
----------------------------------------------------
dashboard    → Summary cards + plan list overview
create_plan  → Create a new Action Plan
my_plans     → List all own plans; click into any for detail/edit/progress
"""

from __future__ import annotations

import streamlit as st
from datetime import datetime, date

from auth import get_current_user
from config import WEF_ELEMENTS, PLAN_STATUSES, STATUS_COLOURS
from database.supabase_client import supabase
from components.action_plan_form import render_form
from components.sidebar import get_current_page
from utils.email_service import send_plan_created


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LAYER  — all DB calls isolated here for easy testing / replacement
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_my_plans(manager_db_id: str) -> list[dict]:
    """Return all action plans belonging to the current manager, newest first."""
    try:
        resp = (
            supabase
            .from_("action_plans")
            .select("*")
            .eq("manager_id", manager_db_id)
            .order("created_at", desc=True)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        st.error(f"Error fetching plans: {exc}")
        return []


def _fetch_plan_by_id(plan_id: str) -> dict | None:
    """Fetch a single plan by UUID."""
    try:
        resp = (
            supabase
            .from_("action_plans")
            .select("*")
            .eq("id", plan_id)
            .single()
            .execute()
        )
        return resp.data
    except Exception:
        return None


def _fetch_used_elements(manager_db_id: str) -> list[int]:
    """Return WEF element numbers already used by this manager."""
    try:
        resp = (
            supabase
            .from_("action_plans")
            .select("wef_element")
            .eq("manager_id", manager_db_id)
            .execute()
        )
        return [row["wef_element"] for row in (resp.data or [])]
    except Exception:
        return []


def _fetch_progress_updates(plan_id: str) -> list[dict]:
    """Return all progress updates for a plan, oldest first."""
    try:
        resp = (
            supabase
            .from_("progress_updates")
            .select("*, employees(name)")
            .eq("action_plan_id", plan_id)
            .order("created_at", desc=False)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        st.error(f"Error fetching updates: {exc}")
        return []


def _fetch_reporting_manager_email(manager_db_id: str) -> str:
    """Return the reporting manager's email, or empty string if not found."""
    try:
        # Get reporting_manager_id from employees
        emp_resp = (
            supabase
            .from_("employees")
            .select("reporting_manager_id")
            .eq("id", manager_db_id)
            .single()
            .execute()
        )
        if not emp_resp.data or not emp_resp.data.get("reporting_manager_id"):
            return ""

        rm_id = emp_resp.data["reporting_manager_id"]

        rm_resp = (
            supabase
            .from_("employees")
            .select("email")
            .eq("id", rm_id)
            .single()
            .execute()
        )
        return rm_resp.data.get("email", "") if rm_resp.data else ""
    except Exception:
        return ""


def _create_plan(manager_db_id: str, zone: str, function_: str, payload: dict) -> dict | None:
    """Insert a new action plan row; returns inserted row or None on error."""
    try:
        now = datetime.utcnow().isoformat()
        row = {
            "manager_id":  manager_db_id,
            "wef_element": payload["wef_element"],
            "title":       payload["title"],
            "description": payload["description"],
            "start_date":  payload["start_date"],
            "target_date": payload["target_date"],
            "status":      "Initiated",
            "zone":        zone,
            "function":    function_,
            "created_at":  now,
            "updated_at":  now,
        }
        resp = supabase.from_("action_plans").insert(row).execute()
        return resp.data[0] if resp.data else None
    except Exception as exc:
        st.error(f"Error creating plan: {exc}")
        return None


def _update_plan(plan_id: str, payload: dict) -> bool:
    """Update title, description, dates, and status of an existing plan."""
    try:
        supabase.from_("action_plans").update({
            "title":       payload["title"],
            "description": payload["description"],
            "start_date":  payload["start_date"],
            "target_date": payload["target_date"],
            "status":      payload["status"],
            "updated_at":  datetime.utcnow().isoformat(),
        }).eq("id", plan_id).execute()
        return True
    except Exception as exc:
        st.error(f"Error updating plan: {exc}")
        return False


def _add_progress_update(plan_id: str, updater_db_id: str, text: str) -> bool:
    """Append a progress update row."""
    try:
        supabase.from_("progress_updates").insert({
            "action_plan_id": plan_id,
            "updated_by":     updater_db_id,
            "updated_by_role": "Manager",
            "update_text":    text,
            "created_at":     datetime.utcnow().isoformat(),
        }).execute()
        return True
    except Exception as exc:
        st.error(f"Error saving update: {exc}")
        return False


def _fetch_manager_function(manager_db_id: str) -> str:
    """Return the manager's function/department from employees table."""
    try:
        resp = (
            supabase
            .from_("employees")
            .select("function")
            .eq("id", manager_db_id)
            .single()
            .execute()
        )
        return resp.data.get("function", "") if resp.data else ""
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _status_badge_html(status: str) -> str:
    colour = STATUS_COLOURS.get(status, "#9E9E9E")
    return (
        f"<span style='background:{colour}22;color:{colour};"
        f"border:1px solid {colour};padding:2px 10px;"
        f"border-radius:12px;font-size:0.78rem;font-weight:600;'>{status}</span>"
    )


def _metric_card(label: str, value: str | int, colour: str = "#2E75B6") -> str:
    return f"""
    <div style='background:#fff;border:1px solid #E5E7EB;border-radius:10px;
                padding:1rem 1.2rem;text-align:center;border-top:3px solid {colour};'>
        <div style='font-size:1.8rem;font-weight:800;color:{colour};'>{value}</div>
        <div style='font-size:0.82rem;color:#6B7280;margin-top:0.2rem;'>{label}</div>
    </div>
    """


def _plan_card_html(plan: dict, idx: int) -> str:
    """HTML card for a plan in the list view."""
    status   = plan.get("status", "Initiated")
    colour   = STATUS_COLOURS.get(status, "#9E9E9E")
    wef_num  = plan.get("wef_element", "—")
    wef_text = WEF_ELEMENTS.get(wef_num, "")
    short_wef = wef_text[:60] + "…" if len(wef_text) > 60 else wef_text
    created  = plan.get("created_at", "")[:10] if plan.get("created_at") else "—"

    return f"""
    <div style='background:#fff;border:1px solid #E5E7EB;border-radius:10px;
                padding:1rem 1.4rem;margin-bottom:0.6rem;
                border-left:4px solid {colour};'>
        <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
            <div>
                <span style='font-weight:700;font-size:0.95rem;color:#111827;'>
                    {plan.get('title','—')}
                </span><br>
                <span style='font-size:0.8rem;color:#6B7280;'>
                    Q{wef_num} — {short_wef}
                </span>
            </div>
            <span style='background:{colour}22;color:{colour};
                         border:1px solid {colour};padding:2px 10px;
                         border-radius:12px;font-size:0.78rem;font-weight:600;
                         white-space:nowrap;margin-left:1rem;'>
                {status}
            </span>
        </div>
        <div style='display:flex;gap:1.5rem;font-size:0.78rem;color:#9CA3AF;margin-top:0.5rem;'>
            <span>📅 {plan.get('start_date','—')} → {plan.get('target_date','—')}</span>
            <span>🕒 Created: {created}</span>
        </div>
    </div>
    """


def _format_update_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso_str[:16] if iso_str else "—"


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE RENDERERS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_dashboard(user: dict) -> None:
    """Dashboard: summary cards + quick plan list."""
    st.markdown("## 🏠 My Dashboard")

    manager_db_id = user["db_id"]
    plans = _fetch_my_plans(manager_db_id)

    # ── Summary metrics ──────────────────────────────────────────────────────
    total     = len(plans)
    initiated = sum(1 for p in plans if p.get("status") == "Initiated")
    ongoing   = sum(1 for p in plans if p.get("status") == "Ongoing")
    closed    = sum(1 for p in plans if p.get("status") == "Closed")
    covered   = len(set(p.get("wef_element") for p in plans))
    remaining = 12 - covered

    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Total Plans",       total,     "#2E75B6"),
        (c2, "Initiated",         initiated, "#9E9E9E"),
        (c3, "Ongoing",           ongoing,   "#FFC107"),
        (c4, "Closed",            closed,    "#4CAF50"),
        (c5, "WEF Elements Left", remaining, "#E57373"),
    ]
    for col, label, value, colour in cards:
        with col:
            st.markdown(_metric_card(label, value, colour), unsafe_allow_html=True)

    # ── WEF Coverage bar ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📊 WEF Element Coverage")

    used_set = set(p.get("wef_element") for p in plans)
    coverage_cols = st.columns(12)
    for i, col in enumerate(coverage_cols, start=1):
        with col:
            is_done  = i in used_set
            bg       = "#2E75B6" if is_done else "#F3F4F6"
            fg       = "#ffffff" if is_done else "#9CA3AF"
            icon     = "✓" if is_done else str(i)
            wef_tip  = WEF_ELEMENTS.get(i, "")
            st.markdown(
                f"<div title='Q{i}: {wef_tip}' "
                f"style='background:{bg};color:{fg};border-radius:6px;"
                f"text-align:center;padding:6px 4px;font-size:0.75rem;"
                f"font-weight:700;cursor:default;'>{icon}</div>",
                unsafe_allow_html=True,
            )

    st.caption("Blue = Action Plan created | Grey = Not yet started")

    # ── Recent plans list ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📋 Recent Action Plans")

    if not plans:
        st.info(
            "You haven't created any Action Plans yet. "
            "Use **➕ Create Action Plan** in the sidebar to get started."
        )
        return

    for plan in plans[:5]:
        status    = plan.get("status", "Initiated")
        colour    = STATUS_COLOURS.get(status, "#9E9E9E")
        wef_num   = plan.get("wef_element", "—")
        wef_text  = WEF_ELEMENTS.get(wef_num, "")
        short_wef = wef_text[:55] + "…" if len(wef_text) > 55 else wef_text
        created   = plan.get("created_at", "")[:10] if plan.get("created_at") else "—"

        with st.container(border=True):
            # Coloured left-accent bar + status badge in one row
            top_left, top_right = st.columns([5, 1])
            with top_left:
                st.markdown(
                    f"<div style='border-left:4px solid {colour};"
                    f"padding-left:0.7rem;'>"
                    f"<span style='font-weight:700;font-size:0.95rem;'>"
                    f"{plan.get('title','—')}</span><br>"
                    f"<span style='font-size:0.8rem;color:#6B7280;'>"
                    f"Q{wef_num} — {short_wef}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with top_right:
                st.markdown(
                    f"<div style='text-align:right;padding-top:4px;'>"
                    f"<span style='background:{colour}22;color:{colour};"
                    f"border:1px solid {colour};padding:2px 10px;"
                    f"border-radius:12px;font-size:0.78rem;font-weight:600;'>"
                    f"{status}</span></div>",
                    unsafe_allow_html=True,
                )

            # Date row
            st.caption(f"📅 {plan.get('start_date','—')} → {plan.get('target_date','—')}   🕒 Created: {created}")

            # Open button — sits inside the container border
            if st.button(
                "✏️ Open in Editor",
                key=f"dash_open_{plan['id']}",
                use_container_width=True,
            ):
                st.session_state["selected_plan_id"] = plan["id"]
                st.session_state["current_page"]     = "my_plans"
                st.rerun()

    if len(plans) > 5:
        st.caption(f"Showing 5 of {len(plans)} plans. Go to **My Action Plans** to see all.")

    if st.button("📋 View All My Plans", use_container_width=False):
        st.session_state.pop("selected_plan_id", None)
        st.session_state["current_page"] = "my_plans"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────

def _render_create_plan(user: dict) -> None:
    """Create Action Plan page."""
    st.markdown("## ➕ Create Action Plan")
    st.caption(
        "Create one Action Plan per Workplace Engagement Framework element. "
        "Maximum 12 plans total."
    )

    manager_db_id = user["db_id"]
    used_elements = _fetch_used_elements(manager_db_id)

    if len(used_elements) >= 12:
        st.success(
            "🎉 You have created Action Plans for all 12 WEF elements. "
            "Well done! You can edit existing plans from **My Action Plans**."
        )
        return

    st.markdown(
        f"<div style='background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;"
        f"padding:0.6rem 1rem;font-size:0.85rem;color:#1E40AF;margin-bottom:1rem;'>"
        f"📌 You have created <strong>{len(used_elements)}/12</strong> Action Plans. "
        f"<strong>{12 - len(used_elements)}</strong> element(s) remaining."
        f"</div>",
        unsafe_allow_html=True,
    )

    def _on_create(payload: dict) -> None:
        # Use zone and function from session (populated via service client at login)
        function_ = user.get("function", "")
        zone      = user.get("zone", "")

        created = _create_plan(manager_db_id, zone, function_, payload)
        if not created:
            return  # error already shown inside _create_plan

        plan_id = created.get("id")

        # ── Email notification ────────────────────────────────────────────────
        rm_email = _fetch_reporting_manager_email(manager_db_id)
        send_plan_created(
            manager_email           = user["email"],
            reporting_manager_email = rm_email,
            plan_details            = payload,
            manager_db_id           = manager_db_id,
            plan_id                 = plan_id,
        )

        st.success(
            f"✅ Action Plan **'{payload['title']}'** created successfully! "
            "Email notifications have been sent."
        )

        # Invalidate cache so dashboard reflects the new plan immediately
        st.session_state.pop("plans_cache", None)

        # Brief pause so the user sees the success message, then navigate
        import time; time.sleep(1.2)
        st.session_state["current_page"] = "my_plans"
        st.rerun()

    render_form(
        user          = user,
        existing_plan = None,
        used_elements = used_elements,
        on_submit     = _on_create,
        readonly      = False,
    )


# ─────────────────────────────────────────────────────────────────────────────

def _render_my_plans(user: dict) -> None:
    """My Action Plans page — list view + drill-down into individual plan."""
    # Sub-page: are we viewing a specific plan?
    selected_plan_id = st.session_state.get("selected_plan_id")

    if selected_plan_id:
        _render_plan_detail(user, selected_plan_id)
    else:
        _render_plan_list(user)


def _render_plan_list(user: dict) -> None:
    """List all action plans for this manager with filter controls."""
    st.markdown("## 📝 My Action Plans")

    manager_db_id = user["db_id"]
    plans = _fetch_my_plans(manager_db_id)

    if not plans:
        st.info(
            "No Action Plans found. "
            "Use **➕ Create Action Plan** in the sidebar to get started."
        )
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown("#### 🔍 Filter Plans")
    fcol1, fcol2 = st.columns(2)

    with fcol1:
        status_filter = st.selectbox(
            "Status",
            options=["All"] + PLAN_STATUSES,
            key="manager_status_filter",
        )
    with fcol2:
        wef_options = sorted(set(p.get("wef_element") for p in plans))
        wef_labels  = ["All"] + [f"Q{n} — {WEF_ELEMENTS.get(n,'')[:40]}" for n in wef_options]
        wef_filter  = st.selectbox("WEF Element", options=wef_labels, key="manager_wef_filter")

    # Apply filters
    filtered = plans
    if status_filter != "All":
        filtered = [p for p in filtered if p.get("status") == status_filter]
    if wef_filter != "All":
        sel_wef = int(wef_filter.split("—")[0].replace("Q", "").strip())
        filtered = [p for p in filtered if p.get("wef_element") == sel_wef]

    st.markdown(f"<small style='color:#6B7280;'>Showing {len(filtered)} plan(s)</small>", unsafe_allow_html=True)
    st.markdown("---")

    # ── Plan rows ─────────────────────────────────────────────────────────────
    if not filtered:
        st.info("No plans match the selected filters.")
        return

    for plan in filtered:
        status   = plan.get("status", "Initiated")
        colour   = STATUS_COLOURS.get(status, "#9E9E9E")
        wef_num  = plan.get("wef_element", "—")
        wef_text = WEF_ELEMENTS.get(wef_num, "")

        with st.container():
            cols = st.columns([5, 2, 1])
            with cols[0]:
                st.markdown(
                    f"<div style='padding:0.4rem 0;'>"
                    f"<strong style='font-size:0.95rem;'>{plan.get('title','—')}</strong><br>"
                    f"<span style='font-size:0.8rem;color:#6B7280;'>"
                    f"Q{wef_num} — {wef_text[:55]}{'…' if len(wef_text)>55 else ''}"
                    f"</span></div>",
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(
                    f"<div style='padding:0.7rem 0;'>"
                    + _status_badge_html(status)
                    + f"</div>",
                    unsafe_allow_html=True,
                )
            with cols[2]:
                if st.button("Open →", key=f"open_plan_{plan['id']}"):
                    st.session_state["selected_plan_id"] = plan["id"]
                    st.rerun()

            st.markdown(
                f"<hr style='margin:0.3rem 0 0.6rem 0;border-color:#F3F4F6;'>",
                unsafe_allow_html=True,
            )


def _render_plan_detail(user: dict, plan_id: str) -> None:
    """
    Detail view for a single action plan.
    Tabs: Overview | Edit Plan | Add Progress Update | Progress History
    """
    plan = _fetch_plan_by_id(plan_id)
    if not plan:
        st.error("Plan not found. It may have been deleted.")
        st.session_state.pop("selected_plan_id", None)
        st.rerun()
        return

    manager_db_id = user["db_id"]

    # Security check: manager can only view their own plans
    if plan.get("manager_id") != manager_db_id:
        st.error("Access denied. You can only view your own Action Plans.")
        st.session_state.pop("selected_plan_id", None)
        st.rerun()
        return

    # ── Back button ───────────────────────────────────────────────────────────
    if st.button("← Back to My Plans"):
        st.session_state.pop("selected_plan_id", None)
        st.rerun()

    status  = plan.get("status", "Initiated")
    wef_num = plan.get("wef_element", "—")

    st.markdown(
        f"## {plan.get('title','—')} &nbsp; {_status_badge_html(status)}",
        unsafe_allow_html=True,
    )
    st.caption(f"Q{wef_num} — {WEF_ELEMENTS.get(wef_num, '')}")
    st.markdown("---")

    tab_overview, tab_edit, tab_update, tab_history = st.tabs([
        "📄 Overview", "✏️ Edit Plan", "➕ Add Progress Update", "📜 Progress History"
    ])

    # ── Tab 1: Overview ───────────────────────────────────────────────────────
    with tab_overview:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Description**")
            st.markdown(
                f"<div style='background:#F9FAFB;border-radius:8px;"
                f"padding:0.8rem 1rem;font-size:0.9rem;color:#374151;'>"
                f"{plan.get('description','—')}</div>",
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown("**Details**")
            details = {
                "🎯 WEF Element":    f"Q{wef_num} — {WEF_ELEMENTS.get(wef_num,'')}",
                "📅 Start Date":     plan.get("start_date", "—"),
                "🏁 Target Date":    plan.get("target_date", "—"),
                "📊 Status":         status,
                "🗺️ Zone":           plan.get("zone", "—"),
                "⚙️ Function":       plan.get("function", "—"),
                "🕒 Created":        (plan.get("created_at", "")[:10] or "—"),
                "🔄 Last Updated":   (plan.get("updated_at", "")[:10] or "—"),
            }
            for key, val in details.items():
                col1, col2 = st.columns([1, 2])
                col1.markdown(f"<small style='color:#6B7280;'>{key}</small>", unsafe_allow_html=True)
                col2.markdown(f"<small style='color:#111827;font-weight:600;'>{val}</small>", unsafe_allow_html=True)

        # Warn if the plan is overdue
        if plan.get("target_date"):
            try:
                target = date.fromisoformat(plan["target_date"])
                if target < date.today() and status != "Closed":
                    st.warning(
                        f"⚠️ This plan's target date ({plan['target_date']}) has passed. "
                        "Consider updating the status or closing it."
                    )
            except ValueError:
                pass

    # ── Tab 2: Edit Plan ──────────────────────────────────────────────────────
    with tab_edit:
        if status == "Closed":
            st.info("🔒 This plan is **Closed** and cannot be edited.")
        else:
            st.markdown("Edit the details below and save changes.")

            used_elements = _fetch_used_elements(manager_db_id)

            def _on_update(payload: dict) -> None:
                success = _update_plan(plan_id, payload)
                if success:
                    st.success(f"✅ Plan updated successfully!")
                    st.session_state.pop("plans_cache", None)
                    import time; time.sleep(0.8)
                    st.rerun()

            render_form(
                user          = user,
                existing_plan = plan,
                used_elements = used_elements,
                on_submit     = _on_update,
                readonly      = False,
            )

    # ── Tab 3: Add Progress Update ────────────────────────────────────────────
    with tab_update:
        if status == "Closed":
            st.info("🔒 This plan is **Closed**. No further updates can be added.")
        else:
            st.markdown("#### Add a Progress Update")
            st.caption(
                "Describe what has been done, what's in progress, "
                "or any blockers. Updates are permanent and cannot be deleted."
            )

            with st.form("progress_update_form"):
                update_text = st.text_area(
                    "Progress Note",
                    height=130,
                    placeholder="e.g. Conducted first round of recognition sessions with team on 12 Mar…",
                    max_chars=1500,
                )
                new_status = st.selectbox(
                    "Update Status",
                    options=PLAN_STATUSES,
                    index=PLAN_STATUSES.index(status),
                    help="You may update the plan status alongside this progress note.",
                )
                save_update = st.form_submit_button("💾 Save Update", use_container_width=True)

            if save_update:
                if not update_text.strip():
                    st.error("⚠️ Progress note cannot be empty.")
                else:
                    # Save the update
                    ok = _add_progress_update(plan_id, manager_db_id, update_text.strip())
                    if ok:
                        # Also update status if changed
                        if new_status != status:
                            _update_plan(plan_id, {
                                "title":       plan["title"],
                                "description": plan["description"],
                                "start_date":  plan["start_date"],
                                "target_date": plan["target_date"],
                                "status":      new_status,
                            })
                        st.success("✅ Progress update saved!")
                        import time; time.sleep(0.8)
                        st.rerun()

    # ── Tab 4: Progress History ───────────────────────────────────────────────
    with tab_history:
        st.markdown("#### 📜 Progress History")
        updates = _fetch_progress_updates(plan_id)

        if not updates:
            st.info("No progress updates yet. Add the first update in **Add Progress Update**.")
        else:
            st.caption(f"{len(updates)} update(s) recorded")
            st.markdown("---")

            for upd in updates:
                role       = upd.get("updated_by_role", "Manager")
                time_str   = _format_update_time(upd.get("created_at", ""))
                update_txt = upd.get("update_text", "—")

                # Visual differentiation: Manager = blue, HRBP = green
                if role == "HRBP":
                    border_col = "#375623"
                    role_icon  = "🗺️ HRBP Update"
                    bg_col     = "#F0FFF4"
                else:
                    border_col = "#2E75B6"
                    role_icon  = "👤 Manager Update"
                    bg_col     = "#EFF6FF"

                updater_name = ""
                if upd.get("employees"):
                    updater_name = upd["employees"].get("name", "")

                import html as _html
                safe_txt  = _html.escape(str(update_txt))
                name_part = f"&#8212; {_html.escape(updater_name)}" if updater_name else ""
                card_html = (
                    f"<div style='border-left:4px solid {border_col};"
                    f"background:{bg_col};border-radius:0 8px 8px 0;"
                    f"padding:0.7rem 1rem;margin-bottom:0.8rem;'>"
                    f"<div style='display:flex;justify-content:space-between;"
                    f"align-items:center;margin-bottom:0.3rem;'>"
                    f"<span style='font-size:0.78rem;font-weight:700;color:{border_col};'>"
                    f"{role_icon} {name_part}</span>"
                    f"<span style='font-size:0.75rem;color:#9CA3AF;'>{time_str}</span>"
                    f"</div>"
                    f"<p style='font-size:0.88rem;color:#374151;margin:0;'>{safe_txt}</p>"
                    f"</div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TOP-LEVEL RENDER — called by app.py
# ═══════════════════════════════════════════════════════════════════════════════

def render() -> None:
    """Entry point called by the role router in app.py."""
    user = get_current_user()
    if not user:
        st.error("Session expired. Please log in again.")
        st.stop()

    # Eligibility guard — only LEVEL 2 Managers should land here,
    # but double-check in the view as a safety net.
    if user.get("role") != "Manager":
        st.error("Access denied. This view is for Managers only.")
        st.stop()

    page = get_current_page()

    if page == "dashboard":
        _render_dashboard(user)
    elif page == "create_plan":
        _render_create_plan(user)
    elif page == "my_plans":
        _render_my_plans(user)
    else:
        # Unknown page key → fall back to dashboard
        st.session_state["current_page"] = "dashboard"
        _render_dashboard(user)