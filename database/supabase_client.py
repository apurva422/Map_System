import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ── Anon client (used by most app operations; respects RLS) ───────────────────
_url:      str = os.environ.get("SUPABASE_URL", "")
_anon_key: str = os.environ.get("SUPABASE_ANON_KEY", "")

supabase: Client = create_client(_url, _anon_key)

# ── Service-role client (bypasses RLS; used for Admin-only ops) ───────────────
_service_key: str = os.environ.get("SUPABASE_SERVICE_KEY", "")

def get_service_client() -> Client:
    """Return a Supabase client using the service-role key.
    Use ONLY for operations that must bypass RLS (e.g. admin user creation,
    eligibility checks across all rows).  Never expose this to the browser.
    """
    if not _service_key:
        raise EnvironmentError(
            "SUPABASE_SERVICE_KEY is not set in your .env file."
        )
    return create_client(_url, _service_key)