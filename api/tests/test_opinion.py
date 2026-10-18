import pytest
from fastapi.testclient import TestClient

from app import summary
from app.main import app
from tests.helpers import tokens_of
from tests.test_summary import _decide

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    summary._explain_cache.clear()
    summary._opinion_cache.clear()
    yield
    summary._opinion_cache.clear()


def _request(note=None):
    """Seller 1: ₹1,200 landed, 3 days. Seller 2: ₹1,150, 4 days (the engine's cheapest pick). Seller 3 is late, so blocked."""
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "Co",
                                         "buyer_name": "B", "note": note}).json()["id"]
    t = tokens_of(rid)
    for sid, price, freight, lead in (("A", 10, 200, 3), ("B", 11, 50, 4), ("C", 400, 0, 7)):
        pack = 50 if sid == "C" else 1
        client.post(f"/api/rfq-by-token/{t[sid]}/quotes", json={"supplier_name": f"S{sid}", "pack_price": price, "pack_size": pack,
                                                               "freight": freight, "lead_days": lead})
    return rid


def _say(monkeypatch, pick, concern="none", phrase=""):
    monkeypatch.setattr(summary, "structured_call", lambda system, user, name, schema, *a, **k:
                        {"text": "Seller 2 wins at ₹1,150 landed."} if name == "selection_explainer"
                        else {"pick": pick, "concern": concern, "note_phrase": phrase})


def _opinion(rid):
    return client.get(f"/api/rfqs/{rid}/summary").json()["ai_opinion"]


def test_no_ai_means_no_opinion():
    assert _opinion(_request()) is None


def test_ai_agreeing_with_the_engine_gets_a_sentence_written_from_engine_numbers(monkeypatch):
    rid = _request()
    _say(monkeypatch, "Seller 2")
    o = _opinion(rid)
    assert o["agrees"] is True and o["pick"] == "Seller 2" and "not a calculation" in o["label"]
    assert o["reason"] == "Seller 2 is the best fit: ₹1,150 landed, arriving in 4 days."


def test_a_deadline_in_the_note_can_justify_the_faster_seller_and_the_sentence_is_exact(monkeypatch):
    rid = _request("our line stops on Friday, we cannot wait")
    _say(monkeypatch, "Seller 1", "deadline", "line stops on Friday")
    o = _opinion(rid)
    assert o["agrees"] is False and o["engine_pick"] == "Seller 2"
    assert o["reason"] == 'Your note says "line stops on Friday". Seller 1 costs ₹50 more than Seller 2 and arrives 1 day sooner.'
    assert client.get(f"/api/rfqs/{rid}/summary").json()["engine_winner"]["supplier"] == "Seller 2"     # the rules' pick is untouched


@pytest.mark.parametrize("note,pick,concern,phrase,why", [
    (None, "Seller 1", "none", "", "differs from the engine with no stated concern (the live model said Seller 1 was cheaper)"),
    ("cash is tight this month", "Seller 1", "cash", "cash is tight", "a cash concern picks the dearer seller (seen from the live model)"),
    ("need it fast", "Seller 1", "deadline", "need it yesterday", "quotes words that are not in the note"),
    ("need it fast", "Seller 1", "deadline", "", "no quote at all"),
    ("need it fast", "Seller 3", "deadline", "need it fast", "a seller the engine blocked"),
])
def test_unjustified_or_illogical_opinions_are_dropped(monkeypatch, note, pick, concern, phrase, why):
    rid = _request(note)
    _say(monkeypatch, pick, concern, phrase)
    assert _opinion(rid) is None, why


def test_a_deadline_concern_cannot_pick_a_slower_seller(monkeypatch):
    rid = _request("need it fast")
    _say(monkeypatch, "Seller 2", "deadline", "need it fast")        # Seller 2 is the engine pick: allowed (agree)
    assert _opinion(rid)["agrees"] is True
    summary._opinion_cache.clear()
    from app import summary as s
    engine = type("R", (), {"quote_id": "x", "landed": 1000.0, "lead_days": 3, "supplier": "Seller A"})()
    slower = type("R", (), {"quote_id": "y", "landed": 900.0, "lead_days": 5, "supplier": "Seller B"})()
    raw = {"pick": "Seller B", "concern": "deadline", "note_phrase": "need it fast"}
    assert s._build_opinion(raw, {"Seller A": engine, "Seller B": slower}, engine, "need it fast") is None


def test_opinion_is_not_shown_after_a_decision_or_on_the_shared_page(monkeypatch):
    rid = _request()
    _say(monkeypatch, "Seller 2")
    assert _opinion(rid) is not None
    _decide(rid)
    assert _opinion(rid) is None
    link = client.post(f"/api/rfqs/{rid}/share").json()["token"]
    assert client.get(f"/api/share/{link}").json().get("ai_opinion") is None


def test_opinion_is_logged_against_the_request(monkeypatch):
    rid = _request()
    _say(monkeypatch, "Seller 2")
    _opinion(rid)
    from app.main import store
    assert any(e["kind"] == "second_opinion" for e in store.ai_log_for(rid))
