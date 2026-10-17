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
