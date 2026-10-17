import pytest

PROVIDER_VARS = ("OPENAI_API_KEY", "MODEL_INTAKE", "MODEL_FALLBACK", "OPENAI_BASE_URL",
                 "ELEVENLABS_API_KEY", "ELEVENLABS_STT_MODEL", "ELEVENLABS_BASE_URL")


@pytest.fixture(autouse=True)
def _no_real_provider_keys(monkeypatch):
    """api/.env may hold real keys. Tests must never reach a real provider; they stub or run keyless."""
    for var in PROVIDER_VARS:
        monkeypatch.delenv(var, raising=False)
