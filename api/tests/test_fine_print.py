"""Fine print: terms hidden in a seller's notes that change which quote is really best. Every flag quotes the seller's own words."""
import pytest
from fastapi.testclient import TestClient

from app import fine_print
from app.auth import AuthUser, get_current_user
from app.main import app
from tests.helpers import tokens_of

client = TestClient(app)


@pytest.mark.parametrize("note,kind,phrase", [
    ("50% advance before dispatch", "advance_payment", "50% advance"),
    ("Price valid for 24 hours only", "price_validity", "valid for 24 hours"),
    ("GST extra, loading charges extra", "extra_charges", "extra"),
    ("Subject to stock availability", "condition", "subject to stock"),
    ("No returns after delivery", "no_returns", "no returns"),
])
def test_rules_catch_the_common_hidden_terms_and_quote_the_sellers_words(note, kind, phrase):
    flags = fine_print.rule_flags(note)
    hit = next(f for f in flags if f["kind"] == kind)
    assert phrase.lower() in hit["phrase"].lower() and hit["phrase"].lower() in note.lower()       # quotes the seller's own words


@pytest.mark.parametrize("note", ["", "Thank you for your enquiry", "We can supply 100 units in 3 days"])
def test_plain_notes_raise_nothing(note):
    assert fine_print.rule_flags(note) == []


def test_a_model_flag_is_kept_only_if_its_phrase_is_really_in_the_note(monkeypatch):
    note = "Delivery is by road. Payment must be made in full 2 days before dispatch."
    monkeypatch.setattr(fine_print, "structured_call", lambda *a, **k: {"flags": [
        {"kind": "advance_payment", "phrase": "Payment must be made in full 2 days before dispatch"},
        {"kind": "price_validity", "phrase": "price valid for 1 hour"},                          # not in the note: dropped
        {"kind": "made_up_kind", "phrase": "Delivery is by road"}]})                             # not an allowed kind: dropped
    flags = fine_print.read(note)
    assert [f["kind"] for f in flags] == ["advance_payment"]
    assert flags[0]["phrase"] in note


def test_the_same_note_is_read_once(monkeypatch):
    calls = []
    monkeypatch.setattr(fine_print, "structured_call", lambda *a, **k: calls.append(1) or {"flags": []})
    fine_print._cache.clear()
    note = "Kindly arrange transport from our godown. Rates as discussed."
    fine_print.read(note); fine_print.read(note)
    assert len(calls) == 1


def request_with_notes():
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    t = tokens_of(rid)
    client.post(f"/api/rfq-by-token/{t['A']}/quotes", json={"supplier_name": "A", "pack_price": 10, "pack_size": 1, "freight": 0, "lead_days": 3, "notes": "100% advance. Price valid for 24 hours."})
    client.post(f"/api/rfq-by-token/{t['B']}/quotes", json={"supplier_name": "B", "pack_price": 11, "pack_size": 1, "freight": 0, "lead_days": 3})
    return rid


def test_the_endpoint_returns_flags_by_alias_and_nothing_for_clean_quotes():
    rid = request_with_notes()
    out = client.get(f"/api/rfqs/{rid}/fine-print").json()["flags"]
    assert {f["kind"] for f in out["Seller 1"]} >= {"advance_payment", "price_validity"}
    assert out.get("Seller 2", []) == []
    assert all("A" != k for k in out)                      # aliases only


def test_only_the_owner_can_read_the_fine_print():
    rid = request_with_notes()
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="other-buyer", email="o@t.dev")
    assert client.get(f"/api/rfqs/{rid}/fine-print").status_code == 404
