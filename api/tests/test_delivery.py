"""After delivery the buyer records what happened. It is their own record: Crossover inspects nothing."""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_current_user
from app.main import app, store
from tests.helpers import quote, tokens_of

client = TestClient(app)
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 200).decode()


def _ordered(uid="d-buyer"):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=f"{uid}@t.test")
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    quote(client, rid, "A"); quote(client, rid, "B", price=11, freight=50)
    client.post(f"/api/rfqs/{rid}/quotes/Seller 2/reveal")
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Seller 2", "reason": "Lowest landed", "approver": "Me"})
    return rid


def test_delivery_can_only_be_recorded_after_the_order():
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="d-early", email="e@t.test")
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                         "buyer_company": "Co", "buyer_name": "B"}).json()["id"]
    r = client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": True, "on_time": True})
    assert r.status_code == 409


def test_a_delivery_record_is_saved_with_the_decision_and_shown_on_the_one_pager():
    rid = _ordered()
    r = client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": False, "on_time": True,
                                                       "note": "Two cartons were M8, not M10"})
    assert r.status_code == 200 and r.json()["delivery"]["matches_quote"] is False
    s = client.get(f"/api/rfqs/{rid}/summary").json()
    assert s["delivery"]["on_time"] is True and s["delivery"]["matches_quote"] is False
    assert s["delivery"]["note"].startswith("Two cartons") and s["delivery"]["recorded_at"]
    assert s["decision"]["delivery"]["matches_quote"] is False                      # on the decision record itself
    assert any(f["label"] == "Delivery matched the quote" and f["value"] == "No" and f["tag"] == "observed" for f in s["evidence"])
    assert "Crossover did not inspect" in s["delivery"]["disclaimer"]


def test_recording_again_replaces_the_record_and_both_questions_are_required():
    rid = _ordered("d-twice")
    assert client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": True}).status_code == 422
    assert client.post(f"/api/rfqs/{rid}/delivery", json={"on_time": True}).status_code == 422
    client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": False, "on_time": False})
    client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": True, "on_time": True})
    assert client.get(f"/api/rfqs/{rid}/summary").json()["delivery"]["matches_quote"] is True


def test_a_photo_is_stored_apart_from_the_record_and_only_its_owner_can_fetch_it():
    rid = _ordered("d-photo")
    r = client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": True, "on_time": True,
                    "media": {"name": "carton.png", "mime": "image/png", "data": PNG}})
    d = r.json()["delivery"]
    assert d["media"] == {"name": "carton.png", "mime": "image/png", "bytes": len(base64.b64decode(PNG))}
    assert PNG not in json.dumps(client.get(f"/api/rfqs/{rid}/summary").json())           # the record carries metadata only
    got = client.get(f"/api/rfqs/{rid}/delivery/media").json()
    assert got["mime"] == "image/png" and got["data"] == PNG
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="d-stranger", email="s@t.test")
    assert client.get(f"/api/rfqs/{rid}/delivery/media").status_code == 404
    assert client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": True, "on_time": True}).status_code == 404


@pytest.mark.parametrize("media,why", [
    ({"name": "x.exe", "mime": "application/x-msdownload", "data": PNG}, "type"),
    ({"name": "x.png", "mime": "image/png", "data": "not base64 !!"}, "base64"),
    ({"name": "big.png", "mime": "image/png", "data": base64.b64encode(b"0" * 3_000_000).decode()}, "size"),
])
def test_only_small_photos_and_videos_are_accepted(media, why):
    rid = _ordered(f"d-bad-{why}")
    r = client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": True, "on_time": True, "media": media})
    assert r.status_code == 422, why


def test_the_shared_page_shows_the_outcome_but_not_the_note_or_the_photo():
    rid = _ordered("d-share")
    client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": True, "on_time": False,
                "note": "Late by two days, ring 9123456780", "media": {"name": "a.png", "mime": "image/png", "data": PNG}})
    link = client.post(f"/api/rfqs/{rid}/share").json()
    app.dependency_overrides.pop(get_current_user, None)
    shared = client.get(f"/api/share/{link['token']}").json()
    assert shared["delivery"]["on_time"] is False and shared["delivery"]["matches_quote"] is True
    assert "note" not in shared["delivery"] and "media" not in shared["delivery"] and "9123456780" not in json.dumps(shared)


def test_delivery_survives_a_restart(tmp_path, monkeypatch):
    from app import persist
    from app.rfq_store import RFQStore
    monkeypatch.setenv("CROSSOVER_DB", str(tmp_path / "x.db"))
    persist._last.clear()
    rid = _ordered("d-persist")
    client.post(f"/api/rfqs/{rid}/delivery", json={"matches_quote": True, "on_time": True,
                "media": {"name": "a.png", "mime": "image/png", "data": PNG}})
    persist.save(store)
    fresh = RFQStore()
    assert persist.load(fresh) and fresh.rfqs[rid].decision["delivery"]["on_time"] is True and fresh.media[rid]["data"] == PNG
