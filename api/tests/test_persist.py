import sqlite3

import pytest

from app import persist
from app.models import Profile, RFQCreate
from app.rfq_store import RFQStore


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    monkeypatch.setenv("CROSSOVER_DB", str(path))
    persist._last.clear()
    return path


def _busy_store():
    """A store with a request, quotes, a reveal, a plan, a seller profile and chat, so a restart has a lot to lose."""
    s = RFQStore()
    s.register_profile("buyer-1", Profile(id="x", role="buyer", full_name="Ramesh", email="r@x.in", phone="9820144556",
                       company="FanWorks", business_type="manufacturer", state="Telangana", city="Hyderabad"))
    s.register_profile("seller-1", Profile(id="x", role="supplier", full_name="Suresh", email="s@x.in", phone="9819022334",
                       company="Bolt Co", business_type="trader", state="Gujarat", city="Surat"))
    rfq = s.create_rfq(RFQCreate(item="M10 bolt", qty=100, need_in_days=5, buyer_company="FanWorks", buyer_name="Ramesh",
                                 priority_mode="fastest", source="voice"), owner_id="buyer-1")
    tok = rfq.supplier_tokens
    s.submit_quote(tok["A"], "A", 10, 1, 200, 3, notes="first")
    s.submit_quote(tok["A"], "A", 10, 1, 150, 3, notes="revised")
    s.submit_quote(tok["B"], "B", 11, 1, 50, 3)
    s.send_target(rfq.id, "A", 51, target_freight=149, sent_by="Ramesh")
    s.add_chat_message(rfq.id, "A", "buyer", "Ramesh", "Can you do better?")
    s.reveal(rfq.id, "A", "buyer-1")
    s.plans["buyer-1"] = "pro"
    s.save_decision(rfq.id, "Seller 1", "cheapest", "Ramesh")
    s.create_share(rfq.id)
    return s, rfq


def test_everything_survives_a_restart(db):
    a, rfq = _busy_store()
    assert persist.save(a) > 0
    b = RFQStore()                                  # a fresh process: only the seed
    assert rfq.id not in b.rfqs
    assert persist.load(b) is True
    r = b.rfqs[rfq.id]
    assert (r.owner_id, r.priority_mode, r.source, r.status) == ("buyer-1", "fastest", "voice", "Decided")
    assert [q.freight for q in b.quotes[rfq.id]["A"]] == [200, 150] and b.quotes[rfq.id]["B"][0].landed_cost == 1150
    assert b.aliases[rfq.id] == {"A": "Seller 1", "B": "Seller 2"}                  # aliases stay stable
    assert b.is_revealed(rfq.id, "A") and not b.is_revealed(rfq.id, "B")
    assert b.reveal_log[-1]["kind"] == "free" and b.plans["buyer-1"] == "pro"      # revealed before the upgrade
    assert b.targets[rfq.id]["A"].sent_by == "Ramesh" and any(m.text == "Can you do better?" for m in b.get_chat_messages(rfq.id, "A"))
    assert b.decisions[rfq.id]["winner_id"] == "Seller 1" and b.shares
    assert b.roles_for("seller-1") == ["seller"] and b.supplier_owner["seller-1"] == "seller-1"
    assert b.supplier_profiles["seller-1"].phone == "9819022334"
    assert any(n.rfq_id == rfq.id for n in b.notifications["A"])
    # and it still behaves: the decided request stays closed to revisions after the restart
    with pytest.raises(ValueError, match="closed or decided"):
        b.submit_quote(b.rfqs[rfq.id].supplier_tokens["B"], "B", 11, 1, 40, 3)


def test_unchanged_state_is_not_rewritten_and_changes_are_picked_up(db):
    s, rfq = _busy_store()
    assert persist.save(s) > 5
    assert persist.save(s) == 0                                                      # nothing changed, nothing written
    s.plans["buyer-1"] = "free"
    assert persist.save(s) == 1                                                      # only that collection
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"        # WAL, as the brief asks
    assert conn.execute("SELECT count(*) FROM state").fetchone()[0] == len(persist.FIELDS)
    conn.close()


def test_first_run_seeds_then_later_runs_load(db, monkeypatch):
    monkeypatch.setenv("PERSIST", "on")
    first = RFQStore()
    assert persist.init(first) == "seeded" and db.exists()
    first.plans["someone"] = "pro"
    persist.save(first)
    second = RFQStore()
    assert persist.init(second) == "loaded" and second.plans["someone"] == "pro"


def test_a_corrupt_file_is_set_aside_and_the_app_starts_from_the_seed(db, monkeypatch):
    monkeypatch.setenv("PERSIST", "on")
    db.write_bytes(b"this is not a sqlite database at all")
    s = RFQStore()
    assert persist.init(s) == "seeded"                                               # did not crash
    assert any(p.name.startswith("app.bad-") for p in db.parent.iterdir())           # the broken file was kept for a look
    assert "A" in s.supplier_profiles


def test_persistence_can_be_switched_off(db, monkeypatch):
    monkeypatch.setenv("PERSIST", "off")
    assert persist.enabled() is False and persist.init(RFQStore()) == "off" and not db.exists()


def test_reset_removes_the_database_files(db, monkeypatch):
    s, _ = _busy_store()
    persist.save(s)
    assert db.exists()
    import runpy
    runpy.run_module("app.reset", run_name="__main__")
    assert not db.exists() and not (db.parent / (db.name + "-wal")).exists()


def test_the_api_saves_after_changes_and_a_new_process_sees_them(db, monkeypatch):
    """End to end through HTTP: create a request, 'restart' by loading into a fresh store."""
    from fastapi.testclient import TestClient
    from app.main import app, store
    monkeypatch.setenv("PERSIST", "on")
    client = TestClient(app)
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Persist Co", "buyer_name": "P"}).json()["id"]
    fresh = RFQStore()
    assert persist.load(fresh, db) is True
    assert fresh.rfqs[rid].buyer_company == "Persist Co"
