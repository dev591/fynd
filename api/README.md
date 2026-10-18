# api

FastAPI service for Crossover: the rules engine, the request-and-quote network, anonymity and reveal, and the AI
helpers. See the repo `README.md` for what the product does and how to run everything.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # fill it in; it is git-ignored
.venv/bin/uvicorn app.main:app --port 8000
.venv/bin/python -m pytest -q   # 301 tests
python3 -m app.reset            # back to the seed data (stop the API first)
```

## Where things live

| File | Job |
|---|---|
| `engine.py` | Landed cost, gates, priority modes, negotiation targets, the three case checks. No identities, no masking |
| `tax.py` | Puts quotes on one GST basis *before* the engine sees them |
| `views.py` | The only way data leaves: buyer, seller and public views. Masking happens here, never in the browser |
| `masking.py` | Hides phone numbers and emails in free text until a seller is revealed |
| `rfq_store.py` | The store: requests, quotes, aliases, reveals, notices, windows (`tick()` with an injectable clock) |
| `persist.py` | SQLite (WAL) write-through; loads on start; a corrupt file is set aside, never fatal |
| `auth.py` | Supabase login tokens. Fail-closed: if auth is not configured, protected routes refuse |
| `intake.py`, `quote_text.py`, `assistant.py`, `summary.py` | AI helpers, each checked by code before a person sees the result |
| `importer.py` | CSV and JSON quote import with row-level errors |

## Rules worth knowing

- Every buyer and seller route needs a signed-in user **with the matching role**; the server checks both. The supplier
  invite links (`/api/rfq-by-token/*`) and shared one-pager links (`/api/share/*`) are public by design and unguessable.
- Buyers address sellers by alias ("Seller 2"); real ids and invite tokens never reach a buyer. Sellers see a buyer only
  as a descriptor until revealed.
- Negotiation is human. No AI or autopilot answers a target; `has_pending_target` stops autopilot.
- `/run`, `/stats`, `/trace/stream` are the pre-hackathon pipeline skeleton; they now require a login and are not used by
  the product.
