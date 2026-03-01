"""Manager eligibility checks — is_eligible_manager() and get_eligible_managers()."""

from database.supabase_client import get_service_client


def is_eligible_manager(employee: dict) -> bool:
    """True if role=Manager and level=LEVEL 2."""
    return (
        employee.get("role", "").strip() == "Manager"
        and employee.get("level", "").strip().upper() == "LEVEL 2"
    )


def get_eligible_managers() -> list[dict]:
    """Return all eligible managers (service client, bypasses RLS)."""
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