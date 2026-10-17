from fastapi.testclient import TestClient

from app.main import app
from app.matching import normalise_item, matching_product, verdict_for
from app.models import RFQ, SupplierProduct
from tests.helpers import tokens_of

client = TestClient(app)


def _rfq(item="M10 bolt", qty=100, need=5, **kw):
    body = {"item": item, "qty": qty, "need_in_days": need, "buyer_company": "Co", "buyer_name": "Buyer", **kw}
    res = client.post("/api/rfqs", json=body).json()
    res["supplier_tokens"] = tokens_of(res["id"])        # test-only peek: the API no longer returns these
    return res


def _inbox(sid):
    return client.get(f"/api/supplier/{sid}/notifications").json()


def test_normalise_item():
    assert normalise_item("  M10   Bolt! ") == "m10 bolt"
    assert normalise_item("5-ply Box") == "5 ply box"


def test_exact_and_alias_match_only():
    p = SupplierProduct(id="p", name="M10 Hex Bolt (Grade 8.8)", pack_price=1, pack_size=1, aliases=["M10 bolt"])
    assert matching_product("m10 BOLT", [p]) is p       # alias
    assert matching_product("M10 Hex Bolt (Grade 8.8)", [p]) is p  # exact name
    assert matching_product("M10 screw", [p]) is None    # no fuzzy matching
    assert matching_product("", [p]) is None


def test_confirming_request_notifies_each_stocking_seller_once():
    before = {s["supplier_id"]: len(_inbox(s["supplier_id"])) for s in client.get("/api/suppliers").json()}
    res = _rfq("M10 bolt")
    matched = set(res["supplier_tokens"])
    assert {"A", "B", "C", "D", "E"} <= matched
    assert not matched & {"F", "G", "H", "I", "J"}      # packaging / electricals do not stock bolts
    assert res["matched"] == len(matched)
    for sid in before:
        delta = len(_inbox(sid)) - before[sid]
        assert delta == (1 if sid in matched else 0)


def test_unmatched_item_notifies_nobody():
    res = _rfq("titanium widget")
    assert res["supplier_tokens"] == {} and res["matched"] == 0


def test_verdict_yes_partly_no_with_reasons():
    res = _rfq("M10 bolt", qty=100, need=5)
    rfq_id = res["id"]
    by_sid = {sid: next(n for n in _inbox(sid) if n["rfq_id"] == rfq_id) for sid in res["supplier_tokens"]}

    assert by_sid["A"]["verdict"]["can_fulfil"] == "yes"            # stock 500, lead 3, moq 50
    assert by_sid["B"]["verdict"]["can_fulfil"] == "yes"            # stock 150 covers 100
    assert by_sid["C"]["verdict"]["can_fulfil"] == "partly"         # lead 7 > 5
    assert by_sid["D"]["verdict"]["can_fulfil"] == "no"             # stock 0
    assert all(n["verdict"]["reasons"] for n in by_sid.values())


def test_verdict_moq_and_untracked_stock():
    rfq = RFQ(id="r", token="t", item="x", qty=10, need_in_days=5, buyer_company="c", buyer_name="b",
              buyer_city="p", buyer_state="m", created_at="now")
    p = SupplierProduct(id="p", name="x", pack_price=1, pack_size=1, moq=50, usual_lead_days=2)
    v = verdict_for(rfq, p)
    assert v.can_fulfil == "partly" and "Minimum order is 50" in v.reasons[0]
    ok = verdict_for(rfq, SupplierProduct(id="q", name="x", pack_price=1, pack_size=1))
    assert ok.can_fulfil == "yes"


def test_mark_read_and_quote_link_works():
    res = _rfq("M10 bolt")
    n = next(n for n in _inbox("A") if n["rfq_id"] == res["id"])
    assert n["status"] == "new" and n["quote_url"] == f"/supplier/quote?token={res['supplier_tokens']['A']}"
    read = client.post(f"/api/supplier/A/notifications/{n['id']}/read")
    assert read.status_code == 200 and read.json()["status"] == "viewed"
    assert client.post("/api/supplier/A/notifications/nope/read").status_code == 404
    # the link in the notification opens the sealed request
    assert client.get(f"/api/rfq-by-token/{res['supplier_tokens']['A']}").status_code == 200


def test_sellers_are_labelled_synthetic():
    sellers = client.get("/api/suppliers").json()
    assert len(sellers) >= 8
    assert all(s["synthetic"] for s in sellers)


def test_draft_quote_numbers_come_from_catalog():
    res = _rfq("M10 bolt", qty=100)
    d = client.get(f"/api/rfq-by-token/{res['supplier_tokens']['A']}/draft").json()
    assert (d["pack_price"], d["pack_size"], d["freight"], d["lead_days"], d["moq"], d["max_qty"]) == (10, 1, 200, 3, 50, 500)
    assert d["verdict"]["can_fulfil"] == "yes"
    # stock becomes the quote cap
    b = client.get(f"/api/rfq-by-token/{res['supplier_tokens']['B']}/draft").json()
    assert b["max_qty"] == 150
    assert client.get("/api/rfq-by-token/nope/draft").status_code == 404


def test_draft_uses_price_break_for_quantity():
    added = client.post("/api/supplier/products/I", json={
        "name": "Test Brass Nut", "pack_price": 10, "pack_size": 1, "stock": 1000, "aliases": ["brass nut test"],
        "price_breaks": [{"min_qty": 100, "pack_price": 8}, {"min_qty": 500, "pack_price": 6}],
    })
    assert added.status_code == 201
    small = _rfq("brass nut test", qty=50)
    big = _rfq("brass nut test", qty=600)
    mid = _rfq("brass nut test", qty=100)
    price = lambda r: client.get(f"/api/rfq-by-token/{r['supplier_tokens']['I']}/draft").json()
    assert price(small)["pack_price"] == 10 and price(small)["price_break_applied"] is None
    assert price(mid)["pack_price"] == 8
    assert price(big)["pack_price"] == 6 and price(big)["price_break_applied"] == 500


def test_activity_funnel_and_live_quote_appears_in_compare():
    res = _rfq("M10 bolt", qty=100)
    rid, toks = res["id"], res["supplier_tokens"]
    act = lambda: client.get(f"/api/rfqs/{rid}/activity").json()
    n = len(toks)
    assert act() == {"notified": n, "viewed": 0, "quoting": 0, "quoted": 0, "declined": 0}

    client.get(f"/api/rfq-by-token/{toks['A']}")                  # A opens the link
    client.get(f"/api/rfq-by-token/{toks['B']}")                  # B opens it
    client.post(f"/api/rfq-by-token/{toks['B']}/quoting")         # B starts typing
    assert act() == {"notified": n, "viewed": 2, "quoting": 1, "quoted": 0, "declined": 0}

    d = client.get(f"/api/rfq-by-token/{toks['A']}/draft").json()
    sent = client.post(f"/api/rfq-by-token/{toks['A']}/quotes", json={
        "pack_price": d["pack_price"], "pack_size": d["pack_size"], "freight": d["freight"],
        "lead_days": d["lead_days"], "moq": d["moq"], "max_qty": d["max_qty"], "origin": "manual",
    })
    assert sent.status_code == 200 and sent.json()["origin"] == "manual"
    assert act() == {"notified": n, "viewed": 2, "quoting": 2, "quoted": 1, "declined": 0}

    # the buyer's next poll already sees it
    details = client.get(f"/api/rfqs/{rid}").json()
    assert details["quotes"]["Seller 1"][0]["landed_cost"] == 1200
    assert details["evaluation"]["winner"]["quote_id"] == "Seller 1"
    assert details["activity"]["quoted"] == 1
