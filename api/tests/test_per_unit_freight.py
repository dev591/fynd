"""Tests for per_unit_freight: a second freight model where total freight = flat + per_unit * units.
No-op default: a quote without per_unit_freight computes exactly as today."""
import pytest
from fastapi.testclient import TestClient

from app.engine import evaluate, order
from app.main import app
from app.models import Need, Quote
from tests.helpers import tokens_of

client = TestClient(app)


def q(price=10, size=1, flat=200, per_unit=None, lead=3, **kw):
    return Quote(
        id=kw.pop("id", "x"), supplier="x", item="M10 bolt",
        pack_price=price, pack_size=size, freight=flat,
        lead_days=lead, per_unit_freight=per_unit, **kw,
    )


# ─── engine.order() ───────────────────────────────────────────────────────────

def test_without_per_unit_nothing_changes():
    o = order(q(), 100)
    assert (o.landed, o.freight) == (1200, 200)


@pytest.mark.parametrize("qty,landed,eff_freight", [
    (1,    10 + 200 + 5,   205),   # flat 200 + 1 unit × ₹5
    (100,  1000 + 200 + 500, 700), # flat 200 + 100 × ₹5
    (50,   500 + 200 + 250, 450),  # flat 200 + 50 × ₹5
])
def test_per_unit_freight_adds_to_flat(qty, landed, eff_freight):
    o = order(q(flat=200, per_unit=5), qty)
    assert o.landed == landed
    assert o.freight == eff_freight


def test_flat_zero_per_unit_only():
    o = order(q(flat=0, per_unit=3), 100)
    assert o.landed == 1000 + 300
    assert o.freight == 300


def test_per_unit_freight_with_pack_rounding():
    # pack_size=10, qty=95 → 10 packs = 100 units; pack_price=100 per pack
    o = order(q(price=100, size=10, flat=0, per_unit=2), 95)
    assert o.units == 100
    assert o.freight == 200          # 100 units × ₹2
    assert o.landed == 1000 + 200    # 10 packs × ₹100 + freight


def test_free_delivery_threshold_uses_goods_value_not_per_unit_freight():
    # free_freight_above applies when goods value meets threshold; flat freight waived, per_unit still added
    from app.models import Quote as Q
    qv = Q(id="x", supplier="x", item="x", pack_price=10, pack_size=1,
           freight=200, per_unit_freight=5, free_freight_above=1000, lead_days=3)
    o = order(qv, 100)
    # goods = 100 × ₹10 = ₹1,000 ≥ ₹1,000 → flat freight waived
    assert o.freight == 500          # 0 flat + 100 × ₹5
    assert o.landed == 1000 + 500


def test_per_unit_with_volume_tiers():
    from app.models import PriceBreak
    # At 500 units: pack price drops to ₹9; per_unit adds ₹2 × 500 = ₹1,000
    qv = Quote(id="x", supplier="x", item="x", pack_price=10, pack_size=1, freight=0,
               lead_days=3, per_unit_freight=2,
               price_breaks=[PriceBreak(min_qty=500, pack_price=9)])
    o = order(qv, 500)
    assert o.pack_price == 9
    assert o.freight == 1000         # 500 × ₹2
    assert o.landed == 4500 + 1000


def test_evaluate_winner_accounts_for_per_unit():
    # A: flat 200, no per-unit; B: flat 0, per-unit 2. At 100 units B freight = 200 = same.
    # At 200 units A=2200, B=2000+400=2400 → A wins at 200.
    a = q(id="A", flat=200, per_unit=None)
    b = q(id="B", flat=0, per_unit=2)
    small = evaluate([a, b], Need(item="M10 bolt", qty=100, need_in_days=5))
    big   = evaluate([a, b], Need(item="M10 bolt", qty=200, need_in_days=5))
    # at 100: A=1200, B=1000+200=1200 — tie, B wins on overbuy (same) then id order: A first → A
    assert small.winner is not None
    # at 200: A=2200, B=2000+400=2400 → A wins
    assert big.winner is not None and big.winner.quote_id == "A"


# ─── API: quote submission ─────────────────────────────────────────────────────

def _rfq(qty=100):
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": 5,
                                          "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    return rid, tokens_of(rid)


def test_per_unit_freight_stored_and_applied_in_landed_cost():
    rid, t = _rfq(100)
    body = {"supplier_name": "x", "pack_price": 10, "pack_size": 1,
            "freight": 200, "lead_days": 3, "per_unit_freight": 5}
    v = client.post(f"/api/rfq-by-token/{t['A']}/quotes", json=body).json()
    assert v["per_unit_freight"] == 5
    # landed = 100 × ₹10 + (200 + 100 × ₹5) = 1000 + 700 = 1700
    assert v["landed_cost"] == 1700


def test_per_unit_freight_gst_normalisation():
    """per_unit_freight is a per-unit cost: it scales to the buyer's GST basis exactly like the pack price."""
    rid, t = _rfq(100)
    body = {"supplier_name": "x", "pack_price": 11.8, "pack_size": 1,
            "freight": 0, "lead_days": 3,
            "tax_rate": 18, "price_includes_tax": True,
            "per_unit_freight": 5.9}   # 5.9 incl GST = 5.0 ex-GST
    v = client.post(f"/api/rfq-by-token/{t['A']}/quotes", json=body).json()
    assert v["per_unit_freight"] == pytest.approx(5.9)
    assert v["compare_per_unit_freight"] == pytest.approx(5.0, rel=1e-3)
    # landed = 100 × 10.0 + 100 × 5.0 = 1500 (ex-GST compare basis)
    assert v["landed_cost"] == pytest.approx(1500)


def test_quote_without_per_unit_is_unchanged():
    rid, t = _rfq(100)
    v = client.post(f"/api/rfq-by-token/{t['A']}/quotes",
                    json={"supplier_name": "x", "pack_price": 10, "pack_size": 1,
                          "freight": 200, "lead_days": 3}).json()
    assert v["landed_cost"] == 1200
    assert v.get("per_unit_freight") is None
    assert v.get("compare_per_unit_freight") is None


def test_bad_per_unit_freight_values_rejected():
    rid, t = _rfq(100)
    for bad in (-1, 0):
        r = client.post(f"/api/rfq-by-token/{t['A']}/quotes",
                        json={"supplier_name": "x", "pack_price": 10, "pack_size": 1,
                              "freight": 200, "lead_days": 3, "per_unit_freight": bad})
        assert r.status_code == 422


# ─── catalog draft ─────────────────────────────────────────────────────────────

def test_catalog_draft_carries_per_unit_freight():
    from app.matching import draft_quote
    from app.models import RFQ, SupplierProduct
    prod = SupplierProduct(id="p", name="M10 bolt", pack_price=10, pack_size=1,
                           usual_lead_days=3, freight=100, per_unit_freight=3.0)
    rfq = RFQ(id="r", token="t", item="M10 bolt", qty=100, need_in_days=5,
              buyer_company="c", buyer_name="b", buyer_city="", buyer_state="",
              created_at="", status="Open", supplier_tokens={})
    d = draft_quote(rfq, prod)
    assert d.per_unit_freight == 3.0


def test_catalog_draft_without_per_unit_is_unchanged():
    from app.matching import draft_quote
    from app.models import RFQ, SupplierProduct
    prod = SupplierProduct(id="p", name="M10 bolt", pack_price=10, pack_size=1, usual_lead_days=3)
    rfq = RFQ(id="r", token="t", item="M10 bolt", qty=100, need_in_days=5,
              buyer_company="c", buyer_name="b", buyer_city="", buyer_state="",
              created_at="", status="Open", supplier_tokens={})
    assert draft_quote(rfq, prod).per_unit_freight is None
