"""The 10am demo path, start to finish, with the model stubbed. If this breaks, the demo breaks."""
from fastapi.testclient import TestClient

from app import intake
from app.main import app, store

client = TestClient(app)


def test_demo_path_end_to_end(monkeypatch):
    # 1. The judge speaks a request. (Model stubbed; the transcript is what the mic would produce.)
    spoken = "I need 100 M10 bolts in 5 days, fastest"
    monkeypatch.setattr(intake, "structured_call", lambda *a, **k: {
        "item": "M10 bolts", "quantity": 100, "need_in_days": 5, "need_by_phrase": None,
        "priority": "fastest", "note": None, "other_items": []})
    draft = client.post("/api/intake/draft", json={"text": spoken}).json()
    assert draft["missing"] == [] and draft["draft"]["item"] == "M10 bolt"

    # 2. Confirm card -> request. Sellers who stock the item are notified (the bells ring).
    d = draft["draft"]
    req = client.post("/api/rfqs/confirm", json={
        "item": d["item"], "qty": d["qty"], "need_in_days": d["need_in_days"],
        "priority_mode": d["priority_mode"], "source": "voice", "buyer_company": "FanWorks",
        "buyer_name": "Ramesh Sharma", "intake_id": draft["request_id"]}).json()
    rid, tok = req["id"], req["supplier_tokens"]
    assert req["matched"] >= 5
    bells = {sid: [n for n in client.get(f"/api/supplier/{sid}/notifications").json() if n["rfq_id"] == rid]
             for sid in tok}
    assert all(len(v) == 1 and v[0]["status"] == "new" for v in bells.values())
    assert bells["D"][0]["verdict"]["can_fulfil"] == "no"        # out of stock: honest verdict

    # 3. Sellers open the link, start quoting, send quotes from their own catalog drafts.
    for sid in ("A", "B"):
        client.get(f"/api/rfq-by-token/{tok[sid]}")
        client.post(f"/api/rfq-by-token/{tok[sid]}/quoting")
        a = client.get(f"/api/rfq-by-token/{tok[sid]}/assist").json()
        dq = a["draft"]
        sent = client.post(f"/api/rfq-by-token/{tok[sid]}/quotes", json={
            "supplier_name": f"Supplier {sid}", "pack_price": dq["pack_price"], "pack_size": dq["pack_size"],
            "freight": dq["freight"], "lead_days": dq["lead_days"], "moq": dq["moq"],
            "max_qty": dq["max_qty"], "notes": a["message"]["text"]})
        assert sent.status_code == 200
    details = client.get(f"/api/rfqs/{rid}").json()
    assert details["activity"]["quoted"] == 2
    ev = details["evaluation"]
    landed = {r["supplier"]: r["landed"] for r in ev["rows"]}
    assert landed["Supplier A"] == 1200

    # 4. Winner with the priority switch: every mode is visible and engine-decided.
    assert set(ev["winners"]) == {"cheapest", "fastest", "balanced"}
    first_winner = ev["winner"]["quote_id"]

    # 5. Buyer reviews and sends a target to the runner-up as a named person.
    runner = "A" if first_winner != "A" else "B"
    gap = ev["winner"]["landed"]
    loser_landed = next(r["landed"] for r in ev["rows"] if r["quote_id"] == runner)
    cut = loser_landed - gap + 1
    freight = next(r["freight"] for r in ev["rows"] if r["quote_id"] == runner) - cut
    t = client.post(f"/api/rfqs/{rid}/targets", json={
        "supplier_id": runner, "cut_needed": cut, "target_freight": freight, "concession_type": "freight",
        "message": "Cut freight to win this order.", "sent_by": "Ramesh Sharma"})
    assert t.status_code == 200 and t.json()["sent_by"] == "Ramesh Sharma"
    assert store.has_pending_target(tok[runner]) is True
    seen = client.get(f"/api/rfq-by-token/{tok[runner]}/quotes/mine").json()
    assert seen["target"]["status"] == "pending"                 # shows on the seller screen

    # 6. The seller revises by hand; the winner flips on the buyer's next poll.
    old = next(r for r in ev["rows"] if r["quote_id"] == runner)
    client.post(f"/api/rfq-by-token/{tok[runner]}/quotes", json={
        "supplier_name": f"Supplier {runner}", "pack_price": old["pack_price"], "pack_size": old["pack_size"],
        "freight": freight, "lead_days": old["lead_days"], "notes": "Revised to your target."})
    flipped = client.get(f"/api/rfqs/{rid}").json()["evaluation"]["winner"]["quote_id"]
    assert flipped == runner and flipped != first_winner
    assert store.has_pending_target(tok[runner]) is False

    # 7. Save the decision (named approver), open the one-pager, create the share link.
    dec = client.post(f"/api/rfqs/{rid}/decision", json={
        "winner_id": flipped, "reason": "Lowest landed after revision", "approver": "Ramesh Sharma"})
    assert dec.status_code == 200
    page = client.get(f"/api/rfqs/{rid}/summary").json()
    assert page["decided"] and page["pick"]["quote_id"] == flipped and page["fingerprint"]
    assert {c["kind"] for c in page["ai_calls"]} >= {"intake_draft", "seller_assist"}
    link = client.post(f"/api/rfqs/{rid}/share").json()
    assert client.get(f"/api/share/{link['token']}").json()["rfq"]["id"] == rid
