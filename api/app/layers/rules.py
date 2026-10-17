import re
from ..core import Ctx, Result


class Rules:
    """Deterministic answers (regex/lookup/trie/algorithm). Register domain rules after the PS drops.
    handler(ctx, match) -> str | None. Zero token cost: prefer this over the LLM whenever exact logic works."""
    name = "rules"

    def __init__(self):
        self.rules: list[tuple[re.Pattern, callable]] = []

    def add(self, pattern: str, handler):
        self.rules.append((re.compile(pattern, re.I), handler))
        return self

    async def run(self, ctx: Ctx):
        for pat, fn in self.rules:
            m = pat.search(ctx.query)
            if m and (ans := fn(ctx, m)) is not None:
                return Result(ans, self.name, detail={"rule": pat.pattern})
        return None
