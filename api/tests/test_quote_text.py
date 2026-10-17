"""Pasting a supplier's message. The model reads it; code checks every number against the message; a person confirms."""
import json

import pytest
from fastapi.testclient import TestClient

from app import quote_text
from app.importer import validate_rows
from app.main import app, store

client = TestClient(app)

CASES = [  # (message, what a faithful model returns, expected rows after the guard)
    ("Acme Traders: M10 bolt Rs 10 per piece, delivery Rs 200, 3 days",
     [dict(supplier="Acme Traders", pack_price=10, pack_size=None, price_basis="per_unit", freight=200, freight_free=None, lead_days=3)],
     [dict(supplier="Acme Traders", pack_price=10, pack_size=1, freight=200, lead_days=3)]),
    ("Gamma Boxes - 400 per box of 50, free delivery, 7 days",
     [dict(supplier="Gamma Boxes", pack_price=400, pack_size=50, price_basis="per_pack", freight=None, freight_free=True, lead_days=7)],
     [dict(supplier="Gamma Boxes", pack_price=400, pack_size=50, freight=0, lead_days=7)]),
    ("Delta: 95 per pack, 3 days",                                       # nobody said how many in a pack
     [dict(supplier="Delta", pack_price=95, pack_size=None, price_basis="per_pack", freight=None, freight_free=None, lead_days=3)],
     [dict(supplier="Delta", pack_price=95, pack_size=None, freight=None, lead_days=3)]),
    ("Beta Hardware ₹11 each + ₹50 shipping. Ready in 3 din. MOQ 20",
     [dict(supplier="Beta Hardware", pack_price=11, pack_size=None, price_basis="per_unit", freight=50, freight_free=None, lead_days=3, moq=20)],
     [dict(supplier="Beta Hardware", pack_price=11, pack_size=1, freight=50, lead_days=3, moq=20)]),
    ("Acme: 10/pc + 200 freight, 3 days\nBeta: 11/pc + 50 freight, 3 days",     # two offers in one message
     [dict(supplier="Acme", pack_price=10, price_basis="per_unit", freight=200, lead_days=3),
      dict(supplier="Beta", pack_price=11, price_basis="per_unit", freight=50, lead_days=3)],
     [dict(supplier="Acme", pack_price=10, freight=200), dict(supplier="Beta", pack_price=11, freight=50)]),
]


def _raw(rows):
    base = dict(supplier=None, pack_price=None, pack_size=None, price_basis=None, freight=None, freight_free=None, lead_days=None,
                moq=None, max_qty=None, gst_rate=None, price_includes_gst=None, notes=None)
    return {"quotes": [{**base, **r} for r in rows]}


@pytest.mark.parametrize("text,model,expected", CASES)
def test_faithful_model_output_becomes_importable_rows(text, model, expected):
    out = quote_text.build_rows(text, _raw(model))
    assert len(out["rows"]) == len(expected)
    for got, want in zip(out["rows"], expected):
        for k, v in want.items():
            assert got[k] == v, (text, k, got)
    assert not [w for w in out["warnings"] if "dropped" in w.lower()]


def test_an_unstated_pack_size_is_never_invented():
    out = quote_text.build_rows(*CASES[2][:1], _raw(CASES[2][1]))
    assert out["rows"][0]["pack_size"] is None
    assert any("pack size" in w.lower() for w in out["warnings"])


def test_per_unit_prices_become_a_pack_of_one_and_say_so():
    out = quote_text.build_rows(CASES[0][0], _raw(CASES[0][1]))
    assert out["rows"][0]["pack_size"] == 1 and any("per unit" in w.lower() for w in out["warnings"])


def test_a_freight_that_is_not_stated_stays_blank_and_is_flagged_not_zeroed():
    out = quote_text.build_rows(CASES[2][0], _raw(CASES[2][1]))
    assert out["rows"][0]["freight"] is None and any("freight" in w.lower() for w in out["warnings"])


def test_invented_numbers_and_names_never_survive():
    """Poison every case: the model returns figures the message does not contain. Zero may survive."""
    invented = 0
    for text, model, _ in CASES:
        poisoned = _raw([{**m, "pack_price": 7777, "freight": 4321, "lead_days": 91, "moq": 555, "gst_rate": 99,
                          "supplier": "Totally Invented Pvt Ltd", "pack_size": 8888} for m in model])
        for row in quote_text.build_rows(text, poisoned)["rows"]:
            invented += sum(row[k] in (7777, 4321, 91, 555, 99, 8888) for k in ("pack_price", "freight", "lead_days", "moq", "tax_rate", "pack_size"))
            invented += row["supplier"] == "Totally Invented Pvt Ltd"
    assert invented == 0


def test_free_delivery_is_only_believed_if_the_message_says_so():
    lie = dict(supplier="Acme", pack_price=10, price_basis="per_unit", freight=None, freight_free=True, lead_days=3)
    out = quote_text.build_rows("Acme: 10 per piece, 3 days", _raw([lie]))
    assert out["rows"][0]["freight"] is None
    assert quote_text.build_rows("Acme: 10 per piece, free shipping, 3 days", _raw([lie]))["rows"][0]["freight"] == 0


def test_rows_from_the_guard_pass_the_importers_own_validation():
    text, model, _ = CASES[1]
    rows = quote_text.build_rows(text, _raw(model))["rows"]
    ok, errs = validate_rows(rows, "M10 bolt")
    assert ok and not errs


def test_nothing_returned_means_a_clear_fallback():
    out = quote_text.build_rows("hello, are you open tomorrow?", _raw([]))
    assert out["rows"] == [] and any("no quote" in w.lower() for w in out["warnings"])
    out = quote_text.build_rows("x", None)
    assert out["rows"] == [] and out["fallback"] is True


# ─── the endpoint ───────────────────────────────────────────────────────────────

def _rfq():
    return client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5,
                                          "buyer_company": "c", "buyer_name": "b"}).json()["id"]


def test_endpoint_drafts_without_saving_anything_then_import_loads_it(monkeypatch):
    monkeypatch.setattr(quote_text, "structured_call", lambda *a, **k: _raw(CASES[4][1]))
    rid = _rfq()
    r = client.post("/api/ai/quote-draft", json={"text": CASES[4][0], "rfq_id": rid}).json()
    assert r["fallback"] is False and [x["supplier"] for x in r["rows"]] == ["Acme", "Beta"] and r["request_id"]
    assert client.get(f"/api/rfqs/{rid}").json()["quotes"] == {}                       # a draft saves nothing
    loaded = client.post(f"/api/rfqs/{rid}/import-quotes", json={"format": "json", "data": json.dumps({"quotes": r["rows"]})})
    assert loaded.status_code == 200 and loaded.json()["imported"] == 2
    assert any(e["kind"] == "quote_draft" for e in store.ai_log_for(rid))               # logged against the request


def test_without_a_key_it_falls_back_to_the_file_import():
    r = client.post("/api/ai/quote-draft", json={"text": CASES[0][0]}).json()
    assert r["fallback"] is True and r["rows"] == [] and "import" in r["message"].lower()


def test_endpoint_is_buyer_only_and_limits_the_text():
    assert client.post("/api/ai/quote-draft", json={"text": "x" * 5001}).status_code == 422
    from app.auth import get_current_user
    app.dependency_overrides.pop(get_current_user, None)
    assert client.post("/api/ai/quote-draft", json={"text": "hi"}).status_code == 401
