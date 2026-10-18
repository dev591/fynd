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
| gsap | cursor trail and small effects | GSAP standard license (free) |
| motion | dashboard micro-interactions | MIT |
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
