import pytest
from fastapi.testclient import TestClient

from app.engine import evaluate, order
from app.main import app
from app.models import Need, PriceBreak, Quote
from tests.helpers import tokens_of

client = TestClient(app)


def q(price=10, size=1, freight=100, lead=3, moq=None, breaks=(), **kw):
    return Quote(id=kw.pop("id", "x"), supplier="x", item="M10 bolt", pack_price=price, pack_size=size, freight=freight,
                 lead_days=lead, moq=moq, price_breaks=[PriceBreak(min_qty=m, pack_price=p) for m, p in breaks], **kw)


def test_without_tiers_nothing_changes():
    o = order(q(), 100)
    assert (o.packs, o.units, o.landed, o.pack_price) == (100, 100, 1100, 10)


@pytest.mark.parametrize("qty,landed,price", [(1, 110, 10), (499, 4990 + 100, 10), (500, 4500 + 100, 9), (999, 8991 + 100, 9), (1000, 8000 + 100, 8)])
def test_the_tier_the_units_reach_sets_the_pack_price(qty, landed, price):
    o = order(q(breaks=[(1, 10), (500, 9), (1000, 8)]), qty)
    assert (o.landed, o.pack_price) == (landed, price)


def test_rounding_up_to_whole_packs_can_cross_into_the_cheaper_tier():
    o = order(q(price=950, size=100, freight=0, breaks=[(1, 950), (500, 900)]), 450)        # 5 packs = 500 units
    assert (o.packs, o.units, o.pack_price, o.landed) == (5, 500, 900, 4500)


def test_minimum_order_quantity_counts_toward_the_tier():
    o = order(q(price=10, moq=600, breaks=[(1, 10), (500, 9)]), 100)                         # must buy 600, so the 500+ tier applies
    assert (o.units, o.pack_price, o.landed) == (600, 9, 5500)


def test_tiers_listed_out_of_order_still_work_and_a_missing_base_tier_falls_back_to_the_pack_price():
    assert order(q(price=10, breaks=[(1000, 8), (500, 9)]), 600).pack_price == 9
    assert order(q(price=10, breaks=[(500, 9)]), 100).pack_price == 10


def test_evaluate_flips_the_winner_with_quantity_and_reports_the_applied_price():
    flat = q(id="A", price=10, freight=200)
    tiered = q(id="B", price=11, freight=50, breaks=[(1, 11), (300, 8)])
    small = evaluate([flat, tiered], Need(item="M10 bolt", qty=100, need_in_days=5))
    big = evaluate([flat, tiered], Need(item="M10 bolt", qty=400, need_in_days=5))
    assert small.winner.quote_id == "B" and small.winner.landed == 1150 and small.winner.pack_price == 11
    assert big.winner.quote_id == "B" and big.winner.landed == 3250 and big.winner.pack_price == 8


def _rfq(qty=600):
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": 5, "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    return rid, tokens_of(rid)


def test_submitted_tiers_are_normalised_to_the_gst_basis_and_drive_the_landed_cost():
    rid, t = _rfq(600)
    body = {"supplier_name": "x", "pack_price": 11.8, "pack_size": 1, "freight": 100, "lead_days": 3,
            "tax_rate": 18, "price_includes_tax": True,
            "price_breaks": [{"min_qty": 1, "pack_price": 11.8}, {"min_qty": 500, "pack_price": 10.62}]}
    v = client.post(f"/api/rfq-by-token/{t['A']}/quotes", json=body).json()
    assert [b["pack_price"] for b in v["compare_breaks"]] == [10.0, 9.0]            # 11.8 / 1.18 and 10.62 / 1.18, ex-GST
    assert v["landed_cost"] == 9 * 600 + 100
    assert [b["pack_price"] for b in v["price_breaks"]] == [11.8, 10.62]            # what the seller typed is kept as stated


def test_a_quote_without_tiers_is_unchanged():
    rid, t = _rfq(100)
    v = client.post(f"/api/rfq-by-token/{t['A']}/quotes", json={"supplier_name": "x", "pack_price": 10, "pack_size": 1, "freight": 200, "lead_days": 3}).json()
    assert v["landed_cost"] == 1200 and v["price_breaks"] == [] and v["compare_breaks"] == []


@pytest.mark.parametrize("breaks", [
    [{"min_qty": 500, "pack_price": 9}, {"min_qty": 500, "pack_price": 8}],            # duplicate quantity
    [{"min_qty": 0, "pack_price": 9}],                                                 # quantity must be 1 or more
    [{"min_qty": 500, "pack_price": 0}],                                               # price must be above zero
    [{"min_qty": 500, "pack_price": 9}, {"min_qty": 1000, "pack_price": 9.5}],         # a bigger order must not cost more per pack
    [{"min_qty": i + 1, "pack_price": 20 - i} for i in range(9)],                      # too many tiers
])
def test_bad_tiers_are_refused(breaks):
    rid, t = _rfq(100)
    r = client.post(f"/api/rfq-by-token/{t['A']}/quotes", json={"supplier_name": "x", "pack_price": 10, "pack_size": 1, "freight": 0, "lead_days": 3, "price_breaks": breaks})
    assert r.status_code == 422


def test_the_catalog_draft_carries_the_whole_tier_list_and_the_price_for_this_quantity():
    from app.matching import draft_quote
    from app.models import RFQ, SupplierProduct
    prod = SupplierProduct(id="p", name="M10 bolt", pack_price=10, pack_size=1, moq=1, usual_lead_days=3, freight=100, stock=5000,
                           price_breaks=[PriceBreak(min_qty=500, pack_price=9), PriceBreak(min_qty=1000, pack_price=8)])
    rfq = RFQ(id="r", token="t", item="M10 bolt", qty=600, need_in_days=5, buyer_company="c", buyer_name="b", buyer_city="", buyer_state="",
              created_at="", status="Open", supplier_tokens={})
    d = draft_quote(rfq, prod)
    assert d.pack_price == 9 and d.price_break_applied == 500
    assert [(b.min_qty, b.pack_price) for b in d.price_breaks] == [(1, 10), (500, 9), (1000, 8)]
    plain = draft_quote(rfq, SupplierProduct(id="p", name="x", pack_price=10, pack_size=1, usual_lead_days=3))
    assert plain.price_breaks == []
