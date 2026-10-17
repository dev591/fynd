"""Seller-side assistant: wording for a catalog draft, and the item-match check.

AI proposes, the catalog decides. The quote numbers are copied from the catalog row by code (see
matching.draft_quote). The model only writes wording, and every number in that wording is checked
against the data afterwards. One stray number and the AI text is discarded for a plain template.
"""
import re
from typing import Any, Optional

from .ai import structured_call
from .engine import order
from .intake import numbers_in_text, singular
from .matching import normalise_item, product_names
from .models import DraftQuote, Quote, RFQ, SupplierProduct

REPLY_SYSTEM = (
    "You write two or three short, plain sentences a seller will send a buyer alongside a quote. "
    "Use only the facts given. Copy every number exactly as given. Do not add any other number, "
    "discount, guarantee, date or promise. Do not mention stock unless the facts say it is short."
)
REPLY_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["message"],
    "properties": {"message": {"type": "string"}},
}

MATCH_SYSTEM = (
    "You compare what a buyer asked for with one catalog item. Answer same, different or unsure, "
    "with one short reason that only mentions sizes, grades or materials that appear in the two names. "
    "Do not add any number that is not in the two names."
)
MATCH_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["verdict", "reason"],
    "properties": {"verdict": {"type": "string", "enum": ["same", "different", "unsure"]},
                   "reason": {"type": "string"}},
}


def numbers_used(text: str) -> set[float]:
    """Every number a reader could take from the text: digits (with commas, decimals) and number words."""
    out = {float(m.replace(",", "")) for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}
    out |= {float(n) for n in numbers_in_text(text)}
    return out


# A reused number can pass the check above ("10% off" when the pack price is 10), so wording that
# makes an offer or a promise is rejected outright. The seller can still add terms by hand.
_PROMISE = re.compile(r"%|percent|discount|\boff\b|\bfree\b|guarantee|warranty|rebate|\boffer|special|bonus|complimentary",
                      re.I)


def makes_promise(text: str) -> bool:
    return bool(_PROMISE.search(text))


def numbers_supported(text: str, allowed: set[float]) -> bool:
    return all(any(abs(n - a) < 0.01 for a in allowed) for n in numbers_used(text))


def landed_for(rfq: RFQ, draft: DraftQuote) -> float | None:
    """Landed cost for the units the seller can actually cover, from the engine, never the model."""
    qty = min(rfq.qty, draft.max_qty) if draft.max_qty else rfq.qty
    q = Quote(id="x", supplier="x", item=rfq.item, pack_price=draft.pack_price, pack_size=draft.pack_size,
              freight=draft.freight, lead_days=draft.lead_days, moq=draft.moq)
    o = order(q, qty)
    return o.landed if o else None


def facts_for(rfq: RFQ, draft: DraftQuote) -> dict[str, Any]:
    landed = landed_for(rfq, draft)
    covered = min(rfq.qty, draft.max_qty) if draft.max_qty else rfq.qty
    return {
        "item": rfq.item, "units_requested": rfq.qty, "units_covered": covered,
        "needed_within_days": rfq.need_in_days, "pack_price": draft.pack_price,
        "units_per_pack": draft.pack_size, "freight": draft.freight, "lead_days": draft.lead_days,
        "minimum_order": draft.moq, "landed_total": landed,
        "can_fulfil": draft.verdict.can_fulfil, "reasons": draft.verdict.reasons,
    }


def allowed_numbers(rfq: RFQ, draft: DraftQuote) -> set[float]:
    allowed: set[float] = set()
    for v in facts_for(rfq, draft).values():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            allowed.add(float(v))
    for r in draft.verdict.reasons:      # the verdict reasons are rules output and may be quoted
        allowed |= numbers_used(r)
    allowed |= numbers_used(rfq.item) | numbers_used(draft.product_name)
    return allowed


def template_message(rfq: RFQ, draft: DraftQuote) -> str:
    f = facts_for(rfq, draft)
    covered = f["units_covered"]
    lines = [
        f"We can supply {covered} of your {rfq.qty} units of {rfq.item}." if covered < rfq.qty
        else f"We can supply your {rfq.qty} units of {rfq.item}.",
        f"Pack price is ₹{draft.pack_price:g} for {draft.pack_size} unit{'s' if draft.pack_size != 1 else ''}, "
        f"freight ₹{draft.freight:g}, delivery in {draft.lead_days} days.",
    ]
    if f["landed_total"] is not None:
        lines.append(f"Total landed cost: ₹{f['landed_total']:,.0f}.")
    return " ".join(lines)


def reply_for(rfq: RFQ, draft: DraftQuote) -> dict[str, Any]:
    """{text, source: 'ai'|'template', discarded_reason}. Falls back to the template on any doubt."""
    template = template_message(rfq, draft)
    facts = facts_for(rfq, draft)
    raw = structured_call(REPLY_SYSTEM, str(facts), "seller_reply", REPLY_SCHEMA)
    if raw is None:
        return {"text": template, "source": "template", "discarded_reason": None, "ai_text": None}
    text = (raw.get("message") or "").strip()
    if not text:
        return {"text": template, "source": "template", "discarded_reason": "empty", "ai_text": text}
    if makes_promise(text):
        return {"text": template, "source": "template",
                "discarded_reason": "AI text made an offer or promise that is not in your data", "ai_text": text}
    if not numbers_supported(text, allowed_numbers(rfq, draft)):
        return {"text": template, "source": "template",
                "discarded_reason": "AI text contained a number that is not in your data", "ai_text": text}
    return {"text": text, "source": "ai", "discarded_reason": None, "ai_text": text}


# ─── Item-match check (warn only, never blocks) ─────────────────────────────

_SIZE = re.compile(r"^m\d+$")


def _tokens(text: str) -> set[str]:
    return {singular(t) for t in normalise_item(text).split()}


def item_match(request_item: str, product: SupplierProduct) -> dict[str, Any]:
    """Rules first (name, alias, conflicting M-size), then the model only for what rules cannot settle."""
    want = normalise_item(request_item)
    if want in product_names(product):
        return {"verdict": "same", "reason": "Matches a catalog name or alias.", "source": "rules"}
    req, cat = _tokens(request_item), _tokens(product.name)
    rs, cs = {t for t in req if _SIZE.match(t)}, {t for t in cat if _SIZE.match(t)}
    if rs and cs and rs.isdisjoint(cs):
        return {"verdict": "different", "source": "rules",
                "reason": f"Request is {', '.join(sorted(rs)).upper()}, catalog item is {', '.join(sorted(cs)).upper()}."}
    raw = structured_call(MATCH_SYSTEM, f"Buyer asked for: {request_item}\nCatalog item: {product.name}",
                          "item_match", MATCH_SCHEMA)
    if raw and raw.get("verdict") in ("same", "different", "unsure"):
        reason = (raw.get("reason") or "").strip()
        allowed = numbers_used(request_item) | numbers_used(product.name)
        if numbers_supported(reason, allowed):
            return {"verdict": raw["verdict"], "reason": reason, "source": "ai"}
    return {"verdict": "unsure", "reason": "No automatic check available.", "source": "none"}
