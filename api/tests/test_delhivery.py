import pytest
from fastapi.testclient import TestClient

from app import delhivery
from app.main import app

client = TestClient(app)


class FakeResp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


@pytest.fixture(autouse=True)
def _no_token(monkeypatch):
    monkeypatch.delenv("DELHIVERY_TOKEN", raising=False)


def test_without_a_token_everything_falls_back_quietly():
    assert delhivery.enabled() is False
    assert delhivery.freight_estimate("400069", "122001", 5000) is None
    r = client.post("/api/logistics/freight", json={"source_pin": "400069", "consignee_pin": "122001", "weight_kg": 5})
    assert r.status_code == 200 and r.json()["suggested_freight"] is None and r.json()["enabled"] is False
    assert client.get("/api/logistics/tat", params={"origin_pin": "400093", "destination_pin": "122001"}).json()["suggested_lead_days"] is None


def test_bad_input_is_refused_before_any_call(monkeypatch):
    monkeypatch.setenv("DELHIVERY_TOKEN", "t")
    monkeypatch.setattr(delhivery.httpx, "request", lambda *a, **k: pytest.fail("must not call the vendor"))
    assert client.get("/api/logistics/pincode/12").status_code == 422
    assert client.post("/api/logistics/freight", json={"source_pin": "abc", "consignee_pin": "122001", "weight_kg": 1}).status_code == 422
    assert client.post("/api/logistics/freight", json={"source_pin": "400069", "consignee_pin": "122001", "weight_kg": 0}).status_code == 422
    assert client.get("/api/logistics/tat", params={"origin_pin": "1", "destination_pin": "2"}).status_code == 422


def test_freight_request_matches_the_vendor_shape_and_suggestion_is_read(monkeypatch):
    monkeypatch.setenv("DELHIVERY_TOKEN", "secret-token")
    seen = {}

    def fake(method, url, headers=None, timeout=None, **kw):
        seen.update(method=method, url=url, headers=headers, **kw)
        return FakeResp({"data": {"charges": {"total_amount": 842.5}}})

    monkeypatch.setattr(delhivery.httpx, "request", fake)
    out = client.post("/api/logistics/freight", json={"source_pin": "400069", "consignee_pin": "122001", "weight_kg": 100, "inv_amount": 123}).json()
    assert out["suggested_freight"] == 842.5 and out["source"] == "Delhivery estimate"
    assert seen["method"] == "POST" and seen["url"].endswith("/freight/estimate")
    assert seen["headers"]["Authorization"] == "Bearer secret-token"
    assert seen["json"]["weight_g"] == 100000 and seen["json"]["source_pin"] == "400069" and seen["json"]["consignee_pin"] == "122001"
    assert seen["json"]["dimensions"][0]["box_count"] == 1 and seen["json"]["freight_mode"] == "fod"
    assert "secret-token" not in str(out)


def test_unrecognised_reply_gives_no_suggestion_but_keeps_the_raw_reply(monkeypatch):
    monkeypatch.setenv("DELHIVERY_TOKEN", "t")
    monkeypatch.setattr(delhivery.httpx, "request", lambda *a, **k: FakeResp({"weird": "shape"}))
    out = client.get("/api/logistics/tat", params={"origin_pin": "400093", "destination_pin": "122001"}).json()
    assert out["suggested_lead_days"] is None and out["raw"] == {"weird": "shape"}


def test_vendor_errors_and_timeouts_return_none(monkeypatch):
    monkeypatch.setenv("DELHIVERY_TOKEN", "t")

    def boom(*a, **k):
        raise delhivery.httpx.ConnectTimeout("slow")

    monkeypatch.setattr(delhivery.httpx, "request", boom)
    assert delhivery.pincode_service("122001") is None
    assert client.get("/api/logistics/pincode/122001").json()["available"] is False


def test_find_number_ignores_booleans_and_searches_nested():
    assert delhivery.find_number({"a": [{"tat": 3}]}, "tat") == 3.0
    assert delhivery.find_number({"tat": True}, "tat") is None


def test_rate_card_zones_and_labelling():
    local = delhivery.rate_card("400069", "400093", 10)
    regional = delhivery.rate_card("400069", "411001", 10)
    national = delhivery.rate_card("400069", "122001", 10)
    assert (local["zone"], regional["zone"], national["zone"]) == ("local", "regional", "national")
    assert local["freight"] < regional["freight"] < national["freight"]
    assert local["lead_days"] < regional["lead_days"] < national["lead_days"]
    assert all(r["basis"] == "rate_card" and "not a Delhivery quote" in r["label"] for r in (local, regional, national))
    assert delhivery.rate_card("40", "122001", 5) is None and delhivery.rate_card("400069", "122001", 0) is None


def test_estimate_endpoint_falls_back_to_the_rate_card_without_a_token():
    r = client.post("/api/logistics/estimate", json={"source_pin": "400069", "consignee_pin": "122001", "weight_kg": 20})
    assert r.status_code == 200 and r.json()["basis"] == "rate_card" and r.json()["freight"] == 250 + 14 * 20
    assert client.post("/api/logistics/estimate", json={"source_pin": "x", "consignee_pin": "122001", "weight_kg": 1}).status_code == 422


def test_estimate_prefers_live_delhivery_numbers_when_the_reply_has_them(monkeypatch):
    monkeypatch.setenv("DELHIVERY_TOKEN", "t")
    replies = iter([FakeResp({"total_amount": 990}), FakeResp({"tat": 4})])
    monkeypatch.setattr(delhivery.httpx, "request", lambda *a, **k: next(replies))
    out = client.post("/api/logistics/estimate", json={"source_pin": "400069", "consignee_pin": "122001", "weight_kg": 20}).json()
    assert (out["basis"], out["freight"], out["lead_days"]) == ("delhivery", 990, 4)


def test_quote_records_how_it_ships_and_only_delhivery_keeps_a_basis():
    from tests.helpers import tokens_of
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 10, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    tok = tokens_of(rid)["A"]
    body = {"supplier_name": "x", "pack_price": 10, "pack_size": 1, "freight": 300, "lead_days": 3}
    own = client.post(f"/api/rfq-by-token/{tok}/quotes", json={**body, "shipping": "own", "shipping_basis": "rate_card"}).json()
    assert own["shipping"] == "own" and own["shipping_basis"] is None
    dl = client.post(f"/api/rfq-by-token/{tok}/quotes", json={**body, "shipping": "delhivery", "shipping_basis": "rate_card"}).json()
    assert dl["shipping"] == "delhivery" and dl["shipping_basis"] == "rate_card"
    assert client.post(f"/api/rfq-by-token/{tok}/quotes", json={**body, "shipping": "courier-x"}).status_code == 422
