"""Matching and the seller-side rules verdict. Pure functions, no AI: the catalog decides."""
import re
from typing import Iterable, List

from .models import DraftQuote, PriceBreak, RFQ, SupplierProduct, Verdict


def normalise_item(name: str) -> str:
    """Lowercase, punctuation to spaces, single-spaced. 'M10  Bolt!' -> 'm10 bolt'."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", name.lower())).strip()


def product_names(p: SupplierProduct) -> set[str]:
    return {normalise_item(n) for n in [p.name, *p.aliases] if n.strip()}


def matching_product(item: str, products: Iterable[SupplierProduct]) -> SupplierProduct | None:
    """Exact name or alias match only. First hit wins."""
    want = normalise_item(item)
    if not want:
        return None
    for p in products:
        if want in product_names(p):
            return p
    return None


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
        price_break_applied=applied, price_breaks=tiers, free_freight_above=product.free_freight_above, tax_rate=product.tax_rate, price_includes_tax=product.price_includes_tax,
        verdict=verdict_for(rfq, product),
    )
