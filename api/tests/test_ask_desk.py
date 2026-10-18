"""Ask the desk: a what-if question becomes engine inputs; the engine recomputes; code writes the answer."""
import pytest
from fastapi.testclient import TestClient

from app import ask_desk
from app.auth import AuthUser, get_current_user
from app.main import app, store
from tests.helpers import tokens_of

client = TestClient(app)
ALIASES = ["Seller 1", "Seller 2", "Seller 3"]


def parse(q):
    return ask_desk.parse_rules(q, ALIASES)


@pytest.mark.parametrize("q,qty", [("what if I need 300?", 300), ("what if we order 1,500 units", 1500), ("what if I need 2 hazaar", 2000),
                                   ("what if I order 250 instead", 250)])
def test_quantity_questions(q, qty):
    assert parse(q).qty == qty


def test_double_and_half_are_worked_out_in_code():
    assert ask_desk.parse_rules("what if I need double", ALIASES, base_qty=100).qty == 200
    assert ask_desk.parse_rules("what if I need half", ALIASES, base_qty=100).qty == 50
    assert parse("what if I need double").qty is None                        # no base quantity, so no guess


@pytest.mark.parametrize("q,out", [("what if Seller 2 is out?", ["Seller 2"]), ("what if seller 1 and seller 3 drop out", ["Seller 1", "Seller 3"]),
                                   ("without Seller 3", ["Seller 3"]), ("what if Seller 9 is out", [])])
def test_excluding_sellers_only_names_real_aliases(q, out):
    assert parse(q).exclude == out


@pytest.mark.parametrize("q,days", [("what if I need it in 3 days", 3), ("what if I need it by tomorrow", 1), ("what if I need it within two weeks", 14)])
def test_deadline_questions(q, days):
    assert parse(q).need_in_days == days


@pytest.mark.parametrize("q,mode", [("what if I want the fastest", "fastest"), ("what if cheapest matters most", "cheapest"), ("make it balanced", "balanced")])
def test_priority_questions(q, mode):
    assert parse(q).priority == mode


def test_a_combined_question_sets_everything_it_names():
    p = parse("what if I need 300 units in 3 days and Seller 2 is out, fastest")
    assert (p.qty, p.need_in_days, p.exclude, p.priority) == (300, 3, ["Seller 2"], "fastest")


@pytest.mark.parametrize("q", ["hello", "what is the weather", "", "what if"])
def test_unrelated_questions_change_nothing(q):
    assert parse(q).empty()


@pytest.mark.parametrize("q", ["what if I need -5", "what if I need 0", "what if I need 99999999999", "what if I need it in 0 days"])
def test_impossible_numbers_are_refused(q):
    p = parse(q)
    assert p.qty is None and p.need_in_days is None


def quoted_request(note=None):
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    t = tokens_of(rid)
    for sid, price, fr, lead in (("A", 10, 200, 3), ("B", 11, 50, 4), ("C", 12, 0, 2)):
        client.post(f"/api/rfq-by-token/{t[sid]}/quotes", json={"supplier_name": sid, "pack_price": price, "pack_size": 1, "freight": fr, "lead_days": lead})
    return rid


def ask(rid, q, **kw):
    return client.post(f"/api/rfqs/{rid}/ask", json={"question": q}, **kw)


def test_what_if_a_seller_drops_out_recomputes_with_the_engine():
    rid = quoted_request()
    out = ask(rid, "what if Seller 2 is out?").json()
    assert out["understood"] and out["baseline"]["winner"] == "Seller 2" and out["result"]["winner"] != "Seller 2"
    assert "Seller 2" not in [r["quote_id"] for r in out["result"]["rows"]]
    assert out["changed"] is True and "Seller 2" in out["sentence"] and out["result"]["winner"] in out["sentence"]


def test_what_if_the_quantity_changes_uses_real_landed_costs():
    rid = quoted_request()
    out = ask(rid, "what if I need 1000?").json()
    assert out["scenario"]["qty"] == 1000
    row = next(r for r in out["result"]["rows"] if r["quote_id"] == out["result"]["winner"])
    assert row["landed"] == 1000 * {"Seller 1": 10, "Seller 2": 11, "Seller 3": 12}[out["result"]["winner"]] + {"Seller 1": 200, "Seller 2": 50, "Seller 3": 0}[out["result"]["winner"]]


def test_what_if_the_deadline_is_tighter_makes_slow_sellers_need_an_exception():
    rid = quoted_request()
    out = ask(rid, "what if I need it in 2 days?").json()
    by = {r["quote_id"]: r for r in out["result"]["rows"]}
    assert by["Seller 3"]["status"] == "eligible" and by["Seller 1"]["status"] == "exception" and by["Seller 2"]["status"] == "exception"
    assert out["result"]["winner"] == "Seller 3"


def test_the_stored_request_is_never_changed_by_a_what_if():
    rid = quoted_request()
    ask(rid, "what if I need 5000 in 1 day, fastest, Seller 1 out")
    rfq = store.rfqs[rid]
    assert (rfq.qty, rfq.need_in_days, rfq.priority_mode) == (100, 5, "cheapest")
    assert rfq.status == "Open" and rfq.decision is None


def test_an_unclear_question_says_so_and_runs_nothing():
    rid = quoted_request()
    out = ask(rid, "tell me a joke").json()
    assert out["understood"] is False and out["result"] is None and "Try" in out["sentence"]


def test_only_the_owner_can_ask_and_answers_carry_aliases_only():
    rid = quoted_request()
    out = ask(rid, "what if Seller 2 is out?")
    assert "Bolt" not in out.text and "Real" not in out.text
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="someone-else", email="x@t.dev")
    assert ask(rid, "what if I need 300").status_code == 404


def test_the_model_can_read_other_phrasings_but_every_value_is_checked_against_the_question(monkeypatch):
    rid = quoted_request()
    monkeypatch.setattr(ask_desk, "structured_call", lambda *a, **k: {"qty": 300, "need_in_days": None, "priority": None, "exclude": ["Seller 2"]})
    out = ask(rid, "supposing we scale up to three hundred and the second one backs out").json()
    assert out["scenario"]["qty"] is None or out["scenario"]["qty"] == 300          # "three hundred" is in the text as words
    monkeypatch.setattr(ask_desk, "structured_call", lambda *a, **k: {"qty": 777, "need_in_days": 9, "priority": "fastest", "exclude": ["Seller 8"]})
    bad = ask(rid, "what about a bigger order?").json()
    assert bad["scenario"]["qty"] is None and bad["scenario"]["need_in_days"] is None and bad["scenario"]["exclude"] == []
    assert bad["scenario"]["priority"] is None                                      # "fastest" was never said


def test_the_answer_sentence_comes_from_engine_numbers_not_from_the_model(monkeypatch):
    rid = quoted_request()
    monkeypatch.setattr(ask_desk, "structured_call", lambda *a, **k: {"qty": None, "need_in_days": None, "priority": None, "exclude": ["Seller 2"], "note": "Seller 2 is free"})
    out = ask(rid, "what if Seller 2 is out?").json()
    assert "free" not in out["sentence"].lower()


@pytest.mark.parametrize("q,qty", [("what if we scale up to five hundred pieces", 500), ("what if I need two thousand units", 2000),
                                   ("what if I need three hundred", 300)])
def test_quantities_spelled_out_in_words(q, qty):
    assert parse(q).qty == qty


@pytest.mark.parametrize("q,out", [("what if the second seller backs out", ["Seller 2"]), ("what if the 3rd supplier is out", ["Seller 3"]),
                                   ("what if the first one cannot deliver", ["Seller 1"]), ("supposing the fifth seller drops out", [])])
def test_sellers_named_by_position(q, out):
    assert parse(q).exclude == out


def test_the_best_or_cheapest_seller_dropping_out_means_todays_winner():
    sc = ask_desk.parse_rules("what if the cheapest guy cannot deliver", ALIASES, best_alias="Seller 2")
    assert sc.exclude == ["Seller 2"] and sc.priority is None
    assert ask_desk.parse_rules("what if the winner is out", ALIASES, best_alias="Seller 2").exclude == ["Seller 2"]
    assert ask_desk.parse_rules("what if the cheapest guy cannot deliver", ALIASES).exclude == []          # no winner known, no guess


def test_an_out_of_range_number_gets_an_explanation_not_a_shrug():
    rid = quoted_request()
    out = ask(rid, "what if I order 100000000 units").json()
    assert out["understood"] is False and "1,000,000" in out["sentence"]


def test_the_cheapest_seller_dropping_out_is_recomputed_through_the_api():
    rid = quoted_request()
    out = ask(rid, "what if the cheapest guy cannot deliver").json()
    assert out["understood"] and out["baseline"]["winner"] not in [r["quote_id"] for r in out["result"]["rows"]]
