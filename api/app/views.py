"""What each audience may see. The store holds the truth; these functions are the only way it leaves the server.

Masking lives here, never in engine.py and never in the browser. Three audiences:
  buyer   sees sellers only as "Seller N" until that seller is revealed.
  seller  sees the buyer only as a descriptor until this seller is revealed.
  public  (a shared one-pager) never sees identities at all.
Functions take the store as an argument so this module does not import it.
"""
from typing import Any, Optional

from .masking import scrub
from .models import ChatMessage, NegotiationTarget, Need
from .engine import evaluate


def verification_text(tier: str, synthetic: bool) -> str:
    """Says exactly what was checked, and no more."""
    text = {
        "none": "No checks yet",
        "email": "Email address confirmed at sign-up",
        "tax_ids": "GSTIN and PAN format and cross-check passed (not checked against government records)",
        "registry": "Demo registry check on synthetic data (no government registry was queried)",
    }.get(tier, "No checks yet")
    return f"{text}; synthetic demo seller" if synthetic else text


def identity_of(store, supplier_id: str) -> dict[str, Any]:
    """Everything that identifies a seller. Only ever returned after a reveal."""
    p = store.supplier_profiles.get(supplier_id)
    if not p:
        return {}
    return {
        "business_name": p.business_name, "contact_name": p.contact_name, "phone": p.phone, "email": p.email,
        "city": p.location_city, "state": p.location_state, "categories": p.categories,
        "description": p.description, "synthetic": p.synthetic,
        "verification_tier": p.verification_tier, "verification_text": verification_text(p.verification_tier, p.synthetic),
    }


def buyer_descriptor(store, rfq) -> str:
    """What a seller may know about a buyer before reveal: kind of business and state, nothing else."""
    prof = store.profiles.get(rfq.owner_id) if rfq.owner_id else None
    kind = prof.business_type.value.capitalize() if prof else "Buyer"
    state = (prof.state if prof else rfq.buyer_state) or ""
    return f"{kind}, {state}" if state else kind


def buyer_contact(store, rfq) -> dict[str, Any]:
    """The buyer's contact, released to a seller only after that seller is revealed."""
    prof = store.profiles.get(rfq.owner_id) if rfq.owner_id else None
    if prof:
        return {"name": prof.full_name, "company": prof.company, "phone": prof.phone, "email": prof.email, "city": prof.city}
    return {"name": rfq.buyer_name, "company": rfq.buyer_company, "phone": None, "email": None, "city": rfq.buyer_city}


# ─── buyer-facing ──────────────────────────────────────────────────────────

def public_rfq(store, rfq) -> dict[str, Any]:
    """The buyer's own request. No invite tokens, no owner id, nothing about who was matched."""
    return {
        "id": rfq.id, "item": rfq.item, "qty": rfq.qty, "need_in_days": rfq.need_in_days,
        "buyer_company": rfq.buyer_company, "buyer_name": rfq.buyer_name,
        "buyer_city": rfq.buyer_city, "buyer_state": rfq.buyer_state, "note": rfq.note,
        "created_at": rfq.created_at, "status": rfq.status, "decision": rfq.decision,
        "priority_mode": rfq.priority_mode, "source": rfq.source,
        "matched_count": len(rfq.supplier_tokens), "quote_count": len(store.aliases.get(rfq.id, {})),
    }


def _alias_order(alias: str) -> int:
    return int(alias.rsplit(" ", 1)[-1])


def buyer_quotes(store, rfq) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for sid, versions in store.quotes.get(rfq.id, {}).items():
        alias = store.alias_for(rfq.id, sid)
        if not alias or not versions:
            continue
        shown = store.is_revealed(rfq.id, sid)
        out[alias] = [v.model_copy(update={"supplier_id": alias, "supplier_name": alias,
                                           "notes": v.notes if shown else scrub(v.notes)}).model_dump() for v in versions]
    return dict(sorted(out.items(), key=lambda kv: _alias_order(kv[0])))


def buyer_targets(store, rfq) -> dict[str, dict]:
    out = {}
    for sid, t in store.targets.get(rfq.id, {}).items():
        alias = store.alias_for(rfq.id, sid)
        if alias:
            out[alias] = t.model_copy(update={"supplier_id": alias}).model_dump()
    return out


def buyer_revealed(store, rfq) -> dict[str, dict]:
    return {store.alias_for(rfq.id, sid): identity_of(store, sid)
            for sid in store.revealed.get(rfq.id, {}) if store.alias_for(rfq.id, sid)}


def buyer_badges(store, rfq) -> dict[str, dict]:
    """Per seller alias: what was checked, and the state only (no city)."""
    out = {}
    for sid, alias in store.aliases.get(rfq.id, {}).items():
        p = store.supplier_profiles.get(sid)
        if p:
            out[alias] = {"verification_tier": p.verification_tier, "verification_text": verification_text(p.verification_tier, p.synthetic),
                          "region": p.location_state, "synthetic": p.synthetic}
    return out


def plan_info(store, buyer_id: str) -> dict[str, Any]:
    return {"plan": store.plan_of(buyer_id), "free_limit": store.free_reveal_limit(), "reveals_left": store.reveals_left(buyer_id)}


def buyer_details(store, rfq, buyer_id: str) -> dict[str, Any]:
    quotes = store.get_latest_quotes_as_engine_input(rfq.id)
    evaluation = evaluate(quotes, Need(item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days),
                          exceptions=store.exceptions_by_alias(rfq.id), mode=rfq.priority_mode) if quotes else None
    return {
        "rfq": public_rfq(store, rfq),
        "quotes": buyer_quotes(store, rfq),
        "targets": buyer_targets(store, rfq),
        "evaluation": evaluation,
        "activity": store.activity(rfq.id),
        "revealed": buyer_revealed(store, rfq),
        "exceptions": {a: r.model_dump() for a, r in store.exceptions_by_alias(rfq.id).items()},
        "badges": buyer_badges(store, rfq),
        "plan": plan_info(store, buyer_id),
    }


def supplier_for_buyer(store, rfq, alias: str) -> Optional[dict[str, Any]]:
    """The click-through panel. Before reveal: alias, state, what was checked. After: the full seller."""
    sid = store.supplier_for_alias(rfq.id, alias)
    p = store.supplier_profiles.get(sid) if sid else None
    if not sid:
        return None
    base = {"supplier_id": alias, "business_name": alias, "location_city": "", "location_state": p.location_state if p else "",
            "categories": p.categories if p else [], "description": None, "products": [], "revealed": False,
            "verification_tier": p.verification_tier if p else "none",
            "verification_text": verification_text(p.verification_tier, p.synthetic) if p else "No checks yet",
            "synthetic": p.synthetic if p else True}
    if store.is_revealed(rfq.id, sid):
        ident = identity_of(store, sid)
        base.update({"revealed": True, "business_name": ident.get("business_name", alias), "location_city": ident.get("city", ""),
                     "description": ident.get("description"), "contact": {k: ident.get(k) for k in ("contact_name", "phone", "email")},
                     "products": [x.model_dump() for x in store.supplier_products.get(sid, [])]})
    return base


def _chat_dump(m: ChatMessage, **changes) -> dict:
    return m.model_copy(update=changes).model_dump()


def chat_for_buyer(store, rfq, supplier_id: str) -> list[dict]:
    alias, shown = store.alias_for(rfq.id, supplier_id), store.is_revealed(rfq.id, supplier_id)
    out = []
    for m in store.get_chat_messages(rfq.id, supplier_id):
        ch: dict[str, Any] = {}
        if m.sender == "supplier" and not shown:
            ch.update(sender_name=alias or "Seller", text=scrub(m.text))
        if m.target:
            ch["target"] = m.target.model_copy(update={"supplier_id": alias or ""})
        out.append(_chat_dump(m, **ch))
    return out


def seller_target_model(t: NegotiationTarget, shown: bool) -> NegotiationTarget:
    """The buyer's name on a target, and any contact detail in its message, wait for the reveal."""
    return t if shown else t.model_copy(update={"sent_by": "Buyer", "message": scrub(t.message)})


def seller_target(t: Optional[NegotiationTarget], shown: bool) -> Optional[dict]:
    return None if t is None else seller_target_model(t, shown).model_dump()


def chat_for_seller(store, rfq, supplier_id: str) -> list[dict]:
    shown = store.is_revealed(rfq.id, supplier_id)
    out = []
    for m in store.get_chat_messages(rfq.id, supplier_id):
        ch: dict[str, Any] = {}
        if m.sender == "buyer" and not shown:
            ch.update(sender_name="Buyer", text=scrub(m.text))
        if m.target:
            ch["target"] = seller_target_model(m.target, shown)
        out.append(_chat_dump(m, **ch))
    return out


# ─── seller-facing ─────────────────────────────────────────────────────────

def seller_request(store, token: str) -> Optional[dict[str, Any]]:
    rfq_id = store.token_to_rfq_id.get(token)
    rfq = store.rfqs.get(rfq_id) if rfq_id else None
    if not rfq:
        return None
    sid = store.token_to_supplier_id.get(token)
    shown = bool(sid) and store.is_revealed(rfq.id, sid)
    store.touch_token(token, "viewed")
    out = {
        "id": rfq.id, "item": rfq.item, "qty": rfq.qty, "need_in_days": rfq.need_in_days,
        "buyer_descriptor": buyer_descriptor(store, rfq), "priority_mode": rfq.priority_mode,
        "note": rfq.note if shown else scrub(rfq.note), "status": rfq.status,
        "supplier_id": sid, "supplier_name": store.get_supplier_name_for_token(token), "unlocked": shown,
    }
    if shown:
        out["buyer_contact"] = buyer_contact(store, rfq)
    return out


def seller_my_quotes(store, token: str) -> dict[str, Any]:
    data = store.get_supplier_quotes_and_target(token)
    rfq_id, sid = store.token_to_rfq_id.get(token), store.token_to_supplier_id.get(token)
    shown = bool(rfq_id and sid) and store.is_revealed(rfq_id, sid)
    return {"quotes": data["quotes"], "target": seller_target(data["target"], shown)}
