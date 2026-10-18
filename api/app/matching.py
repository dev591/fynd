"""Matching and the seller-side rules verdict. Pure functions, no AI: the catalog decides."""
import re
from typing import Iterable, List

from . import ai
from .ai import structured_call
from .models import DraftQuote, PriceBreak, RFQ, SupplierProduct, Verdict


def normalise_item(name: str) -> str:
    """Lowercase, punctuation to spaces, single-spaced. 'M10  Bolt!' -> 'm10 bolt'."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", name.lower())).strip()


def product_names(p: SupplierProduct) -> set[str]:
    """Every name this product answers to: its name, its aliases, the acronym written in brackets ("... (HDI) Boards" is also
    "HDI"), and the name with the bracket removed."""
    out: set[str] = set()
    for n in [p.name, *p.aliases]:
        if not n.strip():
            continue
        out.add(normalise_item(n))
        for acro in re.findall(r"\(([A-Za-z0-9][A-Za-z0-9 .-]{1,14})\)", n):
            out.add(normalise_item(acro))
        bare = normalise_item(re.sub(r"\([^)]*\)", " ", n))
        if bare:
            out.add(bare)
    return out


def singular(token: str) -> str:
    """boards -> board, boxes -> box, glass stays glass. Same rule the intake reader uses."""
    if len(token) > 4 and token.endswith(("xes", "ches", "shes", "sses", "zes")):
        return token[:-2]
    return token[:-1] if len(token) > 3 and token.endswith("s") and not token.endswith("ss") else token


def _tokens(text: str) -> set[str]:
    return {singular(t) for t in normalise_item(text).split()}


def match_with_basis(item: str, products: Iterable[SupplierProduct]) -> tuple[SupplierProduct | None, str | None]:
    """(product, 'exact' | 'similar'). Exact name or alias first. Otherwise one name's words sit inside the other's, so 'HDI boards'
    finds 'High-Density Interconnect (HDI) Boards' and the other way round. A different size or number never matches
    (M10 bolt is not M8 bolt) because then neither side's words contain the other's."""
    want = normalise_item(item)
    if not want:
        return None, None
    plist = list(products)
    for p in plist:
        if want in product_names(p):
            return p, "exact"
    wt = _tokens(item)
    for p in plist:
        for name in product_names(p):
            nt = _tokens(name)
            if nt and wt and (wt <= nt or nt <= wt):
                return p, "similar"
    return None, None


def matching_product(item: str, products: Iterable[SupplierProduct]) -> SupplierProduct | None:
    return match_with_basis(item, products)[0]


# ─── AI: relate a term the rules cannot (PCB and "Multilayer Printed Circuit Board") ───

_ai_cache: dict[tuple, list[str]] = {}
AI_SYSTEM = (
    "A buyer wants an item. From the catalog product names below, list the ones that are the same kind of product, allowing "
    "abbreviations, synonyms and different wording. Do not include products that are merely related, or whose size or "
    "specification makes them a different product. Copy names exactly as given. If none, return an empty list."
)
AI_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["matches"],
             "properties": {"matches": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["name"],
                                                                 "properties": {"name": {"type": "string"}}}}}}


def ai_matches(item: str, candidates: list[tuple[str, SupplierProduct]]) -> dict[str, SupplierProduct]:
    """seller id -> product, for catalog items a model says are the same product. Only names that really exist in the catalog
    are kept; with AI off, or on any failure, nothing is added."""
    if not candidates or not ai.ai_enabled():
        return {}
    names = sorted({p.name for _, p in candidates})[:80]
    key = (normalise_item(item), tuple(names))
    if key not in _ai_cache:
        raw = structured_call(AI_SYSTEM, f"Requested item: {item}\nCatalog products:\n" + "\n".join(f"- {n}" for n in names), "item_match_ai", AI_SCHEMA)
        _ai_cache[key] = [m.get("name") for m in (raw or {}).get("matches", []) if m.get("name") in names]
    chosen = set(_ai_cache[key])
    out: dict[str, SupplierProduct] = {}
    for sid, p in candidates:
        if p.name in chosen and sid not in out:
            out[sid] = p
    return out


def verdict_for(rfq: RFQ, product: SupplierProduct) -> Verdict:
    """Can this seller fulfil the request from its catalog row? yes / partly / no, with reasons."""
    reasons: List[str] = []
    level = "yes"

    if product.stock is not None:
        if product.stock <= 0:
            return Verdict(can_fulfil="no", reasons=["Out of stock (stock is a snapshot, not reserved)."])
        if product.stock < rfq.qty:
            level = "partly"
            reasons.append(f"Stock covers {product.stock} of {rfq.qty} units.")
    if product.usual_lead_days > rfq.need_in_days:
        level = "partly"
        reasons.append(f"Usual lead time is {product.usual_lead_days} days, needed within {rfq.need_in_days}.")
    if product.moq > rfq.qty:
        level = "partly"
        reasons.append(f"Minimum order is {product.moq} units, request is for {rfq.qty}.")
    if not reasons:
        reasons.append("Stock, lead time and minimum order all fit.")
    return Verdict(can_fulfil=level, reasons=reasons)


def draft_quote(rfq: RFQ, product: SupplierProduct) -> DraftQuote:
    """Prefill a quote from the catalog row. The highest price break the quantity reaches wins."""
    price, applied = product.pack_price, None
    for b in sorted(product.price_breaks, key=lambda b: b.min_qty):
        if rfq.qty >= b.min_qty:
            price, applied = b.pack_price, b.min_qty
    tiers = [PriceBreak(min_qty=1, pack_price=product.pack_price), *sorted(product.price_breaks, key=lambda b: b.min_qty)] if product.price_breaks else []
    return DraftQuote(
        product_id=product.id, product_name=product.name,
        pack_price=price, pack_size=product.pack_size, freight=product.freight,
        lead_days=product.usual_lead_days, moq=product.moq,
        max_qty=product.stock if product.stock is not None else product.capacity_cap,
        price_break_applied=applied, price_breaks=tiers,
        free_freight_above=product.free_freight_above,
        per_unit_freight=product.per_unit_freight,
        tax_rate=product.tax_rate, price_includes_tax=product.price_includes_tax,
        verdict=verdict_for(rfq, product),
    )
