# api: volatile pipeline skeleton (pre-hackathon boilerplate, domain-agnostic)
Layered "cheapest first" request pipeline + live trace over SSE. No domain logic; everything is meant to be swapped after the problem statement drops.

Run: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn app.main:app --port 8000`
Test: `.venv/bin/python -m pytest -q`

- `POST /run {query, tenant, meta}` -> answer + which layer answered + tokens + $
- `GET /trace/stream` (SSE): one event per layer hop (`start|hit|miss|done|error`, ms, tokens, $). Feeds the dashboard right rail.
- `GET /stats`: % answered before LLM, $/1k requests, p50/p95. These are the Proof-chapter numbers once real traffic exists.

## How to change it for the real problem
- Order/choice of layers: env `PIPELINE="exact,rules,semantic,llm"`; add new layers to `REGISTRY` in `app/main.py` (class with `name`, `async run(ctx)->Result|None`, optional `learn`).
- Domain logic: register deterministic rules (`Rules.add`), add retrieval/OKF/LangGraph as new layers before `llm`.
- Real LLM: implement `complete(model, prompt)->(text, tin, tout, confidence)` and pass to `LLMCascade`. Default is an offline mock.
- Placeholders to replace: `PRICES` in `core.py` (edit to real pricing), hashed-BoW embedder in `semantic_cache.py` (use a real embedding model + ANN), token estimate (`len/4`).
- State is in-memory (lost on restart). Move cache/queue to Redis and vectors to pgvector when the design needs it.

Caveats: semantic threshold (0.88) is untuned; the mock "confidence" is fake; single process only.
