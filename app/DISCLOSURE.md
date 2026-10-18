# Disclosure log

## Pre-hackathon boilerplate (generic plumbing only, no story/protagonist/product logic)
Written 2026-10-16: Vite + React + TS scaffold, Tailwind tokens (`src/index.css`), Lenis↔ScrollTrigger wiring (`src/lib`),
generic `PinnedChapter` (pin, scrub, progress out, reduced-motion fallback), `SkipToApp`, `Nav`, placeholder chapters.

## Built during the hackathon (Sat 17 Oct, after the PS drop)
Crossover story landing: six chapters in `src/landing/chapters`, the quote-card → cost-curve protagonist
(`CostChart`, `QuoteCard`), the quantity slider + spreadsheet mode (`QtyControl`), and an in-browser copy of the
rules (`src/landing/engine.ts`, `fixture.ts`) that runs the three case checks live. No new dependencies.
Written with Claude Code; reviewed by Dev.
Site-wide polish: `CursorTrail` (canvas ink-drop trail with an SVG goo filter), `Magnetic` CTAs, tilting quote cards,
`ScrollProgress`, and a scrubbed `--enter` entrance in `PinnedChapter`. The trail idea was inspired by a pasted
"particle animation" component whose author and license were not stated, so none of its code was copied; this is an
independent rebuild.
Onboarding Login Wizard (`src/wizard/`): role-selection, account verification, business profile, live GSTIN/PAN state-code validator with non-blocking skippable gate, role policies, and judge demo auto-filler. Seamlessly mounts at `/login` and routes to `/app` with full draft persistence.

## Dependencies installed
| Package | Use | License |
|---|---|---|
| react, react-dom, react-router-dom | UI / routing | MIT |
| vite, typescript | build | MIT / Apache-2.0 |
| tailwindcss, @tailwindcss/vite | styling | MIT |
| gsap (+ScrollTrigger) | landing 3D dive, cursor trail | GSAP standard license (free) |
| lenis | landing smooth scroll | MIT |
| motion | app motion: board reorder, toasts, rings, mic | MIT |
| lucide-react | icons (1.5px stroke) | ISC |
| @fontsource-variable/{fraunces,geist,geist-mono} | fonts | OFL-1.1 |

## 21st.dev components
None installed yet. Record component, author, license here before adding any.

## Backend skeleton (`/Volumes/dev/fynd/api`, pre-hackathon, generic)
Python 3.13: fastapi, uvicorn, pydantic, httpx, pytest (MIT/BSD/Apache). Layered pipeline, LRU+TTL exact cache, brute-force semantic cache with placeholder embedder, model-cascade stub with offline mock provider, SSE trace stream, stats. No domain logic, no real LLM calls.

## Built on Sun 18 Oct (v2: the request-and-quote network)
Written with Claude Code (Anthropic), reviewed by the team. No new frontend packages were added; `qrcode.react` (added by a
teammate for an earlier invite-link screen) was **removed** because nothing uses it any more.

Frontend: role toggle and guards, real Supabase sign-up and sign-in (Supabase's REST auth is called directly, no SDK),
anonymous compare with reveal and a mock paywall, exception dialog, spreadsheet mode, evidence tags, CSV/JSON/pasted-message
import, quote windows with a buyer bell, delivery record, decision one-pager with JSON download, seller inbox/verdict/catalog/
autopilot. Backend: everything under `api/app` apart from the pre-hackathon pipeline skeleton.

AI and external services (all called from the server; keys never reach the browser):
| Service | Use | Notes |
|---|---|---|
| OpenAI Responses API, model `gpt-6-luna` (from env) | intake, pasted-message reading, seller wording, item-match, explainer | strict JSON schema; output is verified by code before anyone sees it |
| ElevenLabs speech-to-text, `scribe_v2` | voice intake transcription | transcript then goes through the same checks as typed text |
| Supabase Auth | sign-up, sign-in, token checks | project URL and anon key are public values; no service key is used |

Python packages: unchanged from the pre-hackathon list (fastapi, uvicorn, pydantic, httpx, pytest). The OpenAI and ElevenLabs calls use
`httpx`; there is no vendor SDK. SQLite comes from the standard library.

Data: the seeded demo sellers, products, prices and history are synthetic and labelled so on the sample-request path. No claim of customers, revenue or a pilot is made
anywhere in the product.

## Built on Sun 18 Oct, later in the day
Written with Claude Code (Anthropic) and Kiro, reviewed by the team.

- **Landing page rebuilt** as one short page (`src/landing/Landing.tsx`): a live quote feed driven by the in-browser rules copy,
  buyer and seller benefits, how it works, and the spreadsheet-vs-Crossover example from the C27 brief. The six pinned scroll
  chapters, `DiveStage`, `PinnedChapter`, `ScrollProgress`, `SkipToApp` and the Lenis wiring were deleted. The packages
  `lenis`, `three`, `@react-three/fiber` and `@react-three/drei` were uninstalled because nothing imports them.
- **AI second opinion** (`api/app/summary.py`): a model reads the buyer's note and may suggest a different option. A live check
  showed it could write true numbers inside false claims, so it no longer writes any text: it chooses a seller and a concern
  (deadline or cash) and quotes the buyer's own words, code verifies the quote and that the pick serves the concern, and code
  writes the sentence from the engine's numbers. The engine's pick never changes. The call is logged with the decision.
- **Shipping choice and estimate.** The seller picks own shipment or Delhivery. Without a Delhivery token the estimate comes from
  a zone rate card we wrote (`api/app/delhivery.py`), labelled "demo rate card, not a Delhivery quote". The Delhivery client
  is written against the pasted API examples and tested only with fake replies; no live Delhivery call has succeeded, because we
  have no token. Pincodes are asked once at sign-up and never shown to the other side.
- **Ten demo seller accounts** (`api/app/demo_roster.py`, `api/scripts/seed_demo_sellers.py`): fictional businesses created in
  Supabase by a script the team runs. The one-click panel on `/signin` is off unless `DEMO_LOGINS=on`.
- **Seller voice quote bar and silent OS notifications** for new requests (built with Kiro): speech to text reuses the
  ElevenLabs path; the quote is a draft the seller checks and sends. Voice output (speech synthesis) was deliberately left out.
- **Deployment:** the API serves the built website from one address (`Dockerfile`, `render.yaml`, `DEPLOY.md`). The Dockerfile
  was written but not built here (no Docker on the dev machine); the same layout was checked by serving the built site with uvicorn.
- **Free delivery above a goods value.** A quote can say delivery is free once the goods are worth at least a stated amount. The
  threshold is on the seller's stated GST basis and is normalised like the pack price; the buyer sees the normalised value
  (`compare_free_freight_above`). Quotes without it compute exactly as before. Found by code review and fixed before this
  note: a folded form section hid the prefilled threshold, the compare screen showed the raw number, and a phone row overflowed.
- **Per-unit freight** (built with Kiro). A second freight component, `per_unit_freight` (₹ per unit), is added to the flat freight
  after the free-delivery waiver: `total freight = flat + per_unit × units`. Normalised to the buyer's GST basis like the pack
  price. A quote without it computes exactly as before. Tested with 15 backend tests against fakes.
- **Split orders.** `best_split` in `api/app/engine.py` finds the cheapest way to cover the whole quantity from two sellers, and
  offers it only when it beats every single seller or when no single seller can cover the quantity (for example, stock caps). It
  uses the same cost rules as `order()` (packs, minimum order, tiers, free delivery, per-unit freight, stock caps) and never
  replaces the normal pick. It is checked against an exhaustive search on random markets. Ordering a split needs both sellers
  revealed, and the quantities always come from the server's own plan, never from the browser. Up to two sellers only.
- **Volume price tiers in the comparison.** `order()` now looks up the pack price for the units ordered from the quote's tiers
  and falls back to the quote's own price, so a quote without tiers (including the three scored case checks) computes exactly as
  before. Tiers are normalised to the buyer's GST basis like the main price and mirrored in the browser copy of the engine
  (`src/landing/engine.ts`); a browser check confirms both agree at every tier boundary.

## UI redesign (Sun 18 Oct, morning)
Written with Claude Code (Anthropic), reviewed by the team. No backend or engine changes.
- **Landing dive** (`src/landing/Dive.tsx`): a pinned 3D stage; scrolling moves a camera through depth layers (the messy
  quote messages, the request broadcast, the live board, the answer). GSAP ScrollTrigger drives it, Lenis smooths the scroll.
  With reduced motion it renders as plain stacked sections.
- **Quote board** (`src/dashboard/QuoteBoard.tsx`): one answer card in plain words, then every quote side by side with yes/no
  checks, best first; the order animates when quotes arrive or the priority changes. The cost chart moved behind "How Crossover
  worked this out".
- **Live toasts** (`src/components/LiveToasts.tsx`): a new or revised quote, a new best, and a new request on the seller inbox.
- Redesigned request list, voice-first new request, seller inbox, split-screen sign-in, plainer wizard copy, ambient backdrop.
- **21st.dev:** no component was copied. Every effect here was written for this project, so there is no third-party component
  licence to record.
- **Ask the desk** (`api/app/ask_desk.py`, `src/dashboard/AskDesk.tsx`): a buyer's what-if question is read into engine inputs
  (quantity, deadline, priority, sellers who drop out). Rules read it first and work with no AI key. Only when the rules find
  nothing is a model asked, and each value it returns is kept only if it appears in the buyer's own words. The engine then
  recomputes and code writes the answer from engine numbers, so the model never states a price, date or winner. Nothing is
  saved and the stored request is never changed. Checked live against the real model on seven phrasings.
- **The desk suggests** (`suggestions()` in `api/app/ask_desk.py`): when quotes arrive, the server scans what-ifs through the rules
  engine (more days, larger quantity, a split, the nearest seller behind the winner, the cost of speed) and lists up to four. Every
  headline is written in code from engine numbers; no model is involved, and a suggestion that can be tried carries the exact
  question to ask. An "order more" idea must be strictly cheaper than today's winner at that quantity, never a tie. Also fixed:
  the website catch-all route now sits last in `main.py`, so no API route added after it is hidden on a deployed server.
- **Request details, history and orders.** Each request has an event log (`events` in the store, saved with everything else); the
  buyer sees it with seller aliases until a reveal, and a seller sees only their own thread plus what the buyer did to the whole
  request. A buyer can edit an open request (limits enforced on the server; every change is logged and each matched seller gets a
  "check your quote" reminder). Order history lists decided requests with the revealed receiver; sellers see orders they won.
- **Fine print** (`api/app/fine_print.py`): rules plus a model read each seller's note for hidden terms. A model flag is kept only
  if its kind is in a fixed list and the phrase it quotes is really in the note, so it can only point at the seller's own words.
  Warnings only; they never change a price or a winner. Tested with fake model replies, not yet against the real model.
- The "Get QR" wording on the new-request button was removed because no QR code was ever generated. A QR code is not built.
- **Payments (Razorpay test mode).** `api/app/razorpay_client.py` is a port of the team's existing Razorpay test-mode project
  (`/Volumes/dev/razorpay`, which uses the official `razorpay` SDK): create an order with auto-capture, open Razorpay Checkout in the
  browser, verify the HMAC signature on the server, confirm the payment was captured, retry transport failures with backoff. It
  uses `httpx`, so no new package was added. Keys are read from the environment only; a live key is refused unless
  `RAZORPAY_ALLOW_LIVE=true`. Prices (₹499 for 10 reveals, ₹1,499 for 30 days Pro) are our assumptions, with the reasoning on the
  page. The server is tested against a faked Razorpay API with real signatures; **no real Razorpay call has been made from this
  codebase yet**, and checkout has not been clicked through in a browser (it needs the team's test keys).
- A buyer who places an order is notified to choose cash on delivery or a 50% advance; a paid advance is shown to the seller on
  their Orders received tab. In test mode no real money moves; the earlier claim that Crossover never holds money applies to
  cash on delivery only.
