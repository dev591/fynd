import pytest
from fastapi.testclient import TestClient

from app.engine import evaluate, order
from app.main import app
from app.models import Need, Quote
from tests.helpers import tokens_of

client = TestClient(app)


def q(price=10, size=1, freight=200, free_above=None, **kw):
    return Quote(id=kw.pop("id", "x"), supplier="x", item="M10 bolt", pack_price=price, pack_size=size, freight=freight,
                 lead_days=3, free_freight_above=free_above, **kw)


def test_without_a_threshold_nothing_changes():
    o = order(q(), 100)
    assert (o.landed, o.freight) == (1200, 200)


@pytest.mark.parametrize("qty,landed,freight", [(99, 990 + 200, 200), (100, 1000, 0), (150, 1500, 0)])
def test_goods_value_at_or_above_the_threshold_waives_freight(qty, landed, freight):
    o = order(q(free_above=1000), qty)
    assert (o.landed, o.freight) == (landed, freight)


def test_pack_rounding_can_cross_the_threshold():
    o = order(q(price=95, size=10, freight=300, free_above=1000), 100)          # 10 packs x 95 = 950: just under
    assert o.freight == 300
    o2 = order(q(price=95, size=10, freight=300, free_above=1000), 110)         # 11 packs x 95 = 1045
    assert (o2.freight, o2.landed) == (0, 1045)


def test_the_waived_freight_can_flip_the_winner_and_the_row_reports_the_applied_freight():
    flat = q(id="A", price=10, freight=200)
    free = q(id="B", price=11, freight=150, free_above=1000)
    small = evaluate([flat, free], Need(item="M10 bolt", qty=50, need_in_days=5))
    big = evaluate([flat, free], Need(item="M10 bolt", qty=100, need_in_days=5))
    assert small.winner.quote_id == "A" and {r.quote_id: r.freight for r in small.rows}["B"] == 150
    assert big.winner.quote_id == "B" and big.winner.landed == 1100 and big.winner.freight == 0


def _rfq(qty):
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": 5, "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    return tokens_of(rid)


def test_the_threshold_follows_the_same_gst_basis_as_the_price():
    t = _rfq(100)
    body = {"supplier_name": "x", "pack_price": 11.8, "pack_size": 1, "freight": 150, "lead_days": 3, "tax_rate": 18,
            "price_includes_tax": True, "free_freight_above": 1180}               # 1,180 of GST-inclusive goods = 1,000 ex-GST
    v = client.post(f"/api/rfq-by-token/{t['A']}/quotes", json=body).json()
    assert v["free_freight_above"] == 1180 and v["compare_free_freight_above"] == pytest.approx(1000)
    assert v["landed_cost"] == 1000                                              # 100 x 10.00 ex-GST, delivery free


def test_a_quote_without_a_threshold_is_unchanged_and_bad_values_are_refused():
    t = _rfq(100)
    v = client.post(f"/api/rfq-by-token/{t['A']}/quotes", json={"supplier_name": "x", "pack_price": 10, "pack_size": 1, "freight": 200, "lead_days": 3}).json()
    assert v["landed_cost"] == 1200 and v["free_freight_above"] is None
    for bad in (-5, 0):
        r = client.post(f"/api/rfq-by-token/{t['A']}/quotes", json={"supplier_name": "x", "pack_price": 10, "pack_size": 1, "freight": 200, "lead_days": 3, "free_freight_above": bad})
        assert r.status_code == 422


def test_the_catalog_draft_carries_the_threshold():
    from app.matching import draft_quote
    from app.models import RFQ, SupplierProduct
    prod = SupplierProduct(id="p", name="M10 bolt", pack_price=10, pack_size=1, usual_lead_days=3, freight=150, free_freight_above=2000)
    rfq = RFQ(id="r", token="t", item="M10 bolt", qty=100, need_in_days=5, buyer_company="c", buyer_name="b", buyer_city="", buyer_state="",
              created_at="", status="Open", supplier_tokens={})
    assert draft_quote(rfq, prod).free_freight_above == 2000
