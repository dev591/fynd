"""Decision one-pager data, savings vs the spreadsheet pick, and the selection explainer.

Every number comes from the engine output. The explainer's wording may come from a model, but the AI
never picks the winner, and its text is dropped for the engine's own reasons list if any number
is unsupported or it names no winner.
"""
import re
from typing import Any, Optional

from .ai import structured_call
from .assistant import makes_promise, numbers_supported
from .engine import balanced_threshold, evaluate, fingerprint, naive_pick, order
from . import views
from .masking import scrub
from .models import EvaluatedRow, Need, RFQ

EXPLAIN_SYSTEM = (
    "You explain, in two or three plain sentences, why one supplier was chosen for a purchase. "
    "The winner is already decided by rules; never change it or suggest another. Use only the facts given. "
    "Copy numbers exactly and write money with the ₹ symbol. Do not add any other number, discount or promise."
)
EXPLAIN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["text"],
    "properties": {"text": {"type": "string"}},
}


OPINION_SYSTEM = (
    "You read a buyer's free-text note next to a purchase decision that rules have already made. The engine_pick is the "
    "rules' choice. Decide whether the note adds a concern the rules cannot see. concern 'deadline' only if the note "
    "says time is critical; concern 'cash' only if it says money is tight; otherwise concern 'none' and pick the "
    "engine_pick. With 'deadline' or 'cash', copy the exact words from the note that show it into note_phrase and pick "
    "the option that serves that concern. With 'none', leave note_phrase empty. Choose only from the options given."
)

_explain_cache: dict[tuple, dict[str, Any]] = {}
_opinion_cache: dict[tuple, Optional[dict[str, Any]]] = {}  # same inputs, same pick: never pay for the same sentence twice


def inr(n: float) -> str:
    return f"₹{n:,.0f}"


def _row(r: EvaluatedRow, qty: Optional[int] = None) -> dict[str, Any]:
    """One quote as the engine saw it. cash_tied_up and cost_per_usable_unit are derived here from engine numbers."""
    unit = (r.pack_price / r.pack_size) if r.pack_size else None
    used = min(qty, r.units) if qty and r.units else qty
    return {
        "quote_id": r.quote_id, "supplier": r.supplier, "status": r.status, "reason": r.reason,
        "approved": r.approved, "landed": r.landed, "lead_days": r.lead_days, "packs": r.packs,
        "units": r.units, "overbuy": r.overbuy, "freight": r.freight, "fill_qty": r.fill_qty,
        "pack_price": r.pack_price, "pack_size": r.pack_size,
        "cash_tied_up": round(r.overbuy * unit, 2) if unit is not None and r.overbuy else 0 if unit is not None else None,
        "cost_per_usable_unit": round(r.landed / used, 2) if r.landed is not None and used else None,
    }


def evidence_facts(rfq, pick: Optional[dict], savings: Optional[dict], mode: str, unstated: int = 0, total: int = 0) -> list[dict[str, str]]:
    """Every number on the one-pager, tagged: observed (a seller or the buyer said it), derived (the engine computed it)
    or assumed (our policy or setting, not a measurement). Values copied from the engine row, never typed."""
    facts: list[dict[str, str]] = []
    add = lambda label, value, tag, source: facts.append({"label": label, "value": value, "tag": tag, "source": source})
    add("Quantity needed", f"{rfq.qty} units", "observed", "Your request")
    add("Need-by", f"within {rfq.need_in_days} days", "observed", "Your request")
    if pick:
        add("Pack price", inr(pick["pack_price"]), "observed", "The seller's quote")
        add("Units per pack", str(pick["pack_size"]), "observed", "The seller's quote")
        add("Freight", inr(pick["freight"]), "observed", "The seller's quote")
        add("Lead time", f"{pick['lead_days']} days", "observed", "The seller's quote")
        add("Packs ordered", str(pick["packs"]), "derived", "Whole packs needed for the quantity, at least the minimum order")
        add("Units received", str(pick["units"]), "derived", "Packs times units per pack")
        add("Landed cost", inr(pick["landed"]), "derived", "Packs times pack price, plus freight")
        if pick.get("cost_per_usable_unit") is not None:
            add("Cost per usable unit", inr(pick["cost_per_usable_unit"]), "derived", "Landed cost over the units you need")
        add("Cash tied up in extra units", inr(pick["cash_tied_up"] or 0), "derived", f"{pick['overbuy']} extra units at the unit price")
    delivery = (rfq.decision or {}).get("delivery")
    if delivery:
        add("Delivery matched the quote", "Yes" if delivery["matches_quote"] else "No", "observed", "Recorded by the buyer after delivery")
        add("Delivered on time", "Yes" if delivery["on_time"] else "No", "observed", "Recorded by the buyer after delivery")
    if savings:
        add("Saving vs spreadsheet pick", inr(savings["difference"]), "derived", "Spreadsheet pick's landed cost minus this pick's, on demo data")
    basis = "ex-GST (you can claim GST back)" if rfq.gst_claimable else "GST-inclusive (you cannot claim GST back)"
    note = (f"Your request setting. {unstated} of {total} quotes did not state a GST basis and are treated as exclusive; "
            "confirm before ordering") if unstated else "Your request setting. Every quote stated its GST basis"
    add("Tax basis", basis, "assumed", note)
    add("Balanced-mode tolerance", f"{round(balanced_threshold() * 100, 1):g}%", "assumed", "Our setting, not a measurement")
    add("Priority mode", mode, "observed", "Chosen on your request")
    return facts


def reasons_list(rows: list[EvaluatedRow], winner: Optional[EvaluatedRow], mode: str) -> list[str]:
    """The engine's own reasons, in words. Always available, and the fallback for the explainer."""
    out: list[str] = []
    if winner and winner.landed is not None:
        basis = {"cheapest": "lowest landed cost", "fastest": "shortest lead time among eligible quotes",
                 "balanced": "fastest within the cost threshold of the cheapest"}.get(mode, "lowest landed cost")
        out.append(f"{winner.supplier} wins on {basis}: {inr(winner.landed)} landed, {winner.lead_days} days.")
    for r in rows:
        if winner and r.quote_id == winner.quote_id:
            continue
        if r.status == "blocked":
            out.append(f"{r.supplier} is blocked: {r.reason}.")
        elif r.status == "exception" and not r.approved:
            out.append(f"{r.supplier} needs a signed exception: {r.reason}.")
        elif r.landed is not None and winner and winner.landed is not None:
            diff = r.landed - winner.landed
            cost = f"{inr(diff)} higher" if diff > 0 else f"{inr(-diff)} lower" if diff < 0 else "the same price"
            days = r.lead_days - winner.lead_days
            lead = f", {abs(days)} day{'' if abs(days) == 1 else 's'} {'slower' if days > 0 else 'faster'}" if days else ""
            out.append(f"{r.supplier} is {cost} at {inr(r.landed)} landed{lead}.")
    return out


_CHEAPEST_CLAIM = re.compile(r"\b(lowest|cheapest|least expensive|best price)\b", re.I)
_FASTEST_CLAIM = re.compile(r"\b(fastest|quickest|shortest|earliest|soonest)\b", re.I)


def _explainer(facts: dict, allowed: set[float], winner_name: str, fallback: str,
               pick_is_cheapest: bool = True, pick_is_fastest: bool = True) -> dict[str, Any]:
    raw = structured_call(EXPLAIN_SYSTEM, str(facts), "selection_explainer", EXPLAIN_SCHEMA)
    if raw is None:
        return {"text": fallback, "source": "engine", "discarded_reason": None}
    text = (raw.get("text") or "").strip()
    if not text or winner_name.lower() not in text.lower():
        return {"text": fallback, "source": "engine", "discarded_reason": "AI text did not name the winner"}
    if makes_promise(text):
        return {"text": fallback, "source": "engine", "discarded_reason": "AI text made an offer or promise"}
    # A superlative must be true of the pick among the allowed quotes, or the sentence misleads even with real numbers.
    if (_CHEAPEST_CLAIM.search(text) and not pick_is_cheapest) or (_FASTEST_CLAIM.search(text) and not pick_is_fastest):
        return {"text": fallback, "source": "engine", "discarded_reason": "AI text claimed the pick was cheapest or fastest when it was not"}
    # "Seller 2" is a label, not a quantity: take the alias digits out before checking numbers.
    if not numbers_supported(re.sub(r"\bSeller \d+\b", "Seller", text), allowed):
        return {"text": fallback, "source": "engine", "discarded_reason": "AI text contained a number not in the engine output"}
    return {"text": text, "source": "ai", "discarded_reason": None}


def second_opinion(store, rfq: RFQ, rows: list[EvaluatedRow], engine_pick: Optional[EvaluatedRow], fp: str) -> Optional[dict[str, Any]]:
    """AI's reading of the buyer's note, alongside the engine's pick and never in place of it.

    The model only chooses a seller and a concern from a fixed list and quotes the buyer's own words. Code checks that the
    quote is really in the note and that the pick serves the concern (a deadline concern needs a faster seller), then writes
    the sentence itself from the engine's numbers, so nothing the model says about prices or days can be wrong."""
    cands = [r for r in rows if r.landed is not None and (r.status == "eligible" or (r.status == "exception" and r.approved))]
    if engine_pick is None or engine_pick.landed is None or len(cands) < 2:
        return None
    note = scrub(rfq.note or "")[:300]
    key = (fp, rfq.priority_mode, note)
    if key in _opinion_cache:
        return _opinion_cache[key]
    by_name = {r.supplier: r for r in cands}
    facts = {"priority": rfq.priority_mode, "buyer_note": note or None, "engine_pick": engine_pick.supplier,
             "options": [{"seller": r.supplier, "landed": round(r.landed), "lead_days": r.lead_days} for r in cands]}
    schema = {"type": "object", "additionalProperties": False, "required": ["pick", "concern", "note_phrase"],
              "properties": {"pick": {"type": "string", "enum": list(by_name)},
                             "concern": {"type": "string", "enum": ["none", "deadline", "cash"]},
                             "note_phrase": {"type": "string"}}}
    raw = structured_call(OPINION_SYSTEM, str(facts), "second_opinion", schema)
    out = _build_opinion(raw, by_name, engine_pick, note)
    if out:
        rid = "op_" + fp[:10]
        store.log_ai("second_opinion", rid, facts, out)
        store.link_ai_log(rid, rfq.id)
    _opinion_cache[key] = out
    return out


def _build_opinion(raw: Optional[dict], by_name: dict[str, EvaluatedRow], engine_pick: EvaluatedRow, note: str) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    pick, concern, phrase = raw.get("pick"), raw.get("concern"), (raw.get("note_phrase") or "").strip()
    row = by_name.get(pick)
    if row is None or concern not in ("none", "deadline", "cash"):
        return None
    if concern == "none":
        if row.quote_id != engine_pick.quote_id:
            return None                                  # no stated concern, so no reason to differ from the rules
    else:
        if not phrase or phrase.lower() not in note.lower():
            return None                                  # the model must point at the buyer's own words
        if row.quote_id != engine_pick.quote_id:
            if concern == "deadline" and not row.lead_days < engine_pick.lead_days:
                return None
            if concern == "cash" and not row.landed < engine_pick.landed:
                return None
    agrees = row.quote_id == engine_pick.quote_id
    if agrees:
        text = f"{row.supplier} is the best fit: {inr(row.landed)} landed, arriving in {row.lead_days} days."
    else:
        d_cost, d_days = round(row.landed - engine_pick.landed), engine_pick.lead_days - row.lead_days
        cost = f"{inr(abs(d_cost))} {'more' if d_cost > 0 else 'less'}" if d_cost else "the same cost"
        days = f"{d_days} day{'' if d_days == 1 else 's'} sooner" if d_days > 0 else f"{-d_days} day{'' if d_days == -1 else 's'} later" if d_days < 0 else "on the same day"
        text = f'Your note says "{phrase}". {row.supplier} costs {cost} than {engine_pick.supplier} and arrives {days}.' \
            if d_cost else f'Your note says "{phrase}". {row.supplier} costs the same as {engine_pick.supplier} and arrives {days}.'
    return {"pick": row.supplier, "agrees": agrees, "reason": text, "engine_pick": engine_pick.supplier,
            "concern": concern, "source": "ai", "label": "AI suggestion, not a calculation"}


def _decision_for(decision: Optional[dict], audience: str) -> Optional[dict]:
    """A shared link shows the decision but not who signed it, and no phone or email typed into the reason."""
    if decision is None or audience == "buyer":
        return decision
    out = {**decision, "approver": "Named approver (hidden on shared links)", "reason": scrub(decision.get("reason")) or ""}
    if out.get("delivery"):
        out["delivery"] = _delivery_for(out["delivery"], "public")
    if out.get("exceptions"):
        out["exceptions"] = _exceptions_for(out["exceptions"], "public")
    return out


def _exceptions_for(exceptions: dict, audience: str) -> dict:
    """A shared link keeps each exception's reason (minus any contact details) but not the name that approved it."""
    if audience == "buyer":
        return exceptions
    return {a: {"reason": scrub(e.get("reason")) or "", "approver": "Named approver (hidden on shared links)"}
            for a, e in exceptions.items()}


def _delivery_for(delivery: Optional[dict], audience: str) -> Optional[dict]:
    """A shared link gets the two outcomes, not the buyer's note or photo."""
    if not delivery or audience == "buyer":
        return delivery
    return {k: delivery[k] for k in ("matches_quote", "on_time", "recorded_at")}


def build_summary(store, rfq_id: str, with_explainer: bool = True, audience: str = "buyer") -> Optional[dict[str, Any]]:
    """audience 'buyer' is the owner's own page; 'public' is a shared link and never carries identities."""
    rfq: Optional[RFQ] = store.get_rfq(rfq_id)
    if not rfq:
        return None
    quotes = store.get_latest_quotes_as_engine_input(rfq_id)
    need = Need(item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days)
    ev = evaluate(quotes, need, exceptions=store.exceptions_by_alias(rfq_id), mode=rfq.priority_mode)
    decision = rfq.decision
    by_id = {r.quote_id: r for r in ev.rows}

    decided_row = by_id.get(decision["winner_id"]) if decision else None
    shown = decided_row or ev.winner

    naive = naive_pick(quotes, need)
    naive_calc = order(naive, rfq.qty) if naive else None
    split = (decision or {}).get("split")
    savings = None
    if decided_row and decided_row.landed is not None and naive and naive_calc:
        done = split["total_landed"] if split else decided_row.landed
        savings = {
            "spreadsheet_pick": naive.supplier, "spreadsheet_landed": naive_calc.landed,
            "crossover_pick": " + ".join(p["quote_id"] for p in split["parts"]) if split else decided_row.supplier,
            "crossover_landed": done,
            "difference": naive_calc.landed - done,
            "label": "on demo data",
        }

    reasons = reasons_list(ev.rows, shown, rfq.priority_mode)
    runner = next((r for r in ev.pool if shown and r.quote_id != shown.quote_id), None)
    explainer = None
    if with_explainer and shown and shown.landed is not None:
        facts = {
            "mode": rfq.priority_mode, "winner": shown.supplier, "winner_landed": shown.landed,
            "winner_lead_days": shown.lead_days, "needed_within_days": rfq.need_in_days, "units": rfq.qty,
            "runner_up": runner.supplier if runner else None,
            "runner_up_landed": runner.landed if runner else None,
            "gap": (runner.landed - shown.landed) if runner and runner.landed is not None else None,
            "excluded": [{"supplier": r.supplier, "reason": r.reason} for r in ev.rows if r.status != "eligible"],
            "savings_vs_spreadsheet": savings["difference"] if savings else None,
        }
        facts = {k: (int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in facts.items()}
        allowed = {float(v) for v in facts.values() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        for e in facts["excluded"]:
            from .assistant import numbers_used
            allowed |= numbers_used(e["reason"] or "")
        fp = fingerprint({"need": need.model_dump(), "mode": rfq.priority_mode,
                          "quotes": [q.model_dump() for q in quotes]})
        key = (fp, shown.quote_id)
        if key not in _explain_cache:
            pool = [r for r in ev.rows if r.landed is not None and (r.status == "eligible" or (r.status == "exception" and r.approved))]
            _explain_cache[key] = _explainer(
                facts, allowed, shown.supplier, " ".join(reasons[:2]),
                pick_is_cheapest=all(shown.landed <= r.landed for r in pool),
                pick_is_fastest=all(shown.lead_days <= r.lead_days for r in pool))
        explainer = _explain_cache[key]

    opinion = None
    if with_explainer and audience == "buyer" and not decision:
        opinion = second_opinion(store, rfq, ev.rows, ev.winner, fingerprint({"need": need.model_dump(), "mode": rfq.priority_mode,
                                                                              "quotes": [q.model_dump() for q in quotes]}))

    return {
        "rfq": {"id": rfq.id, "item": rfq.item, "qty": rfq.qty, "need_in_days": rfq.need_in_days,
                **({"buyer_company": rfq.buyer_company, "buyer_name": rfq.buyer_name} if audience == "buyer" else {}),
                "priority_mode": rfq.priority_mode, "source": rfq.source, "status": rfq.status,
                "created_at": rfq.created_at},
        "decided": decision is not None,
        "decision": _decision_for(decision, audience),
        "pick": _row(shown, rfq.qty) if shown else None,
        "evidence": evidence_facts(
            rfq, _row(shown, rfq.qty) if shown else None, savings, rfq.priority_mode,
            unstated=sum(1 for v in store.quotes.get(rfq_id, {}).values() if v and v[-1].tax_basis == "assumed_exclusive"),
            total=sum(1 for v in store.quotes.get(rfq_id, {}).values() if v)),
        "engine_winner": _row(ev.winner, rfq.qty) if ev.winner else None,
        "overrode_engine": bool(decided_row and ev.winner and decided_row.quote_id != ev.winner.quote_id and not split),
        "split": split,
        "winners_by_mode": {m: (_row(w, rfq.qty) if w else None) for m, w in ev.winners.items()},
        "tradeoffs": ev.tradeoffs,
        "rows": [_row(r, rfq.qty) for r in ev.rows],
        "cheaper_excluded": [_row(r, rfq.qty) for r in ev.cheaper_excluded],
        "reasons": reasons,
        "delivery": _delivery_for((decision or {}).get("delivery"), audience),
        "exceptions": _exceptions_for({a: r.model_dump() for a, r in store.exceptions_by_alias(rfq_id).items()}, audience),
        "explainer": explainer,
        "ai_opinion": opinion,
        "savings": savings,
        "fingerprint": fingerprint({"need": need.model_dump(), "mode": rfq.priority_mode,
                                    "quotes": [q.model_dump() for q in quotes]}),
        "ai_calls": (decision or {}).get("ai_calls", []),
        # Suppliers whose current quote was sent by their autopilot, with no person reviewing it.
        "auto_quotes": [store.alias_for(rfq_id, sid) for sid, v in store.quotes.get(rfq_id, {}).items() if v and v[-1].origin == "auto"],
        "revealed": views.buyer_revealed(store, rfq) if audience == "buyer" else {},
        "synthetic_note": "Demo data is synthetic. Savings figures come from demo data.",
    }


def savings_total(store, owner_id: Optional[str] = None) -> dict[str, Any]:
    """Savings across decided requests the user owns (plus the shared demo request)."""
    total, n = 0.0, 0
    for rid, d in store.decisions.items():
        if store.rfqs[rid].owner_id not in (None, owner_id):
            continue
        s = build_summary(store, rid, with_explainer=False)
        if s and s["savings"]:
            total += s["savings"]["difference"]
            n += 1
    return {"total": total, "decided_count": n, "label": "on demo data"}
