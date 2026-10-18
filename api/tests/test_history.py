"""Request log, editing a request, and order history for buyers and sellers."""
import pytest
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app, store
from tests.helpers import alias, tokens_of

client = TestClient(app)


def as_user(uid):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=f"{uid}@t.dev")


def new_request(qty=100, days=5):
    return client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": days, "buyer_company": "Co", "buyer_name": "Ramesh"}).json()["id"]


def quote(rid, sid, price=10, fr=200, lead=3):
    return client.post(f"/api/rfq-by-token/{tokens_of(rid)[sid]}/quotes", json={"supplier_name": f"Real {sid} Ltd", "pack_price": price, "pack_size": 1, "freight": fr, "lead_days": lead})


def log(rid):
    return client.get(f"/api/rfqs/{rid}/log").json()["events"]


def test_the_log_tells_the_story_in_order_with_aliases_only():
    rid = new_request()
    quote(rid, "A"); quote(rid, "B", 11, 50)
    client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, 'B')}/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": alias(rid, "B"), "reason": "cheapest", "approver": "Ramesh"})
    kinds = [e["kind"] for e in log(rid)]
    assert kinds[0] == "created" and "sellers_notified" in kinds and kinds.count("quote") == 2
    assert kinds.index("reveal") < kinds.index("decision") and kinds[-1] == "decision"
    text = " ".join(e["text"] for e in log(rid))
    assert "Seller 1" in text and "Seller 2" in text
    assert "Real A Ltd" not in text and "Real B Ltd" not in text and "Bolt Express" not in text.split("Revealed")[0]


def test_a_revision_and_a_target_are_logged_for_the_buyer():
    rid = new_request()
    quote(rid, "A"); quote(rid, "A", 10, 150)
    client.post(f"/api/rfqs/{rid}/targets", json={"supplier_id": alias(rid, "A"), "cut_needed": 10, "target_freight": 100, "message": "match", "sent_by": "Ramesh"})
    texts = [e["text"] for e in log(rid)]
    assert any("revised" in t.lower() for t in texts) and any("match a better offer" in t.lower() for t in texts)


def test_only_the_owner_reads_the_log():
    rid = new_request()
    as_user("someone-else")
    assert client.get(f"/api/rfqs/{rid}/log").status_code == 404


def test_the_owner_can_edit_an_open_request_and_each_change_is_logged():
    rid = new_request()
    quote(rid, "A")
    r = client.patch(f"/api/rfqs/{rid}", json={"qty": 150, "need_in_days": 7, "note": "urgent", "priority_mode": "fastest"})
    assert r.status_code == 200
    rfq = store.rfqs[rid]
    assert (rfq.qty, rfq.need_in_days, rfq.note, rfq.priority_mode) == (150, 7, "urgent", "fastest")
    edit = next(e for e in log(rid) if e["kind"] == "edited")
    assert "100" in edit["text"] and "150" in edit["text"]
    notes = store.notifications[tokens_of(rid)["A"] and "A"]
    assert any(n.rfq_id == rid and n.reminder for n in notes)                  # the matched seller is told to check their quote


@pytest.mark.parametrize("body", [{"qty": -1}, {"qty": 0}, {"need_in_days": 0}, {"qty": 10**9}, {"priority_mode": "nonsense"}, {}])
def test_bad_or_empty_edits_are_refused(body):
    rid = new_request()
    assert client.patch(f"/api/rfqs/{rid}", json=body).status_code == 422


def test_a_decided_request_cannot_be_edited_and_strangers_cannot_edit():
    rid = new_request()
    quote(rid, "A")
    client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, 'A')}/reveal")
    other = new_request()
    as_user("stranger")
    assert client.patch(f"/api/rfqs/{other}", json={"qty": 5}).status_code == 404
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="u_test", email="buyer@test.dev")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": alias(rid, "A"), "reason": "r", "approver": "a"})
    assert client.patch(f"/api/rfqs/{rid}", json={"qty": 5}).status_code == 409


def test_order_history_lists_decided_orders_with_the_seller_who_receives_them():
    rid = new_request(qty=100)
    quote(rid, "A", 10, 200); quote(rid, "B", 11, 50)
    client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, 'B')}/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": alias(rid, "B"), "reason": "cheapest", "approver": "Ramesh"})
    orders = client.get("/api/orders").json()["orders"]
    o = next(x for x in orders if x["rfq_id"] == rid)
    assert o["item"] == "M10 bolt" and o["qty"] == 100 and o["total_landed"] == 1150 and o["approver"] == "Ramesh"
    assert o["receivers"][0]["business_name"] and o["receivers"][0]["alias"] == alias(rid, "B")
    assert o["split"] is False and "decided_at" in o


def test_a_buyer_sees_only_their_own_orders():
    rid = new_request()
    quote(rid, "A")
    client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, 'A')}/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": alias(rid, "A"), "reason": "r", "approver": "a"})
    as_user("another-buyer")
    assert all(o["rfq_id"] != rid for o in client.get("/api/orders").json()["orders"])


def test_a_seller_sees_the_orders_they_received_with_the_buyer_contact_and_their_amount():
    rid = new_request(qty=100)
    quote(rid, "A", 10, 200); quote(rid, "B", 11, 50)
    client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, 'B')}/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": alias(rid, "B"), "reason": "cheapest", "approver": "Ramesh"})
    won = client.get("/api/supplier/B/orders").json()["orders"]
    mine = next(o for o in won if o["rfq_id"] == rid)
    assert mine["total"] == 1150 and mine["buyer"]["name"] == "Test User" and mine["qty"] == 100
    assert all(o["rfq_id"] != rid for o in client.get("/api/supplier/A/orders").json()["orders"])      # the losing seller received nothing
