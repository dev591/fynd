"""Negative or zero numbers never get in: a request, a quote, a catalog item or a target with them is refused (422)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import tokens_of

client = TestClient(app)
RFQ = {"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}
QUOTE = {"supplier_name": "x", "pack_price": 10, "pack_size": 1, "freight": 0, "lead_days": 3}
PRODUCT = {"name": "M10 bolt", "pack_price": 10, "pack_size": 1, "moq": 1, "usual_lead_days": 3, "stock": 100, "freight": 0}


@pytest.mark.parametrize("field,value", [("qty", -1), ("qty", 0), ("need_in_days", -1), ("need_in_days", 0), ("qty", 10**9)])
def test_a_request_with_a_bad_quantity_or_deadline_is_refused(field, value):
    assert client.post("/api/rfqs", json={**RFQ, field: value}).status_code == 422


@pytest.mark.parametrize("field,value", [("pack_price", -1), ("pack_price", 0), ("pack_size", -1), ("pack_size", 0),
                                         ("freight", -1), ("lead_days", -1), ("moq", 0), ("moq", -5), ("max_qty", -1), ("max_qty", 0)])
def test_a_quote_with_a_negative_or_zero_number_is_refused(field, value):
    rid = client.post("/api/rfqs", json=RFQ).json()["id"]
    assert client.post(f"/api/rfq-by-token/{tokens_of(rid)['A']}/quotes", json={**QUOTE, field: value}).status_code == 422


def test_free_delivery_and_same_day_are_still_allowed():
    rid = client.post("/api/rfqs", json=RFQ).json()["id"]
    r = client.post(f"/api/rfq-by-token/{tokens_of(rid)['A']}/quotes", json={**QUOTE, "freight": 0, "lead_days": 0})
    assert r.status_code == 200


@pytest.mark.parametrize("field,value", [("pack_price", -1), ("pack_size", 0), ("moq", 0), ("usual_lead_days", -1),
                                         ("stock", -1), ("freight", -1), ("capacity_cap", 0)])
def test_a_catalog_item_with_a_bad_number_is_refused(field, value):
    assert client.post("/api/supplier/products/A", json={**PRODUCT, field: value}).status_code == 422


@pytest.mark.parametrize("body", [{"cut_needed": -1}, {"cut_needed": 10, "target_freight": -1}, {"cut_needed": 10, "target_per_unit": -2}])
def test_a_negotiation_target_with_a_negative_number_is_refused(body):
    rid = client.post("/api/rfqs", json=RFQ).json()["id"]
    client.post(f"/api/rfq-by-token/{tokens_of(rid)['A']}/quotes", json=QUOTE)
    r = client.post(f"/api/rfqs/{rid}/targets", json={"supplier_id": "Seller 1", "message": "m", "sent_by": "B", **body})
    assert r.status_code == 422
