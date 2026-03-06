import streamlit as st
from supabase import create_client, Client

# Anon client (respects RLS)
_url:      str = st.secrets["SUPABASE_URL"]
_anon_key: str = st.secrets["SUPABASE_ANON_KEY"]

supabase: Client = create_client(_url, _anon_key)

# Service-role client (bypasses RLS)
_service_key: str = st.secrets["SUPABASE_SERVICE_KEY"]

def get_service_client() -> Client:
    """Return a service-role Supabase client (bypasses RLS)."""
    if not _service_key:
        raise EnvironmentError(
            "SUPABASE_SERVICE_KEY is not set in your Streamlit secrets."
        )
    return create_client(_url, _service_key)