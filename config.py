"""App-wide configuration and constants."""
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL        = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY   = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Email
EMAIL_SENDER        = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD      = os.environ.get("EMAIL_PASSWORD", "")
SENDGRID_API_KEY    = os.environ.get("SENDGRID_API_KEY", "")

# App constants
APP_TITLE           = "MAP System — Manager Action Planning"
APP_ICON            = "📋"

VALID_ROLES         = ["Manager", "HRBP", "Admin", "CEO"]

WEF_ELEMENTS = {
    1:  "I know what is expected of me at work.",
    2:  "I have the materials and equipment I need to do my work right.",
    3:  "At work, I have the opportunity to do what I do best every day.",
    4:  "In the last seven days, I have received recognition or praise for doing good work.",
    5:  "My manager, or someone at work, seems to care about me as a person.",
    6:  "There is someone at work who encourages my development.",
    7:  "At work, my opinions seem to count.",
    8:  "The mission/purpose of my company makes me feel my job is important.",
    9:  "My associates or fellow employees are committed to doing quality work.",
    10: "I have a best friend at work.",
    11: "In the last six months, someone at work has talked to me about my progress.",
    12: "This last year, I have had opportunities at work to learn and grow.",
}

PLAN_STATUSES       = ["Initiated", "Ongoing", "Closed"]

# Role accent colours
ROLE_COLOURS = {
    "Manager": "#2E75B6",
    "HRBP":    "#375623",
    "Admin":   "#C55A11",
    "CEO":     "#7030A0",
}

# Status badge colours
STATUS_COLOURS = {
    "Initiated": "#9E9E9E",
    "Ongoing":   "#FFC107",
    "Closed":    "#4CAF50",
}