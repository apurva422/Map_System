import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM

def send_email(to: str | list[str], subject: str, body: str, html: bool = False):
    """Send an email to one or more recipients."""
    recipients = [to] if isinstance(to, str) else to

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(recipients)

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, recipients, msg.as_string())

def notify_plan_submitted(to: str, plan_title: str, submitter: str):
    subject = f"[MAP] New Action Plan Submitted: {plan_title}"
    body = f"""
    <h3>New Action Plan Submitted</h3>
    <p><b>Title:</b> {plan_title}</p>
    <p><b>Submitted by:</b> {submitter}</p>
    <p>Please log in to the MAP System to review the plan.</p>
    """
    send_email(to, subject, body, html=True)

def notify_plan_status_change(to: str, plan_title: str, new_status: str):
    subject = f"[MAP] Action Plan Status Updated: {plan_title}"
    body = f"""
    <h3>Action Plan Status Update</h3>
    <p><b>Title:</b> {plan_title}</p>
    <p><b>New Status:</b> {new_status}</p>
    <p>Please log in to the MAP System for more details.</p>
    """
    send_email(to, subject, body, html=True)

def notify_plan_due_reminder(to: str, plan_title: str, due_date: str):
    subject = f"[MAP] Reminder: Action Plan Due Soon — {plan_title}"
    body = f"""
    <h3>Upcoming Due Date Reminder</h3>
    <p><b>Title:</b> {plan_title}</p>
    <p><b>Due Date:</b> {due_date}</p>
    <p>Please ensure your action plan is completed on time.</p>
    """
    send_email(to, subject, body, html=True)
