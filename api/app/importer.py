"""CSV and JSON quote import. Forgiving about column names and number formats, strict and specific about mistakes.

Bad rows are reported with a row number and a plain message ("row 3: pack price is not a number") and skipped;
good rows still load. Nothing here decides a price or fills a gap: a blank pack size stays blank, and the rules
engine then blocks that quote with the reason "pack size unknown".
"""
import csv
import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple

MAX_ROWS = 200
MAX_CHARS = 200_000

# canonical field -> header spellings we accept (compared after lowercasing and dropping punctuation)
HEADERS: Dict[str, set] = {
    "supplier": {"supplier", "suppliername", "name", "vendor", "vendorname", "sellername", "company"},
    "item": {"item", "itemname", "product", "material", "description"},
    "pack_size": {"packsize", "unitsperpack", "unitspack", "qtyperpack", "unitsinpack", "pcsperpack", "packqty"},
    "pack_price": {"packprice", "packpriceinr", "packpricerupees", "priceperpack", "price", "rate", "packrate"},
    "freight": {"freight", "freightcharge", "freightinr", "delivery", "deliverycharge", "shipping"},
    "lead_days": {"leaddays", "lead", "leadtime", "leadtimedays", "deliverydays", "days"},
    "moq": {"moq", "minimumorder", "minorderqty", "minimumorderquantity", "minqty"},
    "max_qty": {"maxqty", "maxquantity", "maxsupply", "capacity", "stock", "available"},
    "tax_rate": {"taxrate", "gstrate", "gst", "gstpercent", "gstpct", "tax"},
    "price_includes_tax": {"priceincludestax", "priceincludesgst", "includesgst", "includestax", "gstincluded",
                           "taxincluded", "gstinclusive", "inclusive"},
    "notes": {"notes", "remarks", "terms", "comment", "comments"},
}
_LOOKUP = {spelling: field for field, spellings in HEADERS.items() for spelling in spellings}
REQUIRED = ("supplier", "pack_price", "lead_days")

_YES = {"yes", "y", "true", "1", "incl", "inclusive", "included", "with gst", "including"}
_NO = {"no", "n", "false", "0", "excl", "exclusive", "excluded", "without gst", "excluding", "extra"}


def _canon(header: str) -> Optional[str]:
    return _LOOKUP.get(re.sub(r"[^a-z0-9]", "", str(header).lower()))


def _canonical_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        field = _canon(key) if key is not None else None
        if field and field not in out:
            out[field] = value
    return out


def _blank(row: Dict[str, Any]) -> bool:
    return all(v is None or str(v).strip() == "" for v in row.values())


def parse_csv(text: str) -> List[Dict[str, Any]]:
    text = (text or "").lstrip("﻿")
    if not text.strip():
        raise ValueError("The file is empty.")
    first = text.splitlines()[0]
    delimiter = ";" if first.count(";") > first.count(",") else "\t" if first.count("\t") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    raw_rows = [{k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in reader]
    rows = [_canonical_row(r) for r in raw_rows if not _blank(r)]     # skip rows that are empty in the file itself
    if not rows:
        raise ValueError("The file has a header but no quote rows.")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"More than {MAX_ROWS} rows. Split the file and import it in parts.")
    return rows


def parse_json(text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ValueError(f"That is not valid JSON ({e.__class__.__name__}).")
    if isinstance(data, dict):
        data = data.get("quotes", data.get("rows"))
    if not isinstance(data, list) or not data or not all(isinstance(x, dict) for x in data):
        raise ValueError('Expected a list of quotes, or {"quotes": [ ... ]}.')
    rows = [_canonical_row(x) for x in data if not _blank(x)]
    if not rows:
        raise ValueError("No quote rows found.")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"More than {MAX_ROWS} rows. Split the file and import it in parts.")
    return rows


def _number(value: Any) -> Optional[float]:
    """'₹1,250.50' -> 1250.5. None when it is not a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"(?i)(₹|rs\.?|inr)", "", str(value)).replace(",", "").replace(" ", "").rstrip("%")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _whole(value: float) -> Optional[int]:
    return int(value) if float(value).is_integer() else None


def validate_rows(rows: List[Dict[str, Any]], request_item: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(good rows with real types, row-level errors). Rows with any error are skipped whole."""
    present = {k for r in rows for k in r}              # which columns exist; a blank cell is a row problem, not a file problem
    missing = [f for f in REQUIRED if f not in present]
    if missing:
        raise ValueError("missing required column(s): " + ", ".join(m.replace("_", " ") for m in missing))

    good: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for n, raw in enumerate(rows, start=1):
        errs: List[Tuple[str, str]] = []
        val = lambda f: (str(raw[f]).strip() if raw.get(f) is not None else "")
        row: Dict[str, Any] = {}

        row["supplier"] = val("supplier")[:80]
        if not row["supplier"]:
            errs.append(("supplier", "supplier is required"))

        price = None
        if not val("pack_price"):
            errs.append(("pack_price", "pack price is required"))
        else:
            price = _number(raw["pack_price"])
            if price is None:
                errs.append(("pack_price", "pack price is not a number"))
            elif price <= 0:
                errs.append(("pack_price", "pack price must be greater than zero"))
        row["pack_price"] = price

        row["pack_size"] = None                          # blank stays blank: the engine blocks it as "pack size unknown"
        if val("pack_size"):
            size = _number(raw["pack_size"])
            if size is None or _whole(size) is None:
                errs.append(("pack_size", "units per pack is not a number" if size is None else "units per pack must be a whole number"))
            elif size <= 0:
                errs.append(("pack_size", "units per pack must be greater than zero"))
            else:
                row["pack_size"] = int(size)

        row["freight"] = 0.0
        if val("freight"):
            f = _number(raw["freight"])
            if f is None:
                errs.append(("freight", "freight is not a number"))
            elif f < 0:
                errs.append(("freight", "freight must be zero or more"))
            else:
                row["freight"] = f

        row["lead_days"] = None
        if not val("lead_days"):
            errs.append(("lead_days", "lead time is required"))
        else:
            d = _number(raw["lead_days"])
            if d is None or _whole(d) is None:
                errs.append(("lead_days", "lead time is not a number" if d is None else "lead time must be whole days"))
            elif d < 0:
                errs.append(("lead_days", "lead time must be zero or more"))
            else:
                row["lead_days"] = int(d)

        for field, label, floor in (("moq", "minimum order", 1), ("max_qty", "maximum quantity", 0)):
            row[field] = None
            if val(field):
                q = _number(raw[field])
                if q is None or _whole(q) is None:
                    errs.append((field, f"{label} is not a whole number"))
                elif q < floor:
                    errs.append((field, f"{label} must be {floor} or more"))
                else:
                    row[field] = int(q)

        row["tax_rate"] = None
        if val("tax_rate"):
            t = _number(raw["tax_rate"])
            if t is None or not 0 <= t <= 100:
                errs.append(("tax_rate", "GST rate must be between 0 and 100"))
            else:
                row["tax_rate"] = t

        row["price_includes_tax"] = None
        if val("price_includes_tax"):
            word = val("price_includes_tax").lower()
            if word in _YES:
                row["price_includes_tax"] = True
            elif word in _NO:
                row["price_includes_tax"] = False
            else:
                errs.append(("price_includes_tax", "price includes GST must be yes or no"))

        row["item"] = val("item")[:120] or None
        row["notes"] = val("notes")[:300] or None

        if errs:
            errors.extend({"row": n, "field": f, "message": f"row {n}: {m}"} for f, m in errs)
        else:
            good.append(row)
    return good, errors


TEMPLATE_CSV = (
    "supplier,item,units_per_pack,pack_price,freight,lead_days,moq,gst_rate,price_includes_gst,notes\n"
    "Acme Traders,M10 bolt,1,10,200,3,,18,no,Ex-warehouse\n"
    "Beta Hardware,M10 bolt,1,11,50,3,,18,no,\n"
    "Gamma Boxes,M10 bolt,50,400,0,7,,18,no,Box of 50\n"
)
