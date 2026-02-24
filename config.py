import os
from dotenv import load_dotenv

load_dotenv()

# ── App ──────────────────────────────────────────────────────────────────────
APP_TITLE = os.getenv("APP_TITLE", "MAP System")

# ── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ── Email ─────────────────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)

# ── Roles ─────────────────────────────────────────────────────────────────────
ROLES = ["manager", "hrbp", "admin", "ceo"]

# ── Action Plan Statuses ──────────────────────────────────────────────────────
AP_STATUSES = ["Draft", "Submitted", "Under Review", "Approved", "Rejected", "Closed"]
