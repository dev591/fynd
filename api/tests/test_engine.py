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
