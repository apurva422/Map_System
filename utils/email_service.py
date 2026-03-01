"""Email functions — smtplib+Gmail (MVP). Swap _send() to switch provider."""

from __future__ import annotations

import os
import smtplib
from datetime import datetime, timedelta, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import EMAIL_SENDER, EMAIL_PASSWORD
from database.supabase_client import supabase, get_service_client


# Internal send helper

def _send(
    to: str | list[str],
    subject: str,
    body_html: str,
    attachment_path: str | None = None,
) -> tuple[bool, str]:
    """Send email via Gmail SMTP SSL. Returns (success, error_msg)."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return False, "EMAIL_SENDER / EMAIL_PASSWORD not configured in .env"

    recipients = [to] if isinstance(to, str) else to
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False, "No valid recipient email addresses provided."

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = ", ".join(recipients)

    msg.attach(MIMEText(body_html, "html"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(attachment_path)}"',
        )
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, recipients, msg.as_string())
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _log_notification(
    recipient_id: str,
    notif_type: str,
    action_plan_id: str | None,
    status: str,
) -> None:
    """Log to notifications_log; never raises."""
    try:
        supabase.from_("notifications_log").insert({
            "recipient_id":   recipient_id,
            "type":           notif_type,
            "action_plan_id": action_plan_id,
            "sent_at":        datetime.utcnow().isoformat(),
            "status":         status,
        }).execute()
    except Exception:
        pass


def _base_footer() -> str:
    return (
        "<hr style='border:none;border-top:1px solid #E5E7EB;margin:1.5rem 0;'>"
        "<p style='color:#9CA3AF;font-size:0.8rem;margin:0;'>"
        "This is an automated message from the MAP System — XYZ Industries HR CoE."
        "</p>"
    )


# Public email functions

def send_plan_created(
    manager_email: str,
    reporting_manager_email: str,
    plan_details: dict,
    manager_db_id: str,
    plan_id: str | None = None,
) -> None:
    """Notify manager and reporting manager of new plan."""
    title      = plan_details.get("title", "—")
    wef        = plan_details.get("wef_element", "—")
    status     = plan_details.get("status", "Initiated")
    target     = plan_details.get("target_date", "—")
    start      = plan_details.get("start_date", "—")
    zone       = plan_details.get("zone", "—")
    function   = plan_details.get("function", "—")

    subject = f"[MAP] New Action Plan Created — {title}"
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#C55A11;padding:16px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;font-size:1.2rem;">📋 New Action Plan Created</h2>
      </div>
      <div style="background:#fff;border:1px solid #E5E7EB;
                  border-radius:0 0 8px 8px;padding:24px;">
        <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
          <tr><td style="padding:6px 0;color:#6B7280;width:140px;">Title</td>
              <td style="padding:6px 0;font-weight:600;">{title}</td></tr>
          <tr><td style="padding:6px 0;color:#6B7280;">WEF Element</td>
              <td style="padding:6px 0;">Q{wef}</td></tr>
          <tr><td style="padding:6px 0;color:#6B7280;">Status</td>
              <td style="padding:6px 0;">{status}</td></tr>
          <tr><td style="padding:6px 0;color:#6B7280;">Start Date</td>
              <td style="padding:6px 0;">{start}</td></tr>
          <tr><td style="padding:6px 0;color:#6B7280;">Target Date</td>
              <td style="padding:6px 0;">{target}</td></tr>
          <tr><td style="padding:6px 0;color:#6B7280;">Zone</td>
              <td style="padding:6px 0;">{zone}</td></tr>
          <tr><td style="padding:6px 0;color:#6B7280;">Function</td>
              <td style="padding:6px 0;">{function}</td></tr>
        </table>
        {_base_footer()}
      </div>
    </div>
    """

    for email in [manager_email, reporting_manager_email]:
        if email and email.strip():
            ok, _ = _send(email, subject, body)
            _log_notification(
                manager_db_id, "plan_created", plan_id,
                "sent" if ok else "failed"
            )


def send_invitation(
    manager_email: str,
    manager_name: str,
    manager_db_id: str,
) -> bool:
    """Send onboarding invitation. Returns True on success."""
    subject = "[MAP] Invitation — Action Planning System, XYZ Industries"
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#C55A11;padding:16px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;font-size:1.2rem;">
          📋 You're Invited to the MAP System
        </h2>
      </div>
      <div style="background:#fff;border:1px solid #E5E7EB;
                  border-radius:0 0 8px 8px;padding:24px;">
        <p style="font-size:0.95rem;">Dear <strong>{manager_name}</strong>,</p>
        <p style="font-size:0.95rem;color:#374151;">
          You have been identified as an eligible manager to participate in the
          <strong>Workplace Engagement Framework Action Planning</strong> initiative
          at XYZ Industries.
        </p>
        <p style="font-size:0.95rem;color:#374151;">
          Please log in to the MAP System and create your Action Plans, one for
          each of the 12 Workplace Engagement Framework elements that are relevant
          to your team.
        </p>
        <div style="background:#FFF5F0;border-left:4px solid #C55A11;
                    padding:12px 16px;border-radius:4px;margin:1rem 0;">
          <p style="margin:0;font-size:0.9rem;color:#374151;">
            <strong>Next step:</strong> Sign in using your XYZ Industries email
            address and the password provided by your HR Business Partner.
          </p>
        </div>
        {_base_footer()}
      </div>
    </div>
    """
    ok, _ = _send(manager_email, subject, body)
    _log_notification(manager_db_id, "invitation", None, "sent" if ok else "failed")
    return ok


def send_zone_report(
    hrbp_email: str,
    zone: str,
    attachment_path: str,
    hrbp_db_id: str,
) -> bool:
    """Email zone report with attachment."""
    subject = f"[MAP] Zone Report — {zone}"
    fname   = os.path.basename(attachment_path) if attachment_path else "report"
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#C55A11;padding:16px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;font-size:1.2rem;">
          📤 Zone Report — {zone}
        </h2>
      </div>
      <div style="background:#fff;border:1px solid #E5E7EB;
                  border-radius:0 0 8px 8px;padding:24px;">
        <p style="font-size:0.95rem;color:#374151;">
          Please find the consolidated Action Plan report for <strong>{zone}</strong>
          attached to this email.
        </p>
        <p style="font-size:0.85rem;color:#6B7280;">Attachment: {fname}</p>
        {_base_footer()}
      </div>
    </div>
    """
    ok, _ = _send(hrbp_email, subject, body, attachment_path=attachment_path)
    _log_notification(hrbp_db_id, "zone_summary", None, "sent" if ok else "failed")
    return ok


def send_admin_feedback(
    manager_email: str,
    feedback_text: str,
    plan_title: str,
    manager_db_id: str,
    plan_id: str | None = None,
    feedback_type: str = "clarification",
) -> bool:
    """Send admin feedback email for a plan."""
    type_label = "Clarification Requested" if feedback_type == "clarification" else "Improvement Suggested"
    badge_colour = "#2563EB" if feedback_type == "clarification" else "#D97706"

    subject = f"[MAP] {type_label} on Your Action Plan — {plan_title}"
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#C55A11;padding:16px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;font-size:1.2rem;">
          💬 Feedback on Your Action Plan
        </h2>
      </div>
      <div style="background:#fff;border:1px solid #E5E7EB;
                  border-radius:0 0 8px 8px;padding:24px;">
        <p style="font-size:0.9rem;color:#6B7280;">
          Action Plan: <strong style="color:#111827;">{plan_title}</strong>
          &nbsp;&nbsp;
          <span style="background:{badge_colour}22;color:{badge_colour};
                       border:1px solid {badge_colour};padding:2px 10px;
                       border-radius:12px;font-size:0.8rem;font-weight:600;">
            {type_label}
          </span>
        </p>
        <blockquote style="border-left:4px solid #C55A11;padding:10px 16px;
                            background:#FFF5F0;border-radius:4px;
                            font-size:0.95rem;color:#374151;margin:1rem 0;">
          {feedback_text}
        </blockquote>
        <p style="font-size:0.9rem;color:#374151;">
          Please review this feedback and update your Action Plan in the MAP System
          accordingly. If you have questions, contact your HR Business Partner.
        </p>
        {_base_footer()}
      </div>
    </div>
    """
    ok, _ = _send(manager_email, subject, body)
    _log_notification(manager_db_id, "feedback", plan_id, "sent" if ok else "failed")
    return ok


def send_weekly_reminder(
    manager_email: str,
    manager_name: str,
    reason: str,           # "no_plans_created" | "plan_stuck_in_initiated"
    manager_db_id: str,
) -> bool:
    """Weekly reminder based on reason ('no_plans_created' or 'plan_stuck_in_initiated')."""
    if reason == "no_plans_created":
        subject    = "[MAP] Reminder — Please Create Your Action Plans"
        headline   = "Action Plans Not Yet Started"
        icon       = "⏰"
        detail_msg = (
            "You have not yet created any Action Plans in the MAP System. "
            "As an eligible Level 2 Manager, you are expected to create plans "
            "aligned to the Workplace Engagement Framework. Please log in and "
            "get started at your earliest convenience."
        )
    else:   # plan_stuck_in_initiated
        subject    = "[MAP] Reminder — Action Plans Awaiting Progress Update"
        headline   = "Action Plans Stuck in Initiated"
        icon       = "🔔"
        detail_msg = (
            "You have one or more Action Plans that have been in "
            "<strong>Initiated</strong> status for over 7 days with no progress "
            "update. Please log in to the MAP System and add a progress note or "
            "update the status to reflect the current state."
        )

    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#C55A11;padding:16px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;font-size:1.2rem;">
          {icon} {headline}
        </h2>
      </div>
      <div style="background:#fff;border:1px solid #E5E7EB;
                  border-radius:0 0 8px 8px;padding:24px;">
        <p style="font-size:0.95rem;">Dear <strong>{manager_name}</strong>,</p>
        <p style="font-size:0.95rem;color:#374151;">{detail_msg}</p>
        {_base_footer()}
      </div>
    </div>
    """
    ok, _ = _send(manager_email, subject, body)
    _log_notification(manager_db_id, "reminder", None, "sent" if ok else "failed")
    return ok


def send_manual_notification(
    recipient_emails: list[str],
    subject: str,
    message: str,
    sender_db_id: str,
    audience_label: str = "Selected Recipients",
) -> dict:
    """Send manual notification from Admin. Returns {sent, failed}."""
    results = {"sent": 0, "failed": 0}
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#C55A11;padding:16px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;font-size:1.2rem;">📢 Message from HR CoE</h2>
      </div>
      <div style="background:#fff;border:1px solid #E5E7EB;
                  border-radius:0 0 8px 8px;padding:24px;">
        <p style="font-size:0.95rem;color:#374151;white-space:pre-wrap;">{message}</p>
        {_base_footer()}
      </div>
    </div>
    """

    for email in recipient_emails:
        if not email or not email.strip():
            continue
        ok, _ = _send(email.strip(), subject, html_body)
        _log_notification(
            sender_db_id, "manual_notification", None,
            "sent" if ok else "failed"
        )
        if ok:
            results["sent"] += 1
        else:
            results["failed"] += 1

    return results


# Reminder checker (cron-callable)

def check_and_send_reminders() -> dict:
    """Check two conditions and send reminders. Returns {no_plans, stuck, errors}."""
    summary = {"no_plans": 0, "stuck": 0, "errors": 0}
    client  = get_service_client()
    cutoff  = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Condition 1: Eligible managers with no plans
    try:
        # All eligible managers
        mgr_resp = (
            client
            .from_("employees")
            .select("id, name, email")
            .eq("is_eligible", True)
            .execute()
        )
        all_eligible: list[dict] = mgr_resp.data or []

        if all_eligible:
            # Managers that have at least one plan
            plan_resp = (
                client
                .from_("action_plans")
                .select("manager_id")
                .execute()
            )
            managers_with_plans = {
                row["manager_id"]
                for row in (plan_resp.data or [])
            }

            for mgr in all_eligible:
                if mgr["id"] not in managers_with_plans:
                    ok = send_weekly_reminder(
                        manager_email  = mgr["email"],
                        manager_name   = mgr["name"],
                        reason         = "no_plans_created",
                        manager_db_id  = mgr["id"],
                    )
                    if ok:
                        summary["no_plans"] += 1
                    else:
                        summary["errors"] += 1

    except Exception as exc:
        summary["errors"] += 1

    # Condition 2: Plans stuck in Initiated > 7 days
    try:
        stuck_resp = (
            client
            .from_("action_plans")
            .select("id, manager_id, title")
            .eq("status", "Initiated")
            .lt("updated_at", cutoff)
            .execute()
        )
        stuck_plans: list[dict] = stuck_resp.data or []

        if stuck_plans:
            # Avoid spamming same manager for multiple stuck plans
            notified_managers: set[str] = set()

            for plan in stuck_plans:
                mgr_id = plan["manager_id"]
                if mgr_id in notified_managers:
                    continue

                # Manager contact details
                mgr_resp = (
                    client
                    .from_("employees")
                    .select("name, email")
                    .eq("id", mgr_id)
                    .single()
                    .execute()
                )
                if not mgr_resp.data:
                    continue

                mgr  = mgr_resp.data
                ok   = send_weekly_reminder(
                    manager_email  = mgr["email"],
                    manager_name   = mgr["name"],
                    reason         = "plan_stuck_in_initiated",
                    manager_db_id  = mgr_id,
                )
                notified_managers.add(mgr_id)

                if ok:
                    summary["stuck"] += 1
                else:
                    summary["errors"] += 1

    except Exception as exc:
        summary["errors"] += 1

    return summary