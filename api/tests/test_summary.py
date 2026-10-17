import json

import pytest
from fastapi.testclient import TestClient

from app import summary
from app.main import app
from tests.helpers import alias, tokens_of

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_explainer_cache():
    summary._explain_cache.clear()
    yield
    summary._explain_cache.clear()


def _decided_request(winner="B", qty=100):
    res = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "Buyer"}).json()
    t = tokens_of(res["id"])
    for sid, price, freight in (("A", 10, 200), ("B", 11, 50)):
        client.post(f"/api/rfq-by-token/{t[sid]}/quotes", json={
            "supplier_name": f"Supplier {sid}", "pack_price": price, "pack_size": 1, "freight": freight, "lead_days": 3})
    return res["id"]


def _decide(rid, winner="B"):
    """Winner is the real supplier id the test cares about. The buyer reveals them, then saves the order."""
    winner = alias(rid, winner)
    client.post(f"/api/rfqs/{rid}/quotes/{winner}/reveal")
    return client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": winner, "reason": "Lowest landed", "approver": "Ramesh"})


def test_summary_before_decision_has_no_savings():
    s = client.get(f"/api/rfqs/{_decided_request()}/summary").json()
    assert s["decided"] is False and s["savings"] is None
    assert s["engine_winner"]["supplier"] == "Seller 2"


def test_savings_vs_spreadsheet_pick_and_running_total():
    before = client.get("/api/savings").json()
    rid = _decided_request()
    _decide(rid)
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    sv = s["savings"]
    assert (sv["spreadsheet_pick"], sv["spreadsheet_landed"]) == ("Seller 1", 1200)
    assert (sv["crossover_pick"], sv["crossover_landed"], sv["difference"]) == ("Seller 2", 1150, 50)
    assert sv["label"] == "on demo data"
    after = client.get("/api/savings").json()
    assert after["total"] - before["total"] == 50 and after["decided_count"] == before["decided_count"] + 1
    assert after["label"] == "on demo data"


def test_human_override_is_reported_not_hidden():
    rid = _decided_request()
    _decide(rid, winner="A")                       # the person chose the dearer supplier
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    assert s["overrode_engine"] is True and s["pick"]["supplier"] == "Seller 1"
    assert s["savings"]["difference"] == 0         # no saving claimed for a spreadsheet-equal pick


def test_fingerprint_is_stable_and_changes_with_inputs():
    rid = _decided_request()
    a = client.get(f"/api/rfqs/{rid}/summary").json()["fingerprint"]
    assert a == client.get(f"/api/rfqs/{rid}/summary").json()["fingerprint"]
    tok = tokens_of(rid)["B"]
    client.post(f"/api/rfq-by-token/{tok}/quotes", json={"supplier_name": "Supplier B", "pack_price": 11,
                                                         "pack_size": 1, "freight": 40, "lead_days": 3})
    assert client.get(f"/api/rfqs/{rid}/summary").json()["fingerprint"] != a


def test_reasons_come_from_engine_when_no_ai():
    rid = _decided_request()
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    assert s["explainer"]["source"] == "engine"
    assert any("Seller 2 wins" in r and "₹1,150" in r for r in s["reasons"])
    assert any("Seller 1 is ₹50 higher" in r for r in s["reasons"])


def test_explainer_keeps_faithful_text_and_discards_bad(monkeypatch):
    rid = _decided_request()
    def say(t):
        summary._explain_cache.clear()      # new model answer on identical inputs: bypass the cache on purpose
        monkeypatch.setattr(summary, "structured_call", lambda *a, **k: {"text": t})

    say("Seller 2 wins at ₹1,150 landed, ₹50 below Seller 1, with delivery in 3 days.")
    ok = client.get(f"/api/rfqs/{rid}/summary").json()["explainer"]
    assert ok["source"] == "ai"

    for bad, why in [
        ("Seller 2 wins at ₹1,100 landed.", "number"),
        ("Seller 1 is the better choice at ₹1,200.", "winner"),
        ("Seller 2 wins, and we guarantee a 5% rebate.", "promise"),
    ]:
        say(bad)
        out = client.get(f"/api/rfqs/{rid}/summary").json()["explainer"]
        assert out["source"] == "engine" and out["discarded_reason"], why
    # the AI never changes who won
    _decide(rid)
    assert client.get(f"/api/rfqs/{rid}/summary").json()["pick"]["supplier"] == "Seller 2"


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
                        lambda *a, **k: calls.append(1) or {"text": "Seller 2 wins at ₹1,150 landed."})
    for _ in range(3):
        client.get(f"/api/rfqs/{rid}/summary")
    assert len(calls) == 1


def test_pack_rounding_is_visible_in_rupees_and_per_usable_unit():
    """Need 100, packs of 12 at 120, freight 0: 9 packs, 108 units, 8 extra, 80 rupees tied up in the extras."""
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    client.post(f"/api/rfq-by-token/{tokens_of(rid)['A']}/quotes", json={
        "supplier_name": "x", "pack_price": 120, "pack_size": 12, "freight": 0, "lead_days": 3})
    row = client.get(f"/api/rfqs/{rid}/summary").json()["rows"][0]
    assert (row["packs"], row["units"], row["overbuy"], row["landed"]) == (9, 108, 8, 1080)
    assert row["cash_tied_up"] == 80 and row["pack_price"] == 120 and row["pack_size"] == 12
    assert row["cost_per_usable_unit"] == 10.8                                   # 1080 over the 100 units actually needed


def test_evidence_facts_are_tagged_observed_assumed_or_derived():
    rid = _decided_request()
    _decide(rid)
    ev = client.get(f"/api/rfqs/{rid}/summary").json()["evidence"]
    tags = {f["label"]: f["tag"] for f in ev}
    assert tags["Pack price"] == "observed" and tags["Freight"] == "observed" and tags["Lead time"] == "observed"
    assert tags["Quantity needed"] == "observed" and tags["Need-by"] == "observed"
    assert tags["Landed cost"] == "derived" and tags["Packs ordered"] == "derived" and tags["Cash tied up in extra units"] == "derived"
    assert tags["Tax basis"] == "assumed" and tags["Balanced-mode tolerance"] == "assumed"
    assert all(f["tag"] in ("observed", "assumed", "derived") and f["source"] for f in ev)
    landed = next(f for f in ev if f["label"] == "Landed cost")
    assert landed["value"] == "₹1,150" and "packs" in landed["source"].lower()
    # nothing in the evidence names a seller
    assert "Bolt Express" not in json.dumps(ev) and "Seller" not in json.dumps([f["value"] for f in ev])
