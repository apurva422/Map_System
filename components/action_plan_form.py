"""Reusable Action Plan form — create, edit, or read-only display."""

from __future__ import annotations

import streamlit as st
from datetime import date, timedelta

from config import WEF_ELEMENTS, PLAN_STATUSES, STATUS_COLOURS


# Helpers

def _status_badge(status: str) -> str:
    """HTML badge for a status."""
    colour = STATUS_COLOURS.get(status, "#9E9E9E")
    return (
        f"<span style='"
        f"background:{colour}22;color:{colour};"
        f"border:1px solid {colour};"
        f"padding:2px 10px;border-radius:12px;"
        f"font-size:0.8rem;font-weight:600;"
        f"'>{status}</span>"
    )


def _wef_label(element_num: int) -> str:
    """Return 'Q1 — I know what is expected…' label."""
    text = WEF_ELEMENTS.get(element_num, "Unknown")
    short = text if len(text) <= 70 else text[:67] + "…"
    return f"Q{element_num} — {short}"


# Public API

def render_form(
    user: dict,
    existing_plan: dict | None = None,
    used_elements: list[int] | None = None,
    on_submit: callable | None = None,
    readonly: bool = False,
) -> None:
    """Render the Action Plan create/edit form."""
    used_elements = used_elements or []
    is_edit       = existing_plan is not None

    # Read-only display
    if readonly and is_edit:
        _render_readonly_card(existing_plan)
        return

    # Form
    form_key = f"ap_form_{'edit' if is_edit else 'create'}_{existing_plan.get('id', 'new') if is_edit else 'new'}"

    with st.form(form_key, clear_on_submit=not is_edit):

        # WEF selector
        st.markdown("**Workplace Engagement Framework Element**")

        if is_edit:
            # WEF locked in edit mode
            locked_num = existing_plan.get("wef_element", 1)
            st.markdown(
                f"<div style='background:#F3F4F6;border-radius:6px;padding:8px 12px;"
                f"font-size:0.9rem;color:#374151;'>"
                f"🔒 <strong>Q{locked_num}</strong> — {WEF_ELEMENTS.get(locked_num, '')}"
                f"</div>",
                unsafe_allow_html=True,
            )
            selected_element = locked_num
        else:
            # Build available elements
            all_elements = list(range(1, 13))
            available    = [e for e in all_elements if e not in used_elements]

            if not available:
                st.warning(
                    "✅ You have already created Action Plans for all 12 WEF elements. "
                    "No new plans can be created."
                )
                return

            options_display = [_wef_label(e) for e in available]

            chosen_label = st.selectbox(
                "Select WEF Element",
                options=options_display,
                help=(
                    f"You have used {len(used_elements)}/12 elements. "
                    "Each element allows exactly one Action Plan."
                ),
            )
            selected_element = available[options_display.index(chosen_label)]

            # Show full question
            st.caption(f"📌 {WEF_ELEMENTS.get(selected_element, '')}")

        st.markdown("---")

        # Core fields
        col_left, col_right = st.columns(2)

        with col_left:
            title = st.text_input(
                "Action Plan Title *",
                value=existing_plan.get("title", "") if is_edit else "",
                max_chars=150,
                placeholder="e.g. Weekly recognition programme",
                help="A short, descriptive title for this Action Plan.",
            )

        with col_right:
            # Status shown in edit mode only
            if is_edit:
                current_status = existing_plan.get("status", "Initiated")
                status_options = PLAN_STATUSES

                # Forward-only guidance
                status = st.selectbox(
                    "Status *",
                    options=status_options,
                    index=status_options.index(current_status),
                    help="Initiated → Ongoing → Closed. Closed is the terminal state.",
                )
            else:
                status = "Initiated"
                st.markdown(
                    "<div style='margin-top:1.6rem;'>"
                    + _status_badge("Initiated")
                    + " <small style='color:#6B7280;'>Status on creation</small></div>",
                    unsafe_allow_html=True,
                )

        description = st.text_area(
            "Description *",
            value=existing_plan.get("description", "") if is_edit else "",
            height=110,
            max_chars=2000,
            placeholder=(
                "Describe the actions you plan to take, the expected outcome, "
                "and how this addresses the selected WEF element."
            ),
        )

        col_d1, col_d2 = st.columns(2)

        with col_d1:
            default_start = (
                date.fromisoformat(existing_plan["start_date"])
                if is_edit and existing_plan.get("start_date")
                else date.today()
            )
            start_date = st.date_input(
                "Start Date *",
                value=default_start,
                help="When will you begin executing this Action Plan?",
            )

        with col_d2:
            default_target = (
                date.fromisoformat(existing_plan["target_date"])
                if is_edit and existing_plan.get("target_date")
                else date.today() + timedelta(days=30)
            )
            target_date = st.date_input(
                "Target Completion Date *",
                value=default_target,
                help="When do you aim to close this Action Plan?",
            )

        st.markdown("---")

        # Submit
        btn_label = "💾 Update Action Plan" if is_edit else "🚀 Create Action Plan"
        submitted = st.form_submit_button(btn_label, use_container_width=True)

    # Validation & callback
    if submitted:
        errors = []
        if not title.strip():
            errors.append("Title is required.")
        if not description.strip():
            errors.append("Description is required.")
        if target_date < start_date:
            errors.append("Target date cannot be before the start date.")

        if errors:
            for err in errors:
                st.error(f"⚠️ {err}")
            return

        payload = {
            "wef_element":  selected_element,
            "title":        title.strip(),
            "description":  description.strip(),
            "start_date":   start_date.isoformat(),
            "target_date":  target_date.isoformat(),
            "status":       status,
        }

        if on_submit:
            on_submit(payload)


# Read-only card

def _render_readonly_card(plan: dict) -> None:
    """Read-only plan card (CEO view)."""
    status  = plan.get("status", "—")
    colour  = STATUS_COLOURS.get(status, "#9E9E9E")
    wef_num = plan.get("wef_element", "—")

    st.markdown(
        f"""
        <div style='background:#F9FAFB;border:1px solid #E5E7EB;
                    border-radius:10px;padding:1.2rem 1.5rem;margin-bottom:0.5rem;'>
            <div style='display:flex;justify-content:space-between;align-items:center;'>
                <span style='font-size:1rem;font-weight:700;color:#111827;'>
                    {plan.get('title','—')}
                </span>
                <span style='background:{colour}22;color:{colour};
                             border:1px solid {colour};padding:2px 12px;
                             border-radius:12px;font-size:0.8rem;font-weight:600;'>
                    {status}
                </span>
            </div>
            <div style='margin:0.6rem 0;font-size:0.85rem;color:#6B7280;'>
                <strong>Q{wef_num}</strong> — {WEF_ELEMENTS.get(wef_num, '')}
            </div>
            <p style='font-size:0.9rem;color:#374151;margin:0.4rem 0;'>
                {plan.get('description','—')}
            </p>
            <div style='display:flex;gap:2rem;font-size:0.8rem;color:#9CA3AF;margin-top:0.8rem;'>
                <span>📅 Start: {plan.get('start_date','—')}</span>
                <span>🎯 Target: {plan.get('target_date','—')}</span>
                <span>🗺️ Zone: {plan.get('zone','—')}</span>
                <span>⚙️ Function: {plan.get('function','—')}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )