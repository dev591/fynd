"""Every account is isolated: no acting as other sellers, no editing someone else's quote, no chat before a reveal."""
import pytest
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app
from tests.helpers import alias, tokens_of

client = TestClient(app)


def as_user(uid):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=f"{uid}@t.dev")


def signed_out():
    app.dependency_overrides.pop(get_current_user, None)


def seller_account(uid, item="Iso widget"):
    as_user(uid)
    client.post("/api/profile", json={"id": "x", "role": "supplier", "full_name": uid, "email": f"{uid}@t.dev", "phone": "9820144556",
                                      "company": f"{uid} Works", "business_type": "trader", "state": "Gujarat", "city": "Surat",
                                      "pincode": "395003", "categories": ["fasteners"]})
    client.post("/api/me/roles", json={"role": "seller"})
    client.post(f"/api/supplier/products/{uid}", json={"name": item, "pack_price": 10, "pack_size": 1, "moq": 1,
                                                       "usual_lead_days": 2, "stock": 1000})


def request_for(item="Iso widget", buyer="iso-buyer"):
    as_user(buyer)
    return client.post("/api/rfqs", json={"item": item, "qty": 50, "need_in_days": 5, "buyer_company": "B Co", "buyer_name": "B"}).json()["id"]


def test_a_new_seller_sees_only_its_own_seller_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    seller_account("iso-new")
    ids = [s["supplier_id"] for s in client.get("/api/suppliers").json()]
    assert ids == ["iso-new"]
    assert client.get("/api/supplier/A/notifications").status_code == 404
    assert client.get("/api/supplier/products/A").status_code == 404
    assert client.post("/api/supplier/products/A", json={"name": "x", "pack_price": 1, "pack_size": 1}).status_code == 404


def test_only_the_seller_a_request_was_sent_to_can_open_or_quote_it(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    seller_account("iso-owner"); seller_account("iso-other")
    rid = request_for()
    tok = tokens_of(rid)["iso-owner"]
    body = {"supplier_name": "x", "pack_price": 9, "pack_size": 1, "freight": 0, "lead_days": 2}
    as_user("iso-other")
    for r in (client.get(f"/api/rfq-by-token/{tok}"), client.post(f"/api/rfq-by-token/{tok}/quotes", json=body),
              client.get(f"/api/rfq-by-token/{tok}/quotes/mine"), client.get(f"/api/rfq-by-token/{tok}/draft"),
              client.post(f"/api/rfq-by-token/{tok}/decline")):
        assert r.status_code == 403, r.request.url
    signed_out()
    assert client.post(f"/api/rfq-by-token/{tok}/quotes", json=body).status_code == 403
    as_user("iso-owner")
    assert client.get(f"/api/rfq-by-token/{tok}").status_code == 200
    assert client.post(f"/api/rfq-by-token/{tok}/quotes", json=body).status_code == 200


def test_chat_stays_locked_on_both_sides_until_the_buyer_reveals_the_seller(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    seller_account("iso-chat")
    rid = request_for(buyer="iso-chat-buyer")
    tok = tokens_of(rid)["iso-chat"]
    as_user("iso-chat")
    client.post(f"/api/rfq-by-token/{tok}/quotes", json={"supplier_name": "x", "pack_price": 9, "pack_size": 1, "freight": 0, "lead_days": 2})
    a = alias(rid, "iso-chat")
    msg = {"sender": "buyer", "sender_name": "B", "text": "hello"}

    as_user("iso-chat-buyer")
    r = client.post(f"/api/rfqs/{rid}/threads/{a}/messages", json=msg)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "reveal_required"
    assert client.get(f"/api/rfqs/{rid}/threads/{a}/messages").json() == []
    as_user("iso-chat")
    assert client.post(f"/api/rfq-by-token/{tok}/messages", json=msg).status_code == 403
    assert client.get(f"/api/rfq-by-token/{tok}/messages").json() == []

    as_user("iso-chat-buyer")
    assert client.post(f"/api/rfqs/{rid}/quotes/{a}/reveal").status_code == 200
    assert client.post(f"/api/rfqs/{rid}/threads/{a}/messages", json=msg).status_code == 201
    as_user("iso-chat")
    assert client.post(f"/api/rfq-by-token/{tok}/messages", json={**msg, "text": "hi back"}).status_code == 201
    assert [m["text"] for m in client.get(f"/api/rfq-by-token/{tok}/messages").json()] == ["hello", "hi back"]


def test_another_buyer_cannot_read_or_write_someone_elses_chat(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    seller_account("iso-c2")
    rid = request_for(buyer="iso-owner-buyer")
    a = None
    tok = tokens_of(rid)["iso-c2"]
    as_user("iso-c2")
    client.post(f"/api/rfq-by-token/{tok}/quotes", json={"supplier_name": "x", "pack_price": 9, "pack_size": 1, "freight": 0, "lead_days": 2})
    a = alias(rid, "iso-c2")
    as_user("iso-stranger-buyer")
    assert client.get(f"/api/rfqs/{rid}/threads/{a}/messages").status_code == 404
    assert client.post(f"/api/rfqs/{rid}/threads/{a}/messages", json={"sender": "buyer", "sender_name": "x", "text": "hi"}).status_code == 404
