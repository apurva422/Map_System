"""
utils/email_service.py
======================
All email logic for the MAP System lives here.

Provider: smtplib + Gmail App Password (MVP).
To switch to SendGrid: add the API key to .env and swap the _send()
helper only — every call site stays the same.

Functions
---------
send_plan_created(manager_email, reporting_manager_email, plan_details)
send_invitation(manager_email, manager_name)
send_zone_report(hrbp_email, zone, attachment_path)
send_admin_feedback(manager_email, feedback_text, plan_title)
send_weekly_reminder(manager_email, manager_name, reason)
check_and_send_reminders()   ← standalone; can be called by a cron job
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

from config import EMAIL_SENDER, EMAIL_PASSWORD
from database.supabase_client import supabase, get_service_client


# ── Internal send helper ──────────────────────────────────────────────────────

def _send(
    to: str | list[str],
    subject: str,
    body_html: str,
    attachment_path: str | None = None,
) -> tuple[bool, str]:
    """
    Send an email via smtplib (Gmail SMTP).
    Returns (success: bool, error_message: str).
    """
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return False, "EMAIL_SENDER / EMAIL_PASSWORD not configured in .env"

    recipients = [to] if isinstance(to, str) else to

    msg = MIMEMultipart("alternative")
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
            f"attachment; filename={os.path.basename(attachment_path)}",
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
    """Write a row to notifications_log regardless of send success/failure."""
    try:
        supabase.from_("notifications_log").insert({
            "recipient_id":   recipient_id,
            "type":           notif_type,
            "action_plan_id": action_plan_id,
            "sent_at":        datetime.utcnow().isoformat(),
            "status":         status,
        }).execute()
    except Exception:
        pass  # never let logging failure crash the app


# ── Public email functions ────────────────────────────────────────────────────

def send_plan_created(
    manager_email: str,
    reporting_manager_email: str,
    plan_details: dict,
    manager_db_id: str,
    plan_id: str | None = None,
) -> None:
    """
    Triggered on every new Action Plan creation.
    Notifies both the manager and their reporting manager.
    Phase 7 will add full HTML templates.
    """
    subject = f"[MAP] New Action Plan Created — {plan_details.get('title', '')}"
    body    = f"""
    <h2>New Action Plan Created</h2>
    <p><strong>Title:</strong> {plan_details.get('title')}</p>
    <p><strong>WEF Element:</strong> {plan_details.get('wef_element')}</p>
    <p><strong>Status:</strong> {plan_details.get('status')}</p>
    <p><strong>Target Date:</strong> {plan_details.get('target_date')}</p>
    <hr><p style="color:#6B7280;font-size:0.85rem;">
    This is an automated message from the MAP System — XYZ Industries.
    </p>
    """
    for email in [manager_email, reporting_manager_email]:
        if email:
            ok, err = _send(email, subject, body)
            _log_notification(manager_db_id, "plan_created", plan_id, "sent" if ok else "failed")


def send_invitation(manager_email: str, manager_name: str, manager_db_id: str) -> bool:
    """
    Triggered by Admin during Stage 1 eligibility & onboarding.
    Returns True on success.
    """
    subject = "[MAP] Invitation — Action Planning System"
    body    = f"""
    <h2>You're Invited to the MAP System</h2>
    <p>Dear <strong>{manager_name}</strong>,</p>
    <p>You have been identified as an eligible manager to participate in the
    Workplace Engagement Framework Action Planning initiative.</p>
    <p>Please log in to the MAP System to create your Action Plans.</p>
    <hr><p style="color:#6B7280;font-size:0.85rem;">
    XYZ Industries — HR Centre of Excellence
    </p>
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
    """Triggered when HRBP or Admin clicks 'Email Zone Report'."""
    subject = f"[MAP] Zone Report — {zone}"
    body    = f"""
    <h2>Zone Report: {zone}</h2>
    <p>Please find the zone action plan report attached.</p>
    <hr><p style="color:#6B7280;font-size:0.85rem;">
    MAP System — XYZ Industries
    </p>
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
) -> bool:
    """Triggered when Admin sends feedback from Phase 5."""
    subject = f"[MAP] Feedback on Your Action Plan — {plan_title}"
    body    = f"""
    <h2>Feedback on Your Action Plan</h2>
    <p><strong>Plan:</strong> {plan_title}</p>
    <blockquote style="border-left:4px solid #C55A11;padding:0.5rem 1rem;
    background:#FFF5F0;">{feedback_text}</blockquote>
    <p>Please review this feedback and update your plan accordingly.</p>
    <hr><p style="color:#6B7280;font-size:0.85rem;">
    MAP System — XYZ Industries HR CoE
    </p>
    """
    ok, _ = _send(manager_email, subject, body)
    _log_notification(manager_db_id, "feedback", plan_id, "sent" if ok else "failed")
    return ok


def send_weekly_reminder(
    manager_email: str,
    manager_name: str,
    reason: str,  # "no_plans_created" | "plan_stuck_in_initiated"
    manager_db_id: str,
) -> bool:
    """
    Reminder email sent weekly by check_and_send_reminders().
    reason drives the message body.
    """
    if reason == "no_plans_created":
        subject  = "[MAP] Reminder — Please Create Your Action Plans"
        reminder = ("You have not yet created any Action Plans in the MAP System. "
                    "Please log in and get started.")
    else:  # plan_stuck_in_initiated
        subject  = "[MAP] Reminder — Action Plans Awaiting Progress"
        reminder = ("You have one or more Action Plans that have been in "
                    "<strong>Initiated</strong> status for over 7 days. "
                    "Please log in and add a progress update.")

    body = f"""
    <h2>Action Plan Reminder</h2>
    <p>Dear <strong>{manager_name}</strong>,</p>
    <p>{reminder}</p>
    <hr><p style="color:#6B7280;font-size:0.85rem;">
    This is an automated weekly reminder from the MAP System — XYZ Industries.
    </p>
    """
    ok, _ = _send(manager_email, subject, body)
    _log_notification(manager_db_id, "reminder", None, "sent" if ok else "failed")
    return ok


# ── Standalone reminder checker (callable by cron) ───────────────────────────

def check_and_send_reminders() -> dict:
    """
    Queries two conditions and sends reminders:
      1. Eligible managers with zero action plans.
      2. Plans with status='Initiated' and updated_at older than 7 days.

    Returns a summary dict: {"no_plans": int, "stuck": int, "errors": int}
    Phase 7 implements the full query logic.
    """
    summary = {"no_plans": 0, "stuck": 0, "errors": 0}
    # Full implementation in Phase 7
    return summary