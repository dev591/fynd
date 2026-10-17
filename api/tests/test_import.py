"""CSV and JSON import: the buyer brings quotes they already have. Row-level errors, good rows still load."""
import json

import pytest
from fastapi.testclient import TestClient

from app.importer import parse_csv, parse_json, validate_rows
from app.main import app, store
from tests.helpers import alias, quote

client = TestClient(app)

CSV = """supplier,item,units_per_pack,pack_price,freight,lead_days,moq,gst_rate,price_includes_gst,notes
Acme Traders,M10 bolt,1,10,200,3,,,,
Beta Hardware,M10 bolt,1,11,50,3,,,,
Gamma Boxes,M10 bolt,50,400,0,7,,,,Box of 50
Delta Mystery,M10 bolt,,95,0,3,,,,pack size not told
"""


def _rfq(qty=100):
    return client.post("/api/rfqs", json={"item": "M10 bolt", "qty": qty, "need_in_days": 5,
                                          "buyer_company": "Co", "buyer_name": "B"}).json()["id"]


def _import(rid, data, fmt="csv"):
    return client.post(f"/api/rfqs/{rid}/import-quotes", json={"format": fmt, "data": data})


# ─── parsing and validating ────────────────────────────────────────────────────

def test_csv_and_json_parse_to_the_same_rows():
    rows_csv = parse_csv(CSV)
    rows_json = parse_json(json.dumps({"quotes": rows_csv}))
    assert len(rows_csv) == 4 and rows_json == rows_csv
    assert parse_json(json.dumps(rows_csv)) == rows_csv                   # a bare array works too


def test_column_names_are_forgiving():
    rows = parse_csv("Supplier Name,Units Per Pack,Pack Price (INR),Lead Days\nAcme,1,10,3\n")
    ok, errs = validate_rows(rows, "M10 bolt")
    assert not errs and ok[0]["supplier"] == "Acme" and ok[0]["pack_size"] == 1 and ok[0]["pack_price"] == 10 and ok[0]["lead_days"] == 3


@pytest.mark.parametrize("csv_text,field,fragment", [
    ("supplier,pack_price,lead_days\nAcme,abc,3\n", "pack_price", "not a number"),
    ("supplier,pack_price,lead_days\nAcme,0,3\n", "pack_price", "greater than zero"),
    ("supplier,pack_price,lead_days\n,10,3\n", "supplier", "required"),
    ("supplier,pack_price,lead_days\nAcme,10,\n", "lead_days", "required"),
    ("supplier,pack_price,lead_days\nAcme,10,-2\n", "lead_days", "zero or more"),
    ("supplier,pack_price,lead_days,units_per_pack\nAcme,10,3,x\n", "pack_size", "not a number"),
    ("supplier,pack_price,lead_days,freight\nAcme,10,3,-5\n", "freight", "zero or more"),
    ("supplier,pack_price,lead_days,gst_rate\nAcme,10,3,150\n", "tax_rate", "between 0 and 100"),
    ("supplier,pack_price,lead_days,price_includes_gst\nAcme,10,3,maybe\n", "price_includes_tax", "yes or no"),
])
def test_each_bad_cell_gets_a_clear_row_level_message(csv_text, field, fragment):
    ok, errs = validate_rows(parse_csv(csv_text), "M10 bolt")
    assert ok == [] and len(errs) == 1
    assert errs[0]["row"] == 1 and errs[0]["field"] == field and fragment in errs[0]["message"], errs


def test_row_numbers_count_data_rows_and_good_rows_still_load():
    data = "supplier,pack_price,lead_days\nAcme,10,3\nBad,oops,3\nBeta,11,3\nWorse,,\n"
    ok, errs = validate_rows(parse_csv(data), "M10 bolt")
    assert [r["supplier"] for r in ok] == ["Acme", "Beta"]
    assert [(e["row"], e["field"]) for e in errs] == [(2, "pack_price"), (4, "pack_price"), (4, "lead_days")]
    assert errs[0]["message"] == "row 2: pack price is not a number"


def test_rupee_signs_commas_and_blanks_are_understood():
    ok, errs = validate_rows(parse_csv('supplier,pack_price,lead_days,freight\nAcme,"₹1,250.50",3,"₹ 200"\n'), "x")
    assert not errs and ok[0]["pack_price"] == 1250.5 and ok[0]["freight"] == 200


def test_unusable_input_is_one_clear_error_not_a_crash():
    for bad in ["", "   ", "supplier,pack_price,lead_days\n"]:           # empty, blank, header only
        with pytest.raises(ValueError):
            validate_rows(parse_csv(bad), "x")
    with pytest.raises(ValueError, match="missing required"):
        validate_rows(parse_csv("not,a,header\n1,2,3\n"), "x")
    with pytest.raises(ValueError):
        parse_json("{not json")
    with pytest.raises(ValueError):
        parse_json('{"hello": 1}')
    with pytest.raises(ValueError, match="200"):
        parse_csv("supplier,pack_price,lead_days\n" + "\n".join(f"S{i},10,3" for i in range(201)))


# ─── the endpoint ───────────────────────────────────────────────────────────────

def test_import_loads_good_rows_blocks_the_rest_and_reports_errors():
    rid = _rfq()
    bad = CSV + "Oops Ltd,M10 bolt,1,not-a-price,0,3,,,,\n"
    r = _import(rid, bad)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 4 and len(body["errors"]) == 1 and body["errors"][0]["row"] == 5
    d = client.get(f"/api/rfqs/{rid}").json()
    assert list(d["quotes"]) == ["Imported 1", "Imported 2", "Imported 3", "Imported 4"]
    rows = {r["quote_id"]: r for r in d["evaluation"]["rows"]}
    assert rows["Imported 1"]["landed"] == 1200 and rows["Imported 2"]["landed"] == 1150
    assert d["evaluation"]["winner"]["quote_id"] == "Imported 2"                  # the brief's case check, from a file
    assert rows["Imported 3"]["status"] == "exception" and "7 days" in rows["Imported 3"]["reason"]
    assert rows["Imported 4"]["status"] == "blocked" and rows["Imported 4"]["reason"] == "pack size unknown"   # missing pack size


def test_imported_suppliers_show_their_name_to_the_buyer_only_and_need_no_reveal():
    rid = _rfq()
    _import(rid, CSV)
    d = client.get(f"/api/rfqs/{rid}").json()
    assert d["revealed"]["Imported 1"]["business_name"] == "Acme Traders"
    assert "not verified" in d["revealed"]["Imported 1"]["verification_text"].lower() or "not checked" in d["revealed"]["Imported 1"]["verification_text"].lower()
    assert all(q["imported"] for versions in d["quotes"].values() for q in versions)
    assert d["plan"]["reveals_left"] == store.reveals_left("u_test")              # importing used no reveals
    ok = client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Imported 2", "reason": "Lowest landed", "approver": "Me"})
    assert ok.status_code == 200                                                   # no reveal needed for a supplier you named


def test_a_shared_page_never_carries_the_buyers_own_supplier_names():
    from app.auth import get_current_user
    rid = _rfq()
    _import(rid, CSV)
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Imported 2", "reason": "x", "approver": "Me"})
    link = client.post(f"/api/rfqs/{rid}/share").json()
    app.dependency_overrides.pop(get_current_user, None)
    blob = client.get(f"/api/share/{link['token']}").text
    for name in ("Acme", "Beta Hardware", "Gamma", "Delta"):
        assert name not in blob, name
    assert "Imported 2" in blob


def test_importing_the_same_supplier_again_makes_a_new_version():
    rid = _rfq()
    _import(rid, "supplier,units_per_pack,pack_price,freight,lead_days\nAcme Traders,1,10,200,3\n")
    _import(rid, "supplier,units_per_pack,pack_price,freight,lead_days\nacme traders,1,10,149,3\n")
    d = client.get(f"/api/rfqs/{rid}").json()
    assert list(d["quotes"]) == ["Imported 1"] and [v["version"] for v in d["quotes"]["Imported 1"]] == [1, 2]
    assert d["quotes"]["Imported 1"][-1]["landed_cost"] == 1149


def test_imported_rows_respect_gst_basis_stock_and_item():
    rid = client.post("/api/rfqs", json={"item": "M10 bolt", "qty": 100, "need_in_days": 5, "buyer_company": "Co",
                                         "buyer_name": "B", "gst_claimable": True}).json()["id"]
    _import(rid, """supplier,item,units_per_pack,pack_price,freight,lead_days,gst_rate,price_includes_gst,max_qty
Plus GST,M10 bolt,1,10,0,3,18,no,
Incl GST,M10 bolt,1,11.80,0,3,18,yes,
Short,M10 bolt,1,5,0,3,,,60
Wrong,M8 washer,1,2,0,3,,,
""")
    rows = {r["quote_id"]: r for r in client.get(f"/api/rfqs/{rid}").json()["evaluation"]["rows"]}
    assert rows["Imported 1"]["landed"] == pytest.approx(1000) and rows["Imported 2"]["landed"] == pytest.approx(1000)
    assert rows["Imported 3"]["fill_qty"] == 60 and rows["Imported 3"]["status"] == "exception"
    assert rows["Imported 4"]["status"] == "blocked" and rows["Imported 4"]["reason"] == "different item"


def test_no_portal_for_imported_suppliers_so_no_targets_or_chat():
    rid = _rfq()
    _import(rid, CSV)
    t = client.post(f"/api/rfqs/{rid}/targets", json={"supplier_id": "Imported 1", "cut_needed": 51, "sent_by": "Me"})
    assert t.status_code == 409 and "negotiate" in str(t.json()).lower()
    assert client.post(f"/api/rfqs/{rid}/threads/Imported 1/messages", json={"sender": "buyer", "sender_name": "b", "text": "hi"}).status_code == 409


def test_import_guards_ownership_size_format_and_closed_requests():
    rid = _rfq()
    assert _import(rid, "").status_code == 422
    assert _import(rid, "supplier\n").status_code == 422
    assert client.post(f"/api/rfqs/{rid}/import-quotes", json={"format": "xml", "data": "<a/>"}).status_code == 422
    assert _import(rid, "x" * 300_000).status_code == 422
    many = "supplier,pack_price,lead_days\n" + "\n".join(f"S{i},10,3" for i in range(250))
    assert _import(rid, many).status_code == 422                                   # more than 200 rows
    assert _import("rfq_nope", CSV).status_code == 404
    client.post(f"/api/rfqs/{rid}/import-quotes", json={"format": "csv", "data": CSV})
    client.post(f"/api/rfqs/{rid}/decision", json={"winner_id": "Imported 2", "reason": "x", "approver": "Me"})
    assert _import(rid, CSV).status_code == 409
    from app.auth import AuthUser, get_current_user
    other = _rfq()
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="intruder", email="i@t.test")
    assert _import(other, CSV).status_code in (403, 404)


def test_json_import_matches_csv_and_the_template_is_downloadable():
    rid = _rfq()
    rows = parse_csv(CSV)
    r = _import(rid, json.dumps({"quotes": rows}), "json")
    assert r.status_code == 200 and r.json()["imported"] == 4
    t = client.get("/api/import-template").json()
    assert "supplier" in t["csv"].splitlines()[0] and json.loads(t["json"])
    ok, errs = validate_rows(parse_csv(t["csv"]), "M10 bolt")
    assert ok and not errs                                                         # the template itself imports cleanly
