from fastapi.testclient import TestClient

from app.main import app, store
from tests.helpers import tokens_of, quote

client = TestClient(app)


def _rfq():
    return client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                          "buyer_company": "Co", "buyer_name": "B"}).json()["id"]


def test_a_seller_can_decline_and_it_counts_as_a_response():
    rid = _rfq()
    n = len(tokens_of(rid))
    assert client.get(f"/api/rfqs/{rid}/activity").json() == {"notified": n, "viewed": 0, "quoting": 0, "quoted": 0, "declined": 0}
    tok = tokens_of(rid)["D"]                                           # D is out of stock: the natural decliner
    r = client.post(f"/api/rfq-by-token/{tok}/decline", json={"reason": "Out of stock until next week"})
    assert r.status_code == 204
    act = client.get(f"/api/rfqs/{rid}/activity").json()
    assert act["declined"] == 1 and act["quoted"] == 0 and act["viewed"] == 1       # declining means they looked
    inbox = next(x for x in client.get("/api/supplier/D/notifications").json() if x["rfq_id"] == rid)
    assert inbox["status"] == "declined" and inbox["has_quoted"] is False


def test_declining_never_shows_the_sellers_reason_to_the_buyer_or_creates_a_quote():
    rid = _rfq()
    client.post(f"/api/rfq-by-token/{tokens_of(rid)['D']}/decline", json={"reason": "call me on 9123456780"})
    d = client.get(f"/api/rfqs/{rid}").json()
    assert d["quotes"] == {} and "9123456780" not in str(d) and "Out of stock" not in str(d)


def test_a_seller_who_declined_can_still_change_their_mind_and_quote():
    rid = _rfq()
    tok = tokens_of(rid)["B"]
    client.post(f"/api/rfq-by-token/{tok}/decline", json={})
    assert client.get(f"/api/rfqs/{rid}/activity").json()["declined"] == 1
    quote(client, rid, "B", price=11, freight=50)
    act = client.get(f"/api/rfqs/{rid}/activity").json()
    assert act["quoted"] == 1 and act["declined"] == 0                               # now counted as quoted, not declined


def test_decline_needs_a_valid_link_and_an_open_request():
    assert client.post("/api/rfq-by-token/nope/decline", json={}).status_code == 404
    rid = _rfq()
    quote(client, rid, "A")
    client.post(f"/api/rfqs/{rid}/quotes/Seller 1/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 1", "reason": "x", "approver": "Me"})
    assert client.post(f"/api/rfq-by-token/{tokens_of(rid)['B']}/decline", json={}).status_code == 409
