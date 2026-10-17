"""Quote windows, buyer notifications and seller reminders. The clock is injected so nothing here waits."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app, store
from tests.helpers import alias, quote, tokens_of

client = TestClient(app)
T0 = datetime(2026, 10, 18, 9, 0, 0)


@pytest.fixture(autouse=True)
def clock():
    """Time stands still at T0 until a test moves it."""
    now = {"t": T0}
    old = store.clock
    store.clock = lambda: now["t"]
    yield now
    store.clock = old


def buyer(uid):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=f"{uid}@t.test")


def new_rfq(uid, **extra):
    buyer(uid)
    return client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                          "buyer_company": "Co", "buyer_name": "B", **extra}).json()["id"]


def notices(uid):
    buyer(uid)
    return client.get("/api/me/notices").json()


# ─── the window itself ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("window,minutes", [("15m", 15), ("24h", 24 * 60), ("3d", 3 * 24 * 60)])
def test_window_lengths(window, minutes):
    rid = new_rfq(f"w-{window}", window=window)
    r = store.rfqs[rid]
    assert datetime.fromisoformat(r.window_ends_at) - T0 == timedelta(minutes=minutes) and r.window_label


def test_today_closes_at_the_end_of_today_but_never_in_under_fifteen_minutes(clock):
    rid = new_rfq("w-today", window="today")
    assert datetime.fromisoformat(store.rfqs[rid].window_ends_at) == datetime(2026, 10, 18, 23, 59, 59)
    clock["t"] = datetime(2026, 10, 18, 23, 55, 0)
    rid2 = new_rfq("w-today-late", window="today")
    assert datetime.fromisoformat(store.rfqs[rid2].window_ends_at) - clock["t"] >= timedelta(minutes=15)


@pytest.mark.parametrize("mode,expected", [("fastest", "15m"), ("balanced", "today"), ("cheapest", "24h")])
def test_default_window_follows_the_priority(mode, expected):
    rid = new_rfq(f"w-{mode}", priority_mode=mode)
    assert store.rfqs[rid].window_key == expected


def test_demo_timing_shortens_every_window_and_says_so(monkeypatch):
    monkeypatch.setenv("DEMO_WINDOW_MINUTES", "2")
    rid = new_rfq("w-demo", window="3d")
    r = store.rfqs[rid]
    assert datetime.fromisoformat(r.window_ends_at) - T0 == timedelta(minutes=2)
    assert r.demo_timing is True and "demo" in r.window_label.lower()
    shown = client.get(f"/api/rfqs/{rid}").json()["rfq"]
    assert shown["demo_timing"] is True and shown["window_ends_at"]


# ─── buyer notifications ────────────────────────────────────────────────────────

def test_first_quote_and_enough_quotes_notify_the_buyer_once_each():
    rid = new_rfq("n-buyer", window="24h")
    assert notices("n-buyer") == {"notices": [], "unread": 0}
    quote(client, rid, "A")
    n = notices("n-buyer")
    assert [x["kind"] for x in n["notices"]] == ["first_quote"] and n["unread"] == 1
    quote(client, rid, "A", freight=150)                                  # a revision is not a new quote
    quote(client, rid, "B", price=11, freight=50)
    assert [x["kind"] for x in notices("n-buyer")["notices"]] == ["first_quote"]
    quote(client, rid, "E", price=10.8, freight=120)                       # third distinct seller = enough
    kinds = [x["kind"] for x in notices("n-buyer")["notices"]]
    assert kinds == ["enough_quotes", "first_quote"]                       # newest first
    quote(client, rid, "A", freight=100)
    assert len(notices("n-buyer")["notices"]) == 2                         # nothing repeated


def test_notices_name_sellers_only_by_alias():
    rid = new_rfq("n-alias", window="24h")
    quote(client, rid, "A"); quote(client, rid, "B", price=11, freight=50); quote(client, rid, "E", price=10.8, freight=120)
    text = " ".join(x["message"] for x in notices("n-alias")["notices"])
    for leak in ("Bolt Express", "Pune Hardware", "Thane", "Mumbai", "synthetic-demo"):
        assert leak not in text


def test_notices_are_private_and_can_be_marked_read():
    rid = new_rfq("n-own", window="24h")
    quote(client, rid, "A")
    nid = notices("n-own")["notices"][0]["id"]
    assert notices("n-stranger") == {"notices": [], "unread": 0}
    buyer("n-stranger")
    assert client.post(f"/api/me/notices/{nid}/read").status_code == 404
    buyer("n-own")
    assert client.post(f"/api/me/notices/{nid}/read").json()["unread"] == 0
    quote(client, rid, "B", price=11, freight=50); quote(client, rid, "E", price=10.8, freight=120)
    assert notices("n-own")["unread"] == 1
    assert client.post("/api/me/notices/read-all").json()["unread"] == 0


# ─── closing ─────────────────────────────────────────────────────────────────────

def test_closing_tells_the_buyer_the_best_option_and_asks_to_confirm(clock):
    rid = new_rfq("c-buyer", window="15m")
    quote(client, rid, "A"); quote(client, rid, "B", price=11, freight=50)
    clock["t"] = T0 + timedelta(minutes=14)
    store.tick()
    assert not store.rfqs[rid].window_closed
    clock["t"] = T0 + timedelta(minutes=15, seconds=1)
    assert store.tick() >= 1
    assert store.rfqs[rid].window_closed
    closed = [x for x in notices("c-buyer")["notices"] if x["kind"] == "window_closed"]
    assert len(closed) == 1 and "Seller 2" in closed[0]["message"] and "1,150" in closed[0]["message"] and "Confirm" in closed[0]["message"]
    store.tick()
    assert len([x for x in notices("c-buyer")["notices"] if x["kind"] == "window_closed"]) == 1      # once


def test_closing_with_no_quotes_says_so(clock):
    rid = new_rfq("c-empty", window="15m")
    clock["t"] = T0 + timedelta(minutes=16)
    store.tick()
    msg = [x for x in notices("c-empty")["notices"] if x["kind"] == "window_closed"][0]["message"]
    assert "no" in msg.lower() and "quote" in msg.lower()


def test_after_close_new_sellers_cannot_start_but_quoted_sellers_can_revise_and_the_buyer_can_decide(clock):
    rid = new_rfq("c-rules", window="15m")
    quote(client, rid, "A"); quote(client, rid, "B", price=11, freight=50)
    clock["t"] = T0 + timedelta(minutes=20)
    store.tick()
    late = quote(client, rid, "E", price=9, freight=0)
    assert late.status_code == 400 and "closed" in late.json()["detail"].lower()
    assert quote(client, rid, "A", freight=100).status_code == 200         # a revision (the negotiation loop) still works
    buyer("c-rules")
    client.post(f"/api/rfqs/{rid}/quotes/Seller 1/reveal")
    assert client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 1", "reason": "x", "approver": "Me"}).status_code == 200


# ─── seller reminders ────────────────────────────────────────────────────────────

def _inbox(sid, rid):
    buyer("u_test")
    return next(n for n in client.get(f"/api/supplier/{sid}/notifications").json() if n["rfq_id"] == rid)


def test_sellers_who_have_not_answered_are_reminded_halfway_and_before_close(clock):
    rid = new_rfq("r-sellers", window="24h")
    quote(client, rid, "A")                                                # A answers; B does not
    client.post(f"/api/rfq-by-token/{tokens_of(rid)['C']}/decline", json={})   # C declines: also an answer
    assert _inbox("B", rid)["reminder"] is None
    clock["t"] = T0 + timedelta(hours=11)
    store.tick()
    assert _inbox("B", rid)["reminder"] is None                            # not halfway yet
    clock["t"] = T0 + timedelta(hours=12, minutes=1)
    store.tick()
    b = _inbox("B", rid)
    assert b["reminder"] and "halfway" in b["reminder"].lower() and b["closes_at"]
    assert _inbox("A", rid)["reminder"] is None and _inbox("C", rid)["reminder"] is None
    clock["t"] = T0 + timedelta(hours=23, minutes=46)
    store.tick()
    assert "15 minutes" in _inbox("B", rid)["reminder"]
    assert _inbox("A", rid)["reminder"] is None


def test_reminders_fire_once_and_opening_the_request_clears_them(clock):
    rid = new_rfq("r-once", window="24h")
    clock["t"] = T0 + timedelta(hours=13)
    first = store.tick()
    assert first >= 1 and store.tick() == 0                                # idempotent: nothing new on the next tick
    assert _inbox("B", rid)["reminder"]
    client.get(f"/api/rfq-by-token/{tokens_of(rid)['B']}")                 # the seller opens their link
    assert _inbox("B", rid)["reminder"] is None
    clock["t"] = T0 + timedelta(hours=14)
    store.tick()
    assert _inbox("B", rid)["reminder"] is None                            # not reminded about the same moment again


def test_short_windows_get_a_halfway_reminder_only(clock):
    rid = new_rfq("r-short", window="15m")
    clock["t"] = T0 + timedelta(minutes=8)
    store.tick()
    assert "halfway" in _inbox("B", rid)["reminder"].lower()
    client.get(f"/api/rfq-by-token/{tokens_of(rid)['B']}")
    clock["t"] = T0 + timedelta(minutes=14)                                # inside the last 15 minutes by definition
    store.tick()
    assert _inbox("B", rid)["reminder"] is None


def test_decided_requests_stop_generating_events(clock):
    rid = new_rfq("r-done", window="24h")
    quote(client, rid, "A")
    buyer("r-done")
    client.post(f"/api/rfqs/{rid}/quotes/Seller 1/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 1", "reason": "x", "approver": "Me"})
    before = len(notices("r-done")["notices"])
    clock["t"] = T0 + timedelta(days=2)
    store.tick()
    assert len(notices("r-done")["notices"]) == before and not store.rfqs[rid].window_closed
