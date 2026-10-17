"""Buyer intake: free text in, a validated request draft out. Nothing is saved here.

The model only extracts what the buyer said. Code then verifies every value against the source text
and drops anything the model invented, so the confirm card never shows an unsupported number or date.
"""
import re
from datetime import date, datetime
from typing import Any, Optional

from .ai import structured_call
from .matching import normalise_item

SYSTEM = (
    "You extract a purchase request from what a buyer said. The buyer may mix English and Hindi. "
    "Copy values exactly as stated. If a value was not stated, return null. Never guess, convert, or infer "
    "a quantity, an item or a date. need_in_days is set only when the buyer said a number of days; "
    "otherwise put the buyer's own words for the deadline (for example 'by Friday') in need_by_phrase. "
    "If the buyer names more than one item, return the first in item and list the rest in other_items. "
    "priority is cheapest, fastest or balanced only if the buyer clearly asked for it."
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["item", "quantity", "need_in_days", "need_by_phrase", "priority", "note", "other_items"],
    "properties": {
        "item": {"type": ["string", "null"]},
        "quantity": {"type": ["integer", "null"]},
        "need_in_days": {"type": ["integer", "null"]},
        "need_by_phrase": {"type": ["string", "null"]},
        "priority": {"type": ["string", "null"], "enum": ["cheapest", "fastest", "balanced", None]},
        "note": {"type": ["string", "null"]},
        "other_items": {"type": "array", "items": {"type": "string"}},
    },
}

_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5, "das": 10, "bees": 20, "pachas": 50,
    "dozen": 12,
}
_MULT = {"hundred": 100, "sau": 100, "thousand": 1000, "hazaar": 1000, "hazar": 1000, "lakh": 100000}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_HINDI_DAYS = {"somvar": 0, "mangalvar": 1, "budhvar": 2, "guruvar": 3, "veervar": 3, "shukravar": 4,
               "shanivar": 5, "ravivar": 6}
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _tokens(text: str) -> list[str]:
    return normalise_item(text).split()


def singular(token: str) -> str:
    if len(token) > 4 and token.endswith(("xes", "ches", "shes", "sses", "zes")):
        return token[:-2]
    return token[:-1] if len(token) > 3 and token.endswith("s") and not token.endswith("ss") else token


def numbers_in_text(text: str) -> set[int]:
    """Every quantity a reader could honestly take from the text: digits, number words, '2 hazaar'."""
    found: set[int] = set()
    low = text.lower().replace(",", "")
    for m in re.finditer(r"\d+(?:\.\d+)?\s*(k|lakh|hazaar|hazar|thousand|hundred|sau)?\b", low):
        base = float(re.match(r"\d+(?:\.\d+)?", m.group(0)).group(0))
        mult = {"k": 1000, "thousand": 1000, "hazaar": 1000, "hazar": 1000, "lakh": 100000,
                "hundred": 100, "sau": 100}.get(m.group(1) or "", 1)
        found.add(int(base * mult))
    words = re.findall(r"[a-z]+|\d+", low)
    total, current, seen = 0, 0, False
    for w in words + ["#"]:
        if w in _WORDS:
            current += _WORDS[w]; seen = True
        elif w in _MULT:
            current = (current or 1) * _MULT[w]; seen = True
            if _MULT[w] >= 1000:
                total += current; current = 0
        else:
            if seen:
                found.add(total + current)
            total, current, seen = 0, 0, False
    return found


def resolve_need_days(phrase: str, today: Optional[date] = None) -> Optional[int]:
    """Turn the buyer's own deadline words into days, in code. None if it cannot be done honestly."""
    today = today or date.today()
    p = phrase.lower().strip()
    m = re.search(r"(\d+)\s*(?:days?|din|dino)", p)
    if m and int(m.group(1)) > 0:
        return int(m.group(1))
    if re.search(r"\b(tomorrow|kal)\b", p):
        return 1
    if "next week" in p or "agle hafte" in p:
        return 7
    for i, name in enumerate(_WEEKDAYS):
        if name in p or name[:3] + "day" in p:
            return ((i - today.weekday()) % 7) or 7
    for name, i in _HINDI_DAYS.items():
        if name in p:
            return ((i - today.weekday()) % 7) or 7
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", p)
    if m:
        d = (date(int(m.group(1)), int(m.group(2)), int(m.group(3))) - today).days
        return d if d > 0 else None
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})", p)
    if m and m.group(2) in _MONTHS:
        month, day = _MONTHS.index(m.group(2)) + 1, int(m.group(1))
        try:
            target = date(today.year, month, day)
            if target <= today:
                target = date(today.year + 1, month, day)
        except ValueError:
            return None
        return (target - today).days
    return None


def snap_item(item: str, catalog_names: dict[str, str]) -> tuple[str, bool]:
    """Use the catalog's own spelling when the item matches a name or alias (plural-insensitive)."""
    key = " ".join(singular(t) for t in _tokens(item))
    hit = catalog_names.get(key)
    return (hit, True) if hit else (item.strip(), False)


def build_draft(text: str, raw: Optional[dict[str, Any]], catalog_names: dict[str, str],
                today: Optional[date] = None) -> dict[str, Any]:
    """Validate the model output against the source text. Unsupported values are dropped and reported."""
    draft: dict[str, Any] = {"item": None, "qty": None, "need_in_days": None, "need_by_phrase": None,
                             "priority_mode": None, "note": None, "catalog_match": False}
    warnings: list[str] = []
    if raw is None:
        return {"draft": draft, "missing": ["item", "qty", "need_in_days"], "warnings": warnings}

    src_tokens = {singular(t) for t in _tokens(text)}
    low = text.lower()

    item = (raw.get("item") or "").strip()
    if item:
        item_tokens = [singular(t) for t in _tokens(item)]
        if item_tokens and all(t in src_tokens for t in item_tokens):
            draft["item"], draft["catalog_match"] = snap_item(item, catalog_names)
        else:
            warnings.append("Dropped an item the buyer did not say.")

    qty = raw.get("quantity")
    if isinstance(qty, int) and qty > 0:
        if qty in numbers_in_text(text):
            draft["qty"] = qty
        else:
            warnings.append("Dropped a quantity the buyer did not say.")

    days = raw.get("need_in_days")
    if isinstance(days, int) and days > 0:
        if days in numbers_in_text(text):
            draft["need_in_days"] = days
        else:
            warnings.append("Dropped a deadline the buyer did not say.")
    phrase = (raw.get("need_by_phrase") or "").strip()
    if phrase and phrase.lower() in low:
        draft["need_by_phrase"] = phrase
        if draft["need_in_days"] is None:
            resolved = resolve_need_days(phrase, today)
            if resolved:
                draft["need_in_days"] = resolved

    pr = raw.get("priority")
    if pr in ("cheapest", "fastest", "balanced"):
        draft["priority_mode"] = pr
    note = (raw.get("note") or "").strip()
    if note and note.lower() in low:
        draft["note"] = note

    others = [o for o in (raw.get("other_items") or []) if isinstance(o, str) and o.strip()]
    if others:
        warnings.append("One item per request for now. Not included: " + ", ".join(others) + ".")

    missing = [k for k, f in (("item", "item"), ("qty", "qty"), ("need_in_days", "need_in_days")) if draft[f] is None]
    return {"draft": draft, "missing": missing, "warnings": warnings}


def draft_from_text(text: str, catalog_names: dict[str, str], today: Optional[date] = None) -> dict[str, Any]:
    """Full intake draft. `fallback` is True when the AI path was unavailable (no key, timeout, refusal)."""
    text = text.strip()
    raw = structured_call(SYSTEM, text, "purchase_request", SCHEMA) if text else None
    out = build_draft(text, raw, catalog_names, today)
    out["fallback"] = raw is None
    out["generated_at"] = datetime.now().isoformat()
    return out
