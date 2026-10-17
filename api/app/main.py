import asyncio, json, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .core import Ctx, Pipeline
from .trace import bus
from .layers.exact_cache import ExactCache
from .layers.rules import Rules
from .layers.semantic_cache import SemanticCache
from .layers.llm import LLMCascade

# Layer order is config, not code: PIPELINE="exact,rules,semantic,llm". Add domain layers to REGISTRY.
REGISTRY = {"exact": ExactCache, "rules": Rules, "semantic": SemanticCache, "llm": LLMCascade}


def build() -> Pipeline:
    order = os.getenv("PIPELINE", "exact,rules,semantic,llm").split(",")
    return Pipeline([REGISTRY[n.strip()]() for n in order])


pipeline = build()
app = FastAPI(title="Fynd pipeline skeleton")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


class RunIn(BaseModel):
    query: str
    tenant: str = "default"
    meta: dict = {}


@app.get("/health")
def health():
    return {"ok": True, "layers": [l.name for l in pipeline.layers]}


@app.post("/run")
async def run(body: RunIn):
    ctx = Ctx(body.query, body.tenant, body.meta)
    r = await pipeline.run(ctx)
    return {"request_id": ctx.request_id, **r.__dict__}


@app.get("/stats")
def stats():
    return pipeline.summary()


@app.get("/trace/stream")
async def trace_stream():
    q = bus.subscribe()

    async def gen():
        try:
            for ev in list(bus.history)[-50:]:
                yield f"data: {json.dumps(ev.dict())}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), 15)
                    yield f"data: {json.dumps(ev.dict())}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
