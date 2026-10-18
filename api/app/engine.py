import hashlib, json, math, os
from typing import Dict, List, Optional
from .models import (
    Quote,
    Need,
    ExceptionRecord,
    OrderCalc,
    EvaluatedRow,
    CompareResult,
)


MODES = ("cheapest", "fastest", "balanced")


def balanced_threshold() -> float:
    """Share above the lowest landed cost that balanced mode will pay to arrive sooner. Our assumption (5%).
    Set BALANCED_TOLERANCE; the older BALANCED_THRESHOLD name still works."""
    raw = os.environ.get("BALANCED_TOLERANCE") or os.environ.get("BALANCED_THRESHOLD") or "0.05"
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.05


def give_up(winners: Dict[str, Optional[EvaluatedRow]]) -> Dict[str, dict]:
    """What each priority mode costs against the cheapest pick, from engine rows only: extra rupees, days saved."""
    base = winners.get("cheapest")
    out: Dict[str, dict] = {}
    for mode in MODES:
        w = winners.get(mode)
        if not base or not w or base.landed is None or w.landed is None:
            out[mode] = {"extra_cost": None, "days_saved": None, "line": None}
        elif mode == "cheapest":
            out[mode] = {"extra_cost": 0, "days_saved": 0, "line": "Lowest landed cost. Nothing given up on price."}
        elif w.quote_id == base.quote_id:
            out[mode] = {"extra_cost": 0, "days_saved": 0, "line": "Same seller as the cheapest pick. Nothing given up."}
        else:
            extra = round(w.landed - base.landed)
            days = base.lead_days - w.lead_days
            when = f"arrives {days} day{'' if days == 1 else 's'} earlier" if days > 0 else "arrives no earlier"
            out[mode] = {"extra_cost": extra, "days_saved": max(days, 0),
                         "line": f"{mode.capitalize()} costs ₹{extra:,} more and {when}."}
    return out


def tier_price(q: Quote, units: int) -> float:
    """Pack price for this many units: the highest volume tier reached, else the quote's own price. No tiers, no change."""
    price = q.pack_price
    for b in sorted(q.price_breaks, key=lambda b: b.min_qty):
        if units >= b.min_qty:
            price = b.pack_price
    return price


def order(q: Quote, qty: int) -> Optional[OrderCalc]:
    if not q.pack_size or q.pack_size <= 0:
        return None
    packs = math.ceil(max(qty, q.moq or 0) / q.pack_size)
    units = packs * q.pack_size
    overbuy = units - qty
    price = tier_price(q, units)
    goods = packs * price
    flat = 0.0 if q.free_freight_above is not None and goods >= q.free_freight_above else q.freight
    per_unit = (q.per_unit_freight or 0.0) * units
    freight = flat + per_unit
    return OrderCalc(packs=packs, units=units, overbuy=overbuy, landed=goods + freight, pack_price=price, freight=freight)


def is_valid_exception(e: Optional[ExceptionRecord]) -> bool:
    return bool(e and len(e.reason.strip()) > 0 and len(e.approver.strip()) > 0)


def rank_key(r: EvaluatedRow):
    """Cheapest landed wins; ties break on shorter lead time, then less overbuy."""
    return (r.landed if r.landed is not None else float("inf"), r.lead_days, r.overbuy)


def fastest_key(r: EvaluatedRow):
    """Shortest lead time wins; ties go to the cheaper landed cost."""
    return (r.lead_days, r.landed if r.landed is not None else float("inf"), r.overbuy)


def mode_key(mode: str):
    return fastest_key if mode == "fastest" else rank_key


def rank_pool(pool: List[EvaluatedRow], mode: str, threshold: Optional[float] = None) -> List[EvaluatedRow]:
    """Order the eligible pool for a mode. Unknown modes behave as cheapest."""
    if mode == "fastest":
        return sorted(pool, key=fastest_key)
    ordered = sorted(pool, key=rank_key)
    if mode == "balanced" and ordered and ordered[0].landed is not None:
        t = balanced_threshold() if threshold is None else threshold
        limit = ordered[0].landed * (1 + t)
        near = sorted((r for r in ordered if r.landed is not None and r.landed <= limit), key=fastest_key)
        return near + [r for r in ordered if r not in near]
    return ordered


def evaluate(
    quotes: List[Quote],
    need: Need,
    exceptions: Optional[Dict[str, ExceptionRecord]] = None,
    mode: str = "cheapest",
    threshold: Optional[float] = None,
) -> CompareResult:
    if exceptions is None:
        exceptions = {}

    rows: List[EvaluatedRow] = []

    for q in quotes:
        if q.item != need.item:
            rows.append(
                EvaluatedRow(
                    quote_id=q.id,
                    supplier=q.supplier,
                    status="blocked",
                    reason="different item",
                    approved=False,
                    lead_days=q.lead_days,
                    pack_price=q.pack_price,
                    pack_size=q.pack_size,
                    freight=q.freight,
                )
            )
            continue

        # Stock below the need is a partial fill: it needs a signed exception, like a late quote.
        short = q.max_qty is not None and q.max_qty < need.qty
        o = order(q, q.max_qty if short else need.qty)
        if not o:
            rows.append(
                EvaluatedRow(
                    quote_id=q.id,
                    supplier=q.supplier,
                    status="blocked",
                    reason="pack size unknown",
                    approved=False,
                    lead_days=q.lead_days,
                    pack_price=q.pack_price,
                    pack_size=q.pack_size,
                    freight=q.freight,
                )
            )
            continue

        late = q.lead_days > need.need_in_days
        exc = exceptions.get(q.id)
        approved = (late or short) and is_valid_exception(exc)
        reasons = []
        if late:
            reasons.append(f"arrives in {q.lead_days} days, needed in {need.need_in_days}")
        if short:
            reasons.append(f"stock covers {q.max_qty} of {need.qty} units")

        rows.append(
            EvaluatedRow(
                quote_id=q.id,
                supplier=q.supplier,
                status="exception" if (late or short) else "eligible",
                reason="; ".join(reasons) if reasons else None,
                approved=approved,
                packs=o.packs,
                units=o.units,
                overbuy=o.overbuy,
                landed=o.landed,
                lead_days=q.lead_days,
                pack_price=o.pack_price if o.pack_price is not None else q.pack_price,
                pack_size=q.pack_size,
                freight=o.freight if o.freight is not None else q.freight,
                fill_qty=q.max_qty if short else None,
            )
        )

    eligible = [r for r in rows if r.status == "eligible" or r.approved]
    pool = rank_pool(eligible, mode, threshold)
    winners = {m: (rank_pool(eligible, m, threshold) or [None])[0] for m in MODES}

    winner = pool[0] if pool else None
    key = mode_key(mode)
    tie = len(pool) > 1 and key(pool[0]) == key(pool[1])

    cheaper_excluded = []
    if winner and winner.landed is not None:
        cheaper_excluded = [
            r for r in rows if r not in pool and r.landed is not None and r.landed < winner.landed
        ]

    return CompareResult(
        rows=rows,
        pool=pool,
        winner=winner,
        tie=tie,
        cheaper_excluded=cheaper_excluded,
        mode=mode if mode in MODES else "cheapest",
        winners=winners,
        tradeoffs=give_up(winners),
    )


def negotiation(loser: EvaluatedRow, winner: EvaluatedRow) -> Optional[dict]:
    if loser.landed is None or winner.landed is None:
        return None
    cut = math.floor(loser.landed - winner.landed) + 1
    if cut <= 0:
        return None
    freight_cut = cut if cut <= loser.freight else None
    per_unit = math.ceil((cut / max(1, loser.units)) * 100) / 100
    return {"cut": cut, "freight": freight_cut, "per_unit": per_unit}


def naive_pick(quotes: List[Quote], need: Need) -> Optional[Quote]:
    eligible = [q for q in quotes if q.lead_days <= need.need_in_days]
    if not eligible:
        return None
    # Naive sheet sorts by sticker price per piece, ignoring freight and pack sizes
    return min(eligible, key=lambda q: q.pack_price / (q.pack_size or 1))


def fingerprint(data: dict) -> str:
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:12]


# Benchmark Scored Case Checks (25 Points)
BENCHMARK_QUOTES = [
    Quote(id="A", supplier="Supplier A", item="M10 bolt", pack_price=10.0, pack_size=1, freight=200.0, lead_days=3, raw="₹10 per bolt + ₹200 delivery"),
    Quote(id="B", supplier="Supplier B", item="M10 bolt", pack_price=11.0, pack_size=1, freight=50.0, lead_days=3, raw="₹11/pc, only ₹50 shipping"),
    Quote(id="C", supplier="Supplier C", item="M10 bolt", pack_price=400.0, pack_size=50, freight=0.0, lead_days=7, raw="₹400 per box of 50, free delivery, 7 days"),
    Quote(id="D", supplier="Supplier D", item="M10 bolt", pack_price=95.0, pack_size=None, freight=0.0, lead_days=3, raw='₹95 "per pack"'),
]
BENCHMARK_NEED = Need(item="M10 bolt", qty=100, need_in_days=5)


def run_case_checks() -> list[dict]:
    A, B, C, D = BENCHMARK_QUOTES
    need = BENCHMARK_NEED

    # Check 1: Landed cost vs Naive unit price
    c1 = evaluate([A, B], need)
    pass1 = (
        c1.rows[0].landed == 1200.0
        and c1.rows[1].landed == 1150.0
        and c1.winner is not None
        and c1.winner.quote_id == "B"
        and naive_pick([A, B], need).id == "A"
    )

    # Check 2: Late supplier gating & exception unlock
    plain = evaluate(BENCHMARK_QUOTES, need)
    blank = evaluate(BENCHMARK_QUOTES, need, {"C": ExceptionRecord(reason="   ", approver="Plant head")})
    signed = evaluate(BENCHMARK_QUOTES, need, {"C": ExceptionRecord(reason="Saves ₹350, stock covers the gap", approver="Plant head")})
    pass2 = (
        plain.winner is not None
        and plain.winner.quote_id != "C"
        and plain.rows[2].status == "exception"
        and blank.winner is not None
        and blank.winner.quote_id != "C"
        and signed.winner is not None
        and signed.winner.quote_id == "C"
    )

    # Check 3: Unknown pack size blocking
    cheap_d = Quote(id="D", supplier="Supplier D", item="M10 bolt", pack_price=1.0, pack_size=None, freight=0.0, lead_days=3)
    d_eval = evaluate([A, B, C, cheap_d], need)
    pass3 = (
        d_eval.rows[3].status == "blocked"
        and d_eval.rows[3].reason == "pack size unknown"
        and d_eval.winner is not None
        and d_eval.winner.quote_id != "D"
    )

    return [
        {"name": "Landed cost", "points": 10, "pass": pass1, "detail": "A ₹1,200 · B ₹1,150 → B wins. Sorted by unit price, the sheet picks A."},
        {"name": "Late supplier", "points": 10, "pass": pass2, "detail": "7-day supplier never recommended. Blank reason rejected; signed reason unlocks it."},
        {"name": "Unknown pack", "points": 5, "pass": pass3, "detail": "No pack size → blocked. Never wins, even priced at ₹1."},
    ]


# ─── Split orders: buy part from one seller and part from another ─────────────────────────────────────────────
# Additive: nothing above changes. It reuses the same cost rules as order() (whole packs, minimum order, volume tiers,
# free-delivery threshold, per-unit freight, stock caps) and is only ever offered next to the normal pick, never in place of it.

POOL = 6                       # sellers considered: the cheapest per unit at the needed quantity
EXHAUSTIVE_LIMIT = 20000       # up to this many split points per pair every point is tried; beyond it, candidate points


def _cost(q: Quote, units: int) -> Optional[tuple]:
    """(landed, units, packs) for ordering `units` from q, or None if impossible. Mirrors order() with no model objects."""
    if units <= 0:
        return (0.0, 0, 0)
    if not q.pack_size or q.pack_size <= 0:
        return None
    packs = math.ceil(max(units, q.moq or 0) / q.pack_size)
    got = packs * q.pack_size
    if q.max_qty is not None and got > q.max_qty:
        return None
    price = tier_price(q, got)
    goods = packs * price
    flat = 0.0 if q.free_freight_above is not None and goods >= q.free_freight_above else q.freight
    return (goods + flat + (q.per_unit_freight or 0.0) * got, got, packs)


def _candidate_points(a: Quote, b: Quote, qty: int, lo: int, hi: int) -> set:
    """Where a pair's total cost can change shape: pack boundaries of either seller, tiers, thresholds, caps, minimums."""
    pts = {lo, hi, lo + 1, hi - 1}
    for first, other in ((a, b), (b, a)):
        step = first.pack_size or 1
        marks = list(range(step, qty, step)) if step > 1 else []
        marks += [t.min_qty for t in first.price_breaks] + [first.moq or 0, first.max_qty or 0]
        marks += [t.min_qty * step for t in first.price_breaks if False]
        if first.free_freight_above is not None and first.pack_price > 0:
            marks += [math.ceil(first.free_freight_above / first.pack_price)] + [math.ceil(first.free_freight_above / t.pack_price) for t in first.price_breaks]
        for m in marks:
            if m <= 0:
                continue
            for d in (-1, 0, 1):
                x = m + d if first is a else qty - (m + d)
                pts.add(x)
    return {x for x in pts if lo <= x <= hi}


def best_split(quotes: List[Quote], need: Need, exceptions: Optional[Dict[str, ExceptionRecord]] = None,
               exhaustive_limit: int = EXHAUSTIVE_LIMIT) -> Optional[dict]:
    """The cheapest way to cover the whole quantity from two sellers, if that beats every single seller (or no single
    seller can cover it). None otherwise. Deterministic: ties go to the lower total, then less extra stock, then id order."""
    exceptions = exceptions or {}
    qty = need.qty
    usable = [x for x in quotes if x.item == need.item and x.pack_size and x.pack_size > 0
              and (x.lead_days <= need.need_in_days or is_valid_exception(exceptions.get(x.id)))]
    if qty < 2 or len(usable) < 2:
        return None

    singles = []
    for x in usable:
        c = _cost(x, qty)
        if c is not None:
            singles.append((c[0], x.id))
    best_single = min(singles) if singles else None

    def per_unit(x: Quote) -> float:
        n = min(qty, x.max_qty) if x.max_qty else qty
        c = _cost(x, n) or _cost(x, max(n, x.moq or 0))
        return (c[0] / max(n, 1)) if c else float("inf")

    pool = sorted(usable, key=lambda x: (per_unit(x), x.id))[:POOL]
    best = None            # (total, extra_units, ids..., k, a, b, ca, cb)
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            lo = max(1, qty - b.max_qty) if b.max_qty is not None else 1
            hi = min(qty - 1, a.max_qty) if a.max_qty is not None else qty - 1
            if lo > hi:
                continue
            ks = range(lo, hi + 1) if hi - lo + 1 <= exhaustive_limit else sorted(_candidate_points(a, b, qty, lo, hi))
            for k in ks:
                ca, cb = _cost(a, k), _cost(b, qty - k)
                if ca is None or cb is None:
                    continue
                key = (round(ca[0] + cb[0], 6), ca[1] + cb[1] - qty, tuple(sorted((a.id, b.id))), k if a.id < b.id else qty - k)
                if best is None or key < best[0]:
                    best = (key, a, b, k, ca, cb)
    if best is None:
        return None
    key, a, b, k, ca, cb = best
    total = ca[0] + cb[0]
    if best_single is not None and not total < best_single[0] - 0.005:
        return None
    rows = sorted([(a, k, ca), (b, qty - k, cb)], key=lambda r: (-r[1], r[0].id))
    return {
        "parts": [{"quote_id": x.id, "qty": n, "packs": c[2], "units": c[1], "landed": c[0], "lead_days": x.lead_days} for x, n, c in rows],
        "total_landed": total,
        "lead_days": max(x.lead_days for x, _, _ in rows),
        "units": ca[1] + cb[1],
        "overbuy": ca[1] + cb[1] - qty,
        "best_single": {"quote_id": best_single[1], "landed": best_single[0]} if best_single else None,
        "saving": round(best_single[0] - total, 2) if best_single else None,
        "reason": "cheaper_than_best_single" if best_single else "no_single_supplier_can_fill",
    }
