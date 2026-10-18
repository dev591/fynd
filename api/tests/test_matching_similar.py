"""Items are matched by meaning, not only by exact name: acronyms, wording, plurals, and (when AI is on) things a rule cannot see."""
import pytest
from fastapi.testclient import TestClient

from app import matching
from app.auth import AuthUser, get_current_user
from app.main import app, store
from app.models import SupplierProduct

client = TestClient(app)


def prod(name, aliases=()):
    return SupplierProduct(id="p", name=name, pack_price=1, pack_size=1, usual_lead_days=2, aliases=list(aliases))


LONG = "High-Density Interconnect (HDI) Boards"


@pytest.mark.parametrize("want", ["HDI", "hdi boards", "HDI board", "High Density Interconnect Boards", "high-density interconnect (hdi) boards"])
def test_a_long_name_with_an_acronym_is_found_by_the_acronym_and_by_wording(want):
    p, basis = matching.match_with_basis(want, [prod(LONG)])
    assert p is not None and basis in ("exact", "similar")


def test_the_name_or_the_acronym_the_seller_wrote_is_exact_and_wording_only_is_similar():
    assert matching.match_with_basis("M10 bolt", [prod("M10 bolt")])[1] == "exact"
    assert matching.match_with_basis("HDI", [prod(LONG)])[1] == "exact"                    # the seller wrote (HDI) in the name
    assert matching.match_with_basis("high density interconnect board", [prod(LONG)])[1] == "similar"
    assert matching.match_with_basis("HDI boards", [prod("HDI")])[1] == "similar"          # the seller's shorter name sits inside the request


@pytest.mark.parametrize("want,name", [("M10 bolt", "M8 bolt"), ("M10 bolt", "M10 nut"), ("HDI", "PCB Connector"), ("copper wire 1.5mm", "copper wire 2.5mm"),
                                       ("M10 bolt", "M12 hex bolt grade 8.8")])
def test_different_items_and_different_sizes_do_not_match(want, name):
    assert matching.match_with_basis(want, [prod(name)])[0] is None


def test_an_exact_match_wins_over_a_similar_one():
    exact, similar = prod("HDI boards"), SupplierProduct(id="q", name="HDI", pack_price=1, pack_size=1, usual_lead_days=2)
    assert matching.match_with_basis("HDI boards", [similar, exact]) == (exact, "exact")


# ─── through the real flow: two friends add differently-named HDI products ───

def seller(uid, product):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=f"{uid}@t.dev")
    client.post("/api/profile", json={"id": "x", "role": "supplier", "full_name": uid, "email": f"{uid}@t.dev", "phone": "9820144556",
                                      "company": f"{uid} Works", "business_type": "manufacturer", "state": "Gujarat", "city": "Surat",
                                      "pincode": "395003", "categories": []})
    client.post("/api/me/roles", json={"role": "seller"})
    client.post(f"/api/supplier/products/{uid}", json={"name": product, "pack_price": 100, "pack_size": 1, "moq": 1, "usual_lead_days": 3, "stock": 500})


def inbox(uid):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=uid, email=f"{uid}@t.dev")
    return client.get(f"/api/supplier/{uid}/notifications").json()


def test_both_friends_receive_an_hdi_request_whatever_they_named_it(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    seller("hdi-long", LONG)
    seller("hdi-short", "HDI")
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="hdi-buyer", email="b@t.dev")
    rid = client.post("/api/rfqs", json={"item": "HDI", "qty": 50, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    long_box, short_box = inbox("hdi-long"), inbox("hdi-short")
    assert any(n["rfq_id"] == rid for n in long_box) and any(n["rfq_id"] == rid for n in short_box)
    assert next(n for n in short_box if n["rfq_id"] == rid)["match_basis"] == "exact"
    assert next(n for n in long_box if n["rfq_id"] == rid)["match_basis"] == "exact"


# ─── AI: only for sellers the rules did not match, and only names that really exist ───

def ai_setup(monkeypatch, reply):
    calls = []
    monkeypatch.setattr(matching.ai, "ai_enabled", lambda: True)
    monkeypatch.setattr(matching, "structured_call", lambda *a, **k: calls.append(1) or reply)
    matching._ai_cache.clear()
    return calls


def test_ai_can_relate_a_term_the_rules_cannot_and_the_match_is_labelled_ai(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    seller("ai-pcb", "Multilayer Printed Circuit Board")
    calls = ai_setup(monkeypatch, {"matches": [{"name": "Multilayer Printed Circuit Board"}]})
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="ai-buyer", email="b@t.dev")
    rid = client.post("/api/rfqs", json={"item": "PCB", "qty": 10, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    n = next(x for x in inbox("ai-pcb") if x["rfq_id"] == rid)
    assert n["match_basis"] == "ai" and calls == [1]


def test_ai_names_that_are_not_in_any_catalog_are_dropped_and_off_means_no_ai(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    seller("ai-nope", "Garden Hose")
    ai_setup(monkeypatch, {"matches": [{"name": "Invented Product"}]})
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="ai-buyer2", email="b@t.dev")
    rid = client.post("/api/rfqs", json={"item": "PCB", "qty": 10, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}).json()["id"]
    assert all(n["rfq_id"] != rid for n in inbox("ai-nope"))
    monkeypatch.setattr(matching.ai, "ai_enabled", lambda: False)
    calls = []
    monkeypatch.setattr(matching, "structured_call", lambda *a, **k: calls.append(1) or {"matches": []})
    matching._ai_cache.clear()
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="ai-buyer2", email="b@t.dev")
    client.post("/api/rfqs", json={"item": "PCB", "qty": 10, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"})
    assert calls == []


def test_the_same_question_is_asked_of_the_model_once(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SELLERS", raising=False)
    seller("ai-once", "Rubber Gasket Ring")
    calls = ai_setup(monkeypatch, {"matches": []})
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="ai-buyer3", email="b@t.dev")
    for _ in range(2):
        client.post("/api/rfqs", json={"item": "O-ring", "qty": 10, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"})
    assert len(calls) == 1
