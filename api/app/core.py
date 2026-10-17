"""Pipeline core. Domain-agnostic: swap/add layers once the problem statement is known."""
import time, uuid
from dataclasses import dataclass, field
from typing import Protocol
from .trace import TraceEvent, bus

# $ per 1M tokens (in, out). EDIT to current provider pricing; these are placeholders.
PRICES = {"small": (0.25, 1.25), "big": (3.0, 15.0), "mock": (0.25, 1.25)}


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)  # crude; replace with provider tokenizer if exact numbers matter


def cost(model: str, tin: int, tout: int) -> float:
    pi, po = PRICES.get(model, (0, 0))
    return (tin * pi + tout * po) / 1_000_000


@dataclass
class Ctx:
    query: str
    tenant: str = "default"  # cache/knowledge namespace, never mix tenants
    meta: dict = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class Result:
    answer: str
    layer: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    detail: dict = field(default_factory=dict)


class Layer(Protocol):
    name: str

    async def run(self, ctx: Ctx) -> Result | None:
        """Return a Result to short-circuit the pipeline, or None to fall through."""

    def learn(self, ctx: Ctx, result: Result) -> None:
        """Optional: called with the final result so cheaper layers can cache it."""


class Pipeline:
    def __init__(self, layers: list):
        self.layers = layers
        self.stats = {"requests": 0, "by_layer": {}, "cost_usd": 0.0, "lat_ms": []}

    async def run(self, ctx: Ctx) -> Result:
        t_all = time.perf_counter()
        result = None
        for layer in self.layers:
            bus.emit(TraceEvent(ctx.request_id, layer.name, "start"))
            t = time.perf_counter()
            try:
                result = await layer.run(ctx)
            except Exception as e:  # a failing layer must not kill the request; fall through
                bus.emit(TraceEvent(ctx.request_id, layer.name, "error", (time.perf_counter() - t) * 1e3, detail={"error": str(e)}))
                continue
            ms = (time.perf_counter() - t) * 1e3
            if result is None:
                bus.emit(TraceEvent(ctx.request_id, layer.name, "miss", ms))
                continue
            bus.emit(TraceEvent(ctx.request_id, layer.name, "hit", ms, result.tokens_in, result.tokens_out, result.cost_usd, result.detail))
            break
        if result is None:
            result = Result("No layer could answer.", "none")
        for layer in self.layers:
            if hasattr(layer, "learn") and layer.name != result.layer:
                layer.learn(ctx, result)
        total = (time.perf_counter() - t_all) * 1e3
        bus.emit(TraceEvent(ctx.request_id, "pipeline", "done", total, result.tokens_in, result.tokens_out, result.cost_usd, {"answered_by": result.layer}))
        s = self.stats
        s["requests"] += 1
        s["by_layer"][result.layer] = s["by_layer"].get(result.layer, 0) + 1
        s["cost_usd"] += result.cost_usd
        s["lat_ms"] = (s["lat_ms"] + [total])[-1000:]
        return result

    def summary(self) -> dict:
        s, lat = self.stats, sorted(self.stats["lat_ms"])
        n = s["requests"]
        p = lambda q: round(lat[min(len(lat) - 1, int(q * len(lat)))], 2) if lat else 0
        pre_llm = n - s["by_layer"].get("llm", 0)
        return {
            "requests": n,
            "by_layer": s["by_layer"],
            "pct_answered_before_llm": round(100 * pre_llm / n, 1) if n else 0,
            "cost_usd": round(s["cost_usd"], 6),
            "cost_per_1k_usd": round(1000 * s["cost_usd"] / n, 4) if n else 0,
            "p50_ms": p(0.5), "p95_ms": p(0.95),
        }
