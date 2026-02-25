"""
utils/validators.py
===================
Eligibility checks for the MAP System.

is_eligible_manager(employee_row) → bool
    True if role == "Manager" AND level == "LEVEL 2"

get_eligible_managers() → list[dict]
    Returns all employees who pass the eligibility check.
    Uses the service-role client to bypass RLS.
"""

from database.supabase_client import get_service_client


def is_eligible_manager(employee: dict) -> bool:
    """Check a single employee dict for manager eligibility."""
    return (
        employee.get("role", "").strip() == "Manager"
        and employee.get("level", "").strip().upper() == "LEVEL 2"
    )


def get_eligible_managers() -> list[dict]:
    """
    Query Supabase for all eligible managers (role=Manager, level=LEVEL 2).
    Uses the service client so RLS does not restrict the query.
    """
    client = get_service_client()
    resp = (
        client
        .from_("employees")
        .select("id, emp_id, name, email, zone, function, reporting_manager_id")
        .eq("role", "Manager")
        .eq("level", "LEVEL 2")
        .execute()
    )
    return resp.data or []