import asyncio
from app.core import Ctx
from app.main import build


def run(p, q, **kw):
    return asyncio.run(p.run(Ctx(q, **kw)))


def test_cache_layers_and_cost():
    p = build()
    a = run(p, "What is the return policy for shoes?")
    assert a.layer == "llm" and a.cost_usd > 0
    b = run(p, "  what is the RETURN policy for shoes? ")  # normalized exact hit
    assert b.layer == "exact_cache" and b.cost_usd == 0
    c = run(p, "return policy for shoes what is the")  # reordered words -> semantic hit
    assert c.layer == "semantic_cache"
    s = p.summary()
    assert s["requests"] == 3 and s["pct_answered_before_llm"] > 60


def test_tenant_isolation():
    p = build()
    run(p, "hello world question", tenant="a")
    assert run(p, "hello world question", tenant="b").layer == "llm"


def test_rules_short_circuit():
    p = build()
    p.layers[1].add(r"order\s+#?(\d+)", lambda c, m: f"Order {m.group(1)} status: shipped")
    r = run(p, "where is order #123")
    assert r.layer == "rules" and r.cost_usd == 0
