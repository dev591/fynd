import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.auth import get_current_user
from app.main import app, store

client = TestClient(app)
SECRET = "test-secret-not-a-real-one-0123456789abcdef"


def b64(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode()


def token(sub="user-1", email="u1@test.dev", secret=SECRET, exp=3600, alg="HS256", aud="authenticated", **extra):
    header = b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    claims = {"sub": sub, "email": email, "aud": aud, "exp": int(time.time()) + exp, **extra}
    claims = {k: v for k, v in claims.items() if v is not None}
    body = b64(json.dumps(claims).encode())
    sig = b64(hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()) if alg != "none" else ""
    return f"{header}.{body}.{sig}"


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(autouse=True)
def real_auth(monkeypatch):
    """Undo the suite-wide fake user: these tests use real signed tokens."""
    app.dependency_overrides.pop(get_current_user, None)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    auth._remote_cache.clear()


# ─── who gets in ────────────────────────────────────────────────────────────

def test_no_token_or_garbage_is_401():
    assert client.get("/api/rfqs").status_code == 401
    assert client.get("/api/rfqs", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/api/rfqs", headers=hdr("not.a.jwt-at-all-but-long-enough")).status_code == 401


def test_valid_token_gets_in_and_identity_comes_from_the_token():
    me = client.get("/api/me", headers=hdr(token(sub="abc-123", email="a@b.in"))).json()
    assert me["user"] == {"id": "abc-123", "email": "a@b.in"} and me["profile"] is None


@pytest.mark.parametrize("bad", [
    lambda: token(exp=-10),                                  # expired
    lambda: token(secret="a-different-secret-entirely"),     # signed with the wrong key
    lambda: token(alg="none"),                               # unsigned token, classic forgery
    lambda: token(aud="somebody-else"),                      # not for logged-in users
    lambda: token(sub=None),                                 # no user
])
def test_forged_expired_or_wrong_tokens_are_rejected(bad):
    assert client.get("/api/rfqs", headers=hdr(bad())).status_code == 401


def test_tampered_payload_is_rejected():
    head, body, sig = token(sub="victim").split(".")
    evil = b64(json.dumps({"sub": "admin", "aud": "authenticated", "exp": int(time.time()) + 999}).encode())
    assert client.get("/api/rfqs", headers=hdr(f"{head}.{evil}.{sig}")).status_code == 401


def test_unconfigured_server_refuses_instead_of_letting_everyone_in(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    r = client.get("/api/rfqs", headers=hdr(token()))
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_public_routes_need_no_login():
    assert client.get("/health").status_code == 200
    assert client.get("/api/case-checks").status_code == 200
    assert client.get("/api/share/shr_nope").status_code == 404          # reachable, just not found
    assert client.get("/api/rfq-by-token/tok_supplier_a").status_code == 200   # invite links stay open


# ─── remote verification (no secret configured) ─────────────────────────────

def test_remote_verification_asks_supabase_and_caches(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co/")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-public-key")
    calls = []

    class R:
        status_code = 200
        def json(self): return {"id": "remote-user", "email": "r@x.in"}

    def fake_get(url, timeout=None, headers=None):
        calls.append((url, headers))
        return R()

    monkeypatch.setattr(auth.httpx, "get", fake_get)
    tok = "header.payload.sig-long-enough-for-the-length-check"
    for _ in range(3):
        me = client.get("/api/me", headers=hdr(tok)).json()
    assert me["user"]["id"] == "remote-user"
    assert len(calls) == 1                                           # polling does not hammer Supabase
    assert calls[0][0] == "https://proj.supabase.co/auth/v1/user"
    assert calls[0][1] == {"apikey": "anon-public-key", "Authorization": f"Bearer {tok}"}


def test_remote_rejection_is_401(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "k")

    class R:
        status_code = 401
        def json(self): return {}

    monkeypatch.setattr(auth.httpx, "get", lambda *a, **k: R())
    assert client.get("/api/rfqs", headers=hdr("header.payload.sig-long-enough-for-the-length")).status_code == 401


def test_bad_hs256_signature_never_falls_through_to_the_network(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "k")
    monkeypatch.setattr(auth.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    assert client.get("/api/rfqs", headers=hdr(token(secret="wrong-secret-here"))).status_code == 401


# ─── nobody sees anybody else's data ────────────────────────────────────────

def _become_seller(tok, company="Other Co"):
    client.post("/api/profile", headers=hdr(tok), json={
        "id": "x", "role": "supplier", "full_name": "S", "email": "e@x.in", "phone": "9820144556",
        "company": company, "business_type": "trader", "state": "Gujarat", "city": "Surat"})


def _new_rfq(tok, item="M10 bolt"):
    return client.post("/api/rfqs", headers=hdr(tok), json={
        "item": item, "qty": 100, "need_in_days": 5, "buyer_company": "Co", "buyer_name": "B"}).json()["id"]


def test_buyers_cannot_see_or_touch_each_others_requests():
    alice, bob = token(sub="alice"), token(sub="bob")
    rid = _new_rfq(alice)
    assert client.get(f"/api/rfqs/{rid}", headers=hdr(alice)).status_code == 200
    assert rid in [r["id"] for r in client.get("/api/rfqs", headers=hdr(alice)).json()]
    assert rid not in [r["id"] for r in client.get("/api/rfqs", headers=hdr(bob)).json()]
    for method, path, body in [
        ("get", f"/api/rfqs/{rid}", None),
        ("get", f"/api/rfqs/{rid}/summary", None),
        ("get", f"/api/rfqs/{rid}/activity", None),
        ("get", f"/api/rfqs/{rid}/ai-log", None),
        ("post", f"/api/rfqs/{rid}/share", {}),
        ("get", f"/api/rfqs/{rid}/threads/A/messages", None),
        ("get", f"/api/rfqs/{rid}/suppliers/A", None),
        ("post", f"/api/rfqs/{rid}/decision", {"winner_id": "A", "reason": "x", "approver": "Bob"}),
        ("post", f"/api/rfqs/{rid}/targets", {"supplier_id": "A", "cut_needed": 1, "sent_by": "Bob"}),
        ("post", f"/api/rfqs/{rid}/threads/A/messages", {"sender": "buyer", "sender_name": "Bob", "text": "hi"}),
    ]:
        r = getattr(client, method)(path, headers=hdr(bob), **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, path, r.status_code)


def test_shared_demo_request_is_visible_to_everyone_signed_in():
    assert "rfq_c27_01" in [r["id"] for r in client.get("/api/rfqs", headers=hdr(token(sub="newcomer"))).json()]


def test_savings_only_count_your_own_decisions():
    alice, bob = token(sub="alice2"), token(sub="bob2")
    before = client.get("/api/savings", headers=hdr(bob)).json()
    rid = _new_rfq(alice)
    toks = client.get(f"/api/rfqs/{rid}", headers=hdr(alice)).json()["rfq"]["supplier_tokens"]
    for sid, price, freight in (("A", 10, 200), ("B", 11, 50)):
        client.post(f"/api/rfq-by-token/{toks[sid]}/quotes", json={
            "supplier_name": sid, "pack_price": price, "pack_size": 1, "freight": freight, "lead_days": 3})
    client.post(f"/api/rfqs/{rid}/decision", headers=hdr(alice), json={"winner_id": "B", "reason": "x", "approver": "Alice"})
    assert client.get("/api/savings", headers=hdr(alice)).json()["total"] >= 50
    assert client.get("/api/savings", headers=hdr(bob)).json() == before


def test_chat_sender_cannot_be_spoofed():
    alice = token(sub="alice3")
    res = client.post("/api/rfqs", headers=hdr(alice), json={
        "item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "C", "buyer_name": "B"}).json()
    rid, tk = res["id"], res["supplier_tokens"]["A"]
    m1 = client.post(f"/api/rfqs/{rid}/threads/A/messages", headers=hdr(alice),
                     json={"sender": "supplier", "sender_name": "Alice", "text": "from the buyer"}).json()
    m2 = client.post(f"/api/rfq-by-token/{tk}/messages",
                     json={"sender": "buyer", "sender_name": "Pretender", "text": "from the link"}).json()
    assert m1["sender"] == "buyer" and m2["sender"] == "supplier"


# ─── sellers and profiles ───────────────────────────────────────────────────

def test_profile_belongs_to_the_token_not_the_request_body():
    tok = token(sub="seller-xyz", email="real@seller.in")
    body = {"id": "someone-else", "role": "supplier", "full_name": "S", "email": "fake@x.in", "phone": "9820144556",
            "company": "Xyz Fasteners", "business_type": "trader", "state": "Maharashtra", "city": "Pune",
            "categories": ["fasteners"], "gstin": "27ABCDE1234F1Z5"}
    saved = client.post("/api/profile", headers=hdr(tok), json=body).json()
    assert saved["id"] == "seller-xyz" and saved["email"] == "real@seller.in"
    assert saved["pan_masked"] == "ABCDEXXXXF" and "pan" not in saved        # masked; no raw PAN field exists
    assert "someone-else" not in store.profiles
    me = client.get("/api/me", headers=hdr(tok)).json()
    assert me["supplier_id"] == "seller-xyz" and me["profile"]["company"] == "Xyz Fasteners"


def test_a_seller_owns_their_catalog_and_others_cannot_touch_it():
    owner, other = token(sub="seller-own"), token(sub="seller-other")
    _become_seller(other)                       # a different seller: the role is fine, the ownership is not
    client.post("/api/profile", headers=hdr(owner), json={
        "id": "x", "role": "supplier", "full_name": "S", "email": "e@x.in", "phone": "9820144556",
        "company": "Own Co", "business_type": "trader", "state": "Gujarat", "city": "Surat"})
    add = client.post("/api/supplier/products/seller-own", headers=hdr(owner), json={
        "name": "Brass Nut X", "pack_price": 5, "pack_size": 1, "stock": 10, "aliases": ["brass nut x"]})
    assert add.status_code == 201
    for method, path in [("get", "/api/supplier/products/seller-own"), ("get", "/api/supplier/seller-own/notifications"),
                         ("get", "/api/supplier/seller-own/autopilot"), ("get", "/api/supplier/profile/seller-own")]:
        assert getattr(client, method)(path, headers=hdr(other)).status_code == 404, path
        assert getattr(client, method)(path, headers=hdr(owner)).status_code == 200, path
    assert client.post("/api/supplier/products/seller-own", headers=hdr(other),
                       json={"name": "evil", "pack_price": 1, "pack_size": 1}).status_code == 404
    # the new seller is findable by matching, like any other
    client.post("/api/me/roles", headers=hdr(other), json={"role": "buyer"})
    rid = client.post("/api/rfqs", headers=hdr(other), json={
        "item": "brass nut x", "qty": 5, "need_in_days": 5, "buyer_company": "C", "buyer_name": "B"}).json()
    assert "seller-own" in rid["supplier_tokens"]
    inbox = client.get("/api/supplier/seller-own/notifications", headers=hdr(owner)).json()
    assert len(inbox) == 1 and inbox[0]["verdict"]["can_fulfil"] == "yes"


def test_seller_list_shows_own_plus_demo_and_demo_can_be_switched_off(monkeypatch):
    tok = token(sub="seller-list")
    client.post("/api/profile", headers=hdr(tok), json={
        "id": "x", "role": "supplier", "full_name": "S", "email": "e@x.in", "phone": "9820144556",
        "company": "List Co", "business_type": "trader", "state": "Gujarat", "city": "Surat"})
    ids = {s["supplier_id"] for s in client.get("/api/suppliers", headers=hdr(tok)).json()}
    assert "seller-list" in ids and "A" in ids
    nobody = token(sub="nobody")
    _become_seller(nobody)
    other = {s["supplier_id"] for s in client.get("/api/suppliers", headers=hdr(nobody)).json()}
    assert "seller-list" not in other and "A" in other
    monkeypatch.setenv("ALLOW_DEMO_SELLERS", "false")
    assert client.get("/api/supplier/A/notifications", headers=hdr(tok)).status_code == 404
    assert {s["supplier_id"] for s in client.get("/api/suppliers", headers=hdr(tok)).json()} == {"seller-list"}


def test_intake_and_old_pipeline_endpoints_need_login():
    assert client.post("/api/intake/draft", json={"text": "x"}).status_code == 401
    assert client.post("/api/intake/transcribe", content=b"1").status_code == 401
    assert client.post("/run", json={"query": "hi"}).status_code == 401
    assert client.get("/stats").status_code == 401
