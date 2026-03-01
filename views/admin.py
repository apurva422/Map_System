"""Admin (HR CoE) view — overview, plans, feedback, export, onboarding, notifications."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

from auth import require_auth
from components.action_plan_form import render_form
from components.sidebar import get_current_page
from config import WEF_ELEMENTS, PLAN_STATUSES, STATUS_COLOURS, ROLE_COLOURS
from database.supabase_client import supabase, get_service_client
from utils.email_service import (
    check_and_send_reminders,
    send_admin_feedback,
    send_invitation,
    send_manual_notification,
    send_zone_report,
)
from utils.export_utils import generate_report, save_temp_file
from utils.validators import get_eligible_managers

ADMIN_COLOUR = ROLE_COLOURS["Admin"]


# --- DB helpers ---

def _fetch_all_plans() -> list[dict]:
    """Return all action plans with manager name denormalized. Uses service client."""
    client = get_service_client()
    resp = (
        client
        .from_("action_plans")
        .select(
            "id, title, description, wef_element, status, zone, function, "
            "start_date, target_date, created_at, updated_at, manager_id, "
            "employees(name, email)"
        )
        .order("created_at", desc=True)
        .execute()
    )
    rows = resp.data or []
    for r in rows:
        emp = r.pop("employees", None) or {}
        r["manager_name"]  = emp.get("name", "—")
        r["manager_email"] = emp.get("email", "")
    return rows


def _plans_to_df(plans: list[dict]) -> pd.DataFrame:
    """Convert plan dicts to a display DataFrame."""
    if not plans:
        return pd.DataFrame()

    display_cols = [
        "manager_name", "zone", "function", "wef_element",
        "title", "status", "start_date", "target_date", "id",
    ]
    df = pd.DataFrame(plans)
    for c in display_cols:
        if c not in df.columns:
            df[c] = "—"

    df["wef_label"] = df["wef_element"].apply(
        lambda n: f"Q{n} — {WEF_ELEMENTS.get(int(n), '')[:55]}…"
        if isinstance(n, (int, float)) else "—"
    )
    return df


def _fetch_progress(plan_id: str) -> list[dict]:
    client = get_service_client()
    resp = (
        client
        .from_("progress_updates")
        .select("update_text, updated_by_role, created_at, employees(name)")
        .eq("action_plan_id", plan_id)
        .order("created_at")
        .execute()
    )
    rows = resp.data or []
    for r in rows:
        emp = r.pop("employees", None) or {}
        r["updater_name"] = emp.get("name", "—")
    return rows


def _fetch_all_zones() -> list[str]:
    client = get_service_client()
    resp   = client.from_("employees").select("zone").execute()
    zones  = sorted({r["zone"] for r in (resp.data or []) if r.get("zone")})
    return zones


def _fetch_all_functions() -> list[str]:
    client = get_service_client()
    resp   = client.from_("employees").select("function").execute()
    funcs  = sorted({r["function"] for r in (resp.data or []) if r.get("function")})
    return funcs


def _fetch_all_managers() -> list[dict]:
    client = get_service_client()
    resp = (
        client
        .from_("employees")
        .select("id, name, email")
        .eq("role", "Manager")
        .order("name")
        .execute()
    )
    return resp.data or []


def _fetch_notification_log(limit: int = 100) -> list[dict]:
    client = get_service_client()
    resp = (
        client
        .from_("notifications_log")
        .select("type, sent_at, status, action_plan_id, employees(name)")
        .order("sent_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = resp.data or []
    for r in rows:
        emp = r.pop("employees", None) or {}
        r["recipient_name"] = emp.get("name", "—")
    return rows


# --- UI helpers ---

def _status_badge_html(status: str) -> str:
    c = STATUS_COLOURS.get(status, "#9E9E9E")
    return (
        f"<span style='background:{c}22;color:{c};border:1px solid {c};"
        f"padding:2px 10px;border-radius:12px;font-size:0.8rem;"
        f"font-weight:600;'>{status}</span>"
    )


def _section_header(icon: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div style="border-left:4px solid {ADMIN_COLOUR};
                    padding:0.4rem 0.8rem;margin-bottom:1rem;">
          <span style="font-size:1.1rem;font-weight:700;">{icon} {title}</span>
          {"<br><small style='color:#6B7280;'>" + subtitle + "</small>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(label: str, value: str, delta: str = "") -> str:
    delta_html = (
        f"<div style='font-size:0.75rem;color:#6B7280;margin-top:2px;'>{delta}</div>"
        if delta else ""
    )
    return f"""
    <div style="background:#fff;border:1px solid #E5E7EB;border-radius:10px;
                padding:1rem 1.2rem;text-align:center;
                border-top:3px solid {ADMIN_COLOUR};">
      <div style="font-size:0.8rem;color:#6B7280;text-transform:uppercase;
                  letter-spacing:0.05em;">{label}</div>
      <div style="font-size:1.8rem;font-weight:700;color:#111827;margin-top:4px;">
        {value}
      </div>
      {delta_html}
    </div>
    """


# --- Page: Overview ---

def _render_overview(user: dict) -> None:
    _section_header("🏠", "Admin Overview", "Full organisational view — all zones & functions")

    plans = _fetch_all_plans()
    df    = _plans_to_df(plans)

    if df.empty:
        st.info("No action plans have been created yet. "
                "Use **Manager Onboarding** to invite eligible managers.")
        return

    total     = len(df)
    closed    = len(df[df["status"] == "Closed"])
    ongoing   = len(df[df["status"] == "Ongoing"])
    initiated = len(df[df["status"] == "Initiated"])
    n_zones   = df["zone"].nunique()
    n_mgrs    = df["manager_name"].nunique()

    pct_closed = f"{int(closed/total*100)}% closed" if total else "—"

    cols = st.columns(5)
    metrics = [
        ("Total Plans",     str(total),    pct_closed),
        ("Initiated",       str(initiated), ""),
        ("Ongoing",         str(ongoing),   ""),
        ("Closed",          str(closed),    ""),
        ("Active Zones",    str(n_zones),   f"{n_mgrs} managers"),
    ]
    for col, (label, val, delta) in zip(cols, metrics):
        with col:
            st.markdown(_metric_card(label, val, delta), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # By zone & status
    st.markdown("#### Plans by Zone & Status")
    pivot = (
        df.groupby(["zone", "status"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for s in PLAN_STATUSES:
        if s not in pivot.columns:
            pivot[s] = 0
    pivot["Total"] = pivot[PLAN_STATUSES].sum(axis=1)
    pivot = pivot.rename(columns={"zone": "Zone"})
    st.dataframe(pivot, use_container_width=True, hide_index=True)

    # WEF coverage
    st.markdown("#### WEF Element Coverage")
    wef_counts = df["wef_element"].value_counts().sort_index().reset_index()
    wef_counts.columns = ["WEF Element", "Plan Count"]
    wef_counts["Question"] = wef_counts["WEF Element"].apply(
        lambda n: f"Q{n} — {WEF_ELEMENTS.get(int(n), '')[:60]}…"
    )
    st.dataframe(wef_counts[["Question", "Plan Count"]], use_container_width=True, hide_index=True)


# --- Page: All Plans ---

def _render_all_plans(user: dict) -> None:
    _section_header("📋", "All Action Plans", "View, filter, and edit any record across all zones")

    # Editing drill-down
    editing_id = st.session_state.get("admin_editing_plan_id")
    if editing_id:
        _render_edit_panel(user, editing_id)
        return

    plans = _fetch_all_plans()
    df    = _plans_to_df(plans)

    if df.empty:
        st.info("No action plans found.")
        return

    # Filters
    with st.expander("🔍 Filters", expanded=True):
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)

        with fc1:
            zone_opts = ["All"] + sorted(df["zone"].dropna().unique().tolist())
            sel_zone  = st.selectbox("Zone", zone_opts, key="ap_filter_zone")
        with fc2:
            func_opts = ["All"] + sorted(df["function"].dropna().unique().tolist())
            sel_func  = st.selectbox("Function", func_opts, key="ap_filter_func")
        with fc3:
            mgr_opts  = ["All"] + sorted(df["manager_name"].dropna().unique().tolist())
            sel_mgr   = st.selectbox("Manager", mgr_opts, key="ap_filter_mgr")
        with fc4:
            wef_opts  = ["All"] + [f"Q{e}" for e in range(1, 13)]
            sel_wef   = st.selectbox("WEF Element", wef_opts, key="ap_filter_wef")
        with fc5:
            status_opts = ["All"] + PLAN_STATUSES
            sel_status  = st.selectbox("Status", status_opts, key="ap_filter_status")

    # Apply
    fdf = df.copy()
    if sel_zone   != "All": fdf = fdf[fdf["zone"]         == sel_zone]
    if sel_func   != "All": fdf = fdf[fdf["function"]     == sel_func]
    if sel_mgr    != "All": fdf = fdf[fdf["manager_name"] == sel_mgr]
    if sel_status != "All": fdf = fdf[fdf["status"]       == sel_status]
    if sel_wef    != "All":
        wef_num = int(sel_wef.replace("Q", ""))
        fdf = fdf[fdf["wef_element"] == wef_num]

    st.caption(f"Showing **{len(fdf)}** of **{len(df)}** plans")

    # Plan table
    if fdf.empty:
        st.warning("No plans match the selected filters.")
        return

    display_cols = ["manager_name", "zone", "function", "wef_label",
                    "title", "status", "start_date", "target_date"]
    rename_map   = {
        "manager_name": "Manager",
        "zone":         "Zone",
        "function":     "Function",
        "wef_label":    "WEF Element",
        "title":        "Title",
        "status":       "Status",
        "start_date":   "Start",
        "target_date":  "Target",
    }
    show_df = fdf[display_cols].rename(columns=rename_map)

    # Style status
    def _style_status(val):
        colour = STATUS_COLOURS.get(val, "#9E9E9E")
        return f"color: {colour}; font-weight: 600;"

    styled = show_df.style.map(_style_status, subset=["Status"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Select plan to edit
    st.markdown("---")
    st.markdown("**Select a plan to edit:**")
    plan_titles = fdf["title"].tolist()
    plan_ids    = fdf["id"].tolist()
    title_map   = {
        f"{row['manager_name']} — {row['title']} [{row['status']}]": pid
        for _, row in fdf.iterrows()
        for pid in [row["id"]]
    }
    if title_map:
        chosen_label = st.selectbox(
            "Choose plan",
            list(title_map.keys()),
            key="admin_plan_select",
        )
        if st.button("✏️ Edit Selected Plan", use_container_width=False):
            st.session_state["admin_editing_plan_id"] = title_map[chosen_label]
            st.rerun()


def _render_edit_panel(user: dict, plan_id: str) -> None:
    """Edit form + progress history for a plan."""
    client = get_service_client()

    if st.button("← Back to All Plans"):
        st.session_state.pop("admin_editing_plan_id", None)
        st.rerun()

    # Fetch plan
    resp = (
        client
        .from_("action_plans")
        .select(
            "id, title, description, wef_element, status, zone, function, "
            "start_date, target_date, manager_id, employees(name, email)"
        )
        .eq("id", plan_id)
        .single()
        .execute()
    )
    if not resp.data:
        st.error("Plan not found.")
        return

    plan = resp.data
    emp  = plan.pop("employees", None) or {}
    plan["manager_name"]  = emp.get("name", "—")
    plan["manager_email"] = emp.get("email", "")

    st.markdown(
        f"**Editing:** {plan['manager_name']} &nbsp;›&nbsp; "
        f"Q{plan['wef_element']} — {WEF_ELEMENTS.get(plan['wef_element'], '')}",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"Zone: **{plan.get('zone','—')}** &nbsp;|&nbsp; "
        f"Function: **{plan.get('function','—')}** &nbsp;|&nbsp; "
        + _status_badge_html(plan.get("status", "—")),
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Edit form
    def _on_admin_edit(payload: dict) -> None:
        payload["updated_at"] = datetime.utcnow().isoformat()
        try:
            get_service_client() \
                .from_("action_plans") \
                .update(payload) \
                .eq("id", plan_id) \
                .execute()
            st.success("✅ Plan updated successfully.")
            st.session_state.pop("admin_editing_plan_id", None)
            st.rerun()
        except Exception as exc:
            st.error(f"Update failed: {exc}")

    render_form(
        user          = user,
        existing_plan = plan,
        used_elements = [],
        on_submit     = _on_admin_edit,
        readonly      = False,
    )

    # Progress history
    st.markdown("---")
    st.markdown("#### 📝 Progress History")
    updates = _fetch_progress(plan_id)
    if not updates:
        st.caption("No progress updates yet.")
    else:
        for u in updates:
            role_colour = (
                ROLE_COLOURS.get("HRBP", "#375623")
                if u.get("updated_by_role") == "HRBP"
                else ROLE_COLOURS.get("Manager", "#2E75B6")
            )
            st.markdown(
                f"""
                <div style="border-left:3px solid {role_colour};
                            padding:8px 12px;margin-bottom:8px;
                            background:#F9FAFB;border-radius:4px;">
                  <div style="font-size:0.8rem;color:#6B7280;">
                    <strong style="color:{role_colour};">
                      {u.get('updated_by_role','—')}
                    </strong>
                    &nbsp;·&nbsp; {u.get('updater_name','—')}
                    &nbsp;·&nbsp; {u.get('created_at','')[:16]}
                  </div>
                  <div style="margin-top:4px;font-size:0.9rem;color:#374151;">
                    {u.get('update_text','—')}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# --- Page: Feedback ---

def _render_feedback(user: dict) -> None:
    _section_header(
        "✉️", "Send Feedback to Manager",
        "Request clarification or suggest improvements on any Action Plan"
    )

    plans = _fetch_all_plans()
    if not plans:
        st.info("No action plans available to give feedback on.")
        return

    # Plan label map
    plan_options: dict[str, dict] = {
        f"{p['manager_name']} — Q{p['wef_element']} | {p['title']} [{p['status']}]": p
        for p in plans
    }

    chosen_label = st.selectbox(
        "Select Action Plan",
        list(plan_options.keys()),
        help="Search by manager name, WEF element, or plan title.",
    )
    selected_plan = plan_options[chosen_label]

    # Plan summary
    with st.container():
        st.markdown(
            f"""
            <div style="background:#FFF5F0;border:1px solid #FDBA74;
                        border-radius:8px;padding:12px 16px;margin:0.5rem 0;">
              <div style="font-weight:600;color:#111827;">{selected_plan['title']}</div>
              <div style="font-size:0.85rem;color:#6B7280;margin-top:4px;">
                Manager: {selected_plan['manager_name']} &nbsp;|&nbsp;
                Zone: {selected_plan.get('zone','—')} &nbsp;|&nbsp;
                {_status_badge_html(selected_plan.get('status','—'))}
              </div>
              <div style="font-size:0.85rem;color:#374151;margin-top:6px;">
                {(selected_plan.get('description','—') or '—').replace('<','&lt;').replace('>','&gt;').replace(chr(10),'<br>')[:200]}
                {'…' if len(selected_plan.get('description','') or '') > 200 else ''}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    feedback_type = st.radio(
        "Feedback Type",
        ["clarification", "improvement"],
        format_func=lambda x: "💬 Request Clarification" if x == "clarification" else "💡 Suggest Improvement",
        horizontal=True,
    )

    feedback_text = st.text_area(
        "Feedback Message *",
        height=130,
        max_chars=2000,
        placeholder=(
            "Write clear, actionable feedback.\n"
            "e.g. 'Please clarify how you plan to measure the success of this action.'"
        ),
    )

    send_col, _ = st.columns([1, 3])
    with send_col:
        if st.button("📤 Send Feedback", use_container_width=True):
            if not feedback_text.strip():
                st.error("Please write a feedback message before sending.")
                return

            # Save feedback
            try:
                supabase.from_("admin_feedback").insert({
                    "action_plan_id": selected_plan["id"],
                    "sent_by":        user["db_id"],
                    "message":        feedback_text.strip(),
                    "feedback_type":  feedback_type,
                    "sent_at":        datetime.utcnow().isoformat(),
                }).execute()
            except Exception as exc:
                st.error(f"Failed to save feedback record: {exc}")
                return

            # Email
            ok = send_admin_feedback(
                manager_email  = selected_plan["manager_email"],
                feedback_text  = feedback_text.strip(),
                plan_title     = selected_plan["title"],
                manager_db_id  = selected_plan["manager_id"],
                plan_id        = selected_plan["id"],
                feedback_type  = feedback_type,
            )

            if ok:
                st.success(
                    f"✅ Feedback sent to **{selected_plan['manager_name']}** "
                    f"and recorded successfully."
                )
            else:
                st.warning(
                    "Feedback saved to the database, but the email could not "
                    "be delivered. Check your email configuration in .env."
                )

    # Feedback history
    st.markdown("---")
    st.markdown("#### 📜 Feedback History for Selected Plan")
    client = get_service_client()
    hist_resp = (
        client
        .from_("admin_feedback")
        .select("message, feedback_type, sent_at, employees(name)")
        .eq("action_plan_id", selected_plan["id"])
        .order("sent_at", desc=True)
        .execute()
    )
    history = hist_resp.data or []
    if not history:
        st.caption("No feedback has been sent for this plan yet.")
    else:
        for h in history:
            emp  = h.pop("employees", None) or {}
            ftype_label = (
                "💬 Clarification" if h.get("feedback_type") == "clarification"
                else "💡 Improvement"
            )
            st.markdown(
                f"""
                <div style="border-left:3px solid {ADMIN_COLOUR};
                            padding:8px 12px;background:#FFF5F0;
                            border-radius:4px;margin-bottom:8px;">
                  <div style="font-size:0.8rem;color:#6B7280;">
                    {ftype_label} &nbsp;·&nbsp; {emp.get('name','Admin')}
                    &nbsp;·&nbsp; {h.get('sent_at','')[:16]}
                  </div>
                  <div style="margin-top:4px;font-size:0.9rem;color:#374151;">
                    {h.get('message','—')}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# --- Page: Export ---

def _render_export(user: dict) -> None:
    _section_header(
        "📤", "Export & Email Reports",
        "Download or email all action plans across zones"
    )

    plans = _fetch_all_plans()
    df    = _plans_to_df(plans)

    if df.empty:
        st.info("No action plans to export yet.")
        return

    # Zone filter
    zone_opts = ["All Zones"] + sorted(df["zone"].dropna().unique().tolist())
    sel_zone  = st.selectbox("Filter by Zone (optional)", zone_opts, key="export_zone")
    export_df = df if sel_zone == "All Zones" else df[df["zone"] == sel_zone]

    report_cols = [
        "manager_name", "zone", "function", "wef_element",
        "title", "description", "status", "start_date", "target_date",
    ]
    # export_df has raw names for generate_report; display_df has renamed names for preview
    export_df = export_df[[c for c in report_cols if c in export_df.columns]].copy()

    display_df = export_df.rename(columns={
        "manager_name": "Manager",
        "zone":         "Zone",
        "function":     "Function",
        "wef_element":  "WEF Element",
        "title":        "Title",
        "description":  "Description",
        "status":       "Status",
        "start_date":   "Start Date",
        "target_date":  "Target Date",
    })

    st.caption(f"**{len(export_df)} plans** ready to export")
    st.dataframe(display_df.head(10), use_container_width=True, hide_index=True)
    if len(export_df) > 10:
        st.caption(f"_Showing first 10 of {len(export_df)} rows. Full data will be in the export._")

    ts       = datetime.now().strftime("%Y%m%d_%H%M")
    zone_tag = sel_zone.replace(" ", "_") if sel_zone != "All Zones" else "AllZones"
    fname    = f"MAP_Report_{zone_tag}_{ts}"

    st.markdown("---")
    st.markdown("#### Download")
    dl_col1, dl_col2, dl_col3 = st.columns(3)

    with dl_col1:
        csv_bytes = generate_report(export_df, "CSV", fname)
        if csv_bytes:
            st.download_button(
                "⬇️ Download CSV",
                data=csv_bytes,
                file_name=f"{fname}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with dl_col2:
        xlsx_bytes = generate_report(export_df, "Excel", fname)
        if xlsx_bytes:
            st.download_button(
                "⬇️ Download Excel",
                data=xlsx_bytes,
                file_name=f"{fname}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with dl_col3:
        try:
            pdf_bytes = generate_report(export_df, "PDF", fname)
            if pdf_bytes:
                st.download_button(
                    "⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"{fname}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        except Exception as exc:
            st.error(f"PDF generation error: {exc}")

    # Email report
    st.markdown("---")
    st.markdown("#### Email Report")

    email_to = st.text_input(
        "Send to (email address)",
        value=user.get("email", ""),
        placeholder="recipient@xyzindustries.com",
        key="export_email_to",
    )
    email_fmt = st.selectbox(
        "Attachment format",
        ["PDF", "Excel", "CSV"],
        key="export_email_fmt",
    )

    if st.button("📧 Send Report via Email", use_container_width=False):
        if not email_to.strip():
            st.error("Please enter a recipient email address.")
            return

        try:
            content = generate_report(export_df, email_fmt, fname)
            if content is None:
                st.error("Could not generate the report file.")
                return

            suffix  = {"CSV": ".csv", "Excel": ".xlsx", "PDF": ".pdf"}[email_fmt]
            tmp_path = save_temp_file(content, suffix)

            ok = send_zone_report(
                hrbp_email    = email_to.strip(),
                zone          = sel_zone,
                attachment_path = tmp_path,
                hrbp_db_id    = user["db_id"],
            )

            try:
                os.remove(tmp_path)
            except Exception:
                pass

            if ok:
                st.success(f"✅ Report sent to **{email_to.strip()}** successfully.")
            else:
                st.warning(
                    "Report generated but email delivery failed. "
                    "Check your email configuration in .env."
                )
        except Exception as exc:
            st.error(f"Export / email error: {exc}")


# --- Page: Onboarding ---

def _render_onboarding(user: dict) -> None:
    _section_header(
        "👥", "Manager Onboarding — Stage 1",
        "Identify eligible managers and send invitation emails"
    )

    st.markdown(
        """
        **Eligibility criteria:** `Role = Manager` AND `Level = LEVEL 2`

        Click **Run Eligibility Check** to preview eligible managers before sending.
        """
    )

    if st.button("🔍 Run Eligibility Check", use_container_width=False):
        with st.spinner("Checking eligibility..."):
            eligible = get_eligible_managers()
        st.session_state["onboarding_eligible"] = eligible
        st.session_state.pop("onboarding_sent_ids", None)

    eligible: list[dict] = st.session_state.get("onboarding_eligible", [])
    if not eligible:
        if "onboarding_eligible" in st.session_state:
            st.warning("No eligible managers found (Role=Manager AND Level=LEVEL 2).")
        return

    # Already-invited check
    client = get_service_client()
    inv_resp = (
        client
        .from_("notifications_log")
        .select("recipient_id")
        .eq("type", "invitation")
        .eq("status", "sent")
        .execute()
    )
    already_invited_ids = {r["recipient_id"] for r in (inv_resp.data or [])}

    st.markdown(f"**{len(eligible)} eligible managers found:**")

    preview_data = []
    for m in eligible:
        invited = "✅ Invited" if m["id"] in already_invited_ids else "⏳ Pending"
        preview_data.append({
            "Name":     m["name"],
            "Email":    m["email"],
            "Zone":     m.get("zone", "—"),
            "Function": m.get("function", "—"),
            "Status":   invited,
        })

    preview_df = pd.DataFrame(preview_data)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    pending_managers = [
        m for m in eligible if m["id"] not in already_invited_ids
    ]

    if not pending_managers:
        st.success("✅ All eligible managers have already been invited.")
        return

    st.caption(f"**{len(pending_managers)}** manager(s) have not yet received an invitation.")

    send_col, _ = st.columns([1, 3])
    with send_col:
        if st.button(
            f"📧 Send Invitation Emails ({len(pending_managers)})",
            use_container_width=True,
        ):
            results = {"sent": 0, "failed": 0}
            progress_bar = st.progress(0)
            status_text  = st.empty()

            for i, mgr in enumerate(pending_managers):
                status_text.text(f"Sending to {mgr['name']}…")
                ok = send_invitation(
                    manager_email  = mgr["email"],
                    manager_name   = mgr["name"],
                    manager_db_id  = mgr["id"],
                )
                if ok:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                progress_bar.progress((i + 1) / len(pending_managers))

            status_text.empty()
            progress_bar.empty()

            if results["failed"] == 0:
                st.success(
                    f"✅ Invitations sent to all **{results['sent']}** managers."
                )
            else:
                st.warning(
                    f"Sent: {results['sent']} &nbsp;|&nbsp; "
                    f"Failed: {results['failed']}. "
                    f"Check email configuration in .env.",
                    icon="⚠️",
                )

            # Refresh
            st.session_state.pop("onboarding_eligible", None)
            st.rerun()


# --- Page: Notifications ---

def _render_notifications(user: dict) -> None:
    _section_header(
        "🔔", "Notifications",
        "Send manual notifications and trigger weekly reminders"
    )

    tab_manual, tab_reminder, tab_log = st.tabs(
        ["📢 Manual Notification", "⏰ Weekly Reminders", "📜 Notification Log"]
    )

    # Tab: Manual notification
    with tab_manual:
        st.markdown("#### Send a Custom Notification")
        st.caption("Compose and send a message to a selected audience.")

        client = get_service_client()

        audience = st.radio(
            "Audience",
            ["All Managers", "All HRBPs", "Specific Zone", "Specific Manager"],
            horizontal=True,
            key="notif_audience",
        )

        recipient_emails: list[str] = []
        audience_label = audience

        if audience == "All Managers":
            resp = client.from_("employees").select("email").eq("role", "Manager").execute()
            recipient_emails = [r["email"] for r in (resp.data or []) if r.get("email")]

        elif audience == "All HRBPs":
            resp = client.from_("employees").select("email").eq("role", "HRBP").execute()
            recipient_emails = [r["email"] for r in (resp.data or []) if r.get("email")]

        elif audience == "Specific Zone":
            zones    = _fetch_all_zones()
            sel_zone = st.selectbox("Select Zone", zones, key="notif_zone")
            if sel_zone:
                resp = (
                    client.from_("employees")
                    .select("email")
                    .eq("zone", sel_zone)
                    .eq("role", "Manager")
                    .execute()
                )
                recipient_emails = [r["email"] for r in (resp.data or []) if r.get("email")]
                audience_label   = f"Zone: {sel_zone}"

        elif audience == "Specific Manager":
            all_managers = _fetch_all_managers()
            mgr_opts     = {m["name"]: m for m in all_managers}
            if mgr_opts:
                sel_mgr_name = st.selectbox(
                    "Select Manager", list(mgr_opts.keys()), key="notif_mgr"
                )
                sel_mgr = mgr_opts[sel_mgr_name]
                recipient_emails = [sel_mgr["email"]]
                audience_label   = f"Manager: {sel_mgr_name}"

        if recipient_emails:
            st.caption(f"**{len(recipient_emails)} recipient(s)** in selected audience.")
        else:
            st.caption("No recipients found for selected audience.")

        notif_subject = st.text_input(
            "Subject *",
            placeholder="[MAP] Message from HR CoE",
            key="notif_subject",
        )
        notif_message = st.text_area(
            "Message *",
            height=120,
            max_chars=3000,
            placeholder="Enter your message here…",
            key="notif_message",
        )

        if st.button("📤 Send Notification", key="send_manual_notif"):
            if not notif_subject.strip():
                st.error("Please enter a subject.")
            elif not notif_message.strip():
                st.error("Please enter a message.")
            elif not recipient_emails:
                st.error("No recipients to send to. Select a valid audience first.")
            else:
                with st.spinner(f"Sending to {len(recipient_emails)} recipient(s)…"):
                    results = send_manual_notification(
                        recipient_emails = recipient_emails,
                        subject          = notif_subject.strip(),
                        message          = notif_message.strip(),
                        sender_db_id     = user["db_id"],
                        audience_label   = audience_label,
                    )
                if results["failed"] == 0:
                    st.success(f"✅ Notification sent to **{results['sent']}** recipient(s).")
                else:
                    st.warning(
                        f"Sent: {results['sent']} | Failed: {results['failed']}. "
                        "Check your email configuration."
                    )

    # Tab: Weekly reminders
    with tab_reminder:
        st.markdown("#### Weekly Reminder Engine")
        st.markdown(
            """
            Triggers two reminder conditions:

            1. **No Plans Created** — Eligible managers who have not created any Action Plans
            2. **Plan Stuck in Initiated** — Plans in `Initiated` status with no update in 7+ days
            """
        )

        st.info(
            "💡 **Production note:** In production, this function would be called "
            "automatically by a scheduled cron job. For the MVP, trigger it manually here.",
            icon="ℹ️",
        )

        if st.button("⏰ Send Weekly Reminders Now", use_container_width=False):
            with st.spinner("Checking conditions and sending reminders…"):
                summary = check_and_send_reminders()

            total_sent = summary["no_plans"] + summary["stuck"]
            if total_sent == 0 and summary["errors"] == 0:
                st.success(
                    "✅ Reminder check complete. No reminders needed right now — "
                    "all managers are active and no plans are stuck."
                )
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("No Plans Reminders", summary["no_plans"])
                with col2:
                    st.metric("Stuck Plan Reminders", summary["stuck"])
                with col3:
                    st.metric("Errors", summary["errors"])

                if summary["errors"] > 0:
                    st.warning(
                        f"{summary['errors']} reminder(s) failed to send. "
                        "Check your email configuration in .env."
                    )
                else:
                    st.success(f"✅ {total_sent} reminder(s) sent successfully.")

    # Tab: Notification log
    with tab_log:
        st.markdown("#### Notification History (Last 100)")
        log = _fetch_notification_log(limit=100)

        if not log:
            st.caption("No notifications have been sent yet.")
        else:
            log_df = pd.DataFrame(log)[
                ["recipient_name", "type", "status", "sent_at", "action_plan_id"]
            ].rename(columns={
                "recipient_name": "Recipient",
                "type":           "Type",
                "status":         "Status",
                "sent_at":        "Sent At",
                "action_plan_id": "Plan ID",
            })
            log_df["Sent At"] = pd.to_datetime(log_df["Sent At"]).dt.strftime("%d %b %Y %H:%M")

            def _style_log_status(val):
                return "color: #4CAF50; font-weight:600;" if val == "sent" else "color: #EF4444; font-weight:600;"

            styled_log = log_df.style.map(_style_log_status, subset=["Status"])
            st.dataframe(styled_log, use_container_width=True, hide_index=True)


# --- Entry point ---

def render() -> None:
    """Route to the correct admin page."""
    user = require_auth()

    page = get_current_page()

    if page == "dashboard":
        _render_overview(user)
    elif page == "all_plans":
        _render_all_plans(user)
    elif page == "feedback":
        _render_feedback(user)
    elif page == "export":
        _render_export(user)
    elif page == "onboarding":
        _render_onboarding(user)
    elif page == "notifications":
        _render_notifications(user)
    else:
        _render_overview(user)  # fallback