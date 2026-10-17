import pytest
from fastapi.testclient import TestClient

from app import summary
from app.main import app
from tests.helpers import alias, tokens_of
from tests.test_summary import _decide

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    summary._explain_cache.clear()
    summary._opinion_cache.clear()
    yield
    summary._opinion_cache.clear()


def _request(note=None):
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "Co",
                                         "buyer_name": "B", "note": note}).json()["id"]
    t = tokens_of(rid)
    for sid, price, freight, lead in (("A", 10, 200, 3), ("B", 11, 50, 4), ("C", 400, 0, 7)):
        pack = 50 if sid == "C" else 1
        client.post(f"/api/rfq-by-token/{t[sid]}/quotes", json={"supplier_name": f"S{sid}", "pack_price": price, "pack_size": pack,
                                                               "freight": freight, "lead_days": lead})
    return rid


def _say(monkeypatch, pick, reason):
    monkeypatch.setattr(summary, "structured_call", lambda system, user, name, schema, *a, **k:
                        {"text": "Seller 2 wins at ₹1,150 landed."} if name == "selection_explainer" else {"pick": pick, "reason": reason})


def _opinion(rid):
    return client.get(f"/api/rfqs/{rid}/summary").json()["ai_opinion"]


def test_no_ai_means_no_opinion():
    assert _opinion(_request()) is None


def test_ai_can_agree_with_the_engine(monkeypatch):
    rid = _request()
    _say(monkeypatch, "Seller 2", "Seller 2 is the lowest at ₹1,150 landed and arrives in 4 days.")
    o = _opinion(rid)
    assert o["source"] == "ai" and o["agrees"] is True and o["pick"] == "Seller 2" and "not a calculation" in o["label"]


def test_ai_can_prefer_another_allowed_option_but_the_engine_pick_does_not_change(monkeypatch):
    rid = _request("need it before the weekend")
    _say(monkeypatch, "Seller 1", "Seller 1 costs ₹50 more at ₹1,200 but arrives 1 day sooner, 3 days against 4.")
    o = _opinion(rid)
    assert o["agrees"] is False and o["pick"] == "Seller 1" and o["engine_pick"] == "Seller 2"
    assert client.get(f"/api/rfqs/{rid}/summary").json()["engine_winner"]["supplier"] == "Seller 2"


def test_ai_cannot_pick_a_seller_the_engine_blocked(monkeypatch):
    rid = _request()
    _say(monkeypatch, "Seller 3", "Seller 3 has the lowest unit price at ₹1,150 landed.")   # the 7-day seller needs an exception
    assert _opinion(rid) is None


@pytest.mark.parametrize("reason", [
    "Seller 1 saves ₹999 overall.",                                       # a number that is not in the engine output
    "Seller 1 is best and we guarantee a 5% rebate.",                      # a promise
    "The first supplier is best at ₹1,200.",                               # does not name its pick
])
def test_bad_ai_text_is_dropped(monkeypatch, reason):
    rid = _request()
    _say(monkeypatch, "Seller 1", reason)
    assert _opinion(rid) is None


def test_opinion_is_not_shown_after_a_decision_or_on_the_shared_page(monkeypatch):
    rid = _request()
    _say(monkeypatch, "Seller 2", "Seller 2 is the lowest at ₹1,150 landed.")
    assert _opinion(rid) is not None
    _decide(rid)
    assert _opinion(rid) is None
    link = client.post(f"/api/rfqs/{rid}/share").json()["token"]
    assert client.get(f"/api/share/{link}").json().get("ai_opinion") is None


def test_opinion_is_logged_against_the_request(monkeypatch):
    rid = _request()
    _say(monkeypatch, "Seller 2", "Seller 2 is the lowest at ₹1,150 landed.")
    _opinion(rid)
    from app.main import store
    assert any(e["kind"] == "second_opinion" for e in store.ai_log_for(rid))
