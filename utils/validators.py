from datetime import date
from database.supabase_client import get_supabase_client

def check_eligibility(employee_id: str) -> tuple[bool, str]:
    """
    Check whether an employee is eligible to submit an action plan.
    Returns (is_eligible: bool, reason: str).
    """
    supabase = get_supabase_client()

    # Rule 1: Employee must exist in profiles
    profile_res = supabase.table("profiles").select("id, role, active").eq("id", employee_id).single().execute()
    if not profile_res.data:
        return False, "Employee profile not found."
    if not profile_res.data.get("active", True):
        return False, "Employee account is inactive."

    # Rule 2: No open (non-closed) action plans already pending
    open_res = supabase.table("action_plans") \
        .select("id") \
        .eq("created_by", employee_id) \
        .not_.in_("status", ["Closed", "Rejected"]) \
        .execute()

    if open_res.data and len(open_res.data) >= 3:
        return False, "Employee already has 3 or more active action plans."

    return True, "Eligible"

def is_plan_overdue(due_date_str: str) -> bool:
    """Return True if the due date has passed."""
    try:
        due = date.fromisoformat(due_date_str)
        return due < date.today()
    except ValueError:
        return False

def validate_plan_payload(payload: dict) -> tuple[bool, str]:
    """Basic field-level validation for action plan payloads."""
    if not payload.get("title", "").strip():
        return False, "Title is required."
    if not payload.get("due_date"):
        return False, "Due date is required."
    if not payload.get("created_by"):
        return False, "Creator ID is missing."
    return True, "Valid"
