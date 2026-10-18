"""After a reveal the buyer gets the seller's full details, including an address. Before it, none of that leaks."""
import json

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app, store
from tests.helpers import alias, tokens_of

client = TestClient(app)
ADDRESS = "Plot 12, MIDC Phase 2, Andheri East"


def as_user(uid):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=f"{uid}@t.dev")


def profile(role, company, address):
    return {"id": "x", "role": role, "full_name": "Priya Shah", "email": "priya@sellerco.in", "phone": "9820144556", "company": company,
            "business_type": "manufacturer", "state": "Maharashtra", "city": "Mumbai", "pincode": "400093", "address": address, "categories": []}


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    as_user("rd-seller")
    client.post("/api/profile", json=profile("supplier", "Shah Circuits Pvt Ltd", ADDRESS))
    client.post("/api/me/roles", json={"role": "seller"})
    client.post("/api/supplier/products/rd-seller", json={"name": "HDI boards", "pack_price": 100, "pack_size": 1, "moq": 1, "usual_lead_days": 3, "stock": 500})
    as_user("rd-buyer")
    client.post("/api/profile", json=profile("buyer", "Buyer Works", "7 Banjara Hills Road"))
    rid = client.post("/api/rfqs", json={"item": "HDI boards", "qty": 20, "need_in_days": 5, "buyer_company": "Buyer Works", "buyer_name": "Ravi"}).json()["id"]
    as_user("rd-seller")
    client.post(f"/api/rfq-by-token/{tokens_of(rid)['rd-seller']}/quotes", json={"supplier_name": "x", "pack_price": 100, "pack_size": 1, "freight": 0, "lead_days": 3})
    as_user("rd-buyer")
    return rid, alias(rid, "rd-seller")


def test_the_address_is_stored_on_the_profile_and_validated(scene):
    assert store.profiles["rd-seller"].address == ADDRESS and store.supplier_profiles["rd-seller"].address == ADDRESS
    as_user("rd-long")
    assert client.post("/api/profile", json=profile("buyer", "X", "a" * 400)).status_code == 422


def test_nothing_identifying_leaks_before_the_reveal(scene):
    rid, a = scene
    everything = json.dumps([client.get(f"/api/rfqs/{rid}").json(), client.get(f"/api/rfqs/{rid}/summary").json(),
                             client.get(f"/api/rfqs/{rid}/suppliers/{a}").json()])
    for secret in (ADDRESS, "Shah Circuits", "9820144556", "priya@sellerco.in", "Priya Shah", "Andheri"):
        assert secret not in everything, secret


def test_after_the_reveal_the_buyer_gets_every_detail_on_the_card_data(scene):
    rid, a = scene
    assert client.post(f"/api/rfqs/{rid}/quotes/{a}/reveal").status_code == 200
    ident = client.get(f"/api/rfqs/{rid}").json()["revealed"][a]
    assert ident["business_name"] == "Shah Circuits Pvt Ltd" and ident["contact_name"] == "Priya Shah"
    assert ident["phone"] == "9820144556" and ident["email"] == "rd-seller@t.dev"
    assert ident["city"] == "Mumbai" and ident["state"] == "Maharashtra" and ident["address"] == ADDRESS
    panel = client.get(f"/api/rfqs/{rid}/suppliers/{a}").json()
    assert panel["contact"]["address"] == ADDRESS and panel["contact"]["phone"] == "9820144556"


def test_the_seller_gets_the_buyers_address_only_after_the_reveal_for_delivery(scene):
    rid, a = scene
    as_user("rd-seller")
    n = next(x for x in client.get("/api/supplier/rd-seller/notifications").json() if x["rfq_id"] == rid)
    assert n["buyer_contact"] is None and "Banjara Hills" not in json.dumps(n)
    as_user("rd-buyer")
    client.post(f"/api/rfqs/{rid}/quotes/{a}/reveal")
    as_user("rd-seller")
    n = next(x for x in client.get("/api/supplier/rd-seller/notifications").json() if x["rfq_id"] == rid)
    assert n["buyer_contact"]["address"] == "7 Banjara Hills Road"


def test_the_shared_page_never_carries_the_address(scene):
    rid, a = scene
    client.post(f"/api/rfqs/{rid}/quotes/{a}/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": a, "reason": "r", "approver": "Ravi"})
    token = client.post(f"/api/rfqs/{rid}/share").json()["token"]
    page = json.dumps(client.get(f"/api/share/{token}").json())
    assert ADDRESS not in page and "Andheri" not in page and "Banjara" not in page
