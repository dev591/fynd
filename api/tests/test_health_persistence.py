from fastapi.testclient import TestClient

from app import persist
from app.main import app

client = TestClient(app)


def test_health_says_where_data_is_saved_and_warns_when_a_hosted_server_would_lose_it(monkeypatch):
    monkeypatch.setenv("PERSIST", "on")
    monkeypatch.delenv("PERSIST_BACKEND", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    h = client.get("/health").json()
    assert h["persistence"]["backend"] == "sqlite" and "warning" not in h["persistence"]
    monkeypatch.setenv("RENDER", "true")                                   # Render sets this on its servers
    w = client.get("/health").json()["persistence"]
    assert "lost" in w["warning"].lower() and "PERSIST_BACKEND" in w["warning"]


def test_health_reports_supabase_when_it_is_the_backend(monkeypatch):
    monkeypatch.setenv("PERSIST", "on")
    monkeypatch.setenv("PERSIST_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://p.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-secret")
    monkeypatch.setenv("RENDER", "true")
    p = client.get("/health").json()["persistence"]
    assert p["backend"] == "supabase" and "warning" not in p
    assert set(p) <= {"state", "backend", "warning"} and "service-secret" not in str(client.get("/health").json())


def test_health_when_supabase_could_not_be_loaded_says_saving_is_off(monkeypatch):
    monkeypatch.setattr("app.main.PERSIST_STATE", "offline")
    p = client.get("/health").json()["persistence"]
    assert p["state"] == "offline" and "not saving" in p["warning"].lower()
