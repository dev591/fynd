# Crossover: reproducible handoff

Commands here were run on the commit that adds this file. Last verified: `pytest` 601 passed; `tsc -b`, `npm run lint` (warnings only) and `npm run build` succeed.
Product description, AI guardrails and the demo path are in `README.md`; deployment detail is in `DEPLOY.md`.

## 1. Prerequisites

Python 3.13, Node 20+, npm. Optional accounts: Supabase (login and production persistence), OpenAI, ElevenLabs, Razorpay (test keys), Delhivery.
**Nothing is needed to run the tests or the rules engine.** Login needs Supabase; every AI path falls back to the manual route without keys.

## 2. Install

```bash
git clone https://github.com/dev591/fynd.git && cd fynd
# submitted source: the commit named in the submission form (or the tip of main)

cd api
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd ../app
npm ci
```

## 3. Configure

```bash
cp api/.env.example api/.env          # server-side, git-ignored
cp app/.env.example app/.env.local    # browser-side, public values only
```

Never commit `.env` files. Never put `SUPABASE_SERVICE_ROLE_KEY` or `RAZORPAY_KEY_SECRET` anywhere under `app/`.

`api/.env` (example values, no secrets):

```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=<public anon key>
OPENAI_API_KEY=            # optional
MODEL_FAST=<model name from your OpenAI dashboard>
ELEVENLABS_API_KEY=        # optional (voice)
ELEVENLABS_STT_MODEL=scribe_v2
RAZORPAY_KEY_ID=rzp_test_...   # optional, test mode only
RAZORPAY_KEY_SECRET=           # optional, server only
FREE_REVEALS=3
BALANCED_TOLERANCE=0.05
DEMO_AUTOPILOT=on
PERSIST_BACKEND=               # empty = local SQLite; "supabase" in production
```

`app/.env.local`:

```
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<public anon key>
VITE_API_URL=                  # blank = http://localhost:8000
```

Full variable list: `api/.env.example` and the table in `README.md`. In Supabase, turn off "Confirm email" for the demo.

## 4. Run (development)

```bash
# terminal 1: API on http://localhost:8000  (health: /health)
cd api && .venv/bin/uvicorn app.main:app --port 8000
# terminal 2: web on http://localhost:5173
cd app && npm run dev
```

State saves to `api/data/app.db` (SQLite). Reset to seed data: `cd api && .venv/bin/python -m app.reset`.
Optional ten demo sellers: see "Ten demo sellers" in `README.md` (`api/scripts/seed_demo_sellers.py`).

## 5. Build

```bash
cd app && npm run build        # tsc -b && vite build, output app/dist
docker build --build-arg VITE_SUPABASE_URL=... --build-arg VITE_SUPABASE_ANON_KEY=... -t crossover .   # repo root
```

## 6. Test

```bash
cd api && .venv/bin/python -m pytest -q               # 601 tests, no keys or network needed
cd app && npx tsc -b && npm run lint && npm run build  # lint prints warnings, no errors
cd api && .venv/bin/python -m tests.golden.run_live    # live-model check of the 15 buyer sentences; needs OPENAI_API_KEY
```

Fixtures: `api/tests/golden/intake_cases.json` (15 buyer sentences), `seller_cases.json` (8 seller cases). Sample data: `api/app/demo_roster.py`, `api/scripts/seed_demo_sellers.py` (fictional sellers).
The three scored case checks are in `api/app/engine.py` (`run_case_checks`) and also served at `GET /api/case-checks`.

## 7. Deploy

One URL (Render blueprint `render.yaml`, or any Docker host):

```bash
docker run -p 8000:8000 --env-file api/.env -v crossover-data:/data crossover
```

Or Vercel (`app/`, root directory `app`) plus Railway (`api/`, volume mounted at `/data`, one replica, `CORS_ORIGINS=<vercel domain>`). Production persistence: run `api/supabase/state.sql` in Supabase, set `PERSIST_BACKEND=supabase` and `SUPABASE_SERVICE_ROLE_KEY`.
Check `/health` after deploy. Set `DEMO_LOGINS=off` and `DEMO_AUTOPILOT=off` on any public deployment. Details and pitfalls (CORS, sleeping free tiers): `DEPLOY.md`.

## 8. Architecture

```
Browser (React + Vite + TS)  ->  FastAPI (api/app/main.py, ~80 routes)  ->  state: in-memory + write-through
  landing / wizard / buyer desk /           engine.py   rules: landed cost, gates, split orders         SQLite (laptop)
  seller desk                               views.py    what each audience may see (anonymity)          or Supabase table (prod)
                                            rfq_store.py requests, quotes, reveals, orders
Supabase Auth: logins, checked on every protected route
OpenAI / ElevenLabs: intake, pasted-message reading, notes, voice. They propose; code validates; a person confirms
Razorpay (test), Delhivery (demo rate card unless a token is set)
```

Principle: the engine and the catalog decide every number; AI never writes a price, pack size, stock level or date.
Negotiation stays human: the engine computes a concession, a named person sends it, the seller revises by hand.

## 9. Scope and contributions

In scope: anonymous quote comparison on landed cost (freight, pack size, MOQ, price tiers, GST basis, lead time), gates with signed exceptions, reveal-to-unlock contact, split orders, ask-the-desk what-ifs, fine-print flags, decision record and one-pager, seller inbox and quoting, test-mode payments.
Contributions: `git shortlog -sn` shows 83 commits across the team's git identities. Code was written with Claude Code and reviewed by the team; the log of what was built when, and which packages and licences are used, is `app/DISCLOSURE.md`. What exists against the brief: `AUDIT.md`.

## 10. Known limits

- A prototype: no customers, no revenue, no pilot. Demo sellers, their prices and history are fictional.
- Reveal bundle prices (₹79 to ₹2,699) and the 5% balanced tolerance are assumptions.
- Payments are Razorpay test mode only; no real money moves. Delhivery freight is from our own demo rate card unless `DELHIVERY_TOKEN` is set. Badges state what was checked; none is a live government check.
- Item matching is by exact name or alias; no spec, grade or brand comparison. No seller reliability score.
- Splits cover at most two sellers; multi-item baskets are compared per item, not jointly. Freight is flat plus per-unit; no per-kg.
- Single uvicorn process (in-memory state with write-through). Not built for scale; keep one replica.
- Chat scrubs phone numbers and emails in common formats, not numbers spelled out in words.
- Not built: live talking voice agent, screenshot reading, help desk, real payments, live Delhivery connection.
- Lint reports a few warnings (`NewRequestForm.tsx`, `DashboardDesk.tsx`); the production build has a large-chunk warning.
