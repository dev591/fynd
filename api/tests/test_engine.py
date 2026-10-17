from app.engine import run_case_checks, evaluate, negotiation, order
from app.models import Quote, Need, EvaluatedRow


def test_three_case_checks_pass_all_25_points():
    checks = run_case_checks()
    assert len(checks) == 3
    assert all(c["pass"] for c in checks)
    total_score = sum(c["points"] for c in checks)
    assert total_score == 25


def test_pack_rounding_and_overbuy():
    # Need 100, pack of 12 at ₹120, freight ₹50
    q = Quote(
        id="pack_test",
        supplier="Pack Co",
        item="M10 bolt",
        pack_price=120.0,
        pack_size=12,
        freight=50.0,
        lead_days=3,
    )
    o = order(q, 100)
    assert o is not None
    assert o.packs == 9  # 9 * 12 = 108
    assert o.units == 108
    assert o.overbuy == 8
    assert o.landed == 9 * 120.0 + 50.0  # 1130.0


def test_negotiation_freight_cut():
    loser = EvaluatedRow(
        quote_id="A",
        supplier="Supplier A",
        status="eligible",
        packs=100,
        units=100,
        overbuy=0,
        landed=1200.0,
        lead_days=3,
        pack_price=10.0,
        pack_size=1,
        freight=200.0,
    )
    winner = EvaluatedRow(
        quote_id="B",
        supplier="Supplier B",
        status="eligible",
        packs=100,
        units=100,
        overbuy=0,
        landed=1150.0,
        lead_days=3,
        pack_price=11.0,
        pack_size=1,
        freight=50.0,
    )
    neg = negotiation(loser, winner)
    assert neg is not None
    assert neg["cut"] == 51.0
    # freight cut from 200 by 51 is valid since cut <= loser freight
    assert neg["freight"] == 51.0


def test_stock_below_need_is_partial_fill_needing_exception():
    from app.models import ExceptionRecord
    need = Need(item="M10 bolt", qty=100, need_in_days=5)
    short = Quote(id="S", supplier="Short", item="M10 bolt", pack_price=5.0, pack_size=1,
                  freight=0.0, lead_days=3, max_qty=60)
    full = Quote(id="F", supplier="Full", item="M10 bolt", pack_price=11.0, pack_size=1,
                 freight=50.0, lead_days=3)

    res = evaluate([short, full], need)
    row = next(r for r in res.rows if r.quote_id == "S")
    assert row.status == "exception"
    assert row.fill_qty == 60
    assert "stock covers 60 of 100" in row.reason
    assert res.winner.quote_id == "F"  # cheaper but short never wins unsigned

    signed = evaluate([short, full], need, {"S": ExceptionRecord(reason="Split order", approver="Plant head")})
    assert signed.winner.quote_id == "S"


def test_no_max_qty_keeps_default_behaviour():
    need = Need(item="M10 bolt", qty=100, need_in_days=5)
    q = Quote(id="A", supplier="A", item="M10 bolt", pack_price=10.0, pack_size=1, freight=200.0, lead_days=3)
    row = evaluate([q], need).rows[0]
    assert row.status == "eligible" and row.fill_qty is None


def _mode_quotes():
    # A cheapest but slow, B 4% dearer and faster, C 20% dearer and fastest
    mk = lambda i, price, lead: Quote(id=i, supplier=i, item="M10 bolt", pack_price=price,
                                      pack_size=1, freight=0.0, lead_days=lead)
    return [mk("A", 10.0, 5), mk("B", 10.4, 3), mk("C", 12.0, 1)]


def test_priority_modes_pick_different_winners():
    need = Need(item="M10 bolt", qty=100, need_in_days=5)
    res = evaluate(_mode_quotes(), need)
    assert res.mode == "cheapest" and res.winner.quote_id == "A"
    assert {m: w.quote_id for m, w in res.winners.items()} == {
        "cheapest": "A", "fastest": "C", "balanced": "B",
    }
    assert evaluate(_mode_quotes(), need, mode="fastest").winner.quote_id == "C"
    assert evaluate(_mode_quotes(), need, mode="balanced").winner.quote_id == "B"


def test_balanced_threshold_is_a_setting():
    need = Need(item="M10 bolt", qty=100, need_in_days=5)
    assert evaluate(_mode_quotes(), need, mode="balanced", threshold=0.01).winner.quote_id == "A"
    assert evaluate(_mode_quotes(), need, mode="balanced", threshold=0.25).winner.quote_id == "C"


def test_fastest_tie_goes_to_cheaper():
    need = Need(item="M10 bolt", qty=100, need_in_days=5)
    mk = lambda i, price: Quote(id=i, supplier=i, item="M10 bolt", pack_price=price,
                                pack_size=1, freight=0.0, lead_days=2)
    assert evaluate([mk("X", 12.0), mk("Y", 11.0)], need, mode="fastest").winner.quote_id == "Y"


def test_unknown_mode_falls_back_to_cheapest_and_late_never_wins():
    need = Need(item="M10 bolt", qty=100, need_in_days=2)
    res = evaluate(_mode_quotes(), need, mode="nonsense")
    assert res.mode == "cheapest" and res.winner.quote_id == "C"  # A, B arrive too late
    assert all(w is None or w.quote_id == "C" for w in res.winners.values())


# ─── v2 additions ────────────────────────────────────────────────────────────

def _ab():
    from app.engine import BENCHMARK_QUOTES
    return BENCHMARK_QUOTES[:2]


def test_crossover_between_a_and_b_is_at_150_and_a_wins_from_151():
    """A: 10/unit + 200 freight. B: 11/unit + 50 freight. They cost the same at 150 units."""
    def landed(qty):
        res = evaluate(_ab(), Need(item="M10 bolt", qty=qty, need_in_days=5))
        return {r.quote_id: r.landed for r in res.rows}, res.winner.quote_id
    l, w = landed(100); assert (l["A"], l["B"], w) == (1200, 1150, "B")
    l, w = landed(149); assert w == "B" and l["B"] < l["A"]
    l, _ = landed(150); assert l["A"] == l["B"] == 1700
    l, w = landed(151); assert w == "A" and l["A"] < l["B"]
    l, w = landed(300); assert w == "A"


def test_balanced_tolerance_setting_and_old_name(monkeypatch):
    from app.engine import balanced_threshold
    assert balanced_threshold() == 0.05
    monkeypatch.setenv("BALANCED_THRESHOLD", "0.2")
    assert balanced_threshold() == 0.2
    monkeypatch.setenv("BALANCED_TOLERANCE", "0.01")          # the brief's name wins
    assert balanced_threshold() == 0.01
    monkeypatch.setenv("BALANCED_TOLERANCE", "oops")
    assert balanced_threshold() == 0.05


def test_what_you_give_up_comes_from_engine_rows_only():
    need = Need(item="M10 bolt", qty=100, need_in_days=5)
    mk = lambda i, price, lead: Quote(id=i, supplier=i, item="M10 bolt", pack_price=price, pack_size=1, freight=0.0, lead_days=lead)
    res = evaluate([mk("A", 10.0, 5), mk("B", 10.4, 3), mk("C", 12.0, 1)], need)
    t = res.tradeoffs
    assert t["cheapest"]["extra_cost"] == 0 and "Nothing given up" in t["cheapest"]["line"]
    assert (t["balanced"]["extra_cost"], t["balanced"]["days_saved"]) == (40, 2)
    assert t["balanced"]["line"] == "Balanced costs ₹40 more and arrives 2 days earlier."
    assert (t["fastest"]["extra_cost"], t["fastest"]["days_saved"]) == (200, 4)
    # one seller only: nothing to give up
    solo = evaluate([mk("A", 10.0, 3)], need).tradeoffs
    assert all(v["extra_cost"] == 0 for v in solo.values())
    # nobody eligible: no invented numbers
    none = evaluate([mk("A", 10.0, 9)], need).tradeoffs
    assert all(v["line"] is None for v in none.values())
