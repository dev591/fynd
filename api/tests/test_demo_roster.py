import pytest
from fastapi.testclient import TestClient

from app import demo_roster
from app.main import app
from app.models import Profile, SupplierProductIn

client = TestClient(app)


def test_roster_is_ten_distinct_valid_sellers_with_overlapping_items():
    r = demo_roster.ROSTER
    assert len(r) == 10 and len({demo_roster.email_of(s) for s in r}) == 10 and len({s["company"] for s in r}) == 10
    for s in r:
        Profile(**demo_roster.profile_payload(s))                    # what the wizard would send is accepted
        for p in s["products"]:
            SupplierProductIn(**p)
    assert sum(any("M10 bolt" in p["aliases"] for p in s["products"]) for s in r) == 10
    assert sum(any("M8 nut" in p["aliases"] for p in s["products"]) for s in r) >= 5


def test_roster_makes_the_comparison_interesting():
    m10 = [(s["company"], p) for s in demo_roster.ROSTER for p in s["products"] if "M10 bolt" in p["aliases"]]
    assert any(p["usual_lead_days"] > 5 for _, p in m10)             # a late seller, so the exception gate shows
    assert any(p["stock"] is not None and p["stock"] < 100 for _, p in m10)   # a short-stock seller, so partial fill shows
    assert len({p["pack_size"] for _, p in m10}) >= 3                # different pack sizes


def test_logins_endpoint_is_off_by_default_and_hands_out_the_list_only_when_enabled(monkeypatch):
    monkeypatch.delenv("DEMO_LOGINS", raising=False)
    monkeypatch.setenv("DEMO_SELLER_PASSWORD", "x" * 10)
    assert client.get("/api/demo/logins").json() == {"enabled": False, "sellers": []}
    monkeypatch.setenv("DEMO_LOGINS", "on")
    on = client.get("/api/demo/logins").json()
    assert on["enabled"] is True and len(on["sellers"]) == 10 and on["password"] == "x" * 10
    monkeypatch.delenv("DEMO_SELLER_PASSWORD")
    assert client.get("/api/demo/logins").json()["enabled"] is False     # no password set means nothing is handed out


@pytest.fixture
def _remove_demo_accounts():
    """The store is shared across tests: take the demo sellers back out so other tests' matching is unaffected."""
    from app.main import store
    yield
    for d in (store.supplier_products, store.supplier_profiles, store.supplier_owner, store.profiles, store.notifications):
        for k in [k for k in d if str(k).startswith("demo-")]:
            d.pop(k, None)


def test_seeding_all_ten_through_the_api_notifies_every_seller_for_the_shared_item(_remove_demo_accounts):
    """Mirrors scripts/seed_demo_sellers.py: profile, seller role, catalog, per account. Then a buyer asks for the shared item."""
    from app.auth import AuthUser, get_current_user

    def as_user(uid, email):
        app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=email)

    ids = []
    for s in demo_roster.ROSTER:
        uid = "demo-" + s["n"]
        ids.append(uid)
        as_user(uid, demo_roster.email_of(s))
        assert client.post("/api/profile", json=demo_roster.profile_payload(s)).status_code in (200, 201)
        assert client.post("/api/me/roles", json={"role": "seller"}).status_code == 200
        sid = client.get("/api/me").json()["supplier_id"]
        assert sid == uid
        for p in s["products"]:
            assert client.post(f"/api/supplier/products/{sid}", json=p).status_code == 201
    as_user("demo-buyer", "b@t.dev")
    client.post("/api/profile", json={**demo_roster.profile_payload(demo_roster.ROSTER[0]), "role": "buyer", "company": "Buyer Co"})
    made = client.post("/api/rfqs", json={"item": "m10 bolt", "qty": 120, "need_in_days": 5, "buyer_company": "Buyer Co", "buyer_name": "B"}).json()
    rid = made["id"] if "id" in made else made["rfq"]["id"]
    for uid, s in zip(ids, demo_roster.ROSTER):
        as_user(uid, demo_roster.email_of(s))
        inbox = client.get(f"/api/supplier/{uid}/notifications").json()
        assert any(n["rfq_id"] == rid for n in inbox), uid


def test_some_demo_sellers_have_volume_tiers_so_the_quantity_slider_can_flip_the_winner():
    tiered = [p for s in demo_roster.ROSTER for p in s["products"] if p["price_breaks"]]
    assert len(tiered) >= 3
    for p in tiered:
        SupplierProductIn(**p)                                              # tiers pass the same validation as any catalog entry
        assert all(b["pack_price"] < p["pack_price"] for b in p["price_breaks"])
