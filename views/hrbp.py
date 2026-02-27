"""
views/hrbp.py
=============
Full HRBP View for the MAP System — Phase 4.

Pages (routed via st.session_state["current_page"])
----------------------------------------------------
dashboard   -> Zone summary cards + status/WEF breakdown
zone_plans  -> Filterable table of all plans in HRBP zone;
               click into any plan for detail + backend update
export      -> Download zone report as CSV / Excel / PDF;
               email zone report
"""

from __future__ import annotations

import io
import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

from auth import get_current_user
from config import WEF_ELEMENTS, PLAN_STATUSES, STATUS_COLOURS
from database.supabase_client import supabase, get_service_client
from components.sidebar import get_current_page
from utils.email_service import send_zone_report


# =============================================================================
# DATA LAYER
# =============================================================================

def _fetch_manager_lookup(manager_ids: list[str]) -> dict[str, dict]:
    """
    Fetch name and email for a list of manager UUIDs.
    Uses the service client to bypass RLS — the HRBP anon role has no
    SELECT policy on the employees table, so the anon client returns nothing.
    Reading employee names is safe; no sensitive fields are exposed.
    NOTE: 'function' is a reserved SQL keyword — read from action_plans directly.
    """
    if not manager_ids:
        return {}
    try:
        svc = get_service_client()
        resp = (
            svc
            .from_("employees")
            .select("id, name, email")
            .in_("id", manager_ids)
            .execute()
        )
        return {row["id"]: row for row in (resp.data or [])}
    except Exception as exc:
        st.error(f"Manager lookup failed: {exc}")
        return {}


def _fetch_zone_plans(zone: str) -> list[dict]:
    """Return all action plans for this zone with manager name/email/function."""
    try:
        resp = (
            supabase
            .from_("action_plans")
            .select("*")
            .eq("zone", zone)
            .order("created_at", desc=True)
            .execute()
        )
        plans = resp.data or []
        if not plans:
            return []

        # Fetch manager details in one round-trip
        manager_ids = list({p["manager_id"] for p in plans if p.get("manager_id")})
        lookup = _fetch_manager_lookup(manager_ids)

        for row in plans:
            emp = lookup.get(row.get("manager_id"), {})
            row["manager_name"]     = emp.get("name", "—")
            row["manager_email"]    = emp.get("email", "")
            # function is already denormalized on action_plans — use it directly
            row["manager_function"] = row.get("function", "—") or "—"
        return plans
    except Exception as exc:
        st.error(f"Error fetching zone plans: {exc}")
        return []


def _fetch_plan_by_id(plan_id: str) -> dict | None:
    try:
        resp = (
            supabase
            .from_("action_plans")
            .select("*")
            .eq("id", plan_id)
            .single()
            .execute()
        )
        if not resp.data:
            return None
        row = resp.data
        # Fetch manager details separately — no FK name dependency
        if row.get("manager_id"):
            lookup = _fetch_manager_lookup([row["manager_id"]])
            emp    = lookup.get(row["manager_id"], {})
            row["manager_name"]     = emp.get("name", "—")
            row["manager_email"]    = emp.get("email", "")
        else:
            row["manager_name"]     = "—"
            row["manager_email"]    = ""
        # function is denormalized on action_plans — read it directly
        row["manager_function"] = row.get("function", "—") or "—"
        return row
    except Exception:
        return None


def _fetch_progress_updates(plan_id: str) -> list[dict]:
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


def _add_hrbp_update(plan_id: str, hrbp_db_id: str, text: str) -> bool:
    try:
        supabase.from_("progress_updates").insert({
            "action_plan_id":  plan_id,
            "updated_by":      hrbp_db_id,
            "updated_by_role": "HRBP",
            "update_text":     text,
            "created_at":      datetime.utcnow().isoformat(),
        }).execute()
        return True
    except Exception as exc:
        st.error(f"Error saving update: {exc}")
        return False


def _fetch_hrbp_email(hrbp_db_id: str) -> str:
    try:
        resp = (
            supabase
            .from_("employees")
            .select("email")
            .eq("id", hrbp_db_id)
            .single()
            .execute()
        )
        return resp.data.get("email", "") if resp.data else ""
    except Exception:
        return ""


# =============================================================================
# UI HELPERS
# =============================================================================

def _status_badge(status: str) -> str:
    colour = STATUS_COLOURS.get(status, "#9E9E9E")
    return (
        f"<span style='background:{colour}22;color:{colour};"
        f"border:1px solid {colour};padding:2px 10px;"
        f"border-radius:12px;font-size:0.78rem;font-weight:600;'>{status}</span>"
    )


def _metric_card(label: str, value, colour: str = "#375623") -> str:
    return (
        f"<div style='background:#fff;border:1px solid #E5E7EB;border-radius:10px;"
        f"padding:1rem 1.2rem;text-align:center;border-top:3px solid {colour};'>"
        f"<div style='font-size:1.8rem;font-weight:800;color:{colour};'>{value}</div>"
        f"<div style='font-size:0.82rem;color:#6B7280;margin-top:0.2rem;'>{label}</div>"
        f"</div>"
    )


def _format_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso_str[:16] if iso_str else "—"


def _plans_to_df(plans: list[dict]) -> "pd.DataFrame":
    if not plans:
        return pd.DataFrame()
    rows = []
    for p in plans:
        wef_num = p.get("wef_element", "")
        rows.append({
            "Plan ID":         p.get("id", ""),
            "Manager":         p.get("manager_name", "—"),
            "Function":        p.get("manager_function", "—"),
            "Zone":            p.get("zone", "—"),
            "WEF Element No.": wef_num,
            "WEF Element":     WEF_ELEMENTS.get(wef_num, ""),
            "Title":           p.get("title", ""),
            "Description":     p.get("description", ""),
            "Status":          p.get("status", ""),
            "Start Date":      p.get("start_date", ""),
            "Target Date":     p.get("target_date", ""),
            "Created At":      (p.get("created_at", "") or "")[:10],
            "Last Updated":    (p.get("updated_at", "") or "")[:10],
        })
    return pd.DataFrame(rows)


def _apply_filters(plans, mgr, fn, wef, sts):
    f = plans
    if mgr != "All":
        f = [p for p in f if p.get("manager_name") == mgr]
    if fn  != "All":
        f = [p for p in f if p.get("manager_function") == fn]
    if wef != "All":
        num = int(wef.split("—")[0].replace("Q","").strip())
        f = [p for p in f if p.get("wef_element") == num]
    if sts != "All":
        f = [p for p in f if p.get("status") == sts]
    return f


# =============================================================================
# PAGE: ZONE DASHBOARD
# =============================================================================

def _render_dashboard(user: dict) -> None:
    zone  = user.get("zone", "—")
    plans = _fetch_zone_plans(zone)

    st.markdown(f"## 🏠 Zone Dashboard — {zone}")
    st.caption(f"All Action Plans across your zone. Total records: **{len(plans)}**")

    total     = len(plans)
    initiated = sum(1 for p in plans if p.get("status") == "Initiated")
    ongoing   = sum(1 for p in plans if p.get("status") == "Ongoing")
    closed    = sum(1 for p in plans if p.get("status") == "Closed")
    managers  = len(set(p.get("manager_id") for p in plans))
    wef_used  = len(set(p.get("wef_element") for p in plans))

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    for col, label, value, colour in [
        (c1, "Total Plans",  total,     "#375623"),
        (c2, "Initiated",    initiated, "#9E9E9E"),
        (c3, "Ongoing",      ongoing,   "#FFC107"),
        (c4, "Closed",       closed,    "#4CAF50"),
        (c5, "Managers",     managers,  "#2E75B6"),
        (c6, "WEF Elements", wef_used,  "#7030A0"),
    ]:
        with col:
            st.markdown(_metric_card(label, value, colour), unsafe_allow_html=True)

    if not plans:
        st.info("No Action Plans have been created in your zone yet.")
        return

    st.markdown("---")
    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown("#### 📊 Plans by Status")
        for status, count in [("Initiated", initiated), ("Ongoing", ongoing), ("Closed", closed)]:
            colour = STATUS_COLOURS.get(status, "#9E9E9E")
            pct    = int((count / total) * 100) if total else 0
            st.markdown(
                f"<div style='margin-bottom:0.7rem;'>"
                f"<div style='display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:3px;'>"
                f"<span>{status}</span><span style='color:#6B7280;'>{count} ({pct}%)</span></div>"
                f"<div style='background:#F3F4F6;border-radius:4px;height:10px;'>"
                f"<div style='background:{colour};width:{max(pct,2)}%;height:10px;border-radius:4px;'></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

    with right_col:
        st.markdown("#### 🎯 Plans by WEF Element")
        wef_counts: dict = {}
        for p in plans:
            k = p.get("wef_element", 0)
            wef_counts[k] = wef_counts.get(k, 0) + 1
        for wef_num, count in sorted(wef_counts.items(), key=lambda x: x[1], reverse=True)[:6]:
            lbl   = WEF_ELEMENTS.get(wef_num, f"Q{wef_num}")
            short = lbl[:38] + "…" if len(lbl) > 38 else lbl
            pct   = int((count / total) * 100) if total else 0
            st.markdown(
                f"<div style='margin-bottom:0.6rem;'>"
                f"<div style='display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:3px;'>"
                f"<span title='{lbl}'>Q{wef_num} — {short}</span>"
                f"<span style='color:#6B7280;'>{count}</span></div>"
                f"<div style='background:#F3F4F6;border-radius:4px;height:8px;'>"
                f"<div style='background:#375623;width:{max(pct,2)}%;height:8px;border-radius:4px;'></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown("#### 📋 Recent Plans in Your Zone")
    for plan in plans[:5]:
        status    = plan.get("status", "Initiated")
        colour    = STATUS_COLOURS.get(status, "#9E9E9E")
        wef_num   = plan.get("wef_element", "—")
        wef_text  = WEF_ELEMENTS.get(wef_num, "")
        short_wef = wef_text[:50] + "…" if len(wef_text) > 50 else wef_text
        st.markdown(
            f"<div style='background:#fff;border:1px solid #E5E7EB;border-radius:10px;"
            f"padding:0.8rem 1.2rem;margin-bottom:0.5rem;border-left:4px solid {colour};'>"
            f"<div style='display:flex;justify-content:space-between;'><div>"
            f"<strong style='font-size:0.92rem;'>{plan.get('title','—')}</strong><br>"
            f"<span style='font-size:0.78rem;color:#6B7280;'>"
            f"{plan.get('manager_name','—')} · Q{wef_num} — {short_wef}</span></div>"
            f"<span style='background:{colour}22;color:{colour};border:1px solid {colour};"
            f"padding:2px 10px;border-radius:12px;font-size:0.76rem;font-weight:600;"
            f"white-space:nowrap;margin-left:1rem;align-self:center;'>{status}</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
    if len(plans) > 5:
        st.caption(f"Showing 5 of {len(plans)}. Go to Zone Action Plans to see all.")


# =============================================================================
# PAGE: ZONE ACTION PLANS
# =============================================================================

def _render_zone_plans(user: dict) -> None:
    if st.session_state.get("selected_plan_id"):
        _render_plan_detail(user, st.session_state["selected_plan_id"])
    else:
        _render_plan_list(user)


def _render_plan_list(user: dict) -> None:
    zone  = user.get("zone", "—")
    plans = _fetch_zone_plans(zone)

    st.markdown(f"## 📋 Zone Action Plans — {zone}")

    if not plans:
        st.info("No Action Plans have been created in your zone yet.")
        return

    fc1, fc2, fc3, fc4 = st.columns(4)
    managers  = sorted(set(p.get("manager_name", "—") for p in plans))
    functions = sorted(set(p.get("manager_function", "—") for p in plans))
    wef_nums  = sorted(set(p.get("wef_element") for p in plans))
    wef_lbl   = [f"Q{n} — {WEF_ELEMENTS.get(n,'')[:35]}" for n in wef_nums]

    with fc1:
        mgr_f = st.selectbox("Manager",     ["All"] + managers,  key="hrbp_mgr")
    with fc2:
        fn_f  = st.selectbox("Function",    ["All"] + functions, key="hrbp_fn")
    with fc3:
        wef_f = st.selectbox("WEF Element", ["All"] + wef_lbl,   key="hrbp_wef")
    with fc4:
        sts_f = st.selectbox("Status",      ["All"] + PLAN_STATUSES, key="hrbp_sts")

    filtered = _apply_filters(plans, mgr_f, fn_f, wef_f, sts_f)
    st.markdown(
        f"<small style='color:#6B7280;'>Showing <strong>{len(filtered)}</strong> of {len(plans)} plans</small>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    if not filtered:
        st.info("No plans match the selected filters.")
        return

    for plan in filtered:
        status   = plan.get("status", "Initiated")
        colour   = STATUS_COLOURS.get(status, "#9E9E9E")
        wef_num  = plan.get("wef_element", "—")
        wef_text = WEF_ELEMENTS.get(wef_num, "")

        row_l, row_r = st.columns([5, 1])
        with row_l:
            st.markdown(
                f"<div style='padding:0.3rem 0;'>"
                f"<strong style='font-size:0.93rem;'>{plan.get('title','—')}</strong><br>"
                f"<span style='font-size:0.8rem;color:#6B7280;'>"
                f"{plan.get('manager_name','—')} · {plan.get('manager_function','—')} · "
                f"Q{wef_num} — {wef_text[:45]}{'…' if len(wef_text)>45 else ''}"
                f"</span></div>",
                unsafe_allow_html=True,
            )
        with row_r:
            b1, b2 = st.columns([1,1])
            with b1:
                st.markdown(
                    f"<div style='padding:0.55rem 0;'>{_status_badge(status)}</div>",
                    unsafe_allow_html=True,
                )
            with b2:
                if st.button("Open →", key=f"hrbp_open_{plan['id']}"):
                    st.session_state["selected_plan_id"] = plan["id"]
                    st.rerun()
        st.markdown("<hr style='margin:0.35rem 0 0.55rem 0;border-color:#F3F4F6;'>", unsafe_allow_html=True)


def _render_plan_detail(user: dict, plan_id: str) -> None:
    plan = _fetch_plan_by_id(plan_id)
    if not plan:
        st.error("Plan not found.")
        st.session_state.pop("selected_plan_id", None)
        st.rerun()
        return

    if plan.get("zone") != user.get("zone"):
        st.error("Access denied. This plan is not in your zone.")
        st.session_state.pop("selected_plan_id", None)
        st.rerun()
        return

    if st.button("← Back to Zone Plans"):
        st.session_state.pop("selected_plan_id", None)
        st.rerun()

    status  = plan.get("status", "Initiated")
    wef_num = plan.get("wef_element", "—")

    st.markdown(
        f"## {plan.get('title','—')} &nbsp; {_status_badge(status)}",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Q{wef_num} — {WEF_ELEMENTS.get(wef_num, '')} · "
        f"Manager: {plan.get('manager_name','—')} · "
        f"Function: {plan.get('manager_function','—')}"
    )
    st.markdown("---")

    tab_ov, tab_upd, tab_hist = st.tabs(["📄 Overview", "➕ Add Backend Update", "📜 Progress History"])

    with tab_ov:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Description**")
            st.markdown(
                f"<div style='background:#F9FAFB;border-radius:8px;padding:0.8rem 1rem;"
                f"font-size:0.9rem;color:#374151;min-height:80px;'>"
                f"{plan.get('description','—')}</div>",
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown("**Plan Details**")
            for key, val in {
                "🎯 WEF Element":  f"Q{wef_num} — {WEF_ELEMENTS.get(wef_num,'')}",
                "📅 Start Date":   plan.get("start_date", "—"),
                "🏁 Target Date":  plan.get("target_date", "—"),
                "📊 Status":       status,
                "👤 Manager":      plan.get("manager_name", "—"),
                "⚙️ Function":     plan.get("manager_function", "—"),
                "🗺️ Zone":         plan.get("zone", "—"),
                "🕒 Created":      (plan.get("created_at","") or "")[:10],
                "🔄 Last Updated": (plan.get("updated_at","") or "")[:10],
            }.items():
                d1, d2 = st.columns([1,2])
                d1.markdown(f"<small style='color:#6B7280;'>{key}</small>", unsafe_allow_html=True)
                d2.markdown(f"<small style='color:#111827;font-weight:600;'>{val}</small>", unsafe_allow_html=True)

    with tab_upd:
        st.markdown("#### Add Backend Update")
        st.caption("Logged as HRBP update. Cannot be deleted.")
        if status == "Closed":
            st.info("This plan is Closed. No further updates can be added.")
        else:
            with st.form(f"hrbp_upd_{plan_id}"):
                txt     = st.text_area("Backend Update Note", height=130, max_chars=1500,
                                        placeholder="e.g. Reviewed with manager during zone call...")
                save_it = st.form_submit_button("💾 Save Backend Update", use_container_width=True)
            if save_it:
                if not txt.strip():
                    st.error("Update note cannot be empty.")
                else:
                    if _add_hrbp_update(plan_id, user["db_id"], txt.strip()):
                        st.success("Backend update saved.")
                        import time; time.sleep(0.8)
                        st.rerun()

    with tab_hist:
        st.markdown("#### Progress History")
        updates = _fetch_progress_updates(plan_id)
        if not updates:
            st.info("No updates recorded yet.")
        else:
            st.caption(f"{len(updates)} update(s)")
            st.markdown("---")
            for upd in updates:
                role   = upd.get("updated_by_role","Manager")
                bc     = "#375623" if role=="HRBP" else "#2E75B6"
                bg     = "#F0FFF4" if role=="HRBP" else "#EFF6FF"
                rlbl   = "🗺️ HRBP Update" if role=="HRBP" else "👤 Manager Update"
                uname  = (upd.get("employees") or {}).get("name","")
                ts     = _format_time(upd.get("created_at",""))
                import html as _html
                safe_txt  = _html.escape(str(upd.get("update_text", "—")))
                name_part = f"&#8212; {_html.escape(uname)}" if uname else ""
                card_html = (
                    f"<div style='border-left:4px solid {bc};background:{bg};"
                    f"border-radius:0 8px 8px 0;padding:0.7rem 1rem;margin-bottom:0.8rem;'>"
                    f"<div style='display:flex;justify-content:space-between;"
                    f"align-items:center;margin-bottom:0.3rem;'>"
                    f"<span style='font-size:0.78rem;font-weight:700;color:{bc};'>"
                    f"{rlbl} {name_part}</span>"
                    f"<span style='font-size:0.75rem;color:#9CA3AF;'>{ts}</span></div>"
                    f"<p style='font-size:0.88rem;color:#374151;margin:0;'>{safe_txt}</p>"
                    f"</div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)


# =============================================================================
# PAGE: EXPORT / EMAIL
# =============================================================================

def _generate_pdf(df: "pd.DataFrame", zone: str) -> bytes | None:
    try:
        from fpdf import FPDF
        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()

        pdf.set_font("Helvetica","B",14)
        pdf.cell(0,10,f"MAP System — Zone Report: {zone}",ln=True,align="C")
        pdf.set_font("Helvetica","",9)
        pdf.cell(0,6,f"Generated: {datetime.today().strftime('%d %b %Y')}",ln=True,align="C")
        pdf.ln(4)

        show_cols  = ["Manager","Function","WEF Element No.","Title","Status","Start Date","Target Date"]
        show_cols  = [c for c in show_cols if c in df.columns]
        col_widths = {"Manager":38,"Function":30,"WEF Element No.":18,"Title":60,
                      "Status":22,"Start Date":22,"Target Date":22}

        pdf.set_fill_color(55,86,35)
        pdf.set_text_color(255,255,255)
        pdf.set_font("Helvetica","B",8)
        for col in show_cols:
            pdf.cell(col_widths.get(col,30),7,col,border=1,fill=True,align="C")
        pdf.ln()

        pdf.set_text_color(30,30,30)
        pdf.set_font("Helvetica","",8)
        fill = False
        for _, row in df[show_cols].iterrows():
            pdf.set_fill_color(240,245,240) if fill else pdf.set_fill_color(255,255,255)
            for col in show_cols:
                val = str(row.get(col,""))
                mc  = int(col_widths.get(col,30)/2.2)
                val = val[:mc]+"…" if len(val)>mc else val
                pdf.cell(col_widths.get(col,30),6,val,border=1,fill=True)
            pdf.ln()
            fill = not fill

        return bytes(pdf.output())
    except Exception as exc:
        st.error(f"PDF error: {exc}")
        return None


def _render_export(user: dict) -> None:
    zone  = user.get("zone","—")
    plans = _fetch_zone_plans(zone)

    st.markdown(f"## 📤 Export Zone Report — {zone}")
    st.caption(f"Export all Action Plans for **{zone}** zone. Currently **{len(plans)}** plan(s).")

    if not plans:
        st.info("No plans to export yet.")
        return

    df = _plans_to_df(plans)
    st.markdown("---")
    st.markdown("### 📥 Download Report")

    dl1, dl2, dl3 = st.columns(3)

    with dl1:
        st.download_button(
            label="⬇️ Download CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"MAP_Zone_{zone}_{datetime.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with dl2:
        xl_buf = io.BytesIO()
        with pd.ExcelWriter(xl_buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="Zone Plans")
        st.download_button(
            label="⬇️ Download Excel",
            data=xl_buf.getvalue(),
            file_name=f"MAP_Zone_{zone}_{datetime.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with dl3:
        if st.button("⬇️ Generate PDF", use_container_width=True, key="gen_pdf"):
            pdf_bytes = _generate_pdf(df, zone)
            if pdf_bytes:
                st.download_button(
                    label="📄 Click to Save PDF",
                    data=pdf_bytes,
                    file_name=f"MAP_Zone_{zone}_{datetime.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="save_pdf",
                )

    st.markdown("---")
    st.markdown("### 📧 Email Zone Report")
    st.caption("Sends the report to your registered email address as an attachment.")

    fmt = st.selectbox("Attachment format", ["CSV","Excel"], key="hrbp_email_fmt")

    if st.button("📧 Send Zone Report to My Email", key="hrbp_send_email"):
        hrbp_email = _fetch_hrbp_email(user["db_id"])
        if not hrbp_email:
            st.error("Could not find your email address. Contact the administrator.")
        else:
            with st.spinner("Generating and sending…"):
                suffix = ".csv" if fmt=="CSV" else ".xlsx"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp_path = tmp.name
                    if fmt=="CSV":
                        tmp.write(df.to_csv(index=False).encode("utf-8"))
                    else:
                        xl2 = io.BytesIO()
                        with pd.ExcelWriter(xl2, engine="openpyxl") as w2:
                            df.to_excel(w2, index=False, sheet_name="Zone Plans")
                        tmp.write(xl2.getvalue())

                ok = send_zone_report(
                    hrbp_email=hrbp_email,
                    zone=zone,
                    attachment_path=tmp_path,
                    hrbp_db_id=user["db_id"],
                )
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

            if ok:
                st.success(f"Zone report sent to **{hrbp_email}** successfully!")
            else:
                st.error("Email failed. Check EMAIL_SENDER/EMAIL_PASSWORD in .env or download manually.")

    st.markdown("---")
    st.markdown("### 👀 Report Preview")
    st.dataframe(
        df.drop(columns=["Plan ID","Description"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# TOP-LEVEL RENDER
# =============================================================================

def render() -> None:
    user = get_current_user()
    if not user:
        st.error("Session expired. Please log in again.")
        st.stop()
    if user.get("role") != "HRBP":
        st.error("Access denied. This view is for HRBPs only.")
        st.stop()
    if not user.get("zone"):
        st.error("Your account has no zone assigned. Contact the HR Administrator.")
        st.stop()

    page = get_current_page()
    if page == "dashboard":
        _render_dashboard(user)
    elif page == "zone_plans":
        _render_zone_plans(user)
    elif page == "export":
        _render_export(user)
    else:
        st.session_state["current_page"] = "dashboard"
        _render_dashboard(user)