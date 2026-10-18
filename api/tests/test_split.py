import random

import pytest
from fastapi.testclient import TestClient

from app.engine import best_split, order
from app.main import app
from app.models import ExceptionRecord, Need, PriceBreak, Quote
from tests.helpers import alias, tokens_of

client = TestClient(app)


def q(id, price=10, size=1, freight=0, lead=3, moq=None, cap=None, tiers=(), free=None, per_unit=None):
    return Quote(id=id, supplier=id, item="M10 bolt", pack_price=price, pack_size=size, freight=freight, lead_days=lead, moq=moq,
                 max_qty=cap, price_breaks=[PriceBreak(min_qty=m, pack_price=p) for m, p in tiers], free_freight_above=free,
                 per_unit_freight=per_unit)


def need(qty=100, days=5):
    return Need(item="M10 bolt", qty=qty, need_in_days=days)


def parts(plan):
    return {p["quote_id"]: p["qty"] for p in plan["parts"]}


def test_when_no_single_seller_has_enough_stock_the_split_covers_the_whole_quantity():
    plan = best_split([q("A", 10, freight=50, cap=60), q("B", 11, freight=20, cap=60)], need(100))
    assert parts(plan) == {"A": 60, "B": 40}
    assert plan["total_landed"] == 650 + 460 and plan["reason"] == "no_single_supplier_can_fill" and plan["best_single"] is None
    assert sum(p["qty"] for p in plan["parts"]) == 100


def test_a_split_is_offered_when_it_is_cheaper_than_the_best_single_seller():
    plan = best_split([q("A", 10), q("B", 9, cap=50)], need(100))
    assert parts(plan) == {"A": 50, "B": 50} and plan["total_landed"] == 950
    assert plan["reason"] == "cheaper_than_best_single" and plan["best_single"] == {"quote_id": "A", "landed": 1000} and plan["saving"] == 50


def test_no_split_when_one_seller_is_already_the_cheapest():
    assert best_split([q("A", 9), q("B", 10), q("C", 11)], need(100)) is None


def test_fewer_than_two_usable_sellers_means_no_split():
    assert best_split([q("A", 10, cap=50)], need(100)) is None
    assert best_split([], need(100)) is None


def test_late_sellers_are_left_out_unless_a_written_exception_is_signed():
    quotes = [q("A", 10, cap=50), q("B", 12, cap=50), q("L", 8, lead=9, cap=60)]
    plain = best_split(quotes, need(100))
    assert plain is not None and set(parts(plain)) == {"A", "B"}
    blank = best_split(quotes, need(100), {"L": ExceptionRecord(reason="  ", approver="x")})
    assert set(parts(blank)) == {"A", "B"}                                           # a blank reason never unlocks a gate
    signed = best_split(quotes, need(100), {"L": ExceptionRecord(reason="Plant stops without it", approver="Ramesh")})
    assert "L" in parts(signed)


def test_a_seller_with_no_pack_size_or_a_different_item_is_never_used():
    bad = Quote(id="D", supplier="D", item="M10 bolt", pack_price=1, pack_size=None, freight=0, lead_days=3)
    other = Quote(id="E", supplier="E", item="M12 nut", pack_price=1, pack_size=1, freight=0, lead_days=3)
    assert best_split([q("A", 10, cap=60), q("B", 11, cap=60), bad, other], need(100)) is not None
    assert best_split([q("A", 10, cap=60), bad, other], need(100)) is None


def test_pack_rounding_and_minimum_orders_are_costed_by_the_real_order_function():
    plan = best_split([q("A", 400, size=50, moq=50), q("B", 9.5)], need(120))
    for p in plan["parts"]:
        src = {"A": q("A", 400, size=50, moq=50), "B": q("B", 9.5)}[p["quote_id"]]
        o = order(src, p["qty"])
        assert (p["packs"], p["units"], p["landed"]) == (o.packs, o.units, o.landed)
    assert plan["total_landed"] < min(order(q("A", 400, size=50, moq=50), 120).landed, order(q("B", 9.5), 120).landed)


def _oracle(quotes, n, exceptions=None):
    """Exhaustive search with the real order(): every ordered pair, every split point. The reference answer."""
    exceptions = exceptions or {}
    usable = [x for x in quotes if x.pack_size and (x.lead_days <= n.need_in_days or exceptions.get(x.id))]
    def cost(x, units):
        o = order(x, units)
        return None if o is None or (x.max_qty is not None and o.units > x.max_qty) else o.landed
    singles = [c for c in (cost(x, n.qty) for x in usable) if c is not None]
    best = None
    for i, a in enumerate(usable):
        for b in usable[i + 1:]:
            for k in range(1, n.qty):
                ca, cb = cost(a, k), cost(b, n.qty - k)
                if ca is not None and cb is not None and (best is None or ca + cb < best):
                    best = ca + cb
    return best, (min(singles) if singles else None)


def _random_quotes(rng, n):
    out = []
    for i in range(n):
        size = rng.choice([1, 1, 5, 10, 50])
        price = round(rng.uniform(5, 15), 1) * size
        tiers = []
        if rng.random() < 0.4:
            first = rng.choice([100, 150, 250])
            tiers = [(1, price), (first, round(price * 0.9, 2)), (first * 2, round(price * 0.8, 2))]
        out.append(q(chr(65 + i), price=price, size=size, freight=rng.choice([0, 50, 150, 300]), lead=rng.choice([2, 3, 4]),
                     moq=rng.choice([None, None, size, size * 2]), cap=rng.choice([None, None, 120, 200, 350]), tiers=tiers,
                     free=rng.choice([None, None, 800, 2000]), per_unit=rng.choice([None, None, 0.2, 0.75, 2.0])))
    return out


@pytest.mark.parametrize("seed", range(40))
def test_the_split_matches_an_exhaustive_search_on_random_markets(seed):
    rng = random.Random(seed)
    quotes = _random_quotes(rng, rng.choice([2, 3, 4]))
    n = need(rng.choice([60, 100, 180, 300]))
    best_pair, best_single = _oracle(quotes, n)
    plan = best_split(quotes, n)
    offered = best_pair is not None and (best_single is None or best_pair < best_single - 0.005)
    if not offered:
        assert plan is None
        return
    assert plan is not None and plan["total_landed"] == pytest.approx(best_pair)
    assert sum(p["qty"] for p in plan["parts"]) == n.qty and all(p["qty"] >= 1 for p in plan["parts"])


@pytest.mark.parametrize("seed", range(25))
def test_the_candidate_point_search_used_for_huge_orders_finds_the_same_optimum(seed):
    rng = random.Random(1000 + seed)
    quotes = _random_quotes(rng, 3)
    n = need(rng.choice([80, 140, 260]))
    full, forced = best_split(quotes, n), best_split(quotes, n, exhaustive_limit=0)
    assert (full is None) == (forced is None)
    if full:
        assert forced["total_landed"] == pytest.approx(full["total_landed"])


def test_ties_resolve_the_same_way_every_time():
    quotes = [q("A", 10, cap=60), q("B", 10, cap=60), q("C", 10, cap=60)]
    first = best_split(quotes, need(100))
    assert all(best_split(quotes, need(100)) == first for _ in range(5))


# ─── through the API: aliases only, buyer only, both sellers revealed before an order is saved ───

def _stocked_request(qty=100):
    """Demo sellers A, B, C quote an item. Seller caps make a split the only way to cover the quantity."""
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": 5, "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    t = tokens_of(rid)
    for sid, price, fr, cap in (("A", 10, 50, 60), ("B", 11, 20, 60)):
        client.post(f"/api/rfq-by-token/{t[sid]}/quotes", json={"supplier_name": f"Real {sid} Ltd", "pack_price": price, "pack_size": 1,
                                                               "freight": fr, "lead_days": 3, "max_qty": cap})
    return rid


def test_the_options_endpoint_returns_the_plan_with_aliases_only():
    rid = _stocked_request()
    r = client.get(f"/api/rfqs/{rid}/split-options")
    assert r.status_code == 200
    plan = r.json()["plan"]
    assert {p["quote_id"] for p in plan["parts"]} == {"Seller 1", "Seller 2"} and plan["total_landed"] == 1110
    assert "Real A Ltd" not in r.text and "Real B Ltd" not in r.text


def test_the_options_endpoint_says_none_when_one_seller_wins_alone():
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    t = tokens_of(rid)
    for sid, price in (("A", 9), ("B", 10)):
        client.post(f"/api/rfq-by-token/{t[sid]}/quotes", json={"supplier_name": "x", "pack_price": price, "pack_size": 1, "freight": 0, "lead_days": 3})
    assert client.get(f"/api/rfqs/{rid}/split-options").json()["plan"] is None


def test_a_split_order_needs_both_sellers_revealed_then_is_saved_with_both_parts():
    rid = _stocked_request()
    body = {"winner_id": "Seller 1", "reason": "Only way to cover the quantity", "approver": "Ramesh", "split": True}
    r = client.post(f"/api/rfqs/{rid}/decision", json=body)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "reveal_required"
    client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, 'A')}/reveal")
    assert client.post(f"/api/rfqs/{rid}/decision", json=body).status_code == 409              # the second seller is still hidden
    client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, 'B')}/reveal")
    d = client.post(f"/api/rfqs/{rid}/decision", json=body)
    assert d.status_code == 200
    split = d.json()["split"]
    assert {p["quote_id"]: p["qty"] for p in split["parts"]} == {"Seller 1": 60, "Seller 2": 40} and split["total_landed"] == 1110
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    assert s["decided"] and s["split"]["total_landed"] == 1110 and s["overrode_engine"] is False
    assert s["rfq"]["status"] == "Decided" and s["savings"]["crossover_pick"] == "Seller 1 + Seller 2"
    shared = client.get(f"/api/share/{client.post(f'/api/rfqs/{rid}/share').json()['token']}").json()
    assert shared["split"]["total_landed"] == 1110 and "Real A Ltd" not in str(shared) and "Real B Ltd" not in str(shared)


def test_a_split_decision_is_refused_when_no_split_exists():
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    t = tokens_of(rid)
    client.post(f"/api/rfq-by-token/{t['A']}/quotes", json={"supplier_name": "x", "pack_price": 9, "pack_size": 1, "freight": 0, "lead_days": 3})
    client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, 'A')}/reveal")
    r = client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 1", "reason": "x", "approver": "y", "split": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_split"


def test_a_split_decision_cannot_choose_its_own_quantities():
    rid = _stocked_request()
    for a in ("A", "B"):
        client.post(f"/api/rfqs/{rid}/quotes/{alias(rid, a)}/reveal")
    body = {"winner_id": "Seller 1", "reason": "r", "approver": "a", "split": True, "parts": [{"quote_id": "Seller 1", "qty": 99}]}
    d = client.post(f"/api/rfqs/{rid}/decision", json=body).json()
    assert {p["quote_id"]: p["qty"] for p in d["split"]["parts"]} == {"Seller 1": 60, "Seller 2": 40}      # the server's own plan, always


def test_per_unit_freight_is_part_of_the_split_cost_exactly_as_in_order():
    a, b = q("A", 10, freight=50, per_unit=1.5, cap=60), q("B", 11, freight=20, cap=60)
    plan = best_split([a, b], need(100))
    for p in plan["parts"]:
        o = order({"A": a, "B": b}[p["quote_id"]], p["qty"])
        assert p["landed"] == o.landed
    assert plan["total_landed"] == 60 * 10 + 50 + 60 * 1.5 + 40 * 11 + 20 or plan["total_landed"] == 40 * 10 + 50 + 40 * 1.5 + 60 * 11 + 20
