# Crossover

**A request-and-quote desk for small manufacturers.** A buyer says what they need; every seller who stocks it is
notified; quotes come back **without seller names**; the buyer compares true landed cost, picks one, and only then
**reveals** that seller to unlock contact details. Sellers pay nothing. The rules engine decides every number. AI only
handles the talking, and a person confirms every step.

FyndHacks problem **C27, Supplier Quote Comparison Desk**.

> **Honest status.** This is a tested prototype. There are no customers, no revenue and no pilot yet. The sellers in the
> demo are fictional businesses we made up, and their prices and history are demo data. Prices for reveal packs
> (₹499 for 10, ₹1,499 a month) and the 5% "balanced" tolerance are **assumptions**, not results. The payment screen is a
> mock: nothing is charged or stored. The Delhivery freight estimate comes from our own demo rate card, not from Delhivery
> (we have no token), and says so on screen. Verification badges say exactly what was checked, and no badge is a live
> government check.

## The problem in one line

A spreadsheet that sorts quotes by price per unit picks the wrong supplier: it ignores freight, pack sizes, minimum
orders, GST basis and delivery dates. With 100 units, supplier A at ₹10 + ₹200 freight costs ₹1,200 and B at ₹11 + ₹50
costs ₹1,150, so B wins. Above 150 units A wins. Crossover treats a quote as a cost curve with hard gates on top.

## What it does

| Area | What you can do |
|---|---|
| **Compare** | Volume price tiers from a seller's catalog (the tier the order reaches sets the pack price, shown to the buyer and used by the quantity slider). Landed cost per seller, cost per usable unit, cash tied up in extra units, quantity slider (the winner can flip), spreadsheet mode (shows the naive pick and the rupee difference), winner under cheapest / fastest / balanced with a "what you give up" line |
| **Split order** | When no single seller can cover the quantity, or two together are cheaper, the best two-seller split is shown beside the normal pick with each seller's share, the total and the saving. Ordering it needs both sellers revealed; the quantities are the server's, not editable |
| **Gates** | Different item, unknown pack size (blocked), late delivery or short stock (needs a **written reason and a named approver**; a blank reason is refused), cheaper-but-excluded list |
| **Tax** | Quotes are put on one GST basis (ex-GST if you can claim it back). A basis the seller did not state is treated as exclusive and flagged |
| **Anonymous quotes** | Sellers appear as "Seller 1/2…". Name, contact, city and products unlock per seller with **Reveal** (3 free, then a mock paywall) |
| **Negotiation (human)** | The engine computes the concession ("A wins if freight drops by ₹51"); a named person reviews and sends it; the seller revises by hand. No AI or autopilot answers a target |
| **Intake** | Type or speak a request (English or Hinglish) → confirm card the buyer must check → request. The manual form always works |
| **Import** | CSV or JSON, or paste a supplier's WhatsApp message. Bad rows are reported by row number and good rows still load. Nothing is guessed |
| **Shipping** | Each seller says whether they ship themselves or by Delhivery. A labelled estimate (demo rate card until a real token is set) can fill freight and lead time, only when the seller presses "Use this". Pincodes are asked once at sign-up and never shown to the other side |
| **AI second opinion** | Beside the engine's pick, a model may suggest a different allowed option for the buyer's note and priority. Numbers are checked in code, the engine's pick never changes, and the call is logged with the decision |
| **Seller side** | Inbox with a rules-based "can you fulfil" verdict, a quote drafted from your own catalog (numbers copied by code), stock/price breaks, decline, optional autopilot |
| **Windows** | A request closes after 15 min / today / 24 h / 3 days; the buyer is told at the first quote, at enough quotes, and at close with the best option; silent sellers are reminded |
| **Record** | Saved decision with input fingerprint, every number tagged observed / derived / assumed, printable one-pager, JSON download, read-only share link, delivery record |

## How AI is used (and not used)

**AI proposes, the engine and the catalog decide, a person confirms.** The model never writes a price, pack size, stock
level or date that is not in the data.

| Feature | Model's job | Guardrail |
|---|---|---|
| Buyer intake (chat, voice) | Extract item, quantity, deadline wording | Strict JSON schema; code checks every value against what the buyer said and drops the rest; deadlines like "Friday" are resolved in code; confirm card; 8 s timeout falls back to the manual form |
| Pasted supplier message | Read it into quote rows | Same checks; unstated pack size/freight/lead time stay blank and flagged; "free delivery" needs those words |
| Seller note | Word a short message | Every number must exist in the data and offers/promises are rejected, else a template is used |
| Seller voice quote | Turn a spoken quote into draft fields | Same number checks as pasted messages; unstated fields stay blank; the seller edits and presses Send |
| Second opinion | Read the buyer's note for a deadline or cash concern and choose among options the engine allowed | The model only picks a seller and a concern and quotes the buyer's own words; code checks the quote and that the pick serves the concern, then writes the sentence from engine numbers. Engine pick unchanged |
| Item-match, "why this supplier" | Warn / explain | Warn only; the explanation can never pick or change the winner |

Voice uses ElevenLabs speech-to-text; text understanding uses OpenAI. Keys stay on the server. With no keys, every AI
path falls back to the manual route. Live check against the real models: 15 buyer sentences, **0 invented values**; 7
pasted messages read correctly.

## Run it

Needs Python 3.13 and Node 20+.

```bash
# API (http://localhost:8000)
cd api
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then fill in the values (see below). Never commit .env
.venv/bin/uvicorn app.main:app --port 8000

# Web (http://localhost:5173)
cd app
cp .env.example .env.local      # VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (public values)
npm install && npm run dev
```

Login is real: **Supabase Auth**. Sign up in the wizard (`/login`), or `/signin`. In Supabase, switch off "Confirm email"
for the demo. The API checks every token (locally with the JWT secret, or by asking Supabase).

State is saved to **SQLite (WAL)** at `api/data/app.db`. `cd api && python3 -m app.reset` returns to the seed data.

### Configuration (`api/.env`)

| Variable | Meaning |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Supabase project (public values). Needed to verify logins remotely |
| `SUPABASE_JWT_SECRET` | Optional: verify HS256 logins locally (faster). Server-side only |
| `OPENAI_API_KEY`, `MODEL_FAST` | Text understanding. Model name read from env, never hard-coded |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_STT_MODEL` | Voice transcription |
| `FREE_REVEALS` (3) | Free seller reveals per buyer |
| `BALANCED_TOLERANCE` (0.05) | How far above the cheapest "balanced" mode will pay to arrive sooner. An assumption |
| `DEMO_AUTOPILOT` (on) | Synthetic demo sellers answer by themselves so quotes land in seconds |
| `DEMO_WINDOW_MINUTES` (off) | Shorten every quote window for a demo; the UI says "demo timing" |
| `ALLOW_DEMO_SELLERS` (true) | Let any seller-role user act as a synthetic demo seller |
| `PERSIST` (on), `CROSSOVER_DB` | SQLite persistence and its path |
| `CORS_ORIGINS` | Extra allowed browser origins (localhost and private networks are always allowed) |

### Ten demo sellers (optional, local demos only)

For a live buyer-and-seller demo: put `DEMO_SELLER_PASSWORD` (you choose it) in `api/.env`, start the API, then run
`cd api && python3 scripts/seed_demo_sellers.py`. It creates ten seller accounts in Supabase and fills their profile and
catalog through the normal API (safe to run again; "Confirm email" must be off, or set `SUPABASE_SERVICE_ROLE_KEY` for the
script only). Then set `DEMO_LOGINS=on` and restart the API: `/signin` shows the ten sellers as one-click logins. This hands
out a shared password, so never turn it on for a public deployment.

### One public address

The API serves the built website, so a deployment is a single URL with https (needed for the microphone and browser
notifications on both laptops). See `DEPLOY.md` and `render.yaml`.

## Test it

```bash
cd api && python3 -m pytest -q          # 436 tests
cd app && npx tsc -b && npm run lint && npm run build
cd api && python3 -m tests.golden.run_live   # real-model check of the 15 buyer sentences (needs keys)
```

The three scored case checks (landed cost, late supplier needs an exception, unknown pack size blocks) are tests, and so
are anonymity (a scan of every buyer and seller response for hidden fields), reveal and quota, roles, auth, the GST
worked example, import errors, windows with a fake clock, persistence across a restart, and the whole demo path.

## The demo path

1. Sign in with an account that has both roles (header toggle: Buyer / Seller).
2. **New request**: say or type "100 M10 bolts in 5 days, fastest" → check the confirm card → **Confirm**.
3. Demo sellers on autopilot quote at once. Quotes appear as **Seller 1, 2, 3**. Flip **cheapest / fastest / balanced** and
   **Spreadsheet mode**. Drag the quantity past 150 and the winner flips.
4. **Review target** for the runner-up (a person sends it). Switch to the **Seller** role, open the request, revise by hand.
   The winner flips on the buyer's next poll.
5. **Reveal** the winner → **Place order** (cash on delivery; Crossover never holds money) → open the **one-pager**.

## Layout

```
api/app/     engine.py (rules; landed cost + gates untouched), tax.py, views.py (what each audience may see),
             rfq_store.py, persist.py, auth.py, intake.py, quote_text.py, assistant.py, summary.py, importer.py
api/tests/   320 tests + golden sets (15 buyer sentences, 8 seller cases)
api/supabase/schema.sql   an early Postgres draft with row-level security. NOT used and NOT kept in sync: the live API uses SQLite
app/src/     landing story, wizard, buyer desk, seller desk, shared components
AUDIT.md     what exists against the v2 brief, and the decisions made
```

## Security notes

- Login tokens are checked on **every** buyer and seller route; the server enforces roles and ownership. If login is not
  configured, protected routes refuse instead of opening up.
- A JWT secret that was once published in a repository is rejected by hash and never trusted again (logins are then
  verified by asking Supabase). Rotate any secret that has been committed.
- Secrets live in git-ignored `.env` files and environment variables only. The browser holds only the public Supabase URL
  and anon key.
- Shared one-pager links are unguessable, read-only and carry no seller or buyer identity.

## Known limits, stated plainly

- Item matching is by exact name or alias only. No spec, grade or brand comparison.
- A partial fill is an exception that needs sign-off. A split order covers the quantity from up to two sellers (never three), is offered next to the normal pick, and needs both sellers revealed.
- Freight is one flat amount per quote: volume price tiers, a free-delivery-above threshold, and a per-unit freight component (total freight = flat + per_unit × units dispatched) are now modelled. Per-kg freight is not.
- Seller reliability is not scored.
- One uvicorn process. SQLite and in-memory state are fine for a demo, not for scale.
- Chat scrubs phone numbers and emails in common formats; it cannot catch a number spelled out in words.
- Not built: a live talking voice agent (voice input and silent notifications exist), screenshot reading, a help desk, any real payment, a live Delhivery connection, split orders between two sellers, and joint optimisation of a multi-item basket (each item is compared on its own).
- Written with Claude Code (see `app/DISCLOSURE.md`); the team reviews and can explain each part.
