"""
seed_employees.py
─────────────────────────────────────────────────────────────────────────────
Seeds the existing `employees` table from the HR CSV.
No schema changes required — works with the table exactly as designed.

ZONE → HRBP mapping (one HRBP per zone, based on majority coverage):
  SOUTH       → Neha Iyer
  NORTH       → Priya Nair
  MUMBAI      → Raj Malhotra
  WEST & EAST → Sunil Desai
  HO          → no HRBP assigned (visible to Admin/CEO only)

PASSES
  1. Upsert all 2 000 employees (core fields, no FKs yet)
  2. Set reporting_manager_id via Position Code hierarchy
  3. Add HRBP records (one per zone) if not already present

USAGE
  python seed_employees.py
  python seed_employees.py --csv path/to/file.csv
─────────────────────────────────────────────────────────────────────────────
"""

import os, sys, time, argparse
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()
SUPABASE_URL         = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BATCH_SIZE           = 100

# Zone → HRBP mapping derived from CSV majority coverage
HRBP_ZONE_MAP = [
    # (emp_id stub,       name,           email,                            zone)
    ("hrbp_neha",   "Neha Iyer",    "neha.iyer@xyzindustries.in",    "SOUTH"),
    ("hrbp_priya",  "Priya Nair",   "priya.nair@xyzindustries.in",   "NORTH"),
    ("hrbp_raj",    "Raj Malhotra", "raj.malhotra@xyzindustries.in", "MUMBAI"),
    ("hrbp_sunil",  "Sunil Desai",  "sunil.desai@xyzindustries.in",  "WEST & EAST"),
]

HRBP_EMAILS = {e for _, _, e, _ in HRBP_ZONE_MAP}
HRBP_NAMES  = {n for _, n, _, _ in HRBP_ZONE_MAP}

# ── Client ────────────────────────────────────────────────────────────────────

def client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Batch upsert ──────────────────────────────────────────────────────────────

def upsert(db: Client, rows: list, label: str):
    ok = fail = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i : i + BATCH_SIZE]
        try:
            db.table("employees").upsert(chunk, on_conflict="emp_id").execute()
            ok += len(chunk)
            print(f"  [{label}] {min(i + BATCH_SIZE, len(rows))}/{len(rows)}")
        except Exception as e:
            fail += len(chunk)
            print(f"  [{label}] FAILED batch {i // BATCH_SIZE + 1}: {e}")
        time.sleep(0.1)
    return ok, fail

# ── Derive role ───────────────────────────────────────────────────────────────

def role_for(row: pd.Series) -> str:
    email = f"{row['Username']}@xyzindustries.in"
    name  = f"{row['First Name']} {row['Last Name']}"
    if email in HRBP_EMAILS or name in HRBP_NAMES:
        return "HRBP"
    return "Manager"

# ── Pass 1: core employee rows ────────────────────────────────────────────────

def pass1(db: Client, df: pd.DataFrame) -> list:
    print("\n-- PASS 1: employees -----------------------------------------------")
    rows = []
    for _, r in df.iterrows():
        role  = role_for(r)
        level = str(r.get("Employee Level", "") or "")
        rows.append({
            "emp_id":      str(r["Person Id"]),
            "name":        f"{r['First Name']} {r['Last Name']}",
            "email":       f"{r['Username']}@xyzindustries.in",
            "role":        role,
            "level":       level,
            "zone":        str(r.get("Zone", "") or ""),
            "function":    str(r.get("Function Name", "") or ""),
            "is_eligible": role == "Manager" and "LEVEL 2" in level.upper(),
            # kept locally for Pass 2, not sent to DB
            "_pos":        str(r.get("Position Code", "")   or ""),
            "_parent":     str(r.get("Parent Position", "") or ""),
        })

    db_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    ok, fail = upsert(db, db_rows, "employees")
    print(f"  Done: {ok} ok, {fail} failed")
    return rows

# ── Pass 2: reporting_manager_id ──────────────────────────────────────────────

def pass2(db: Client, rows: list):
    print("\n-- PASS 2: reporting_manager_id ------------------------------------")

    resp          = db.table("employees").select("id,emp_id").execute()
    uuid_by_empid = {r["emp_id"]: r["id"] for r in resp.data}
    empid_by_pos  = {r["_pos"]: r["emp_id"] for r in rows if r["_pos"]}

    updates = []
    for r in rows:
        mgr_empid = empid_by_pos.get(r["_parent"])
        if not mgr_empid:
            continue
        mgr_uuid  = uuid_by_empid.get(mgr_empid)
        self_uuid = uuid_by_empid.get(r["emp_id"])
        if mgr_uuid and self_uuid and mgr_uuid != self_uuid:
            updates.append({"emp_id": r["emp_id"], "reporting_manager_id": mgr_uuid})

    print(f"  {len(updates)}/{len(rows)} links found")
    ok = fail = 0
    for i, u in enumerate(updates):
        try:
            db.table("employees") \
              .update({"reporting_manager_id": u["reporting_manager_id"]}) \
              .eq("emp_id", u["emp_id"]) \
              .execute()
            ok += 1
            if (i + 1) % 100 == 0 or (i + 1) == len(updates):
                print(f"  [reporting_mgr] {i + 1}/{len(updates)}")
        except Exception as e:
            fail += 1
            print(f"  [reporting_mgr] FAILED emp_id={u['emp_id']}: {e}")
        time.sleep(0.05)
    print(f"  Done: {ok} ok, {fail} failed")

# ── Pass 3: ensure HRBP records exist ─────────────────────────────────────────

def pass3(db: Client, df: pd.DataFrame):
    print("\n-- PASS 3: HRBP records --------------------------------------------")
    existing = {f"{u}@xyzindustries.in" for u in df["Username"]}

    stubs = []
    for emp_id, name, email, zone in HRBP_ZONE_MAP:
        if email not in existing:
            stubs.append({
                "emp_id":      emp_id,
                "name":        name,
                "email":       email,
                "role":        "HRBP",
                "level":       "",
                "zone":        zone,
                "function":    "HUMAN RESOURCES",
                "is_eligible": False,
            })
            print(f"  Inserting stub: {name} ({zone})")

    if stubs:
        upsert(db, stubs, "hrbp-stubs")
    else:
        print("  All 4 HRBPs already in CSV - no stubs needed")

# ── Summary ───────────────────────────────────────────────────────────────────

def summary(db: Client):
    print("\n-- Summary ---------------------------------------------------------")
    total    = db.table("employees").select("id", count="exact").execute()
    eligible = db.table("employees").select("id", count="exact").eq("is_eligible", True).execute()
    hrbps    = db.table("employees").select("id", count="exact").eq("role", "HRBP").execute()
    print(f"  Total employees  : {total.count}")
    print(f"  Eligible managers: {eligible.count}")
    print(f"  HRBPs            : {hrbps.count}")
    print()
    print("  Zone -> HRBP assignment:")
    for _, name, _, zone in HRBP_ZONE_MAP:
        print(f"    {zone:<14} -> {name}")
    print(f"    {'HO':<14} -> (Admin/CEO only)")
    print()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="Employee_Data.csv")
    parser.add_argument("--skip-pass2", action="store_true", help="Skip reporting_manager_id (Pass 1 already done)")
    parser.add_argument("--skip-pass3", action="store_true", help="Skip HRBP stub insertion")
    args = parser.parse_args()

    print(f"Loading {args.csv}...")
    try:
        df = pd.read_csv(args.csv)
    except FileNotFoundError:
        print(f"ERROR: {args.csv} not found"); sys.exit(1)
    print(f"  {len(df)} rows loaded")

    db = client()
    print("Connected to Supabase")

    if not args.skip_pass3:
        pass3(db, df)
    rows = pass1(db, df)
    if not args.skip_pass2:
        pass2(db, rows)
    summary(db)

if __name__ == "__main__":
    main()