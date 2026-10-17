import math, re, zlib
from ..core import Ctx, Result


def hash_embed(text: str, dim=256) -> list[float]:
    """Dependency-free placeholder embedder (hashed bag of words). Swap for a real model by passing embed=..."""
    v = [0.0] * dim
    for w in re.findall(r"\w+", text.lower()):
        v[zlib.crc32(w.encode()) % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class SemanticCache:
    """Brute-force cosine over stored vectors (fine to ~10k entries). Replace the scan with HNSW/pgvector/FAISS at scale.
    THRESHOLD MUST BE TUNED on labeled paraphrase / non-paraphrase pairs; wrong hits are worse than misses."""
    name = "semantic_cache"

    def __init__(self, embed=hash_embed, threshold=0.88, capacity=10_000):
        self.embed, self.threshold, self.capacity = embed, threshold, capacity
        self.items: list[tuple[str, list[float], Result]] = []

    async def run(self, ctx: Ctx):
        q = self.embed(ctx.query)
        best, score = None, 0.0
        for tenant, vec, res in self.items:
            if tenant != ctx.tenant:
                continue
            s = sum(a * b for a, b in zip(q, vec))
            if s > score:
                best, score = res, s
        if best and score >= self.threshold:
            return Result(best.answer, self.name, detail={"similarity": round(score, 3)})
        return None

    def learn(self, ctx, result):
        self.items.append((ctx.tenant, self.embed(ctx.query), result))
        if len(self.items) > self.capacity:
            self.items.pop(0)
