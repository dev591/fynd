"""Decision one-pager data, savings vs the spreadsheet pick, and the selection explainer.

Every number comes from the engine output. The explainer's wording may come from a model, but the AI
never picks the winner, and its text is dropped for the engine's own reasons list if any number
is unsupported or it names no winner.
"""
import re
from typing import Any, Optional

from .ai import structured_call
from .assistant import makes_promise, numbers_supported
from .engine import evaluate, fingerprint, naive_pick, order
from . import views
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


_explain_cache: dict[tuple, dict[str, Any]] = {}  # same inputs, same pick: never pay for the same sentence twice


def inr(n: float) -> str:
    return f"₹{n:,.0f}"


def _row(r: EvaluatedRow) -> dict[str, Any]:
    return {
        "quote_id": r.quote_id, "supplier": r.supplier, "status": r.status, "reason": r.reason,
        "approved": r.approved, "landed": r.landed, "lead_days": r.lead_days, "packs": r.packs,
        "units": r.units, "overbuy": r.overbuy, "freight": r.freight, "fill_qty": r.fill_qty,
    }


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
            out.append(f"{r.supplier} is {inr(r.landed - winner.landed)} higher at {inr(r.landed)} landed.")
    return out


def _explainer(facts: dict, allowed: set[float], winner_name: str, fallback: str) -> dict[str, Any]:
    raw = structured_call(EXPLAIN_SYSTEM, str(facts), "selection_explainer", EXPLAIN_SCHEMA)
    if raw is None:
        return {"text": fallback, "source": "engine", "discarded_reason": None}
    text = (raw.get("text") or "").strip()
    if not text or winner_name.lower() not in text.lower():
        return {"text": fallback, "source": "engine", "discarded_reason": "AI text did not name the winner"}
    if makes_promise(text):
        return {"text": fallback, "source": "engine", "discarded_reason": "AI text made an offer or promise"}
    # "Seller 2" is a label, not a quantity: take the alias digits out before checking numbers.
    if not numbers_supported(re.sub(r"\bSeller \d+\b", "Seller", text), allowed):
        return {"text": fallback, "source": "engine", "discarded_reason": "AI text contained a number not in the engine output"}
    return {"text": text, "source": "ai", "discarded_reason": None}


def build_summary(store, rfq_id: str, with_explainer: bool = True, audience: str = "buyer") -> Optional[dict[str, Any]]:
    """audience 'buyer' is the owner's own page; 'public' is a shared link and never carries identities."""
    rfq: Optional[RFQ] = store.get_rfq(rfq_id)
    if not rfq:
        return None
    quotes = store.get_latest_quotes_as_engine_input(rfq_id)
    need = Need(item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days)
    ev = evaluate(quotes, need, mode=rfq.priority_mode)
    decision = rfq.decision
    by_id = {r.quote_id: r for r in ev.rows}

    decided_row = by_id.get(decision["winner_id"]) if decision else None
    shown = decided_row or ev.winner

    naive = naive_pick(quotes, need)
    naive_calc = order(naive, rfq.qty) if naive else None
    savings = None
    if decided_row and decided_row.landed is not None and naive and naive_calc:
        savings = {
            "spreadsheet_pick": naive.supplier, "spreadsheet_landed": naive_calc.landed,
            "crossover_pick": decided_row.supplier, "crossover_landed": decided_row.landed,
            "difference": naive_calc.landed - decided_row.landed,
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
            _explain_cache[key] = _explainer(facts, allowed, shown.supplier, " ".join(reasons[:2]))
        explainer = _explain_cache[key]

    return {
        "rfq": {"id": rfq.id, "item": rfq.item, "qty": rfq.qty, "need_in_days": rfq.need_in_days,
                **({"buyer_company": rfq.buyer_company, "buyer_name": rfq.buyer_name} if audience == "buyer" else {}),
                "priority_mode": rfq.priority_mode, "source": rfq.source, "status": rfq.status,
                "created_at": rfq.created_at},
        "decided": decision is not None,
        "decision": decision,
        "pick": _row(shown) if shown else None,
        "engine_winner": _row(ev.winner) if ev.winner else None,
        "overrode_engine": bool(decided_row and ev.winner and decided_row.quote_id != ev.winner.quote_id),
        "winners_by_mode": {m: (_row(w) if w else None) for m, w in ev.winners.items()},
        "tradeoffs": ev.tradeoffs,
        "rows": [_row(r) for r in ev.rows],
        "cheaper_excluded": [_row(r) for r in ev.cheaper_excluded],
        "reasons": reasons,
        "explainer": explainer,
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
