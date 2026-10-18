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


def identity_of(store, supplier_id: str, rfq_id: Optional[str] = None) -> dict[str, Any]:
    """Everything that identifies a seller. Only ever returned after a reveal (or for a supplier the buyer named)."""
    if store.is_known(supplier_id):
        name = store.known_suppliers.get(rfq_id or "", {}).get(supplier_id, "Imported supplier")
        return {"business_name": name, "contact_name": None, "phone": None, "email": None, "city": "", "state": "",
                "categories": [], "description": "Imported by you from a file.", "synthetic": False, "imported": True,
                "verification_tier": "none",
                "verification_text": "Imported by you. Crossover has not checked this seller."}
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
        "created_at": rfq.created_at, "status": rfq.status, "decision": rfq.decision, "gst_claimable": rfq.gst_claimable,
        "budget": rfq.budget, "order_id": rfq.order_id,
        "priority_mode": rfq.priority_mode, "source": rfq.source,
        "window_key": rfq.window_key, "window_label": rfq.window_label, "window_ends_at": rfq.window_ends_at,
        "window_closed": rfq.window_closed, "demo_timing": rfq.demo_timing, "min_quotes": rfq.min_quotes,
        "matched_count": len(rfq.supplier_tokens), "quote_count": len(store.aliases.get(rfq.id, {})),
    }


def buyer_quotes(store, rfq) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for sid, versions in store.quotes.get(rfq.id, {}).items():
        alias = store.alias_for(rfq.id, sid)
        if not alias or not versions:
            continue
        shown = store.is_revealed(rfq.id, sid)
        out[alias] = [v.model_copy(update={"supplier_id": alias, "supplier_name": alias,
                                           "notes": v.notes if shown else scrub(v.notes)}).model_dump() for v in versions]
    order = {a: i for i, a in enumerate(store.aliases.get(rfq.id, {}).values())}      # the order sellers first quoted
    return dict(sorted(out.items(), key=lambda kv: order.get(kv[0], 0)))


def buyer_targets(store, rfq) -> dict[str, dict]:
    out = {}
    for sid, t in store.targets.get(rfq.id, {}).items():
        alias = store.alias_for(rfq.id, sid)
        if alias:
            out[alias] = t.model_copy(update={"supplier_id": alias}).model_dump()
    return out


def buyer_revealed(store, rfq) -> dict[str, dict]:
    """Sellers this buyer unlocked, plus suppliers they imported by name."""
    out = {store.alias_for(rfq.id, sid): identity_of(store, sid, rfq.id)
           for sid in store.revealed.get(rfq.id, {}) if store.alias_for(rfq.id, sid)}
    for sid in store.known_suppliers.get(rfq.id, {}):
        if store.alias_for(rfq.id, sid):
            out[store.alias_for(rfq.id, sid)] = identity_of(store, sid, rfq.id)
    return out


def buyer_badges(store, rfq) -> dict[str, dict]:
    """Per seller alias: what was checked, and the state only (no city)."""
    out = {}
    for sid, alias in store.aliases.get(rfq.id, {}).items():
        p = store.supplier_profiles.get(sid)
        if store.is_known(sid):
            out[alias] = {"verification_tier": "none", "region": "", "synthetic": False,
                          "verification_text": "Imported by you. Crossover has not checked this seller."}
        elif p:
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
    if store.is_known(sid):
        ident = identity_of(store, sid, rfq.id)
        return {"supplier_id": alias, "business_name": ident["business_name"], "location_city": "", "location_state": "",
                "categories": [], "description": ident["description"], "products": [], "revealed": True,
                "verification_tier": "none", "verification_text": ident["verification_text"], "synthetic": False}
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
        "closes_at": rfq.window_ends_at, "window_closed": rfq.window_closed,
    }
    if shown:
        out["buyer_contact"] = buyer_contact(store, rfq)
    return out


def seller_my_quotes(store, token: str) -> dict[str, Any]:
    data = store.get_supplier_quotes_and_target(token)
    rfq_id, sid = store.token_to_rfq_id.get(token), store.token_to_supplier_id.get(token)
    shown = bool(rfq_id and sid) and store.is_revealed(rfq_id, sid)
    return {"quotes": data["quotes"], "target": seller_target(data["target"], shown)}


# ─── request log and order history ─────────────────────────────────────────

_FIELD = {"qty": "quantity", "need_in_days": "deadline", "note": "note", "priority_mode": "priority"}


def _changes_text(changes: dict) -> str:
    out = []
    for k, (old, new) in changes.items():
        unit = " days" if k == "need_in_days" else ""
        out.append(f"{_FIELD.get(k, k)} {old if old not in (None, '') else '—'}{unit} → {new if new not in (None, '') else '—'}{unit}")
    return ", ".join(out)


def _money(n) -> str:
    return f"₹{round(n):,}" if n is not None else "a quote"


def render_event(store, rfq, e, audience: str, viewer_sid: str | None = None) -> str | None:
    """One log line in words for this audience. None = this audience does not see the event. Buyers see aliases only."""
    m, sid = e.meta, e.seller_id
    alias = store.alias_for(rfq.id, sid) if sid else None
    if audience == "buyer":
        if e.kind == "created":
            return f"You created this request: {m.get('qty')} × {m.get('item')}, needed in {m.get('need_in_days')} days"
        if e.kind == "sellers_notified":
            n = m.get("count", 0)
            return f"{n} seller{'' if n == 1 else 's'} who stock {m.get('item')} {'was' if n == 1 else 'were'} notified"
        if e.kind == "quote":
            return f"{alias} {'sent a quote' if m.get('version', 1) == 1 else 'revised their quote (v' + str(m.get('version')) + ')'}: {_money(m.get('landed'))} to your door"
        if e.kind == "imported":
            return "You imported a quote from a file"
        if e.kind == "declined":
            return f"{alias} said they can't supply this"
        if e.kind == "target":
            return f"You asked {alias} to match a better offer: {scrub(m.get('message') or '')}"
        if e.kind == "reveal":
            name = store._supplier_name(sid) if sid else ""
            return f"You revealed {alias}" + (f" ({name})" if name else "")
        if e.kind == "exception":
            return f"You approved {alias} anyway: “{scrub(m.get('reason') or '')}”, signed by {m.get('approver')}"
        if e.kind == "exception_withdrawn":
            return f"You withdrew the approval for {alias}"
        if e.kind == "edited":
            return f"You changed the request: {_changes_text(m.get('changes', {}))}"
        if e.kind == "decision":
            parts = m.get("split")
            return f"You placed a split order with {' and '.join(parts)}" if parts else f"You placed the order with {m.get('winner')}"
        if e.kind == "delivery":
            return "You recorded the delivery" + (" (on time)" if m.get("on_time") else " (late)")
        return None
    # seller: only their own thread, plus what the buyer did to the request as a whole
    if e.kind == "created":
        return f"A buyer asked for {m.get('qty')} × {m.get('item')}, needed in {m.get('need_in_days')} days"
    if e.kind == "edited":
        return f"The buyer changed the request: {_changes_text(m.get('changes', {}))}"
    if e.kind == "decision":
        mine = viewer_sid and store.alias_for(rfq.id, viewer_sid)
        winners = (m.get("split") or [m.get("winner")])
        return "You won this order" if mine in winners else "The buyer chose another seller"
    if sid != viewer_sid:
        return None
    if e.kind == "quote":
        return f"You {'sent a quote' if m.get('version', 1) == 1 else 'revised your quote (v' + str(m.get('version')) + ')'}: {_money(m.get('landed'))}"
    if e.kind == "declined":
        return "You said you can't supply this"
    if e.kind == "target":
        return f"The buyer asked you to match a better offer: {scrub(m.get('message') or '')}"
    if e.kind == "reveal":
        return "The buyer unlocked your contact"
    if e.kind == "delivery":
        return "The buyer recorded the delivery"
    return None


def request_log(store, rfq, audience: str, viewer_sid: str | None = None) -> list[dict]:
    out = []
    for e in store.events.get(rfq.id, []):
        text = render_event(store, rfq, e, audience, viewer_sid)
        if text:
            out.append({"id": e.id, "at": e.at, "kind": e.kind, "text": text})
    return out


def _decision_parts(store, rfq) -> list[tuple[str, int, float | None]]:
    """(alias, units, total) for each seller on a decided request: one for a normal order, two for a split."""
    d = rfq.decision or {}
    if d.get("split"):
        return [(p["quote_id"], p["qty"], p["landed"]) for p in d["split"]["parts"]]
    alias = d.get("winner_id")
    sid = store.supplier_for_alias(rfq.id, alias) if alias else None
    latest = (store.quotes.get(rfq.id, {}).get(sid) or [None])[-1] if sid else None
    return [(alias, rfq.qty, latest.landed_cost if latest else None)] if alias else []


def _delivery_status(d: dict) -> str:
    dv = (d or {}).get("delivery")
    if not dv:
        return "Awaiting delivery"
    return "Delivered on time" if dv.get("on_time") and dv.get("matches_quote") else "Delivered, with a problem noted"


def buyer_orders(store, buyer_id: str) -> list[dict]:
    out = []
    for rfq in store.rfqs.values():
        if rfq.owner_id != buyer_id or not rfq.decision:
            continue
        revealed = buyer_revealed(store, rfq)
        parts = _decision_parts(store, rfq)
        out.append({
            "rfq_id": rfq.id, "item": rfq.item, "qty": rfq.qty, "decided_at": rfq.decision.get("decided_at"),
            "total_landed": (rfq.decision["split"]["total_landed"] if rfq.decision.get("split") else (parts[0][2] if parts else None)),
            "approver": rfq.decision.get("approver"), "reason": rfq.decision.get("reason"), "split": bool(rfq.decision.get("split")),
            "status": _delivery_status(rfq.decision),
            "receivers": [{"alias": a, "units": u, "total": t, **{k: (revealed.get(a) or {}).get(k) for k in
                           ("business_name", "contact_name", "phone", "email", "city", "state")}} for a, u, t in parts],
        })
    return sorted(out, key=lambda o: o["decided_at"] or "", reverse=True)


def seller_orders(store, supplier_id: str) -> list[dict]:
    out = []
    for rfq in store.rfqs.values():
        if not rfq.decision:
            continue
        for alias, units, total in _decision_parts(store, rfq):
            if store.supplier_for_alias(rfq.id, alias) != supplier_id:
                continue
            out.append({"rfq_id": rfq.id, "item": rfq.item, "qty": units, "total": total, "decided_at": rfq.decision.get("decided_at"),
                        "status": _delivery_status(rfq.decision), "buyer": buyer_contact(store, rfq),
                        "payment": rfq.decision.get("payment_note"), "split": bool(rfq.decision.get("split"))})
    return sorted(out, key=lambda o: o["decided_at"] or "", reverse=True)
