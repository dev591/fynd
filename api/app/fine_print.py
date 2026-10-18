"""Fine print: terms hidden in a seller's notes that change which quote is really best (advance payment, a short price
validity, extra charges, conditions, no returns). Rules read every note and need no key. A model is also asked, and each flag it
returns is kept only if its quoted phrase is really in the note and its kind is one we know, so it can only point at the
seller's own words, never invent a term. Nothing here changes a price or a winner: it is a warning shown beside the quote."""
import re
from typing import Dict, List

from .ai import structured_call

KINDS = {
    "advance_payment": "Asks for payment before delivery",
    "price_validity": "The price is only valid for a short time",
    "extra_charges": "Charges that are not in the total",
    "condition": "The offer depends on a condition",
    "no_returns": "No returns",
}
_RULES = [
    ("advance_payment", re.compile(r"\b\d{1,3}\s*%\s*advance\b|\badvance (?:payment|required)\b|\bpay(?:ment)? (?:first|upfront|in advance|before dispatch)\b|\bfull payment (?:before|in advance)\b|\bpayment must be made[^.]*before dispatch\b", re.I)),
    ("price_validity", re.compile(r"\b(?:price )?valid (?:for|till|until|only)\b[^.,;]{0,30}|\bprice (?:holds|expires)[^.,;]{0,30}|\bquote (?:expires|valid)[^.,;]{0,30}", re.I)),
    ("extra_charges", re.compile(r"\b(?:gst|tax|taxes|loading|unloading|packing|packaging|handling|insurance|transport|octroi)(?: charges)? (?:extra|additional|not included|to be paid)\b|\bplus (?:gst|taxes|loading|packing)\b|\bextra (?:charges|for packing|for loading)\b", re.I)),
    ("condition", re.compile(r"\bsubject to (?:stock|availability|confirmation|approval|prior sales)\b|\bonly if\b[^.,;]{0,40}|\bprovided (?:that )?[^.,;]{0,40}|\bconditional\b[^.,;]{0,30}", re.I)),
    ("no_returns", re.compile(r"\bno returns?\b|\bnon[- ]returnable\b|\bno (?:refund|replacement)s?\b", re.I)),
]
SYSTEM = (
    "Read a supplier's note on a price quote. List only terms that could cost the buyer money or flexibility and are not "
    "in the price: advance_payment, price_validity, extra_charges, condition, no_returns. For each, copy the exact words from "
    "the note into phrase. If there are none, return an empty list. Never invent a term or change the words."
)
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["flags"],
          "properties": {"flags": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["kind", "phrase"],
                                   "properties": {"kind": {"type": "string", "enum": list(KINDS)}, "phrase": {"type": "string"}}}}}}
_cache: Dict[str, List[dict]] = {}


def rule_flags(note: str) -> List[dict]:
    out: List[dict] = []
    for kind, rx in _RULES:
        m = rx.search(note or "")
        if m:
            out.append({"kind": kind, "phrase": m.group(0).strip(" .,;"), "label": KINDS[kind]})
    return out


def read(note: str) -> List[dict]:
    """Rules first, then the model; one entry per kind, every phrase taken from the note."""
    note = (note or "").strip()
    if len(note) < 8:
        return []
    if note in _cache:
        return _cache[note]
    flags = rule_flags(note)
    have = {f["kind"] for f in flags}
    raw = structured_call(SYSTEM, note[:600], "fine_print", SCHEMA)
    low = note.lower()
    for f in (raw or {}).get("flags", []):
        kind, phrase = f.get("kind"), (f.get("phrase") or "").strip()
        if kind in KINDS and kind not in have and phrase and phrase.lower() in low:
            flags.append({"kind": kind, "phrase": note[low.index(phrase.lower()):low.index(phrase.lower()) + len(phrase)], "label": KINDS[kind]})
            have.add(kind)
    _cache[note] = flags
    return flags


def for_request(store, rfq) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for sid, versions in store.quotes.get(rfq.id, {}).items():
        if not versions:
            continue
        flags = read(versions[-1].notes or "")
        if flags:
            out[store.alias_for(rfq.id, sid) or sid] = flags
    return out
