"""Reading a supplier's pasted message (WhatsApp, email) into quote rows.

The model only reads. Code then checks every number against the message and drops what the message does not say,
so nothing is invented: a pack size nobody stated stays blank (the engine blocks it), freight nobody stated stays
blank and is flagged, and 'free delivery' is only believed if those words are in the message. The rows come back
as a draft for the buyer to check and edit; nothing is saved until they confirm through the normal import.
"""
import re
from typing import Any, Optional

from .ai import structured_call
from .assistant import numbers_used
from .matching import normalise_item

SYSTEM = (
    "You read a message a supplier sent a buyer and extract each price offer in it. The message may mix English and Hindi. "
    "Copy numbers exactly as written. If something is not stated, return null. Never guess a pack size, freight, GST rate, "
    "minimum order or lead time. price_basis is 'per_unit' if the price is for one piece (per piece, each, /pc), "
    "'per_pack' if it is per pack, box or carton, otherwise null. freight_free is true only if the message says delivery, "
    "shipping or freight is free. If the message contains no price offer, return an empty list."
)

_NUM = {"type": ["number", "null"]}
_INT = {"type": ["integer", "null"]}
_QUOTE_FIELDS = {
    "supplier": {"type": ["string", "null"]}, "pack_price": _NUM, "pack_size": _INT,
    "price_basis": {"type": ["string", "null"], "enum": ["per_unit", "per_pack", None]},
    "freight": _NUM, "freight_free": {"type": ["boolean", "null"]}, "lead_days": _INT, "moq": _INT, "max_qty": _INT,
    "gst_rate": _NUM, "price_includes_gst": {"type": ["boolean", "null"]}, "notes": {"type": ["string", "null"]},
}
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["quotes"],
    "properties": {"quotes": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": list(_QUOTE_FIELDS), "properties": _QUOTE_FIELDS}}},
}

_FREE = re.compile(r"\bfree\s+(?:delivery|shipping|freight|dispatch)\b|\b(?:delivery|shipping|freight)\s+(?:is\s+)?free\b|\bno\s+(?:delivery|shipping|freight)\s+charges?\b", re.I)


def build_rows(text: str, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Importer-shaped rows plus plain-language warnings. Anything the message does not support is dropped."""
    if raw is None:
        return {"rows": [], "warnings": [], "fallback": True}
    allowed = numbers_used(text)
    low = text.lower()
    src_tokens = set(normalise_item(text).split())
    warnings: list[str] = []

    def supported(v: Any) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and any(abs(float(v) - a) < 0.01 for a in allowed)

    rows = []
    for i, q in enumerate(raw.get("quotes") or [], start=1):
        tag = f"Quote {i}: " if len(raw.get("quotes", [])) > 1 else ""
        row: dict[str, Any] = {"supplier": None, "item": None, "pack_size": None, "pack_price": None, "freight": None,
                               "lead_days": None, "moq": None, "max_qty": None, "tax_rate": None, "price_includes_tax": None,
                               "notes": None}
        name = (q.get("supplier") or "").strip()
        if name:
            if name and all(t in src_tokens for t in normalise_item(name).split()):
                row["supplier"] = name
            else:
                warnings.append(f"{tag}Dropped a supplier name the message does not contain.")
        if not row["supplier"]:
            warnings.append(f"{tag}Supplier name not found. Type it in.")

        if supported(q.get("pack_price")):
            row["pack_price"] = float(q["pack_price"])
        elif q.get("pack_price") is not None:
            warnings.append(f"{tag}Dropped a price the message does not state.")

        if supported(q.get("pack_size")) and int(q["pack_size"]) > 0:
            row["pack_size"] = int(q["pack_size"])
        elif q.get("price_basis") == "per_unit" and row["pack_price"] is not None:
            row["pack_size"] = 1
            warnings.append(f"{tag}The price is per unit, so it is treated as a pack of 1.")
        else:
            warnings.append(f"{tag}Pack size not stated, so this quote will be blocked as 'pack size unknown' until you fill it in.")

        if supported(q.get("freight")):
            row["freight"] = float(q["freight"])
        elif q.get("freight_free") and _FREE.search(text):
            row["freight"] = 0.0
        else:
            warnings.append(f"{tag}Freight not stated. It is blank here and will count as 0 on import, so check it.")

        if supported(q.get("lead_days")) and int(q["lead_days"]) >= 0:
            row["lead_days"] = int(q["lead_days"])
        else:
            warnings.append(f"{tag}Lead time not stated. It is required, so fill it in.")

        for field in ("moq", "max_qty"):
            if supported(q.get(field)) and int(q[field]) >= 0:
                row[field] = int(q[field])
        if supported(q.get("gst_rate")) and 0 <= q["gst_rate"] <= 100:
            row["tax_rate"] = float(q["gst_rate"])
            if isinstance(q.get("price_includes_gst"), bool):
                row["price_includes_tax"] = q["price_includes_gst"]
        notes = (q.get("notes") or "").strip()
        if notes and notes.lower() in low:
            row["notes"] = notes[:300]

        if row["supplier"] or row["pack_price"] is not None:
            rows.append(row)

    if not rows:
        warnings = ["No quote found in that message."]
    return {"rows": rows, "warnings": warnings, "fallback": False}


def draft_from_message(text: str) -> dict[str, Any]:
    text = text.strip()
    raw = structured_call(SYSTEM, text, "supplier_quotes", SCHEMA) if text else None
    return build_rows(text, raw)
