"""Case check 2 in the app: a late (or short) seller is never recommended unless a named person writes a reason."""
import json

from fastapi.testclient import TestClient

from app.main import app, store
from tests.helpers import alias, quote, tokens_of

client = TestClient(app)


def _scene():
    """B is cheap but arrives in 7 days against a 5-day need; A is dearer and on time."""
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    quote(client, rid, "A", price=10, freight=200, lead=3)           # 1,200 landed, on time
    quote(client, rid, "B", price=8, freight=50, lead=7)             # 850 landed, too slow
    return rid, alias(rid, "A"), alias(rid, "B")


def _eval(rid):
    return client.get(f"/api/rfqs/{rid}").json()


def test_a_late_seller_is_not_recommended_and_the_saving_given_up_is_shown():
    rid, a, b = _scene()
    d = _eval(rid)
    row = next(r for r in d["evaluation"]["rows"] if r["quote_id"] == b)
    assert row["status"] == "exception" and "7 days" in row["reason"] and d["evaluation"]["winner"]["quote_id"] == a
    assert [r["quote_id"] for r in d["evaluation"]["cheaper_excluded"]] == [b]      # listed as cheaper but excluded
    assert d["exceptions"] == {}


def test_a_blank_reason_or_blank_approver_is_rejected_and_changes_nothing():
    rid, a, b = _scene()
    for body in [{"alias": b, "reason": "", "approver": "Plant head"}, {"alias": b, "reason": "   ", "approver": "Plant head"},
                 {"alias": b, "reason": "Stock covers the gap", "approver": ""}, {"alias": b, "reason": "ok", "approver": "  "}]:
        assert client.post(f"/api/rfqs/{rid}/exceptions", json=body).status_code == 422, body
    assert _eval(rid)["evaluation"]["winner"]["quote_id"] == a and _eval(rid)["exceptions"] == {}


def test_a_signed_exception_unlocks_the_late_seller_and_is_on_the_record():
    rid, a, b = _scene()
    r = client.post(f"/api/rfqs/{rid}/exceptions", json={"alias": b, "reason": "Saves 350, our stock covers the gap",
                                                         "approver": "Plant head"})
    assert r.status_code == 200 and r.json()["exceptions"][b]["approver"] == "Plant head"
    d = _eval(rid)
    assert d["evaluation"]["winner"]["quote_id"] == b                             # now allowed to win
    assert next(x for x in d["evaluation"]["rows"] if x["quote_id"] == b)["approved"] is True
    assert d["exceptions"][b]["reason"].startswith("Saves 350")
    # the saved decision and the one-pager carry the exception
    client.post(f"/api/rfqs/{rid}/quotes/{b}/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": b, "reason": "Cheapest with exception", "approver": "Plant head"})
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    assert s["exceptions"][b]["approver"] == "Plant head" and s["pick"]["quote_id"] == b
    assert s["decision"]["exceptions"][b]["reason"].startswith("Saves 350")


def test_withdrawing_an_exception_puts_the_gate_back():
    rid, a, b = _scene()
    client.post(f"/api/rfqs/{rid}/exceptions", json={"alias": b, "reason": "ok for now", "approver": "Plant head"})
    assert _eval(rid)["evaluation"]["winner"]["quote_id"] == b
    assert client.delete(f"/api/rfqs/{rid}/exceptions/{b}").status_code == 200
    assert _eval(rid)["evaluation"]["winner"]["quote_id"] == a and _eval(rid)["exceptions"] == {}


def test_exceptions_cannot_name_real_ids_or_other_buyers_requests_or_a_decided_request():
    rid, a, b = _scene()
    assert client.post(f"/api/rfqs/{rid}/exceptions", json={"alias": "B", "reason": "x", "approver": "y"}).status_code == 404
    assert client.post(f"/api/rfqs/{rid}/exceptions", json={"alias": "Seller 9", "reason": "x", "approver": "y"}).status_code == 404
    client.post(f"/api/rfqs/{rid}/quotes/{a}/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": a, "reason": "on time", "approver": "Me"})
    assert client.post(f"/api/rfqs/{rid}/exceptions", json={"alias": b, "reason": "late", "approver": "Me"}).status_code == 409


def test_exception_unlocks_a_short_supplier_too():
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    quote(client, rid, "A", price=10, freight=200, lead=3, max_qty=60)               # stock covers 60 of 100
    quote(client, rid, "B", price=11, freight=50, lead=3)
    a = alias(rid, "A")
    row = next(r for r in _eval(rid)["evaluation"]["rows"] if r["quote_id"] == a)
    assert row["status"] == "exception" and row["fill_qty"] == 60
    client.post(f"/api/rfqs/{rid}/exceptions", json={"alias": a, "reason": "Take 60 now, 40 elsewhere", "approver": "Plant head"})
    assert next(r for r in _eval(rid)["evaluation"]["rows"] if r["quote_id"] == a)["approved"] is True
