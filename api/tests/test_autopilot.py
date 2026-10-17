import pytest
from fastapi.testclient import TestClient

from app.main import app, store
from tests.helpers import tokens_of

client = TestClient(app)


@pytest.fixture(autouse=True)
def _autopilot_off_after():
    yield
    store.autopilot.clear()


def _request(qty=100, need=5, item="M10 bolt"):
    res = client.post("/api/rfqs", json={"item": item, "qty": qty, "need_in_days": need,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()
    res["supplier_tokens"] = tokens_of(res["id"])        # test-only peek
    return res


def _quotes(rid):
    """The buyer's view is keyed by alias; tests think in seller ids, so translate back."""
    by_alias = client.get(f"/api/rfqs/{rid}").json()["quotes"]
    back = {a: sid for sid, a in store.aliases.get(rid, {}).items()}
    return {back[a]: v for a, v in by_alias.items()}


def test_autopilot_is_off_by_default_and_sends_nothing():
    assert client.get("/api/supplier/A/autopilot").json() == {"enabled": False}
    assert _quotes(_request()["id"]) == {}


def test_toggle_persists_and_unknown_seller_404():
    assert client.put("/api/supplier/A/autopilot", json={"enabled": True}).json() == {"enabled": True}
    assert client.get("/api/supplier/A/autopilot").json()["enabled"] is True
    assert client.put("/api/supplier/A/autopilot", json={"enabled": False}).json()["enabled"] is False
    assert client.put("/api/supplier/ZZ/autopilot", json={"enabled": True}).status_code == 404


def test_autopilot_quotes_from_catalog_and_is_marked_auto():
    client.put("/api/supplier/A/autopilot", json={"enabled": True})
    rid = _request()["id"]
    q = _quotes(rid)["A"][0]
    assert q["origin"] == "auto"
    assert (q["pack_price"], q["pack_size"], q["freight"], q["lead_days"], q["landed_cost"]) == (10, 1, 200, 3, 1200)
    assert "₹1,200" in q["notes"]                    # template wording, every number from data
    assert set(_quotes(rid)) == {"A"}                 # sellers without autopilot stay silent
    # the buyer's compare picks it up like any other quote
    assert client.get(f"/api/rfqs/{rid}").json()["evaluation"]["winner"]["quote_id"] == "Seller 1"


def test_autopilot_leaves_anything_but_a_clean_yes_to_a_person():
    for sid in ("C", "D", "E"):
        client.put(f"/api/supplier/{sid}/autopilot", json={"enabled": True})
    client.put("/api/supplier/B/autopilot", json={"enabled": True})
    rid = _request(qty=100, need=5)["id"]
    quoted = _quotes(rid)
    assert "C" not in quoted       # lead 7 > 5: partly
    assert "D" not in quoted       # out of stock: no
    assert "B" in quoted and "E" in quoted     # stock 150 / 400, leads fit
    # bigger than B's stock: partly, so B stays silent
    assert "B" not in _quotes(_request(qty=200, need=5)["id"])


def test_autopilot_never_answers_a_target_or_revises():
    client.put("/api/supplier/A/autopilot", json={"enabled": True})
    res = _request()
    rid, tok = res["id"], res["supplier_tokens"]["A"]
    assert len(_quotes(rid)["A"]) == 1
    client.post(f"/api/rfqs/{rid}/targets", json={"supplier_id": "Seller 1", "cut_needed": 51, "target_freight": 149,
                                                  "concession_type": "freight", "sent_by": "Ramesh Sharma"})
    assert store.has_pending_target(tok) is True
    rfq = store.get_rfq(rid)
    assert store.maybe_autopilot_quote(rfq, "A") is None        # already quoted, and a target is waiting
    assert len(_quotes(rid)["A"]) == 1                          # still one version: nothing revised it
    assert client.get(f"/api/rfq-by-token/{tok}/quotes/mine").json()["target"]["status"] == "pending"


def test_autopilot_does_not_quote_when_a_target_is_pending_even_on_a_fresh_seller():
    client.put("/api/supplier/E/autopilot", json={"enabled": True})
    res = _request()
    rid = res["id"]
    # simulate a target waiting before any quote exists
    from app.models import NegotiationTarget
    store.targets[rid]["E"] = NegotiationTarget(id="t", supplier_id="E", message="m", cut_needed=1,
                                                concession_type="freight", sent_at="now", sent_by="x")
    store.quotes[rid].pop("E", None)
    assert store.maybe_autopilot_quote(store.get_rfq(rid), "E") is None


def test_client_cannot_claim_auto_origin():
    res = _request()
    tok = res["supplier_tokens"]["A"]
    sent = client.post(f"/api/rfq-by-token/{tok}/quotes", json={
        "pack_price": 10, "pack_size": 1, "freight": 200, "lead_days": 3, "origin": "auto"}).json()
    assert sent["origin"] == "manual"


def test_one_pager_lists_auto_quotes():
    client.put("/api/supplier/A/autopilot", json={"enabled": True})
    rid = _request()["id"]
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    assert s["auto_quotes"] == ["Seller 1"]
