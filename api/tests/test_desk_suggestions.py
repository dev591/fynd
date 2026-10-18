"""The desk speaks first: when quotes arrive it works out what the buyer could do for a better outcome. Engine numbers only."""
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app, store
from tests.helpers import tokens_of

client = TestClient(app)


def request(quotes, qty=100, days=5):
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": days, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    t = tokens_of(rid)
    for sid, price, fr, lead in quotes:
        client.post(f"/api/rfq-by-token/{t[sid]}/quotes", json={"supplier_name": sid, "pack_price": price, "pack_size": 1, "freight": fr, "lead_days": lead})
    return rid


def sug(rid):
    return client.get(f"/api/rfqs/{rid}/suggestions").json()["suggestions"]


def by_kind(items, kind):
    return next((s for s in items if s["kind"] == kind), None)


BASE = (("A", 10, 200, 3), ("B", 11, 50, 4), ("C", 12, 0, 2))


def test_ordering_more_is_suggested_when_it_makes_a_cheaper_seller_win_per_unit():
    rid = request(BASE)
    s = by_kind(sug(rid), "quantity")
    assert s and "Seller 1" in s["headline"] and "200" in s["headline"] and s["saving"] is not None
    answer = client.post(f"/api/rfqs/{rid}/ask", json={"question": s["question"]}).json()       # the chip asks the same engine
    assert answer["understood"] and answer["result"]["winner"] == "Seller 1" and answer["scenario"]["qty"] == 200


def test_waiting_a_few_more_days_is_suggested_when_a_late_seller_would_save_money():
    rid = request(BASE + (("D", 8, 0, 7),))
    s = by_kind(sug(rid), "deadline")
    assert s and "2 more days" in s["headline"] and "Seller 4" in s["headline"] and s["saving"] == 350
    answer = client.post(f"/api/rfqs/{rid}/ask", json={"question": s["question"]}).json()
    assert answer["result"]["winner"] == "Seller 4"


def test_a_seller_just_behind_is_flagged_with_the_concession_that_would_win():
    s = by_kind(sug(request(BASE)), "negotiate")
    assert s and s["question"] is None and "₹51" in s["headline"]


def test_the_fastest_option_is_described_with_its_price_of_speed():
    s = by_kind(sug(request(BASE)), "priority")
    assert s and "Seller 3" in s["headline"] and "2 days sooner" in s["headline"] and "₹50 more" in s["headline"]


def test_a_split_that_saves_money_is_suggested():
    rid = request((("A", 10, 0, 3), ("B", 9, 0, 3)), qty=100)
    client.post(f"/api/rfq-by-token/{tokens_of(rid)['B']}/quotes", json={"supplier_name": "B", "pack_price": 9, "pack_size": 1, "freight": 0, "lead_days": 3, "max_qty": 50})
    s = by_kind(sug(rid), "split")
    assert s and "₹50" in s["headline"] and s["question"] is None


def test_few_quotes_or_a_decided_request_get_no_suggestions_and_there_are_at_most_four():
    assert sug(request((("A", 10, 200, 3),))) == []
    rid = request(BASE + (("D", 8, 0, 7),))
    assert len(sug(rid)) <= 4
    store.rfqs[rid].status = "Decided"
    assert sug(rid) == []


def test_suggestions_never_change_the_request_and_only_the_owner_can_see_them():
    rid = request(BASE)
    sug(rid)
    r = store.rfqs[rid]
    assert (r.qty, r.need_in_days, r.status) == (100, 5, "Open")
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="other-buyer", email="o@t.dev")
    assert client.get(f"/api/rfqs/{rid}/suggestions").status_code == 404
