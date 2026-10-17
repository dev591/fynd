import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import assistant
from app.main import app, store
from app.matching import draft_quote
from app.models import RFQ, SupplierProduct

client = TestClient(app)
SELLER = json.loads((Path(__file__).parent / "golden" / "seller_cases.json").read_text())["cases"]


def _rfq(qty=100, need=5, item="M10 bolt"):
    return RFQ(id="r", token="t", item=item, qty=qty, need_in_days=need, buyer_company="c", buyer_name="b",
               buyer_city="p", buyer_state="m", created_at="now")


def _prod(**kw):
    base = dict(id="p", name="M10 Hex Bolt", pack_price=10, pack_size=1, freight=200, usual_lead_days=3,
                moq=50, stock=500, aliases=["M10 bolt"])
    return SupplierProduct(**{**base, **kw})


def _use_model(monkeypatch, message):
    monkeypatch.setattr(assistant, "structured_call", lambda *a, **k: {"message": message})


def test_template_numbers_all_come_from_data():
    rfq, draft = _rfq(), draft_quote(_rfq(), _prod())
    text = assistant.template_message(rfq, draft)
    assert assistant.numbers_supported(text, assistant.allowed_numbers(rfq, draft))
    assert "₹1,200" in text            # 100 x 10 + 200 freight, from the engine
    assert "3 days" in text


def test_faithful_ai_text_is_kept(monkeypatch):
    rfq, draft = _rfq(), draft_quote(_rfq(), _prod())
    _use_model(monkeypatch, "We can supply your 100 units of M10 bolt at ₹10 each with ₹200 freight, in 3 days. Total ₹1,200.")
    out = assistant.reply_for(rfq, draft)
    assert out["source"] == "ai" and out["discarded_reason"] is None


def test_ai_text_with_invented_number_is_discarded_for_template(monkeypatch):
    rfq, draft = _rfq(), draft_quote(_rfq(), _prod())
    for bad in [
        "We can supply 100 units at ₹9 each.",                       # wrong price
        "Special 10% discount if you confirm today, 3 days delivery.",  # invented discount
        "We can deliver in four days at ₹10.",                        # wrong lead time as a number word
        "Total ₹1,250 including freight.",                            # wrong total
    ]:
        _use_model(monkeypatch, bad)
        out = assistant.reply_for(rfq, draft)
        assert out["source"] == "template", bad
        assert out["discarded_reason"] and out["ai_text"] == bad
        assert assistant.numbers_supported(out["text"], assistant.allowed_numbers(rfq, draft))


def test_no_key_uses_template():
    rfq, draft = _rfq(), draft_quote(_rfq(), _prod())
    out = assistant.reply_for(rfq, draft)
    assert out["source"] == "template" and out["discarded_reason"] is None


def test_golden_seller_cases_never_invent_numbers(monkeypatch):
    """8 seller cases: a poisoned model reply must never reach the seller; templates only use data."""
    assert len(SELLER) == 8
    invented = 0
    for c in SELLER:
        rfq = _rfq(c["qty"], c["need"])
        draft = draft_quote(rfq, _prod(stock=c["stock"], usual_lead_days=c["lead"], moq=c["moq"]))
        _use_model(monkeypatch, "Great news: 15% off and 2 free samples!")
        out = assistant.reply_for(rfq, draft)
        if not assistant.numbers_supported(out["text"], assistant.allowed_numbers(rfq, draft)):
            invented += 1
        assert out["source"] == "template"
    assert invented == 0


def test_partial_cover_template_says_what_it_can_cover():
    rfq = _rfq(100)
    draft = draft_quote(rfq, _prod(stock=60))
    text = assistant.template_message(rfq, draft)
    assert "60 of your 100 units" in text


# ─── item match ───────────────────────────────────────────────────────────────

def test_item_match_rules_alias_and_size_conflict():
    assert assistant.item_match("m10 BOLT", _prod())["verdict"] == "same"
    m8 = _prod(name="M8 Hex Bolt", aliases=[])
    out = assistant.item_match("M10 bolt", m8)
    assert out["verdict"] == "different" and out["source"] == "rules" and "M10" in out["reason"] and "M8" in out["reason"]


def test_item_match_without_ai_is_unsure_and_never_raises():
    out = assistant.item_match("brass nut", _prod(name="Steel Washer", aliases=[]))
    assert out["verdict"] == "unsure" and out["source"] == "none"


def test_item_match_ai_reason_with_unsupported_number_is_dropped(monkeypatch):
    monkeypatch.setattr(assistant, "structured_call",
                        lambda *a, **k: {"verdict": "different", "reason": "Grade 12.9 is stronger."})
    out = assistant.item_match("hex bolt", _prod(name="Hex Bolt Zinc", aliases=[]))
    assert out["source"] == "none"
    monkeypatch.setattr(assistant, "structured_call",
                        lambda *a, **k: {"verdict": "same", "reason": "Both are hex bolts."})
    assert assistant.item_match("hex bolt", _prod(name="Hex Bolt Zinc", aliases=[]))["source"] == "ai"


# ─── endpoints and origin ─────────────────────────────────────────────────────

def _new(qty=100):
    return client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": 5,
                                          "buyer_company": "Co", "buyer_name": "B"}).json()


def _send(token, d, notes, **over):
    body = {"pack_price": d["pack_price"], "pack_size": d["pack_size"], "freight": d["freight"],
            "lead_days": d["lead_days"], "moq": d["moq"], "max_qty": d["max_qty"], "notes": notes, **over}
    return client.post(f"/api/rfq-by-token/{token}/quotes", json=body).json()


def test_assist_endpoint_and_origin_labels(monkeypatch):
    res = _new()
    tok = res["supplier_tokens"]["A"]
    # no AI: template wording, so a sent quote is not labelled as an AI draft
    a = client.get(f"/api/rfq-by-token/{tok}/assist").json()
    assert a["message"]["source"] == "template" and a["draft"]["pack_price"] == 10
    assert _send(tok, a["draft"], a["message"]["text"])["origin"] == "manual"

    # with AI wording: unchanged = sent, any edit = edited
    monkeypatch.setattr(assistant, "structured_call",
                        lambda *a, **k: {"message": "We can supply your 100 units at ₹10 each, in 3 days."})
    a = client.get(f"/api/rfq-by-token/{tok}/assist").json()
    assert a["message"]["source"] == "ai"
    assert _send(tok, a["draft"], a["message"]["text"])["origin"] == "ai_draft_sent"
    assert _send(tok, a["draft"], a["message"]["text"], freight=150)["origin"] == "ai_draft_edited"
    assert _send(tok, a["draft"], a["message"]["text"] + " Thanks.")["origin"] == "ai_draft_edited"

    log = client.get(f"/api/rfqs/{res['id']}/ai-log").json()
    assert any(e["kind"] == "seller_assist" for e in log)


def test_client_cannot_claim_ai_origin():
    tok = _new()["supplier_tokens"]["A"]
    d = client.get(f"/api/rfq-by-token/{tok}/draft").json()
    assert _send(tok, d, None, origin="ai_draft_sent")["origin"] == "manual"


def test_item_match_endpoint():
    tok = _new()["supplier_tokens"]["A"]
    prod = store.supplier_products["A"][0]
    assert client.post(f"/api/rfq-by-token/{tok}/item-match", json={"product_id": prod.id}).json()["verdict"] == "same"
    assert client.post(f"/api/rfq-by-token/{tok}/item-match", json={"product_id": "nope"}).status_code == 404
    assert client.get("/api/rfq-by-token/nope/assist").status_code == 404
