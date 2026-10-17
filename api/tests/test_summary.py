from fastapi.testclient import TestClient

from app import summary
from app.main import app

client = TestClient(app)


def _decided_request(winner="B", qty=100):
    res = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "Buyer"}).json()
    t = res["supplier_tokens"]
    for sid, price, freight in (("A", 10, 200), ("B", 11, 50)):
        client.post(f"/api/rfq-by-token/{t[sid]}/quotes", json={
            "supplier_name": f"Supplier {sid}", "pack_price": price, "pack_size": 1, "freight": freight, "lead_days": 3})
    return res["id"]


def _decide(rid, winner="B"):
    return client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": winner, "reason": "Lowest landed", "approver": "Ramesh"})


def test_summary_before_decision_has_no_savings():
    s = client.get(f"/api/rfqs/{_decided_request()}/summary").json()
    assert s["decided"] is False and s["savings"] is None
    assert s["engine_winner"]["supplier"] == "Supplier B"


def test_savings_vs_spreadsheet_pick_and_running_total():
    before = client.get("/api/savings").json()
    rid = _decided_request()
    _decide(rid)
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    sv = s["savings"]
    assert (sv["spreadsheet_pick"], sv["spreadsheet_landed"]) == ("Supplier A", 1200)
    assert (sv["crossover_pick"], sv["crossover_landed"], sv["difference"]) == ("Supplier B", 1150, 50)
    assert sv["label"] == "on demo data"
    after = client.get("/api/savings").json()
    assert after["total"] - before["total"] == 50 and after["decided_count"] == before["decided_count"] + 1
    assert after["label"] == "on demo data"


def test_human_override_is_reported_not_hidden():
    rid = _decided_request()
    _decide(rid, winner="A")                       # the person chose the dearer supplier
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    assert s["overrode_engine"] is True and s["pick"]["supplier"] == "Supplier A"
    assert s["savings"]["difference"] == 0         # no saving claimed for a spreadsheet-equal pick


def test_fingerprint_is_stable_and_changes_with_inputs():
    rid = _decided_request()
    a = client.get(f"/api/rfqs/{rid}/summary").json()["fingerprint"]
    assert a == client.get(f"/api/rfqs/{rid}/summary").json()["fingerprint"]
    tok = client.get(f"/api/rfqs/{rid}").json()["rfq"]["supplier_tokens"]["B"]
    client.post(f"/api/rfq-by-token/{tok}/quotes", json={"supplier_name": "Supplier B", "pack_price": 11,
                                                         "pack_size": 1, "freight": 40, "lead_days": 3})
    assert client.get(f"/api/rfqs/{rid}/summary").json()["fingerprint"] != a


def test_reasons_come_from_engine_when_no_ai():
    rid = _decided_request()
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    assert s["explainer"]["source"] == "engine"
    assert any("Supplier B wins" in r and "₹1,150" in r for r in s["reasons"])
    assert any("Supplier A is ₹50 higher" in r for r in s["reasons"])


def test_explainer_keeps_faithful_text_and_discards_bad(monkeypatch):
    rid = _decided_request()
    say = lambda t: monkeypatch.setattr(summary, "structured_call", lambda *a, **k: {"text": t})

    say("Supplier B wins at ₹1,150 landed, ₹50 below Supplier A, with delivery in 3 days.")
    ok = client.get(f"/api/rfqs/{rid}/summary").json()["explainer"]
    assert ok["source"] == "ai"

    for bad, why in [
        ("Supplier B wins at ₹1,100 landed.", "number"),
        ("Supplier A is the better choice at ₹1,200.", "winner"),
        ("Supplier B wins, and we guarantee a 5% rebate.", "promise"),
    ]:
        say(bad)
        out = client.get(f"/api/rfqs/{rid}/summary").json()["explainer"]
        assert out["source"] == "engine" and out["discarded_reason"], why
    # the AI never changes who won
    _decide(rid)
    assert client.get(f"/api/rfqs/{rid}/summary").json()["pick"]["supplier"] == "Supplier B"


def test_share_link_needs_a_decision_and_is_unguessable_and_stable():
    rid = _decided_request()
    assert client.post(f"/api/rfqs/{rid}/share").status_code == 409
    _decide(rid)
    link = client.post(f"/api/rfqs/{rid}/share").json()
    assert link["token"].startswith("shr_") and len(link["token"]) > 30 and link["url"] == f"/share/{link['token']}"
    assert client.post(f"/api/rfqs/{rid}/share").json()["token"] == link["token"]
    shared = client.get(f"/api/share/{link['token']}").json()
    assert shared["rfq"]["id"] == rid and shared["decided"] is True
    assert client.get("/api/share/shr_nope").status_code == 404


def test_explainer_is_cached_for_the_same_inputs(monkeypatch):
    rid = _decided_request()
    calls = []
    monkeypatch.setattr(summary, "structured_call",
                        lambda *a, **k: calls.append(1) or {"text": "Supplier B wins at ₹1,150 landed."})
    for _ in range(3):
        client.get(f"/api/rfqs/{rid}/summary")
    assert len(calls) == 1
