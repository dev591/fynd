from fastapi.testclient import TestClient
from app.main import app
from tests.helpers import alias, quote, tokens_of

client = TestClient(app)


def new_request(item="M10 bolt", qty=100, need=5, **extra):
    """A request owned by the test user. Returns the create response."""
    return client.post("/api/rfqs", json={"item": item, "qty": qty, "need_in_days": need,
                                          "buyer_company": "Co", "buyer_name": "Buyer", **extra}).json()


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_case_checks_endpoint():
    res = client.get("/api/case-checks")
    assert res.status_code == 200
    data = res.json()
    assert data["score"] == 25
    assert data["all_passed"] is True


def test_rfq_lifecycle_and_sealed_bids():
    # 1. Buyer creates RFQ
    rfq_payload = {
        "item": "M10 bolt",
        "qty": 100,
        "need_in_days": 5,
        "buyer_company": "FanWorks Precision Manufacturing",
        "buyer_name": "Ramesh Sharma",
        "buyer_city": "Pune",
        "buyer_state": "Maharashtra",
        "note": "Need delivery by Friday.",
    }
    create_res = client.post("/api/rfqs", json=rfq_payload)
    assert create_res.status_code == 200
    rfq_data = create_res.json()
    rfq_id = rfq_data["id"]
    token = tokens_of(rfq_id)["A"]
    assert "token" not in rfq_data and "supplier_tokens" not in rfq_data     # invite tokens never go to the buyer

    # 2. Supplier opens token link: sealed bids (no competitor info)
    supplier_view = client.get(f"/api/rfq-by-token/{token}")
    assert supplier_view.status_code == 200
    sv = supplier_view.json()
    assert sv["item"] == "M10 bolt"
    assert "quotes" not in sv  # sealed bid!
    assert "competitors" not in sv

    # 3. Supplier submits quote v1
    q1_payload = {
        "supplier_name": "Supplier Suresh",
        "pack_price": 10.0,
        "pack_size": 1,
        "freight": 200.0,
        "lead_days": 3,
        "moq": 1,
        "notes": "v1 initial quote",
    }
    q1_res = client.post(f"/api/rfq-by-token/{token}/quotes", json=q1_payload)
    assert q1_res.status_code == 200
    q1 = q1_res.json()
    assert q1["version"] == 1
    assert q1["landed_cost"] == 1200.0

    # 4. Buyer checks RFQ details: see supplier v1
    buyer_view = client.get(f"/api/rfqs/{rfq_id}")
    assert buyer_view.status_code == 200
    bv = buyer_view.json()
    seller = alias(rfq_id, "A")
    assert seller == "Seller 1" and seller in bv["quotes"]

    # 5. Buyer sends target concession
    target_payload = {
        "supplier_id": seller,
        "cut_needed": 51.0,
        "target_freight": 149.0,
        "concession_type": "freight",
        "message": "Cut freight to ₹149 to win this order.",
        "sent_by": "Ramesh Sharma",
    }
    target_res = client.post(f"/api/rfqs/{rfq_id}/targets", json=target_payload)
    assert target_res.status_code == 200
    assert target_res.json()["status"] == "pending"

    # 6. Supplier checks /quotes/mine: sees pending target
    mine_res = client.get(f"/api/rfq-by-token/{token}/quotes/mine")
    assert mine_res.status_code == 200
    mine_data = mine_res.json()
    assert len(mine_data["quotes"]) == 1
    assert mine_data["target"] is not None
    assert mine_data["target"]["target_freight"] == 149.0

    # 7. Supplier submits revised quote v2 matching target
    q2_payload = {
        "supplier_name": "Supplier Suresh",
        "pack_price": 10.0,
        "pack_size": 1,
        "freight": 149.0,
        "lead_days": 3,
        "moq": 1,
        "notes": "v2 matched buyer target freight",
    }
    q2_res = client.post(f"/api/rfq-by-token/{token}/quotes", json=q2_payload)
    assert q2_res.status_code == 200
    q2 = q2_res.json()
    assert q2["version"] == 2
    assert q2["landed_cost"] == 1149.0

    # Target should now be marked accepted
    mine_after = client.get(f"/api/rfq-by-token/{token}/quotes/mine").json()
    assert mine_after["target"]["status"] == "accepted"

    # 8. Buyer saves decision and closes RFQ
    decision_payload = {
        "winner_id": seller,
        "reason": "Supplier A cut freight to ₹149, saving ₹51.",
        "approver": "Ramesh Sharma",
    }
    assert client.post(f"/api/rfqs/{rfq_id}/decision", json=decision_payload).status_code == 409   # not revealed yet
    assert client.post(f"/api/rfqs/{rfq_id}/quotes/{seller}/reveal").status_code == 200
    dec_res = client.post(f"/api/rfqs/{rfq_id}/decision", json=decision_payload)
    assert dec_res.status_code == 200
    assert dec_res.json()["winner_id"] == seller

    # 9. Further quote revisions rejected after decision
    rev_after_lock = client.post(f"/api/rfq-by-token/{token}/quotes", json=q2_payload)
    assert rev_after_lock.status_code == 400


# ─── Tests for new endpoints (Phase 1) ────────────────────────────────────

def test_create_rfq_notifies_several_sellers_without_handing_the_buyer_their_links():
    data = new_request("M8 washer", 500, 7)
    assert data["matched"] >= 2
    assert "supplier_tokens" not in data and "supplier_urls" not in data and "token" not in data
    for sid, tok in tokens_of(data["id"]).items():             # each seller's own link still works
        sv = client.get(f"/api/rfq-by-token/{tok}")
        assert sv.status_code == 200 and sv.json()["item"] == "M8 washer"


def test_supplier_profile_get_and_update():
    # Seed data should have profile for A
    res = client.get("/api/supplier/profile/A")
    assert res.status_code == 200
    assert res.json()["business_name"] == "Bolt Express Industrial Supplies"

    # Update
    res = client.put("/api/supplier/profile/A", json={
        "business_name": "Updated Supplies Co",
        "location_city": "Delhi",
        "location_state": "Delhi",
        "categories": ["fasteners"],
    })
    assert res.status_code == 200
    assert res.json()["business_name"] == "Updated Supplies Co"


def test_supplier_products_crud():
    # List existing
    res = client.get("/api/supplier/products/A")
    assert res.status_code == 200
    assert len(res.json()) >= 2

    # Add
    res = client.post("/api/supplier/products/A", json={
        "name": "M12 Washer",
        "category": "fasteners",
        "pack_price": 5,
        "pack_size": 1,
        "moq": 10,
        "usual_lead_days": 2,
        "unit": "pc",
    })
    assert res.status_code == 201
    prod_id = res.json()["id"]
    assert res.json()["name"] == "M12 Washer"

    # Update
    res = client.put(f"/api/supplier/products/A/{prod_id}", json={
        "name": "M12 Washer (Galvanized)",
        "category": "fasteners",
        "pack_price": 6,
        "pack_size": 1,
        "moq": 10,
        "usual_lead_days": 2,
        "unit": "pc",
    })
    assert res.status_code == 200
    assert res.json()["name"] == "M12 Washer (Galvanized)"

    # Delete
    res = client.delete(f"/api/supplier/products/A/{prod_id}")
    assert res.status_code == 204

    # Verify gone
    res = client.get("/api/supplier/products/A")
    prod_ids = [p["id"] for p in res.json()]
    assert prod_id not in prod_ids


def test_buyer_supplier_profile_clickthrough():
    """Before a reveal the panel shows an alias and what was checked. After, the seller."""
    rid = new_request()["id"]
    quote(client, rid, "A"); quote(client, rid, "B")
    pre = client.get(f"/api/rfqs/{rid}/suppliers/Seller 1").json()
    assert pre["business_name"] == "Seller 1" and pre["revealed"] is False and pre["products"] == []
    assert pre["verification_text"] and pre["location_city"] == ""
    assert client.get(f"/api/rfqs/{rid}/suppliers/Seller 2").status_code == 200
    assert client.get(f"/api/rfqs/{rid}/suppliers/Seller 9").status_code == 404      # not on the request
    assert client.get(f"/api/rfqs/{rid}/suppliers/A").status_code == 404             # real ids are not addresses
    client.post(f"/api/rfqs/{rid}/quotes/Seller 1/reveal")
    post = client.get(f"/api/rfqs/{rid}/suppliers/Seller 1").json()
    from app.main import store
    assert post["revealed"] is True and post["business_name"] == store.supplier_profiles["A"].business_name
    assert len(post["products"]) >= 2 and post["contact"]["phone"]


def test_chat_buyer_and_token_routes():
    """Buyer posts via the request route (by alias), supplier posts via their link."""
    rid = new_request()["id"]
    quote(client, rid, "A")
    tok = tokens_of(rid)["A"]
    res = client.post(f"/api/rfqs/{rid}/threads/Seller 1/messages", json={
        "sender": "buyer", "sender_name": "Ramesh Sharma", "text": "Can you reduce freight?"})
    assert res.status_code == 201 and res.json()["text"] == "Can you reduce freight?"

    res = client.get(f"/api/rfqs/{rid}/threads/Seller 1/messages")
    assert res.status_code == 200 and len(res.json()) >= 1

    res = client.post(f"/api/rfq-by-token/{tok}/messages", json={
        "sender": "supplier", "sender_name": "Supplier A", "text": "We can match the freight."})
    assert res.status_code == 201 and res.json()["text"] == "We can match the freight."

    res = client.get(f"/api/rfq-by-token/{tok}/messages")
    assert res.status_code == 200 and len(res.json()) >= 2
    seller_sees = {m["sender"]: m["sender_name"] for m in res.json()}
    assert seller_sees["buyer"] == "Buyer"                       # the buyer's name waits for the reveal

    # the buyer sees the seller's message under the alias, not the name the seller typed
    buyer_sees = client.get(f"/api/rfqs/{rid}/threads/Seller 1/messages").json()
    assert [m["sender_name"] for m in buyer_sees if m["sender"] == "supplier"] == ["Seller 1"]

    res = client.post("/api/rfq-by-token/invalid_token/messages", json={
        "sender": "supplier", "sender_name": "X", "text": "test"})
    assert res.status_code == 404


def test_send_target_creates_chat_message():
    """Sending a negotiation target should also drop a chat card."""
    rid = new_request()["id"]
    quote(client, rid, "A")
    res = client.post(f"/api/rfqs/{rid}/targets", json={
        "supplier_id": "Seller 1", "cut_needed": 51.0, "target_freight": 149.0,
        "concession_type": "freight", "message": "Cut freight to ₹149 to win.", "sent_by": "Ramesh Sharma"})
    assert res.status_code == 200 and res.json()["supplier_id"] == "Seller 1"
    msgs = client.get(f"/api/rfqs/{rid}/threads/Seller 1/messages").json()
    target_msgs = [m for m in msgs if m.get("target") is not None]
    assert len(target_msgs) >= 1
    assert target_msgs[-1]["target"]["target_freight"] == 149.0 and target_msgs[-1]["target"]["supplier_id"] == "Seller 1"


def test_catalog_stock_caps_quote_in_compare():
    # Seller adds an item with stock 60
    prod = client.post("/api/supplier/products/A", json={
        "name": "M10 bolt", "pack_price": 9.0, "pack_size": 1, "stock": 60,
        "freight": 100.0, "price_breaks": [{"min_qty": 100, "pack_price": 8.0}],
    })
    assert prod.status_code == 201
    assert prod.json()["stock"] == 60

    rfq = new_request()
    token = tokens_of(rfq["id"])["A"]
    # Quote carries the stock as its cap
    client.post(f"/api/rfq-by-token/{token}/quotes", json={
        "pack_price": 9.0, "pack_size": 1, "freight": 100.0, "lead_days": 3, "max_qty": 60,
    })
    ev = client.get(f"/api/rfqs/{rfq['id']}").json()["evaluation"]
    row = next(r for r in ev["rows"] if r["quote_id"] == "Seller 1")
    assert row["status"] == "exception"
    assert row["fill_qty"] == 60


def test_rfq_priority_mode_and_source_roundtrip():
    rfq = client.post("/api/rfqs", json={
        "item": "M10 bolt", "qty": 100, "need_in_days": 5,
        "buyer_company": "Co", "buyer_name": "Buyer",
        "priority_mode": "fastest", "source": "chat",
    }).json()
    assert rfq["rfq"]["priority_mode"] == "fastest" and rfq["rfq"]["source"] == "chat"
    default = client.post("/api/rfqs", json={
        "item": "M10 bolt", "qty": 1, "need_in_days": 5,
        "buyer_company": "Co", "buyer_name": "Buyer",
    }).json()
    assert default["rfq"]["priority_mode"] == "cheapest" and default["rfq"]["source"] == "form"


def test_compare_endpoint_returns_winner_per_mode():
    body = {
        "quotes": [
            {"id": "A", "supplier": "A", "item": "M10 bolt", "pack_price": 10, "pack_size": 1, "freight": 0, "lead_days": 5},
            {"id": "C", "supplier": "C", "item": "M10 bolt", "pack_price": 12, "pack_size": 1, "freight": 0, "lead_days": 1},
        ],
        "need": {"item": "M10 bolt", "qty": 100, "need_in_days": 5},
        "mode": "fastest",
    }
    res = client.post("/api/compare", json=body).json()
    assert res["winner"]["quote_id"] == "C"
    assert res["winners"]["cheapest"]["quote_id"] == "A"


def test_target_must_name_the_person_who_sent_it():
    rid = new_request()["id"]
    quote(client, rid, "A")
    body = {"supplier_id": "Seller 1", "cut_needed": 51.0, "target_freight": 149.0, "concession_type": "freight"}
    assert client.post(f"/api/rfqs/{rid}/targets", json=body).status_code == 422
    assert client.post(f"/api/rfqs/{rid}/targets", json={**body, "sent_by": "  "}).status_code == 422
    ok = client.post(f"/api/rfqs/{rid}/targets", json={**body, "sent_by": "Ramesh Sharma",
                                                       "message": "Edited by a person."})
    assert ok.status_code == 200
    assert ok.json()["sent_by"] == "Ramesh Sharma" and ok.json()["message"] == "Edited by a person."


def test_pending_target_blocks_automation_until_a_human_revises():
    from app.main import store
    res = new_request()
    tok = tokens_of(res["id"])["A"]
    quote(client, res["id"], "A")
    assert store.has_pending_target(tok) is False
    client.post(f"/api/rfqs/{res['id']}/targets", json={
        "supplier_id": "Seller 1", "cut_needed": 10, "target_freight": 150, "concession_type": "freight",
        "sent_by": "Ramesh Sharma"})
    assert store.has_pending_target(tok) is True            # autopilot (task 9) must stay silent here
    client.post(f"/api/rfq-by-token/{tok}/quotes", json={
        "pack_price": 10, "pack_size": 1, "freight": 150, "lead_days": 3})
    assert store.has_pending_target(tok) is False           # the seller's own revision cleared it


def test_decision_record_lists_ai_calls_and_needs_a_named_approver():
    from app.main import store
    res = client.post("/api/rfqs/confirm", json={
        "item": "M10 bolt", "qty": 100, "need_in_days": 5, "source": "chat",
        "buyer_company": "Co", "buyer_name": "B", "priority_mode": "fastest"}).json()
    rid = res["id"]
    quote(client, rid, "A")
    client.post(f"/api/rfqs/{rid}/quotes/Seller 1/reveal")
    store.log_ai("intake_draft", "intk_test", {"text": "x"}, {"draft": {}})
    store.link_ai_log("intk_test", rid)
    d = client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 1", "reason": "Fastest", "approver": "Ramesh Sharma"})
    assert d.status_code == 200
    body = d.json()
    assert body["approver"] == "Ramesh Sharma" and body["mode"] == "fastest" and body["source"] == "chat"
    assert [c["kind"] for c in body["ai_calls"]] == ["intake_draft"]
