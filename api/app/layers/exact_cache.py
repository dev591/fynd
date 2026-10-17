import hashlib, re, time
from collections import OrderedDict
from ..core import Ctx, Result


def normalize(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


class ExactCache:
    """Hash map + LRU + TTL. Key includes tenant (+ version to invalidate on prompt/model change)."""
    name = "exact_cache"

    def __init__(self, capacity=10_000, ttl=3600, version="v1"):
        self.d: OrderedDict[str, tuple[float, Result]] = OrderedDict()
        self.capacity, self.ttl, self.version = capacity, ttl, version

    def key(self, ctx: Ctx) -> str:
        return hashlib.sha256(f"{self.version}|{ctx.tenant}|{normalize(ctx.query)}".encode()).hexdigest()

    async def run(self, ctx):
        k = self.key(ctx)
        hit = self.d.get(k)
        if not hit or time.time() - hit[0] > self.ttl:
            self.d.pop(k, None)
            return None
        self.d.move_to_end(k)
        r = hit[1]
        return Result(r.answer, self.name, 0, 0, 0.0, {"source_layer": r.layer})

    def learn(self, ctx, result):
        self.d[self.key(ctx)] = (time.time(), result)
        self.d.move_to_end(self.key(ctx))
        while len(self.d) > self.capacity:
            self.d.popitem(last=False)
