import pytest
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app, store

client = TestClient(app)


def as_user(uid, email="u@test.dev"):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=email)


def make_profile(role, **kw):
    return {"id": "ignored", "role": role, "full_name": "Pat", "email": "x@y.in", "phone": "9820144556",
            "company": "Pat Works", "business_type": "manufacturer", "state": "Telangana", "city": "Hyderabad",
            "categories": ["fasteners"], **kw}


BUYER_CALLS = [("get", "/api/rfqs", None), ("get", "/api/savings", None),
               ("post", "/api/rfqs", {"item": "x", "qty": 1, "need_in_days": 1, "buyer_company": "c", "buyer_name": "b"}),
               ("post", "/api/intake/draft", {"text": "x"})]
SELLER_CALLS = [("get", "/api/suppliers", None), ("get", "/api/supplier/A/notifications", None),
                ("get", "/api/supplier/A/autopilot", None), ("get", "/api/supplier/products/A", None)]


def call(m, path, body):
    return getattr(client, m)(path, **({"json": body} if body is not None else {}))


def test_no_profile_means_buyer_only():
    as_user("roles-new")
    me = client.get("/api/me").json()
    assert me["roles"] == ["buyer"]
    assert all(call(*c).status_code != 403 for c in BUYER_CALLS)
    for c in SELLER_CALLS:
        r = call(*c)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "role_required", c


def test_seller_only_account_cannot_use_buyer_endpoints():
    as_user("roles-seller")
    client.post("/api/profile", json=make_profile("supplier"))
    assert client.get("/api/me").json()["roles"] == ["seller"]
    for c in BUYER_CALLS:
        assert call(*c).status_code == 403, c
    assert client.get("/api/supplier/roles-seller/notifications").status_code == 200


def test_one_account_can_hold_both_roles_and_use_both_sides():
    as_user("roles-both")
    client.post("/api/profile", json=make_profile("buyer"))
    assert client.get("/api/me").json()["roles"] == ["buyer"]
    added = client.post("/api/me/roles", json={"role": "seller"})
    assert added.status_code == 200 and added.json()["roles"] == ["buyer", "seller"]
    me = client.get("/api/me").json()
    assert me["supplier_id"] == "roles-both"                         # a seller record now exists, owned by them
    assert client.post("/api/me/roles", json={"role": "seller"}).json()["roles"] == ["buyer", "seller"]  # idempotent
    assert all(call(*c).status_code != 403 for c in BUYER_CALLS + SELLER_CALLS)


def test_adding_seller_needs_a_profile_first_and_rejects_nonsense():
    as_user("roles-noprofile")
    assert client.post("/api/me/roles", json={"role": "seller"}).status_code == 409
    assert client.post("/api/me/roles", json={"role": "admin"}).status_code == 422


def test_seller_role_added_later_does_not_touch_other_users():
    as_user("roles-a"); client.post("/api/profile", json=make_profile("buyer"))
    as_user("roles-b"); client.post("/api/profile", json=make_profile("buyer"))
    as_user("roles-a"); client.post("/api/me/roles", json={"role": "seller"})
    as_user("roles-b")
    assert client.get("/api/me").json()["roles"] == ["buyer"]
    assert client.get("/api/supplier/roles-a/notifications").status_code == 403


def _seller_account(uid, company):
    as_user(uid, f"{uid}@test.dev")
    client.post("/api/profile", json=make_profile("supplier", company=company))
    client.post("/api/me/roles", json={"role": "seller"})
    client.post(f"/api/supplier/products/{uid}", json={"name": "Zinc widget", "pack_price": 10, "pack_size": 1,
                                                       "moq": 1, "usual_lead_days": 2, "stock": 500})


def test_two_separate_accounts_with_the_same_item_are_both_notified():
    for uid, co in (("seller-one", "One Works"), ("seller-two", "Two Works")):
        _seller_account(uid, co)
    as_user("buyer-x", "bx@test.dev")
    client.post("/api/profile", json=make_profile("buyer"))
    rid = client.post("/api/rfqs", json={"item": "zinc widget", "qty": 50, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    for uid in ("seller-one", "seller-two"):
        as_user(uid, f"{uid}@test.dev")
        inbox = client.get(f"/api/supplier/{uid}/notifications").json()
        assert any(n["rfq_id"] == rid for n in inbox), uid
