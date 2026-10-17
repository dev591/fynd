import pytest

from app.auth import AuthUser, get_current_user
from app.main import app

TEST_USER = AuthUser(id="u_test", email="buyer@test.dev")

PROVIDER_VARS = ("OPENAI_API_KEY", "MODEL_INTAKE", "MODEL_FALLBACK", "OPENAI_BASE_URL",
                 "ELEVENLABS_API_KEY", "ELEVENLABS_STT_MODEL", "ELEVENLABS_BASE_URL",
                 "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_JWT_SECRET", "ALLOW_DEMO_SELLERS")


@pytest.fixture(autouse=True)
def _no_real_provider_keys(monkeypatch):
    """api/.env may hold real keys. Tests must never reach a real provider; they stub or run keyless."""
    for var in PROVIDER_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _signed_in_as_test_user():
    """Every test acts as one signed-in user, so nothing here calls Supabase. test_auth.py removes this on purpose."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)
