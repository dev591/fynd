"""LLM layer with a cascade: small model first, escalate to big on low confidence / schema failure.
Providers are pluggable: implement `async complete(model, prompt) -> (text, tokens_in, tokens_out, confidence)`."""
from ..core import Ctx, Result, est_tokens, cost


class MockProvider:
    """Offline default so the whole pipeline/UI works without keys. Replace in config."""

    async def complete(self, model, prompt):
        text = f"[{model}] answer to: {prompt[:80]}"
        conf = 0.6 if model == "small" and len(prompt) > 120 else 0.95  # pretend long prompts are hard
        return text, est_tokens(prompt), est_tokens(text), conf


class LLMCascade:
    name = "llm"

    def __init__(self, provider=None, small="small", big="big", escalate_below=0.8, max_context_tokens=4000):
        self.p = provider or MockProvider()
        self.small, self.big, self.thr, self.max_ctx = small, big, escalate_below, max_context_tokens

    def build_prompt(self, ctx: Ctx) -> str:
        # Stable prefix first (prompt-cache friendly), variable part last. Retrieved context goes in ctx.meta["context"].
        context = ctx.meta.get("context", "")[: self.max_ctx * 4]
        return f"{ctx.meta.get('system', 'You are a helpful commerce assistant.')}\n\n{context}\n\nQ: {ctx.query}"

    async def run(self, ctx: Ctx):
        prompt = self.build_prompt(ctx)
        text, ti, to, conf = await self.p.complete(self.small, prompt)
        c, used, tin, tout = cost(self.small, ti, to), self.small, ti, to
        escalated = conf < self.thr
        if escalated:
            text, ti2, to2, conf = await self.p.complete(self.big, prompt)
            c += cost(self.big, ti2, to2)
            used, tin, tout = self.big, tin + ti2, tout + to2
        return Result(text, self.name, tin, tout, c, {"model": used, "escalated": escalated, "confidence": conf})
