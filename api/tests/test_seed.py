from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app
from app.rfq_store import RFQStore
from tests.helpers import tokens_of

client = TestClient(app)


def test_last_order_uses_labelled_synthetic_history_then_the_buyers_own_order():
    from urllib.parse import quote as q
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="fresh-buyer-seed", email="f@t.test")   # no orders yet
    r = client.get(f"/api/items/{q('M10 bolt')}/last-order").json()
    assert r["last"]["source"] == "synthetic_history" and "Synthetic" in r["last"]["label"]
    assert (r["last"]["qty"], r["last"]["landed"]) == (100, 1320)
    assert r["today"]["landed"] == 1150 and r["difference"] == 170                  # B is cheapest today within 5 days
    assert "seller" not in str(r["today"]).lower().replace("sellers_checked", "")  # numbers only: nobody is named
    assert client.get(f"/api/items/{q('no such thing')}/last-order").json()["today"] is None

    # once this buyer has decided an order for the item, their own order replaces the synthetic one
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    for sid, price, fr in (("A", 10, 200), ("B", 11, 50)):
        client.post(f"/api/rfq-by-token/{tokens_of(rid)[sid]}/quotes", json={
            "supplier_name": sid, "pack_price": price, "pack_size": 1, "freight": fr, "lead_days": 3})
    client.post(f"/api/rfqs/{rid}/quotes/Seller 2/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 2", "reason": "x", "approver": "A"})
    mine = client.get(f"/api/items/{q('M10 bolt')}/last-order").json()
    assert mine["last"]["source"] == "your_last_order" and mine["last"]["landed"] == 1150
    assert mine["difference"] == 0                                                   # nothing cheaper today


def test_demo_autopilot_can_be_on_so_quotes_arrive_in_seconds(monkeypatch):
    monkeypatch.setenv("DEMO_AUTOPILOT", "on")
    store = RFQStore()
    assert sum(1 for s in store.autopilot.values() if s.enabled) >= 8              # about 8 sellers on autopilot
    from app.models import RFQCreate
    rfq = store.create_rfq(RFQCreate(item="M10 bolt", qty=100, need_in_days=5, buyer_company="c", buyer_name="b"), owner_id="u")
    quoted = store.quotes[rfq.id]
    assert {"A", "B", "E"} <= set(quoted)                                           # clean 'yes' verdicts answered at once
    assert "C" not in quoted and "D" not in quoted                                   # too slow / out of stock stay for a person
    assert all(v[-1].origin == "auto" for v in quoted.values())
    assert list(store.aliases[rfq.id].values()) == [f"Seller {i}" for i in range(1, len(quoted) + 1)]


def test_demo_autopilot_off_means_nobody_answers_alone(monkeypatch):
    monkeypatch.setenv("DEMO_AUTOPILOT", "off")
    assert not any(s.enabled for s in RFQStore().autopilot.values())


def test_seed_is_synthetic_and_covers_three_categories():
    store = RFQStore()
    demo = [p for p in store.supplier_profiles.values() if p.synthetic]
    assert len(demo) >= 8 and all(p.contact_name and "synthetic" in p.contact_name for p in demo)
    cats = {c for p in demo for c in p.categories}
    assert {"fasteners", "packaging", "electricals"} <= cats
    assert all(h["synthetic"] for h in store.history)
