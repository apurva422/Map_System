"""
debug_auth.py
=============
Run this ONCE to pinpoint the auth failure:
    python debug_auth.py

Delete this file before production.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL", "")
key = os.environ.get("SUPABASE_ANON_KEY", "")

client = create_client(url, key)

EMAIL    = input("Enter your login email: ").strip()
PASSWORD = input("Enter your password: ").strip()

print("\n── Step 1: Sign in ──────────────────────────────────────────")
try:
    resp = client.auth.sign_in_with_password({"email": EMAIL, "password": PASSWORD})
    auth_uid = resp.user.id
    print(f"✓ Signed in successfully")
    print(f"  auth_uid = {auth_uid}")
except Exception as e:
    print(f"✗ Sign-in failed: {e}")
    exit(1)

print("\n── Step 2: Inspect auth_users table columns ─────────────────")
try:
    # Fetch ALL columns so we can see exact names
    result = client.from_("auth_users").select("*").limit(3).execute()
    print(f"  Rows returned: {len(result.data)}")
    if result.data:
        print(f"  Column names: {list(result.data[0].keys())}")
        print(f"  First row:    {result.data[0]}")
    else:
        print("  ✗ No rows returned at all — check RLS or table name")
except Exception as e:
    print(f"  ✗ Query failed: {e}")

print("\n── Step 3: Query auth_users by auth_uid ─────────────────────")
try:
    result = client.from_("auth_users").select("*").eq("auth_uid", auth_uid).execute()
    print(f"  Rows returned: {len(result.data)}")
    if result.data:
        print(f"  Row: {result.data[0]}")
        emp_id_col = list(result.data[0].keys())
        print(f"  ✓ emp_id value = {result.data[0].get('emp_id', 'COLUMN NOT FOUND')}")
    else:
        print(f"  ✗ No row matched auth_uid = {auth_uid}")
        print("     → Either the auth_uid stored in the table is different,")
        print("       or the column is not named 'auth_uid'")
except Exception as e:
    print(f"  ✗ Query failed: {e}")

print("\n── Step 4: Inspect employees table columns ──────────────────")
try:
    result = client.from_("employees").select("*").limit(3).execute()
    print(f"  Rows returned: {len(result.data)}")
    if result.data:
        print(f"  Column names: {list(result.data[0].keys())}")
        print(f"  First row:    {result.data[0]}")
    else:
        print("  ✗ No rows returned at all — check RLS or table name")
except Exception as e:
    print(f"  ✗ Query failed: {e}")

print("\n── Step 5: Query employees by emp_id ────────────────────────")
try:
    # Get emp_id from auth_users first
    au_result = client.from_("auth_users").select("*").eq("auth_uid", auth_uid).execute()
    if au_result.data:
        emp_id = au_result.data[0].get("emp_id")
        print(f"  Looking up emp_id = '{emp_id}'")
        emp_result = client.from_("employees").select("*").eq("emp_id", emp_id).execute()
        print(f"  Rows returned: {len(emp_result.data)}")
        if emp_result.data:
            print(f"  ✓ Employee row: {emp_result.data[0]}")
        else:
            print(f"  ✗ No employee matched emp_id = '{emp_id}'")
            print("     → emp_id mismatch between tables or column named differently")
    else:
        print("  ✗ Skipped — auth_users lookup failed in Step 3")
except Exception as e:
    print(f"  ✗ Query failed: {e}")

print("\n── Done ─────────────────────────────────────────────────────")
print("Share the output above to identify the exact failure point.")