# MAP System — Core Services Explained

> A breakdown of the four key services that power the MAP (Manager Action Planning) System.

---

## 1. 🔐 Authentication (`auth.py`)

### What It Does

The authentication module handles **user login, logout, and session management**. It controls who can access the app and what information is loaded about them after they sign in.

### How It Works

| Step | What Happens |
|------|-------------|
| **1. Login Form** | A Streamlit form collects the user's **email** and **password**. |
| **2. Supabase Auth** | The credentials are sent to **Supabase Auth** via `supabase.auth.sign_in_with_password()`. Supabase checks the email/password and returns a unique `auth_uid` (a user ID). |
| **3. Profile Fetch** | The system uses the `auth_uid` to look up two database tables:<br>• `auth_users` — maps `auth_uid` → `emp_id`, `role`, `zone`<br>• `employees` — maps `emp_id` → `name`, `email`, `function` |
| **4. Session Set** | The user's profile (name, role, zone, department, etc.) is saved in Streamlit's `session_state` so it persists across page interactions. |
| **5. Logout** | Signs out from Supabase Auth, clears the session, and refreshes the page. |

### Key Functions

| Function | Purpose |
|----------|---------|
| `login()` | Renders the sign-in form and processes authentication |
| `logout()` | Signs out and clears the session |
| `require_auth()` | Guard — if not logged in, shows login page and stops execution |
| `get_current_user()` | Returns the logged-in user's profile dict, or `None` |
| `_fetch_employee_profile()` | Internal — queries Supabase for the user's full profile |

### Simple Explanation

> **Think of it like a building security desk.** When you arrive (open the app), the guard (auth module) asks for your badge (email + password). It checks your identity with the security database (Supabase Auth), then pulls up your employee record to know your name, department, and access level. Once verified, you get a visitor pass (session) that lets you move around the building without showing your badge again until you leave (logout).

---

## 2. 🗄️ Supabase Connection (`database/supabase_client.py`)

### What It Does

This module creates and provides the **database connections** to Supabase. It sets up two types of clients that the rest of the app uses to read and write data.

### How It Works

The module reads three environment variables from the `.env` file:

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | The URL of the Supabase project (where the database lives) |
| `SUPABASE_ANON_KEY` | The anonymous/public key — used by regular users; **respects Row Level Security (RLS)** |
| `SUPABASE_SERVICE_KEY` | The service-role key — used for admin operations; **bypasses RLS** |

It exposes two things:

| Export | Type | Usage |
|--------|------|-------|
| `supabase` | Client object | Default client — used for normal user operations. Follows RLS rules (users can only see/edit data they're allowed to). |
| `get_service_client()` | Function → Client | Returns a service-role client — used for admin/system operations that need access to all data regardless of RLS rules. |

### Simple Explanation

> **Think of it like having two keys to a filing cabinet.** The regular key (`supabase`) only opens the drawers you're allowed to access — a manager can see their own plans, an HRBP can see their zone's plans. The master key (`get_service_client()`) opens every drawer — used by the system itself when it needs to do things like fetch any user's profile during login or send reminders to all managers.

---

## 3. 📤 Export Service (`utils/export_utils.py`)

### What It Does

Generates downloadable **reports** from action plan data in three formats: **CSV**, **Excel**, and **PDF**.

### How It Works

| Format | How It's Generated |
|--------|-------------------|
| **CSV** | Uses `pandas` `.to_csv()` to convert the data table to a comma-separated text file. |
| **Excel** | Uses `pandas` with the `openpyxl` engine to write a proper `.xlsx` spreadsheet. |
| **PDF** | Uses `fpdf2` to create a formatted document with headers, styled table rows, status colours, and a summary section at the bottom. |

### PDF Report Features

The PDF report is the most detailed format and includes:

- **Branded header** — orange accent bar with "MAP System" title and generation timestamp
- **Table columns** — Manager, Zone, Function, Q#, Title, Status, Start Date, Target Date
- **Colour-coded statuses** — Grey for Initiated, Yellow for Ongoing, Green for Closed
- **Alternating row shading** — for readability
- **Summary footer** — total record count and per-status breakdown
- **Unicode sanitisation** — converts special characters (em dashes, smart quotes, etc.) to safe Latin-1 equivalents so the PDF doesn't crash

### Key Functions

| Function | Purpose |
|----------|---------|
| `generate_report(df, format, filename)` | Main entry point — takes a DataFrame and format string, returns file bytes |
| `save_temp_file(content, suffix)` | Saves generated bytes to a temporary file (e.g., for email attachments) |
| `_build_pdf(df, title)` | Internal — renders the full PDF document |
| `_sanitize(text)` | Internal — cleans Unicode characters for PDF compatibility |

### Simple Explanation

> **Think of it like a print shop.** You hand over your data (the list of action plans) and tell them what format you want. If you want a quick text dump, they give you a CSV. If you want a nice spreadsheet, they give you an Excel file. If you want a polished, branded document you can email to your boss, they create a PDF with your company's colors, a header, and a neat summary at the bottom.

---

## 4. 📧 Email Service (`utils/email_service.py`)

### What It Does

Sends **automated email notifications** for different events in the MAP System — plan creation, invitations, feedback, reminders, and custom admin messages. Every email sent is also logged to the database for auditing.

### How It Works

Emails are sent using **Gmail SMTP over SSL** (`smtp.gmail.com`, port 465). The sender credentials (`EMAIL_SENDER` and `EMAIL_PASSWORD`) come from the `.env` file.

### Email Types

| Function | Trigger | Who Receives It |
|----------|---------|-----------------|
| `send_plan_created()` | A new action plan is created | Manager + their Reporting Manager |
| `send_invitation()` | An eligible manager is invited to the system | The invited Manager |
| `send_zone_report()` | Zone report is exported and shared | The HRBP for that zone |
| `send_admin_feedback()` | Admin sends feedback on a plan | The Manager who owns the plan |
| `send_weekly_reminder()` | Automated check finds managers who haven't started or are stuck | The Manager |
| `send_manual_notification()` | Admin composes a custom message | Selected recipients |
| `check_and_send_reminders()` | Cron/scheduled job runs | Managers meeting reminder conditions |

### Reminder Logic (`check_and_send_reminders`)

This function runs two automated checks:

| Condition | Who Gets Reminded | Message |
|-----------|-------------------|---------|
| **No plans created** | Eligible managers who haven't created any action plans yet | "Please create your Action Plans" |
| **Plans stuck > 7 days** | Managers whose plans have been in "Initiated" status for over 7 days without update | "Your plans are awaiting a progress update" |

It avoids spamming — each manager only gets **one** reminder per check, even if they have multiple stuck plans.

### Notification Logging

Every email attempt (successful or failed) is recorded in the `notifications_log` table:

| Field | What's Stored |
|-------|---------------|
| `recipient_id` | The employee's database ID |
| `type` | Type of notification (e.g., `plan_created`, `invitation`, `reminder`) |
| `action_plan_id` | The related plan (if applicable) |
| `sent_at` | Timestamp |
| `status` | `"sent"` or `"failed"` |

### Email Design

All emails share a consistent look:
- **Orange header bar** (`#C55A11`) with a title
- **Clean white body** with structured content
- **Automated footer** — "This is an automated message from the MAP System"
- Support for **file attachments** (used for zone reports)

### Simple Explanation

> **Think of it like a post office inside the app.** Whenever something important happens — a plan is created, feedback is given, someone forgets to update their work — the post office automatically writes a professional-looking letter and sends it to the right person's email inbox. It also keeps a log book (notifications_log) of every letter sent, so the admin can check later if the emails actually went through or not. There's also a weekly patrol (check_and_send_reminders) that goes around checking if anyone needs a nudge.

---

## How They All Connect

```
┌─────────────────────────────────────────────────────────┐
│                       User Opens App                     │
│                            │                             │
│                     ┌──────▼──────┐                      │
│                     │   auth.py   │                      │
│                     │  (Login)    │                      │
│                     └──────┬──────┘                      │
│                            │ uses                        │
│                  ┌─────────▼──────────┐                  │
│                  │  supabase_client   │                  │
│                  │  (DB Connection)   │                  │
│                  └─────────┬──────────┘                  │
│                            │ provides data to            │
│               ┌────────────┼────────────┐                │
│               │                         │                │
│        ┌──────▼──────┐          ┌───────▼───────┐        │
│        │ export_utils │          │ email_service │        │
│        │ (Reports)    │          │ (Notifications)│       │
│        └─────────────┘          └───────────────┘        │
└─────────────────────────────────────────────────────────┘
```

1. **Auth** verifies the user → uses **Supabase Connection** to check credentials and fetch profile
2. **Supabase Connection** is the backbone — every module uses it to talk to the database
3. **Export** pulls plan data from the database and generates downloadable files
4. **Email Service** sends notifications and can attach exported reports (e.g., zone reports)

---

## 5. 🗃️ Supabase Read & Write — How Data Flows

Once the connection is established (via `supabase_client.py`), every part of the app reads and writes rows using a **chaining pattern**. Here's exactly how it works, with real examples from the codebase.

### Reading Rows (SELECT)

The pattern is always: **table → select → filter → execute → use `.data`**

#### Example 1: Fetch all plans for a manager (`manager.py`)

```python
resp = (
    supabase
    .from_("action_plans")          # 1. Pick the table
    .select("*")                    # 2. Which columns (* = all)
    .eq("manager_id", manager_db_id)# 3. Filter: only this manager's plans
    .order("created_at", desc=True) # 4. Sort: newest first
    .execute()                      # 5. Run the query
)
plans = resp.data or []             # 6. Get the list of row dicts
```

**What's happening step by step:**

| Step | Code | SQL Equivalent |
|------|------|----------------|
| Pick table | `.from_("action_plans")` | `FROM action_plans` |
| Choose columns | `.select("*")` | `SELECT *` |
| Filter | `.eq("manager_id", id)` | `WHERE manager_id = id` |
| Sort | `.order("created_at", desc=True)` | `ORDER BY created_at DESC` |
| Run it | `.execute()` | Sends the request to Supabase |

The result (`resp.data`) is a **list of Python dicts** — each dict is one row:
```python
[
    {"id": "abc-123", "title": "Weekly Recognition", "status": "Ongoing", ...},
    {"id": "def-456", "title": "Skills Workshop", "status": "Initiated", ...},
]
```

#### Example 2: Fetch a single row (`auth.py`)

```python
resp = (
    supabase
    .from_("auth_users")
    .select("emp_id, role, zone")   # Only specific columns
    .eq("auth_uid", auth_uid)       # Match by auth UID
    .single()                       # Expect exactly one row (not a list)
    .execute()
)
emp_id = resp.data["emp_id"]        # Direct dict access (not a list)
```

`.single()` is the key difference — instead of returning `[{...}]`, it returns `{...}` directly. Use it when you know there's exactly one matching row.

#### Example 3: Fetch with a JOIN (`manager.py`)

```python
resp = (
    supabase
    .from_("progress_updates")
    .select("*, employees(name)")   # JOIN: also get the employee's name
    .eq("action_plan_id", plan_id)
    .order("created_at", desc=False)
    .execute()
)
```

The `employees(name)` part tells Supabase to follow the foreign key relationship and include the employee's `name` in the result. Each row comes back as:
```python
{"id": "...", "update_text": "...", "employees": {"name": "Ravi Kumar"}}
```

> **Simple explanation:** Reading from Supabase is like writing a sentence: *"From the action_plans table, select everything, where the manager is this person, sorted by newest first, and go."* The result is just a list of Python dictionaries — one dict per row.

---

### Writing Rows (INSERT)

The pattern is: **table → insert(dict) → execute**

#### Example: Create a new action plan (`manager.py`)

```python
row = {
    "manager_id":  manager_db_id,
    "wef_element": payload["wef_element"],
    "title":       payload["title"],
    "description": payload["description"],
    "start_date":  payload["start_date"],
    "target_date": payload["target_date"],
    "status":      "Initiated",
    "zone":        zone,
    "function":    function_,
    "created_at":  datetime.utcnow().isoformat(),
    "updated_at":  datetime.utcnow().isoformat(),
}

resp = supabase.from_("action_plans").insert(row).execute()
new_plan = resp.data[0]             # The inserted row (with generated id)
```

You build a plain Python dict with the column names as keys, pass it to `.insert()`, and call `.execute()`. Supabase returns the inserted row with any auto-generated fields like the `id` (UUID).

#### Example: Log a notification (`email_service.py`)

```python
supabase.from_("notifications_log").insert({
    "recipient_id":   recipient_id,
    "type":           "plan_created",
    "action_plan_id": plan_id,
    "sent_at":        datetime.utcnow().isoformat(),
    "status":         "sent",
}).execute()
```

> **Simple explanation:** Writing is even simpler — you make a Python dictionary with the column names and values, and tell Supabase *"insert this into that table."* It's like filling out a form and clicking submit.

---

### Updating Rows (UPDATE)

The pattern is: **table → update(dict) → filter → execute**

#### Example: Update an existing plan (`manager.py`)

```python
supabase.from_("action_plans").update({
    "title":       payload["title"],
    "description": payload["description"],
    "start_date":  payload["start_date"],
    "target_date": payload["target_date"],
    "status":      payload["status"],
    "updated_at":  datetime.utcnow().isoformat(),
}).eq("id", plan_id).execute()
```

**Important:** The `.eq("id", plan_id)` filter tells Supabase *which* row to update. Without it, it would update every row in the table.

> **Simple explanation:** Updating is like reading + writing combined. You say *"in this table, change these fields, but only for the row where the id matches."* The filter (`.eq()`) acts like a search target.

---

### Quick Reference — All Operations

| Operation | Pattern | When Used |
|-----------|---------|-----------|
| **Read many** | `.from_("table").select("*").eq("col", val).execute()` | Fetching plan lists, employee lists |
| **Read one** | `.from_("table").select("*").eq("col", val).single().execute()` | Fetching a single plan or profile |
| **Read with JOIN** | `.select("*, other_table(col)")` | Getting employee names with progress updates |
| **Insert** | `.from_("table").insert({...}).execute()` | Creating plans, logging notifications |
| **Update** | `.from_("table").update({...}).eq("id", val).execute()` | Editing plan details, changing status |
| **Filter operators** | `.eq()` `.lt()` `.gt()` `.in_()` | Equals, less than, greater than, in list |

---

## 6. 🖥️ How the UI is Built

The MAP System UI is built with **Streamlit** — a Python framework that turns Python scripts into interactive web apps. There's no separate HTML/JS frontend; everything is written in Python.

### The Architecture at a Glance

```
app.py (entry point)
  │
  ├── Load CSS (assets/style.css)
  ├── Auth gate (require_auth)
  ├── Sidebar (components/sidebar.py)
  │     └── Navigation buttons per role
  │
  └── Route to view by role:
        ├── views/manager.py   (Manager role)
        ├── views/hrbp.py      (HRBP role)
        ├── views/admin.py     (Admin role)
        └── views/ceo.py       (CEO role)

Each view uses:
  ├── components/action_plan_form.py  (form component)
  ├── components/dashboard_charts.py  (Plotly charts)
  └── utils/ (export, email, validators)
```

### Step-by-Step: What Happens When You Open the App

| Step | File | What Happens |
|------|------|-------------|
| 1 | `app.py` | `st.set_page_config()` sets the browser tab title, icon, and wide layout |
| 2 | `app.py` | `_load_css()` injects `style.css` into the page via `st.markdown(<style>...)` |
| 3 | `app.py` | `require_auth()` checks if you're logged in. If not → shows login form + `st.stop()` |
| 4 | `app.py` | Builds the **sidebar** — accent bar, user info, navigation buttons |
| 5 | `sidebar.py` | `render_nav(role)` creates nav buttons based on your role |
| 6 | `app.py` | `_route(role)` calls `manager.render()`, `hrbp.render()`, etc. |
| 7 | `views/*.py` | The view reads `get_current_page()` and renders the matching sub-page |

### How Streamlit Works (the tricky part)

Streamlit re-runs the **entire Python script from top to bottom** every time:
- A button is clicked
- A form is submitted
- A selectbox changes
- Any widget interaction

This is fundamentally different from traditional web apps. There's no "event handler" that runs just one function — the whole script re-executes.

#### How state survives re-runs: `st.session_state`

```python
# Saving state
st.session_state["current_page"] = "my_plans"
st.session_state["user"] = {"name": "Ravi", "role": "Manager", ...}

# Reading state
page = st.session_state.get("current_page", "dashboard")
user = st.session_state.get("user")
```

`session_state` is a persistent dictionary that survives re-runs. Without it, all variables would reset on every click. The entire navigation system, login session, and drill-down state depend on this.

> **Simple explanation:** Imagine the app is like a flipbook. Every time you click anything, Streamlit redraws the entire page from scratch. But it remembers your choices (which page you're on, who you are) in a special notebook called `session_state`. So even though it redraws everything, it knows where you left off.

### How Navigation Works (`sidebar.py`)

```python
_NAV_ITEMS = {
    "Manager": [
        ("🏠", "Dashboard",         "dashboard"),
        ("➕", "Create Action Plan", "create_plan"),
        ("📝", "My Action Plans",   "my_plans"),
    ],
    "HRBP": [...],
    "Admin": [...],
    "CEO": [...],
}
```

Each role gets different nav items. When you click a button:
1. `st.session_state["current_page"]` is set to the page key (e.g., `"my_plans"`)
2. Any drill-down state (like `selected_plan_id`) is cleared
3. `st.rerun()` triggers a full re-render, and the view checks `get_current_page()` to decide what to show

> **Simple explanation:** The sidebar is just a list of buttons. Clicking one saves *"I want to see this page"* to session_state, then redraws the app. The view file then looks at that saved value and decides what to display.

### How Forms Work (`action_plan_form.py`)

Forms use `st.form()` — a Streamlit feature that groups inputs together and only processes them when the submit button is clicked (not on every keystroke).

```python
with st.form("login_form"):
    email     = st.text_input("Email")
    password  = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Sign In")

if submitted:
    # Only runs when the button is clicked
    # email and password have the user's input
```

The action plan form is **reusable** — it handles both create and edit:

| Mode | `existing_plan` param | Behaviour |
|------|-----------------------|-----------|
| Create | `None` | Shows empty fields, WEF element selector, status locked to "Initiated" |
| Edit | `{...plan dict...}` | Pre-fills fields, locks WEF element, shows status dropdown |
| Read-only | `{...}` + `readonly=True` | Shows a styled card with no editable fields (CEO view) |

The form uses a **callback pattern**: it validates input, builds a `payload` dict, and calls `on_submit(payload)`. The parent view decides what to do — insert a new row or update an existing one.

> **Simple explanation:** The form is like a Swiss Army knife — one piece of code handles creating new plans, editing existing plans, and viewing plans read-only. It knows which mode to use based on the parameters it receives.

### How the Dashboard Charts Work (`dashboard_charts.py`)

Charts are built with **Plotly** (interactive charting library) and displayed via `st.plotly_chart()`.

| Chart | Type | What It Shows |
|-------|------|---------------|
| `chart_plans_by_zone()` | Bar chart | Number of plans in each zone |
| `chart_plans_by_function()` | Bar chart | Number of plans per department |
| `chart_wef_distribution()` | Horizontal bar | Plans per WEF element (Q1–Q12) |
| `chart_status_distribution()` | Donut chart | Initiated vs Ongoing vs Closed breakdown |
| `chart_status_by_zone()` | Grouped bar | Status breakdown within each zone |
| `chart_plans_over_time()` | Line + bar | Monthly trend of plan creation |
| `summary_metrics_strip()` | Metric cards | Total plans, % closed, zones, managers |

Each chart function takes a pandas DataFrame, does the aggregation (counting, grouping), and returns a Plotly `Figure` object. The views just call `st.plotly_chart(fig)`.

> **Simple explanation:** The dashboard takes the raw data table, counts things up (how many plans per zone, per status, etc.), and draws interactive charts. It's essentially: *data in, picture out.*

### How Styling Works (`assets/style.css`)

Streamlit has a default dark theme. The app overrides it with a custom CSS file injected via:

```python
with open("assets/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
```

Key styling decisions:

| Element | Style |
|---------|-------|
| Background | Light grey `#F5F7FA` — clean, professional look |
| Sidebar | Pure white with grey border |
| Text | Dark `#1A1A2E` globally forced via `!important` |
| Forms | White cards with subtle shadow |
| Nav buttons | Transparent with hover highlight |
| Sign-out button | Red-tinted background |
| Active tab | Blue underline `#2E75B6` |
| Scrollbars | Thin 6px, subtle grey |

Many UI elements also use **inline HTML** with `st.markdown(html, unsafe_allow_html=True)` for things Streamlit doesn't natively support, like:
- Status badges with rounded corners and color coding
- Metric cards with accent borders
- Progress history timeline cards
- Plan cards with left accent borders

> **Simple explanation:** Streamlit gives you a basic-looking app out of the box. The CSS file is like a coat of paint that makes everything look polished — white cards, subtle shadows, branded colours. For anything Streamlit can't style natively (like custom badges or cards), raw HTML is injected directly into the page.
