from fastapi.testclient import TestClient

from app.main import app
from app.matching import normalise_item, matching_product, verdict_for
from app.models import RFQ, SupplierProduct

client = TestClient(app)


def _rfq(item="M10 bolt", qty=100, need=5, **kw):
    body = {"item": item, "qty": qty, "need_in_days": need, "buyer_company": "Co", "buyer_name": "Buyer", **kw}
    return client.post("/api/rfqs", json=body).json()


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
    assert by_sid["B"]["verdict"]["can_fulfil"] == "partly"         # stock 80 of 100
    assert "80 of 100" in " ".join(by_sid["B"]["verdict"]["reasons"])
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
