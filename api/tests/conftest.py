import os

# Before the app is imported: no demo autopilot, no database file. Tests build exactly the state they need.
os.environ["DEMO_AUTOPILOT"] = "off"
os.environ["PERSIST"] = "off"

import pytest

from app.auth import AuthUser, get_current_user, optional_user
from app.main import app, store
from app.models import Profile

TEST_USER = AuthUser(id="u_test", email="buyer@test.dev")

PROVIDER_VARS = ("OPENAI_API_KEY", "MODEL_INTAKE", "MODEL_FALLBACK", "OPENAI_BASE_URL",
                 "ELEVENLABS_API_KEY", "ELEVENLABS_STT_MODEL", "ELEVENLABS_BASE_URL",
                 "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_JWT_SECRET", "ALLOW_DEMO_SELLERS",
                 "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_ALLOW_LIVE")


@pytest.fixture(autouse=True)
def _no_real_provider_keys(monkeypatch):
    """api/.env may hold real keys. Tests must never reach a real provider; they stub or run keyless."""
    for var in PROVIDER_VARS:
        monkeypatch.delenv(var, raising=False)
    # General tests share one user across the suite, so give them a generous allowance. Quota tests set their own.
    monkeypatch.setenv("FREE_REVEALS", "1000")
    # Most tests drive the synthetic demo sellers A, B, C directly. Isolation tests switch this off themselves.
    monkeypatch.setenv("ALLOW_DEMO_SELLERS", "true")


@pytest.fixture(autouse=True)
def _signed_in_as_test_user():
    """Every test acts as one signed-in user, so nothing here calls Supabase. test_auth.py removes this on purpose."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    # Token routes read an optional login: follow whoever the test is signed in as, or nobody once it signs out.
    app.dependency_overrides[optional_user] = lambda: app.dependency_overrides[get_current_user]() \
        if get_current_user in app.dependency_overrides else None
    store.profiles.setdefault(TEST_USER.id, Profile(
        id=TEST_USER.id, role="buyer", full_name="Test User", email=TEST_USER.email, phone="9820144556",
        company="Test Co", business_type="manufacturer", state="Telangana", city="Hyderabad",
        roles=["buyer", "seller"]))
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(optional_user, None)
