from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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
    token = rfq_data["token"]
    assert "token" in rfq_data
    assert "supplier_url" in rfq_data

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
    assert "A" in bv["quotes"] or len(bv["quotes"]) > 0

    # 5. Buyer sends target concession
    target_payload = {
        "supplier_id": "A",
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
        "winner_id": "A",
        "reason": "Supplier A cut freight to ₹149, saving ₹51.",
        "approver": "Ramesh Sharma",
    }
    dec_res = client.post(f"/api/rfqs/{rfq_id}/decision", json=decision_payload)
    assert dec_res.status_code == 200
    assert dec_res.json()["winner_id"] == "A"

    # 9. Further quote revisions rejected after decision
    rev_after_lock = client.post(f"/api/rfq-by-token/{token}/quotes", json=q2_payload)
    assert rev_after_lock.status_code == 400


# ─── Tests for new endpoints (Phase 1) ────────────────────────────────────

def test_create_rfq_returns_multiple_supplier_tokens():
    """New RFQ should return multiple supplier tokens so 2+ suppliers can quote."""
    res = client.post("/api/rfqs", json={
        "item": "M8 washer",
        "qty": 500,
        "need_in_days": 7,
        "buyer_company": "TestCo",
        "buyer_name": "Test Buyer",
    })
    assert res.status_code == 200
    data = res.json()
    assert "supplier_tokens" in data
    assert "supplier_urls" in data
    assert len(data["supplier_tokens"]) >= 2
    # Each token should resolve to a different supplier
    for sid, tok in data["supplier_tokens"].items():
        sv = client.get(f"/api/rfq-by-token/{tok}")
        assert sv.status_code == 200
        assert sv.json()["item"] == "M8 washer"


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
    """Buyer can see supplier profile only if on the request."""
    # Supplier A has a token on the seeded RFQ
    res = client.get("/api/rfqs/rfq_c27_01/suppliers/A")
    assert res.status_code == 200
    assert "business_name" in res.json()
    assert len(res.json()["products"]) >= 2

    # Supplier B should also work (has token on seeded RFQ)
    res = client.get("/api/rfqs/rfq_c27_01/suppliers/B")
    assert res.status_code == 200

    # Supplier not on request → 404
    res = client.get("/api/rfqs/rfq_c27_01/suppliers/Z")
    assert res.status_code == 404


def test_chat_buyer_and_token_routes():
    """Buyer posts via RFQ route, supplier posts via token route."""
    # Buyer posts
    res = client.post("/api/rfqs/rfq_c27_01/threads/A/messages", json={
        "sender": "buyer",
        "sender_name": "Ramesh Sharma",
        "text": "Can you reduce freight?",
    })
    assert res.status_code == 201
    assert res.json()["text"] == "Can you reduce freight?"

    # Get messages (buyer view)
    res = client.get("/api/rfqs/rfq_c27_01/threads/A/messages")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Supplier posts via token
    res = client.post("/api/rfq-by-token/tok_supplier_a/messages", json={
        "sender": "supplier",
        "sender_name": "Supplier A",
        "text": "We can match the freight.",
    })
    assert res.status_code == 201
    assert res.json()["text"] == "We can match the freight."

    # Supplier gets messages via token
    res = client.get("/api/rfq-by-token/tok_supplier_a/messages")
    assert res.status_code == 200
    assert len(res.json()) >= 2

    # Invalid token
    res = client.post("/api/rfq-by-token/invalid_token/messages", json={
        "sender": "supplier",
        "sender_name": "X",
        "text": "test",
    })
    assert res.status_code == 404


def test_send_target_creates_chat_message():
    """Sending a negotiation target should also drop a chat card."""
    # Send target
    res = client.post("/api/rfqs/rfq_c27_01/targets", json={
        "supplier_id": "A",
        "cut_needed": 51.0,
        "target_freight": 149.0,
        "concession_type": "freight",
        "message": "Cut freight to ₹149 to win.",
        "sent_by": "Ramesh Sharma",
    })
    assert res.status_code == 200

    # Check chat has a message with target attached
    res = client.get("/api/rfqs/rfq_c27_01/threads/A/messages")
    msgs = res.json()
    target_msgs = [m for m in msgs if m.get("target") is not None]
    assert len(target_msgs) >= 1
    assert target_msgs[-1]["target"]["target_freight"] == 149.0


def test_catalog_stock_caps_quote_in_compare():
    # Seller adds an item with stock 60
    prod = client.post("/api/supplier/products/A", json={
        "name": "M10 bolt", "pack_price": 9.0, "pack_size": 1, "stock": 60,
        "freight": 100.0, "price_breaks": [{"min_qty": 100, "pack_price": 8.0}],
    })
    assert prod.status_code == 201
    assert prod.json()["stock"] == 60

    rfq = client.post("/api/rfqs", json={
        "item": "M10 bolt", "qty": 100, "need_in_days": 5,
        "buyer_company": "Co", "buyer_name": "Buyer",
    }).json()
    token = rfq["supplier_tokens"]["A"]
    # Quote carries the stock as its cap
    client.post(f"/api/rfq-by-token/{token}/quotes", json={
        "pack_price": 9.0, "pack_size": 1, "freight": 100.0, "lead_days": 3, "max_qty": 60,
    })
    ev = client.get(f"/api/rfqs/{rfq['id']}").json()["evaluation"]
    row = next(r for r in ev["rows"] if r["quote_id"] == "A")
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
    body = {"supplier_id": "A", "cut_needed": 51.0, "target_freight": 149.0, "concession_type": "freight"}
    assert client.post("/api/rfqs/rfq_c27_01/targets", json=body).status_code == 422
    assert client.post("/api/rfqs/rfq_c27_01/targets", json={**body, "sent_by": "  "}).status_code == 422
    ok = client.post("/api/rfqs/rfq_c27_01/targets", json={**body, "sent_by": "Ramesh Sharma",
                                                           "message": "Edited by a person."})
    assert ok.status_code == 200
    assert ok.json()["sent_by"] == "Ramesh Sharma" and ok.json()["message"] == "Edited by a person."


def test_pending_target_blocks_automation_until_a_human_revises():
    from app.main import store
    res = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()
    tok = res["supplier_tokens"]["A"]
    assert store.has_pending_target(tok) is False
    client.post(f"/api/rfqs/{res['id']}/targets", json={
        "supplier_id": "A", "cut_needed": 10, "target_freight": 150, "concession_type": "freight",
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
    store.log_ai("intake_draft", "intk_test", {"text": "x"}, {"draft": {}})
    store.link_ai_log("intk_test", rid)
    d = client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "A", "reason": "Fastest", "approver": "Ramesh Sharma"})
    assert d.status_code == 200
    body = d.json()
    assert body["approver"] == "Ramesh Sharma" and body["mode"] == "fastest" and body["source"] == "chat"
    assert [c["kind"] for c in body["ai_calls"]] == ["intake_draft"]
