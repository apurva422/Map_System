# 📋 MAP System — Manager Action Planning

A **Streamlit** web application for managing **Workplace Engagement Framework (WEF)** action plans across an organisation. Each eligible Manager creates up to **12 Action Plans** (one per WEF question), tracked through HRBPs, Admin, and the CEO — all backed by **Supabase** with Row-Level Security.

---

## Roles & Capabilities

### 👤 Manager
- **Dashboard** — summary cards (total / initiated / ongoing / closed), WEF coverage bar (12 elements), recent plans list
- **Create Action Plan** — pick a WEF element (already-used elements are disabled), set title, description, dates; status defaults to *Initiated*; email sent to Manager + Reporting Manager on creation
- **Edit / Update** — modify plan details, add progress updates, advance status (Initiated → Ongoing → Closed); Closed plans are locked
- **Progress History** — timeline of updates from both Manager and HRBP, visually distinguished by role

### 🗺️ HRBP (HR Business Partner)
- **Zone Dashboard** — summary cards and status/WEF breakdown for their zone only
- **Zone Action Plans** — filterable table of all plans in their zone; drill into any plan for full detail
- **Backend Updates** — can add progress notes on any zone plan (tagged as `HRBP`); Manager updates are never overwritten
- **Export & Email** — download zone report as CSV / Excel / PDF, or email it directly

### ⚙️ Admin
- **Org Dashboard** — full visibility across all zones and functions
- **All Plans** — unrestricted filterable table; can edit title, description, status, and dates on any plan
- **Feedback** — select a plan → compose a message → choose type (Clarification / Improvement); logged in `admin_feedback` and emailed to the manager
- **Manager Onboarding** — run eligibility check (role = Manager, level = LEVEL 2) → preview eligible managers → bulk send invitation emails; each invitation logged in `notifications_log`
- **Notifications** — manual notification composer with audience selector (All Managers / All HRBPs / Specific Zone); weekly reminder trigger for managers with no plans or stuck plans
- **Export** — same CSV / Excel / PDF with no zone restriction

### 👔 CEO (Business Head)
- **Read-only dashboard** with **6 Plotly charts**:
  - Plans by Zone · Plans by Function · WEF Distribution · Status Donut · Status by Zone (grouped) · Monthly Trend
- **Filter bar** — Zone, Function, Status, Manager multiselects; all charts and metrics update live
- **Summary metrics** — total plans, % closed, active zones, active managers
- **All Plans** — browse + export (CSV / Excel / PDF)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit 1.42 |
| Database | Supabase (PostgreSQL + Auth + RLS) |
| Charts | Plotly 5.24 |
| PDF export | fpdf2 |
| Excel export | openpyxl |
| Email | smtplib (Gmail App Password) |

---

## Project Structure

```
map_system/
├── app.py                  # Entry point — CSS, auth gate, role router
├── auth.py                 # Login, logout, session management
├── config.py               # Env vars, constants, WEF elements, colours
├── requirements.txt
│
├── database/
│   └── supabase_client.py  # Anon client (respects RLS) + service client (bypasses RLS)
│
├── views/
│   ├── manager.py          # Dashboard, create/edit plans, progress updates
│   ├── hrbp.py             # Zone dashboard, zone plans, backend updates, export
│   ├── admin.py            # Org dashboard, all plans, feedback, onboarding, notifications
│   └── ceo.py              # Read-only dashboard (6 charts) + all plans
│
├── components/
│   ├── sidebar.py          # Role-aware navigation (clears drill-down state on page change)
│   ├── action_plan_form.py # Reusable form — create / edit / read-only modes
│   └── dashboard_charts.py # 6 Plotly chart functions + 4-card metrics strip
│
├── utils/
│   ├── email_service.py    # All email logic + notifications_log writer
│   ├── export_utils.py     # CSV / Excel / PDF report generator
│   └── validators.py       # Manager eligibility checks (service client)
│
├── assets/
│   └── style.css           # Global stylesheet
│
└── .streamlit/
    └── config.toml         # Streamlit theme config
```

---

## Database Schema

Six tables in Supabase:

| Table | Purpose |
|-------|---------|
| `employees` | HR master data — name, email, role, level, zone, function, reporting_manager_id, is_eligible |
| `auth_users` | Bridge between Supabase Auth UID and employee record; role + zone denormalised for fast RLS |
| `action_plans` | Core table — one row per plan; `UNIQUE(manager_id, wef_element)` prevents duplicates at DB level |
| `progress_updates` | Append-only log; `updated_by_role` distinguishes Manager vs HRBP notes |
| `notifications_log` | Audit trail of every email sent/attempted; enables retry and Admin history view |
| `admin_feedback` | Governance-level feedback (Clarification / Improvement) — separate from progress updates |

### RLS Policies

- **Manager** — SELECT / INSERT / UPDATE on `action_plans` where `manager_id = auth.uid()`
- **HRBP** — SELECT on `action_plans` where zone matches their zone in `auth_users`
- **Admin / CEO** — Full SELECT on all tables; Admin also gets UPDATE
- **progress_updates** — Manager can INSERT on own plans; HRBP can INSERT on zone plans; no DELETE

---

## Setup & Run

### 1. Navigate to the project

```bash
cd map_system
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password
```

> **Note:** Use a [Gmail App Password](https://support.google.com/accounts/answer/185833), not your regular password.

### 5. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501**.

---

## How It Works

### Authentication Flow

1. User enters their **email** on the login page.
2. `auth.py` queries the `employees` table to find a matching record.
3. On success, user info (name, role, zone, function, db_id) is stored in `st.session_state`.
4. `app.py` reads the role and routes to the correct view module.

### Action Plan Lifecycle

```
Initiated  →  Ongoing  →  Closed
```

- Managers create up to **12 plans** (one per WEF element); duplicates blocked by DB constraint.
- Progress updates can be added by both the **Manager** and their **HRBP**.
- Status progresses forward; **Closed** is terminal — plan becomes read-only.

### Data Access Pattern

- **Anon client** — respects Supabase RLS; used for regular CRUD operations.
- **Service client** — bypasses RLS; used for admin reads, eligibility checks, cross-table lookups (e.g. fetching manager names for HRBP view).

### Email Notifications

| Trigger | Recipients | Function |
|---------|-----------|----------|
| Plan created | Manager + Reporting Manager | `send_plan_created()` |
| Admin feedback | Manager | `send_admin_feedback()` |
| Manager onboarding | Eligible managers | `send_invitation()` |
| Weekly reminder | Managers with no plans / stuck plans | `send_weekly_reminder()` |
| Manual notification | Admin-selected audience | `send_manual_notification()` |
| Zone report | HRBP | `send_zone_report()` |

All sends are logged in `notifications_log` with status `sent` or `failed`.

### Exports

All views use `utils/export_utils.py` → `generate_report(df, format, filename)`:

- **CSV** — raw data download
- **Excel** — formatted `.xlsx` (openpyxl)
- **PDF** — landscape report with styled header/footer, status-coloured rows, summary block

Streamlit's `st.download_button` handles in-browser downloads. For emailed reports, the file is passed as an attachment to `email_service`.

---

## License

Internal use — Godrej Industries.
