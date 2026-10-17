"""Section 5 of the v2 brief. If these fail, the product's promise is broken."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app, store

client = TestClient(app)

BUYER = dict(uid="anon-buyer", email="ramesh.private@buyerco.test", name="Ramesh Private", company="Private Buyer Works Pvt Ltd",
             phone="9876501234", city="Secunderabad")
SELLER_PHONE, SELLER_MAIL = "9123456780", "sales.private@sellerco.test"
NOTE = f"Call me on {SELLER_PHONE} or write {SELLER_MAIL} for a better rate"


def act_as(uid, email=None):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=email or f"{uid}@t.test")


def profile(role, **kw):
    return {"id": "x", "role": role, "full_name": kw.pop("full_name", "Some Person"), "email": kw.pop("email", "p@t.test"),
            "phone": kw.pop("phone", "9820144556"), "company": kw.pop("company", "Some Co"),
            "business_type": "manufacturer", "state": kw.pop("state", "Telangana"), "city": kw.pop("city", "Hyderabad"),
            "categories": ["fasteners"], **kw}


@pytest.fixture
def scene(monkeypatch):
    """A buyer with a distinctive identity, a request for M10 bolts, and quotes from two demo sellers with contact details in notes."""
    monkeypatch.setenv("FREE_REVEALS", "3")
    uid = f"{BUYER['uid']}-{len(store.rfqs)}"
    act_as(uid, BUYER["email"])
    client.post("/api/profile", json=profile("buyer", full_name=BUYER["name"], company=BUYER["company"], phone=BUYER["phone"],
                                             city=BUYER["city"]))
    created = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                             "buyer_company": BUYER["company"], "buyer_name": BUYER["name"],
                                             "buyer_city": BUYER["city"]}).json()
    rid = created["id"]
    tokens = dict(store.rfqs[rid].supplier_tokens)            # internal: only the test peeks at these
    for sid, price, freight in (("A", 10, 200), ("B", 11, 50)):
        r = client.post(f"/api/rfq-by-token/{tokens[sid]}/quotes", json={
            "supplier_name": store.supplier_profiles[sid].business_name, "pack_price": price, "pack_size": 1,
            "freight": freight, "lead_days": 3, "notes": NOTE})
        assert r.status_code == 200, r.text
    return {"uid": uid, "rid": rid, "tokens": tokens, "created": created}


def seller_identity_values(sids):
    """Everything that identifies these sellers. None of it may appear in a buyer response before reveal."""
    vals = set()
    for sid in sids:
        p = store.supplier_profiles[sid]
        vals |= {p.business_name, p.location_city, p.contact_name, p.phone, p.email, store.rfqs and sid}
    vals |= {SELLER_PHONE, SELLER_MAIL}
    return {v for v in vals if v and len(v) > 1}


def walk_strings(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            yield from walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_strings(v)
    elif isinstance(node, str):
        yield node


def assert_clean(payload, sids, where):
    blob = json.dumps(payload)
    for v in seller_identity_values(sids) - set(sids):
        assert v not in blob, f"{where} leaks {v!r}"
    ids = set(sids) | {store.supplier_owner.get(s) for s in sids if store.supplier_owner.get(s)}
    for s in walk_strings(payload):
        assert s not in ids, f"{where} exposes a seller id {s!r}"
    assert "tok_" not in blob, f"{where} exposes an invite token"
    assert "supplier_tokens" not in blob, f"{where} exposes supplier_tokens"
    assert not re.search(r"\d{5}\s?\d{5}", blob.replace(BUYER["phone"], "")), f"{where} contains a phone-like number"


def buyer_endpoints(scene, alias):
    rid = scene["rid"]
    return {
        "create response": scene["created"],
        "GET /api/rfqs": client.get("/api/rfqs").json(),
        "GET /api/rfqs/{id}": client.get(f"/api/rfqs/{rid}").json(),
        "GET summary": client.get(f"/api/rfqs/{rid}/summary").json(),
        "GET activity": client.get(f"/api/rfqs/{rid}/activity").json(),
        "GET ai-log": client.get(f"/api/rfqs/{rid}/ai-log").json(),
        "GET supplier click-through": client.get(f"/api/rfqs/{rid}/suppliers/{alias}").json(),
        "GET chat thread": client.get(f"/api/rfqs/{rid}/threads/{alias}/messages").json(),
        "GET savings": client.get("/api/savings").json(),
        "GET recommendations": client.get("/api/recommendations").json(),
    }


# ─── 1. the buyer sees no seller identity before reveal ─────────────────────────

def test_buyer_responses_hold_no_seller_identity_before_reveal(scene):
    sids = list(scene["tokens"])                       # every matched seller, quoted or not
    first_alias = next(iter(client.get(f"/api/rfqs/{scene['rid']}").json()["quotes"]))
    for where, payload in buyer_endpoints(scene, first_alias).items():
        assert_clean(payload, sids, where)


def test_aliases_are_stable_and_ordered_by_first_quote(scene):
    d = client.get(f"/api/rfqs/{scene['rid']}").json()
    assert list(d["quotes"]) == ["Seller 1", "Seller 2"]                      # A quoted first
    assert {r["quote_id"] for r in d["evaluation"]["rows"]} == {"Seller 1", "Seller 2"}
    assert d["evaluation"]["winner"]["supplier"] in ("Seller 1", "Seller 2")
    again = client.get(f"/api/rfqs/{scene['rid']}").json()
    assert list(again["quotes"]) == ["Seller 1", "Seller 2"]                   # stable on re-read
    # a revised quote keeps its alias; a third seller gets the next one
    client.post(f"/api/rfq-by-token/{scene['tokens']['A']}/quotes", json={"supplier_name": "x", "pack_price": 9, "pack_size": 1, "freight": 200, "lead_days": 3})
    client.post(f"/api/rfq-by-token/{scene['tokens']['C']}/quotes", json={"supplier_name": "x", "pack_price": 8, "pack_size": 50, "freight": 0, "lead_days": 7})
    after = client.get(f"/api/rfqs/{scene['rid']}").json()["quotes"]
    assert list(after) == ["Seller 1", "Seller 2", "Seller 3"] and len(after["Seller 1"]) == 2


def test_the_engine_decision_does_not_depend_on_who_the_seller_is(scene):
    d = client.get(f"/api/rfqs/{scene['rid']}").json()["evaluation"]
    landed = {r["supplier"]: r["landed"] for r in d["rows"]}
    assert landed == {"Seller 1": 1200, "Seller 2": 1150} and d["winner"]["supplier"] == "Seller 2"


def test_buyer_cannot_target_or_chat_by_real_seller_id(scene):
    rid = scene["rid"]
    assert client.post(f"/api/rfqs/{rid}/targets", json={"supplier_id": "A", "cut_needed": 1, "sent_by": "Me"}).status_code == 404
    assert client.get(f"/api/rfqs/{rid}/suppliers/A").status_code == 404
    assert client.get(f"/api/rfqs/{rid}/threads/A/messages").status_code == 404
    ok = client.post(f"/api/rfqs/{rid}/targets", json={"supplier_id": "Seller 1", "cut_needed": 51, "target_freight": 149,
                                                       "concession_type": "freight", "sent_by": BUYER["name"]})
    assert ok.status_code == 200 and ok.json()["supplier_id"] == "Seller 1"


# ─── 2. notes are scrubbed until reveal ─────────────────────────────────────────

def test_phone_numbers_and_emails_in_seller_notes_are_scrubbed_until_reveal(scene):
    quotes = client.get(f"/api/rfqs/{scene['rid']}").json()["quotes"]
    note = quotes["Seller 1"][0]["notes"]
    assert SELLER_PHONE not in note and SELLER_MAIL not in note and "better rate" in note
    client.post(f"/api/rfqs/{scene['rid']}/quotes/Seller 1/reveal")
    revealed = client.get(f"/api/rfqs/{scene['rid']}").json()["quotes"]["Seller 1"][0]["notes"]
    assert SELLER_PHONE in revealed and SELLER_MAIL in revealed                # raw text comes back after reveal
    assert SELLER_PHONE not in client.get(f"/api/rfqs/{scene['rid']}").json()["quotes"]["Seller 2"][0]["notes"]


def test_scrubber_catches_common_formats_and_spares_prices():
    from app.masking import scrub
    for s in ["call +91 98765 43210 now", "9876543210", "98765-43210", "(040) 2345 6789", "wa +44 7700 900123", "a.b+c@mail.co.in"]:
        assert "[hidden" in scrub(s), s
    for s in ["total ₹1,20,000 for 100 units", "lead 3 days, MOQ 50, freight 200", "M10 x 1.5 grade 8.8", "1150"]:
        assert scrub(s) == s, s


# ─── 3. reveal and the quota ────────────────────────────────────────────────────

def reveal(scene, alias):
    return client.post(f"/api/rfqs/{scene['rid']}/quotes/{alias}/reveal")


def test_reveal_unlocks_identity_and_consumes_exactly_one_free_reveal(scene):
    before = client.get("/api/me/plan").json()
    assert before == {"plan": "free", "free_limit": 3, "reveals_left": 3}
    r = reveal(scene, "Seller 1")
    assert r.status_code == 200
    ident = r.json()["seller"]
    assert ident["business_name"] == store.supplier_profiles["A"].business_name and ident["phone"] and ident["email"]
    assert client.get("/api/me/plan").json()["reveals_left"] == 2
    again = reveal(scene, "Seller 1")                                          # idempotent: same pair
    assert again.status_code == 200 and again.json()["seller"] == ident
    assert client.get("/api/me/plan").json()["reveals_left"] == 2
    assert reveal(scene, "Seller 2").status_code == 200
    assert client.get("/api/me/plan").json()["reveals_left"] == 1


def test_revealed_seller_is_free_on_the_buyers_next_request(scene):
    reveal(scene, "Seller 1")
    left = client.get("/api/me/plan").json()["reveals_left"]
    r2 = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 50, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()
    client.post(f"/api/rfq-by-token/{store.rfqs[r2['id']].supplier_tokens['A']}/quotes",
                json={"supplier_name": "x", "pack_price": 10, "pack_size": 1, "freight": 100, "lead_days": 3})
    ok = client.post(f"/api/rfqs/{r2['id']}/quotes/Seller 1/reveal")
    assert ok.status_code == 200 and client.get("/api/me/plan").json()["reveals_left"] == left


def test_no_reveals_left_returns_402_and_no_identity(scene, monkeypatch):
    monkeypatch.setenv("FREE_REVEALS", "1")
    assert reveal(scene, "Seller 1").status_code == 200
    blocked = reveal(scene, "Seller 2")
    assert blocked.status_code == 402 and blocked.json()["code"] == "reveals_exhausted"
    assert_clean(blocked.json(), ["B"], "402 body")
    d = client.get(f"/api/rfqs/{scene['rid']}").json()
    assert "Seller 2" not in d["revealed"]
    assert store.supplier_profiles["B"].business_name not in json.dumps(d)


def test_mock_upgrade_unlocks_unlimited_reveals_and_is_labelled_dev(scene, monkeypatch):
    monkeypatch.setenv("FREE_REVEALS", "0")
    assert reveal(scene, "Seller 1").status_code == 402
    up = client.post("/api/dev/mock-upgrade").json()
    assert up["plan"] == "pro" and "mock" in up["note"].lower()
    assert reveal(scene, "Seller 1").status_code == 200 and reveal(scene, "Seller 2").status_code == 200
    assert client.get("/api/me/plan").json()["plan"] == "pro"


def test_reveal_is_buyer_only_and_owner_only(scene):
    act_as("someone-else")
    assert client.post(f"/api/rfqs/{scene['rid']}/quotes/Seller 1/reveal").status_code == 404
    act_as(scene["uid"])
    assert reveal(scene, "Seller 9").status_code == 404                         # no such alias
    log = [e for e in store.reveal_log if e["rfq_id"] == scene["rid"]]
    assert log == []                                                            # nothing logged for failed attempts


def test_every_reveal_is_logged(scene):
    reveal(scene, "Seller 1"); reveal(scene, "Seller 1"); reveal(scene, "Seller 2")
    log = [e for e in store.reveal_log if e["rfq_id"] == scene["rid"]]
    assert [(e["alias"], e["kind"]) for e in log] == [("Seller 1", "free"), ("Seller 2", "free")]
    assert {"buyer_id", "supplier_id", "rfq_id", "at"} <= set(log[0])


# ─── 4. order handoff needs a reveal; shared page never carries identity ────────

def test_saving_a_decision_needs_the_winner_to_be_revealed(scene):
    rid = scene["rid"]
    body = {"winner_id": "Seller 2", "reason": "Lowest landed", "approver": BUYER["name"]}
    blocked = client.post(f"/api/rfqs/{rid}/decision", json=body)
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "reveal_required"
    reveal(scene, "Seller 2")
    ok = client.post(f"/api/rfqs/{rid}/decision", json=body)
    assert ok.status_code == 200 and "cash on delivery" in ok.json()["payment_note"].lower()


def test_shared_one_pager_never_carries_identity_even_after_reveal(scene):
    rid = scene["rid"]
    reveal(scene, "Seller 2")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 2", "reason": "x", "approver": BUYER["name"]})
    link = client.post(f"/api/rfqs/{rid}/share").json()
    app.dependency_overrides.pop(get_current_user, None)                       # a stranger with the link, not signed in
    shared = client.get(f"/api/share/{link['token']}").json()
    assert_clean(shared, ["A", "B"], "shared page")
    assert "Seller 2" in json.dumps(shared)


# ─── 5. sellers see no buyer identity before reveal ─────────────────────────────

def buyer_values():
    return {BUYER["email"], BUYER["name"], BUYER["company"], BUYER["phone"], BUYER["city"]}


def assert_no_buyer(payload, where):
    blob = json.dumps(payload)
    for v in buyer_values():
        assert v not in blob, f"{where} leaks the buyer: {v!r}"


def seller_views(scene, sid="A"):
    tok = scene["tokens"][sid]
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="demo-seller-acting", email="s@t.test")
    store.profiles["demo-seller-acting"] = store.profiles["u_test"]
    out = {
        "token request page": client.get(f"/api/rfq-by-token/{tok}").json(),
        "token my quotes": client.get(f"/api/rfq-by-token/{tok}/quotes/mine").json(),
        "token chat": client.get(f"/api/rfq-by-token/{tok}/messages").json(),
        "token assist": client.get(f"/api/rfq-by-token/{tok}/assist").json(),
        "inbox": [n for n in client.get(f"/api/supplier/{sid}/notifications").json() if n["rfq_id"] == scene["rid"]],
    }
    act_as(scene["uid"], BUYER["email"])
    return out


def test_seller_sees_buyer_only_as_a_descriptor_before_reveal(scene):
    rid = scene["rid"]
    # the buyer talks and negotiates, putting their name into every field they control
    client.post(f"/api/rfqs/{rid}/threads/Seller 1/messages", json={"sender": "buyer", "sender_name": BUYER["name"],
                "text": f"Reach me on {BUYER['phone']} / {BUYER['email']}, can you do better?"})
    client.post(f"/api/rfqs/{rid}/targets", json={"supplier_id": "Seller 1", "cut_needed": 51, "target_freight": 149,
                "concession_type": "freight", "sent_by": BUYER["name"], "message": f"Freight 149 please, ring {BUYER['phone']}"})
    views = seller_views(scene)
    for where, payload in views.items():
        assert_no_buyer(payload, where)
    page = views["token request page"]
    assert page["item"] == "M10 bolt" and page["qty"] == 100 and page["buyer_descriptor"] == "Manufacturer, Telangana"
    assert not any(k in page for k in ("buyer_company", "buyer_name", "buyer_city", "buyer_contact"))
    assert views["token my quotes"]["target"]["sent_by"] == "Buyer"
    assert views["inbox"][0]["buyer_descriptor"] == "Manufacturer, Telangana" and views["inbox"][0]["unlocked"] is False


def test_seller_gets_buyer_contact_and_a_notification_only_after_being_revealed(scene):
    rid = scene["rid"]
    reveal(scene, "Seller 1")
    note = next(n for n in store.notifications["A"] if n.rfq_id == rid)
    assert note.status == "new" and note.unlocked_at                         # the bell rings: "a buyer unlocked you"
    views = seller_views(scene, "A")
    page = views["token request page"]
    assert page["buyer_contact"]["company"] == BUYER["company"] and page["buyer_contact"]["phone"] == BUYER["phone"]
    inbox = views["inbox"][0]
    assert inbox["unlocked"] is True and inbox["buyer_contact"]["email"] == BUYER["email"]
    # the other seller, not revealed, still learns nothing
    for where, payload in seller_views(scene, "B").items():
        assert_no_buyer(payload, f"unrevealed seller / {where}")


# ─── found by the live rehearsal ────────────────────────────────────────────────

def test_buyer_location_comes_from_their_profile_not_a_hardcoded_default():
    act_as("loc-buyer")
    client.post("/api/profile", json=profile("buyer", state="Telangana", city="Hyderabad"))
    rid = client.post("/api/rfqs/confirm", json={"item": "M10 bolt", "qty": 10, "need_in_days": 5,
                      "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    r = client.get(f"/api/rfqs/{rid}").json()["rfq"]
    assert (r["buyer_city"], r["buyer_state"]) == ("Hyderabad", "Telangana")          # not Pune / Maharashtra
    assert "Pune" not in json.dumps(r)
    tok = store.rfqs[rid].supplier_tokens["A"]
    assert client.get(f"/api/rfq-by-token/{tok}").json()["buyer_descriptor"] == "Manufacturer, Telangana"


def test_a_buyer_with_no_profile_gets_no_invented_location():
    act_as("loc-noprofile")
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 10, "need_in_days": 5,
                      "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    r = client.get(f"/api/rfqs/{rid}").json()["rfq"]
    assert (r["buyer_city"], r["buyer_state"]) == ("", "")
    assert client.get(f"/api/rfq-by-token/{store.rfqs[rid].supplier_tokens['A']}").json()["buyer_descriptor"] == "Buyer"


def test_shared_page_hides_the_approvers_name_and_contact_details_in_the_reason(scene):
    rid = scene["rid"]
    reveal(scene, "Seller 2")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 2", "approver": BUYER["name"],
                "reason": f"Lowest landed, call me on {BUYER['phone']} or {BUYER['email']}"})
    link = client.post(f"/api/rfqs/{rid}/share").json()
    own = client.get(f"/api/rfqs/{rid}/summary").json()
    assert own["decision"]["approver"] == BUYER["name"]                              # the buyer still sees their own record
    app.dependency_overrides.pop(get_current_user, None)
    shared = client.get(f"/api/share/{link['token']}").json()
    blob = json.dumps(shared)
    for v in buyer_values():
        assert v not in blob, f"shared page leaks the buyer: {v!r}"
    assert shared["decision"]["reason"].startswith("Lowest landed") and shared["decision"]["approver"]
