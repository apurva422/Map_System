"""
create_user.py
─────────────────────────────────────────────────────────────────────────────
Creates a fully wired user in the MAP system:
  1. Supabase Auth account  (email + password)
  2. employees row          (if emp_id not already in DB)
  3. auth_users row         (links Auth UID → employee record)

USAGE
  python create_user.py

You will be prompted for each field interactively.
─────────────────────────────────────────────────────────────────────────────
"""

import os, sys, getpass
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL         = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

VALID_ROLES = ["Manager", "HRBP", "Admin", "CEO"]
VALID_ZONES = ["NORTH", "SOUTH", "MUMBAI", "WEST & EAST", "HO"]

# ── Client ────────────────────────────────────────────────────────────────────

def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Prompts ───────────────────────────────────────────────────────────────────

def prompt(label: str, required: bool = True, default: str = "") -> str:
    suffix = f" [{default}]" if default else (" (required)" if required else " (optional, press Enter to skip)")
    while True:
        val = input(f"  {label}{suffix}: ").strip()
        if not val and default:
            return default
        if not val and required:
            print("    ! This field is required.")
            continue
        return val

def prompt_choice(label: str, options: list, default: str = "") -> str:
    display = " / ".join(
        f"[{o}]" if o == default else o for o in options
    )
    print(f"  {label} — {display}")
    while True:
        val = input("  Choice: ").strip()
        if not val and default:
            return default
        if val in options:
            return val
        print(f"    ! Must be one of: {', '.join(options)}")

# ── Steps ─────────────────────────────────────────────────────────────────────

def create_auth_user(db: Client, email: str, password: str) -> str:
    """Create Supabase Auth account. Returns auth_uid."""
    print("\n  Creating Auth account...", end=" ")
    resp = db.auth.admin.create_user({
        "email":            email,
        "password":         password,
        "email_confirm":    True,   # skip confirmation email
    })
    uid = resp.user.id
    print(f"done  (uid: {uid})")
    return uid


def upsert_employee(db: Client, emp: dict) -> str:
    """Insert employee row if emp_id doesn't exist. Returns the DB uuid."""
    existing = (
        db.table("employees")
        .select("id,emp_id,name,role")
        .eq("emp_id", emp["emp_id"])
        .execute()
    )
    if existing.data:
        row = existing.data[0]
        print(f"\n  Employee record already exists: {row['name']} ({row['role']})")
        confirm = input("  Update role/zone from this script? (y/n) [n]: ").strip().lower()
        if confirm == "y":
            db.table("employees").update({
                "role":    emp["role"],
                "zone":    emp["zone"],
                "function": emp["function"],
            }).eq("emp_id", emp["emp_id"]).execute()
            print("  Employee record updated.")
        return row["id"]
    else:
        result = db.table("employees").insert(emp).execute()
        row_id = result.data[0]["id"]
        print(f"\n  Employee record created (id: {row_id})")
        return row_id


def upsert_auth_users(db: Client, auth_uid: str, emp_id: str, role: str, zone: str):
    """Insert or replace the auth_users bridge row."""
    db.table("auth_users").upsert({
        "auth_uid": auth_uid,
        "emp_id":   emp_id,
        "role":     role,
        "zone":     zone,
    }, on_conflict="auth_uid").execute()
    print("  auth_users record created.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db = get_client()

    print("\n════════════════════════════════════════")
    print("  MAP System — Create User")
    print("════════════════════════════════════════\n")

    # ── Collect inputs ────────────────────────────────────────────────────────
    print("── Identity ─────────────────────────────")
    name     = prompt("Full name")
    emp_id   = prompt("Employee ID  (must be unique, e.g. EMP001)")
    email    = prompt("Login email")
    password = getpass.getpass("  Password (min 6 chars): ").strip()
    while len(password) < 6:
        print("    ! Password must be at least 6 characters.")
        password = getpass.getpass("  Password: ").strip()

    print("\n── Role & Access ─────────────────────────")
    role = prompt_choice("Role", VALID_ROLES)
    zone = prompt_choice("Zone", VALID_ZONES,
                         default="HO" if role in ("Admin", "CEO") else "")

    print("\n── Optional details ──────────────────────")
    function = prompt("Function / Department", required=False)
    level    = prompt("Employee level  (e.g. L2-LEVEL 2)", required=False)

    is_eligible = role == "Manager" and "LEVEL 2" in level.upper()

    # ── Confirm ───────────────────────────────────────────────────────────────
    print("\n── Summary ───────────────────────────────")
    print(f"  Name        : {name}")
    print(f"  Emp ID      : {emp_id}")
    print(f"  Email       : {email}")
    print(f"  Role        : {role}")
    print(f"  Zone        : {zone}")
    print(f"  Function    : {function or '—'}")
    print(f"  Level       : {level or '—'}")
    print(f"  is_eligible : {is_eligible}")
    print()

    go = input("Create this user? (y/n): ").strip().lower()
    if go != "y":
        print("Cancelled.")
        sys.exit(0)

    # ── Execute ───────────────────────────────────────────────────────────────
    print("\n── Creating ──────────────────────────────")

    try:
        auth_uid = create_auth_user(db, email, password)
    except Exception as e:
        print(f"\n  ERROR creating Auth account: {e}")
        print("  The email may already be registered in Supabase Auth.")
        sys.exit(1)

    emp_row = {
        "emp_id":      emp_id,
        "name":        name,
        "email":       email,
        "role":        role,
        "zone":        zone,
        "function":    function,
        "level":       level,
        "is_eligible": is_eligible,
    }

    try:
        upsert_employee(db, emp_row)
    except Exception as e:
        print(f"\n  ERROR creating employee record: {e}")
        sys.exit(1)

    try:
        upsert_auth_users(db, auth_uid, emp_id, role, zone)
    except Exception as e:
        print(f"\n  ERROR creating auth_users record: {e}")
        sys.exit(1)

    print("\n  User created successfully.")
    print(f"  They can now log in with: {email}")


if __name__ == "__main__":
    main()