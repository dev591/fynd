"""Tax bases differ: compare everything on one basis. The brief's worked example, as tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app, store
from app.tax import normalise_price
from tests.helpers import alias, tokens_of

client = TestClient(app)


def test_the_briefs_worked_example_claimable_gst():
    """10 + 18% GST versus 11.80 GST-inclusive: the same real price once GST is claimable."""
    a, a_note = normalise_price(10.0, 18.0, False, claimable=True)
    b, b_note = normalise_price(11.80, 18.0, True, claimable=True)
    assert a == pytest.approx(10.0) and b == pytest.approx(10.0)
    assert a_note == b_note == "stated"


def test_the_briefs_worked_example_gst_not_claimable():
    a, _ = normalise_price(10.0, 18.0, False, claimable=False)
    b, _ = normalise_price(11.80, 18.0, True, claimable=False)
    assert a == pytest.approx(11.80) and b == pytest.approx(11.80)        # 1,180 per 100 units for each


def test_no_stated_basis_is_treated_as_exclusive_and_flagged():
    for rate, inc in [(None, None), (18.0, None), (None, True)]:
        price, note = normalise_price(10.0, rate, inc, claimable=True)
        assert price == 10.0 and note == "assumed_exclusive"
        price, note = normalise_price(10.0, rate, inc, claimable=False)
        assert price == 10.0 and note == "assumed_exclusive"               # we do not invent a tax rate


def test_zero_and_odd_rates_are_safe():
    assert normalise_price(10.0, 0.0, True, claimable=True)[0] == 10.0
    assert normalise_price(10.0, 0.0, False, claimable=False)[0] == 10.0
    assert normalise_price(10.0, 28.0, True, claimable=True)[0] == pytest.approx(10 / 1.28)
    with pytest.raises(ValueError):
        normalise_price(10.0, -5.0, True, claimable=True)


def _scene(claimable):
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "Co",
                                         "buyer_name": "B", "gst_claimable": claimable}).json()["id"]
    t = tokens_of(rid)
    base = {"supplier_name": "x", "pack_size": 1, "freight": 0, "lead_days": 3}
    client.post(f"/api/rfq-by-token/{t['A']}/quotes", json={**base, "pack_price": 10.0, "tax_rate": 18, "price_includes_tax": False})
    client.post(f"/api/rfq-by-token/{t['B']}/quotes", json={**base, "pack_price": 11.80, "tax_rate": 18, "price_includes_tax": True})
    return rid


def test_two_sellers_with_different_tax_bases_tie_on_the_same_real_price():
    rid = _scene(claimable=True)
    ev = client.get(f"/api/rfqs/{rid}").json()["evaluation"]
    landed = {r["quote_id"]: r["landed"] for r in ev["rows"]}
    assert landed["Seller 1"] == pytest.approx(1000) and landed["Seller 2"] == pytest.approx(1000)
    assert ev["tie"] is True                                                # a sheet would have said 10 beats 11.80


def test_not_claimable_compares_inclusive_prices():
    rid = _scene(claimable=False)
    ev = client.get(f"/api/rfqs/{rid}").json()["evaluation"]
    assert [r["landed"] for r in ev["rows"]] == [pytest.approx(1180), pytest.approx(1180)]


def test_the_quote_shows_what_was_quoted_and_what_it_was_compared_as():
    rid = _scene(claimable=True)
    q = client.get(f"/api/rfqs/{rid}").json()["quotes"]["Seller 2"][0]
    assert q["pack_price"] == 11.80 and q["tax_rate"] == 18 and q["price_includes_tax"] is True
    assert q["compare_price"] == pytest.approx(10.0) and q["tax_basis"] == "stated"


def test_an_unstated_basis_is_flagged_on_the_quote_and_in_the_evidence():
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    client.post(f"/api/rfq-by-token/{tokens_of(rid)['A']}/quotes", json={
        "supplier_name": "x", "pack_price": 10, "pack_size": 1, "freight": 200, "lead_days": 3})
    q = client.get(f"/api/rfqs/{rid}").json()["quotes"]["Seller 1"][0]
    assert q["tax_basis"] == "assumed_exclusive" and q["compare_price"] == 10
    client.post(f"/api/rfqs/{rid}/quotes/Seller 1/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 1", "reason": "x", "approver": "Me"})
    ev = {f["label"]: f for f in client.get(f"/api/rfqs/{rid}/summary").json()["evidence"]}
    assert ev["Tax basis"]["tag"] == "assumed" and "did not state" in ev["Tax basis"]["source"].lower()


def test_request_defaults_to_the_buyers_profile_policy():
    from app.auth import AuthUser, get_current_user
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="tax-buyer", email="t@t.test")
    client.post("/api/profile", json={"id": "x", "role": "buyer", "full_name": "T", "email": "t@t.test", "phone": "9820144556",
                "company": "Co", "business_type": "manufacturer", "state": "Telangana", "city": "Hyderabad",
                "buyer": {"gst_claimable": False, "spend_band": "x", "need_by_buffer_days": 5}})
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 1, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    assert store.rfqs[rid].gst_claimable is False
    rid2 = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 1, "need_in_days": 5, "buyer_company": "c",
                                          "buyer_name": "b", "gst_claimable": True}).json()["id"]
    assert store.rfqs[rid2].gst_claimable is True                              # an explicit choice on the request wins
