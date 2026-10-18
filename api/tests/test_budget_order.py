"""A buyer's budget and shared order id: stored, shown to the buyer, never shown to a seller."""
from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import tokens_of

client = TestClient(app)
BASE = {"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "Co", "buyer_name": "Buyer"}


def make(**extra):
    r = client.post("/api/rfqs", json={**BASE, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_budget_and_order_id_round_trip():
    r = make(budget=5000, order_id="ord_" + "a1" * 4)
    assert r["rfq"]["budget"] == 5000 and r["rfq"]["order_id"] == "ord_a1a1a1a1"
    listed = {x["id"]: x for x in client.get("/api/rfqs").json()}
    assert listed[r["id"]]["budget"] == 5000 and listed[r["id"]]["order_id"] == "ord_a1a1a1a1"
    detail = client.get(f"/api/rfqs/{r['id']}").json()["rfq"]
    assert detail["budget"] == 5000


def test_budget_is_optional():
    r = make()
    assert r["rfq"]["budget"] is None and r["rfq"]["order_id"] is None


def test_bad_budget_or_order_id_is_refused():
    for bad in ({"budget": 0}, {"budget": -10}, {"order_id": "../x"}, {"order_id": "ord_ZZZ"}):
        assert client.post("/api/rfqs", json={**BASE, **bad}).status_code == 422, bad


def test_seller_never_sees_the_budget():
    r = make(budget=4321, order_id="ord_" + "b2" * 4)
    tok = next(iter(tokens_of(r["id"]).values()))
    seller_view = client.get(f"/api/rfq-by-token/{tok}")
    assert seller_view.status_code == 200
    text = seller_view.text
    assert "budget" not in text and "4321" not in text and "ord_" not in text


def test_confirm_card_carries_budget():
    r = client.post("/api/rfqs/confirm", json={**BASE, "budget": 7500})
    assert r.status_code == 200 and r.json()["rfq"]["budget"] == 7500
