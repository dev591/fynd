"""Razorpay (test mode): reveal packs and Pro, and the 50% advance on an order. The Razorpay API is faked; signatures are real."""
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from app import razorpay_client as rz
from app.auth import AuthUser, get_current_user
from app.main import app, store
from tests.helpers import alias, tokens_of

client = TestClient(app)
SECRET = "test-secret"


class Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise rz.httpx.HTTPStatusError("err", request=None, response=None)


class FakeRazorpay:
    def __init__(self):
        self.orders, self.calls, self.fail = {}, [], False

    def request(self, method, url, auth=None, json=None, timeout=None, **_):
        self.calls.append((method, url, auth, json))
        if self.fail:
            raise rz.httpx.ConnectError("down")
        if method == "POST" and url.endswith("/orders"):
            oid = f"order_{len(self.orders) + 1}"
            self.orders[oid] = {"id": oid, "amount": json["amount"], "currency": json["currency"], "status": "created", "notes": json.get("notes", {})}
            return Resp(self.orders[oid])
        if method == "GET" and "/payments/" in url:
            pid = url.rsplit("/", 1)[-1]
            oid = pid.replace("pay_", "order_")
            return Resp({"id": pid, "status": "captured", "amount": self.orders[oid]["amount"], "order_id": oid})
        return Resp({}, 404)


@pytest.fixture
def razor(monkeypatch):
    fake = FakeRazorpay()
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_abc123")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", SECRET)
    monkeypatch.setattr(rz.httpx, "request", fake.request)
    monkeypatch.setattr(rz, "_SLEEP", lambda s: None)
    return fake


def sign(order_id, payment_id, secret=SECRET):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def pay(order_id, secret=SECRET):
    pid = order_id.replace("order_", "pay_")
    return {"razorpay_order_id": order_id, "razorpay_payment_id": pid, "razorpay_signature": sign(order_id, pid, secret)}


def as_user(uid):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=f"{uid}@t.dev")


# ─── configuration and safety ─────────────────────────────────────────────

def test_payments_are_off_without_keys_and_the_config_says_so():
    c = client.get("/api/payments/config").json()
    assert c["enabled"] is False and c["mode"] == "off" and c["key_id"] is None
    assert client.post("/api/payments/order", json={"product": "reveals_10"}).status_code == 503


def test_test_keys_turn_it_on_and_only_the_public_key_id_is_ever_returned(razor):
    c = client.get("/api/payments/config").json()
    assert c["enabled"] and c["mode"] == "test" and c["key_id"] == "rzp_test_abc123"
    assert SECRET not in str(c) and {p["id"] for p in c["products"]} == {"reveals_1", "reveals_5", "reveals_10", "reveals_20", "reveals_30", "reveals_50"}


def test_live_keys_are_refused_unless_explicitly_allowed(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_live_abc")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", SECRET)
    assert client.get("/api/payments/config").json()["enabled"] is False
    monkeypatch.setenv("RAZORPAY_ALLOW_LIVE", "true")
    assert client.get("/api/payments/config").json()["mode"] == "live"


def test_the_prices_are_the_pitch_deck_ladder():
    ps = {p["reveals"]: p for p in client.get("/api/payments/config").json()["products"]}
    assert {n: p["amount_rupees"] for n, p in ps.items()} == {1: 79, 5: 349, 10: 649, 20: 1199, 30: 1699, 50: 2699}
    assert ps[10]["per_reveal"] == 64.9 and ps[50]["per_reveal"] == 53.98 and ps[30]["per_reveal"] == 56.63


# ─── reveal bundles ───────────────────────────────────────────────

def test_buying_a_bundle_adds_its_reveals(razor):
    as_user("rz-pack")
    before = store.reveals_left("rz-pack")
    o = client.post("/api/payments/order", json={"product": "reveals_10"}).json()
    assert o["amount_paise"] == 64900 and o["key_id"] == "rzp_test_abc123" and razor.calls[-1][2] == ("rzp_test_abc123", SECRET)
    r = client.post("/api/payments/verify", json=pay(o["order_id"]))
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert store.reveals_left("rz-pack") == before + 10


def test_every_bundle_adds_exactly_its_reveals_and_charges_its_price(razor):
    for n, price in [(1, 79), (5, 349), (20, 1199), (30, 1699), (50, 2699)]:
        uid = f"rz-b{n}"
        as_user(uid)
        before = store.reveals_left(uid)
        o = client.post("/api/payments/order", json={"product": f"reveals_{n}"}).json()
        assert o["amount_paise"] == price * 100
        assert client.post("/api/payments/verify", json=pay(o["order_id"])).status_code == 200
        assert store.reveals_left(uid) == before + n


def test_the_old_pro_subscription_is_no_longer_for_sale(razor):
    as_user("rz-nopro")
    assert client.post("/api/payments/order", json={"product": "pro_30d"}).status_code == 422


def test_a_bad_signature_changes_nothing(razor):
    as_user("rz-bad")
    before = store.reveals_left("rz-bad")
    o = client.post("/api/payments/order", json={"product": "reveals_10"}).json()
    r = client.post("/api/payments/verify", json=pay(o["order_id"], secret="wrong"))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_signature"
    assert store.reveals_left("rz-bad") == before


def test_verifying_twice_applies_it_once(razor):
    as_user("rz-twice")
    before = store.reveals_left("rz-twice")
    o = client.post("/api/payments/order", json={"product": "reveals_10"}).json()
    assert client.post("/api/payments/verify", json=pay(o["order_id"])).status_code == 200
    assert client.post("/api/payments/verify", json=pay(o["order_id"])).json()["status"] == "paid"
    assert store.reveals_left("rz-twice") == before + 10


def test_someone_else_cannot_claim_a_payment(razor):
    as_user("rz-owner")
    o = client.post("/api/payments/order", json={"product": "reveals_10"}).json()
    as_user("rz-thief")
    assert client.post("/api/payments/verify", json=pay(o["order_id"])).status_code == 404
    assert client.post("/api/payments/verify", json=pay("order_unknown")).status_code == 404


def test_an_unknown_product_or_an_unreachable_razorpay_is_a_clean_error(razor):
    as_user("rz-err")
    assert client.post("/api/payments/order", json={"product": "free_money"}).status_code == 422
    razor.fail = True
    r = client.post("/api/payments/order", json={"product": "reveals_10"})
    assert r.status_code == 502 and "try again" in r.json()["detail"].lower()


def test_a_payment_razorpay_did_not_capture_is_not_applied(razor, monkeypatch):
    as_user("rz-nocap")
    o = client.post("/api/payments/order", json={"product": "reveals_10"}).json()
    monkeypatch.setattr(rz, "fetch_payment", lambda pid: {"id": pid, "status": "failed", "amount": 64900, "order_id": o["order_id"]})
    r = client.post("/api/payments/verify", json=pay(o["order_id"]))
    assert r.status_code == 402 and store.reveals_left("rz-nocap") == store.free_reveal_limit()


# ─── the order: notification, cash on delivery, or 50% now ───────────────────

def decided_order(buyer="rz-buyer"):
    as_user(buyer)
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "Co", "buyer_name": "R"}).json()["id"]
    client.post(f"/api/rfq-by-token/{tokens_of(rid)['B']}/quotes", json={"supplier_name": "B", "pack_price": 11, "pack_size": 1, "freight": 50, "lead_days": 3})
    a = alias(rid, "B")
    client.post(f"/api/rfqs/{rid}/quotes/{a}/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": a, "reason": "cheapest", "approver": "R"})
    return rid


def test_placing_an_order_notifies_the_buyer_to_choose_how_to_pay():
    rid = decided_order("rz-notice")
    notes = [n for n in store.buyer_notices["rz-notice"] if n.rfq_id == rid]
    n = next(x for x in notes if x.kind == "order_placed")
    assert "cash on delivery" in n.message.lower() and "50%" in n.message
    pay_state = client.get(f"/api/rfqs/{rid}/payment").json()
    assert pay_state["total"] == 1150 and pay_state["advance"] == 575 and pay_state["balance"] == 575 and pay_state["method"] is None


def test_choosing_cash_on_delivery_records_it_and_needs_no_razorpay():
    rid = decided_order("rz-cod")
    r = client.post(f"/api/rfqs/{rid}/payment", json={"method": "cod"})
    assert r.status_code == 200 and r.json()["method"] == "cod" and r.json()["status"] == "pay_on_delivery"
    assert "cash on delivery" in client.get(f"/api/rfqs/{rid}/summary").json()["decision"]["payment_note"].lower()


def test_paying_fifty_percent_now_is_half_the_total_and_leaves_the_rest_for_delivery(razor):
    rid = decided_order("rz-half")
    o = client.post("/api/payments/order", json={"product": "order_advance", "rfq_id": rid}).json()
    assert o["amount_paise"] == 57500
    r = client.post("/api/payments/verify", json=pay(o["order_id"]))
    assert r.status_code == 200
    st = client.get(f"/api/rfqs/{rid}/payment").json()
    assert st["method"] == "split_50" and st["status"] == "advance_paid" and st["advance"] == 575 and st["balance"] == 575
    assert any(n.kind == "payment_received" for n in store.buyer_notices["rz-half"])
    assert "575" in client.get(f"/api/rfqs/{rid}/summary").json()["decision"]["payment_note"]
    assert "advance" in " ".join(e["text"].lower() for e in client.get(f"/api/rfqs/{rid}/log").json()["events"])


def test_the_seller_sees_the_advance_in_orders_received(razor):
    rid = decided_order("u_test")                  # the shared test account holds both roles, so it can read seller screens too
    o = client.post("/api/payments/order", json={"product": "order_advance", "rfq_id": rid}).json()
    client.post("/api/payments/verify", json=pay(o["order_id"]))
    mine = next(x for x in client.get("/api/supplier/B/orders").json()["orders"] if x["rfq_id"] == rid)
    assert "575" in mine["payment"] and mine["payment_status"] == "advance_paid"


def test_an_advance_needs_a_decided_order_that_is_yours_and_is_paid_only_once(razor):
    as_user("rz-guard")
    open_rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 10, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    assert client.post("/api/payments/order", json={"product": "order_advance", "rfq_id": open_rid}).status_code == 409
    rid = decided_order("rz-once")
    o = client.post("/api/payments/order", json={"product": "order_advance", "rfq_id": rid}).json()
    client.post("/api/payments/verify", json=pay(o["order_id"]))
    assert client.post("/api/payments/order", json={"product": "order_advance", "rfq_id": rid}).status_code == 409
    as_user("rz-other")
    assert client.post("/api/payments/order", json={"product": "order_advance", "rfq_id": rid}).status_code == 404
    assert client.post(f"/api/rfqs/{rid}/payment", json={"method": "cod"}).status_code == 404


def test_cod_cannot_replace_an_advance_already_paid(razor):
    rid = decided_order("rz-lock")
    o = client.post("/api/payments/order", json={"product": "order_advance", "rfq_id": rid}).json()
    client.post("/api/payments/verify", json=pay(o["order_id"]))
    assert client.post(f"/api/rfqs/{rid}/payment", json={"method": "cod"}).status_code == 409
