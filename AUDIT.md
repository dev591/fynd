# AUDIT.md: Crossover v2 Step 0

Audited Sun 18 Oct 01:59 IST on `main` (19 commits not yet pushed to `origin/main`). Feature stop is 11:00 IST, so about 9 hours remain. Nothing in the code was changed for this audit.

Status key: **exists** (works and is tested), **partial**, **missing**.

## 0. The repo is not what the brief assumes

| Brief says | Reality |
|---|---|
| `engine.py`, 24 passing tests | `api/app/engine.py` exists. **109** tests pass, including the three case checks. |
| `api.py`, `loader.py` | Neither exists. The API is a package: `api/app/main.py` plus `rfq_store.py`, `auth.py`, `intake.py`, `assistant.py`, `matching.py`, `summary.py`. |
| `contracts.ts` | Does not exist on `main`. Types live in `app/src/api/client.ts`. (A `src/contracts.ts` exists only on a teammate's `origin/backend` branch.) |
| Crossover at 151 is a tested check | **Not tested.** Only the negotiation cut of 51 is asserted (`test_engine.py:61`). I will add a crossover test. |
| SQLite behind FastAPI | **Not true today.** All app data is in memory (`RFQStore`). A restart wipes it. `api/supabase/schema.sql` (Postgres) was written but is not connected. |
| Supabase for login only | **True.** Sign-up and sign-in call Supabase; FastAPI verifies the token on every request (`api/app/auth.py`). |

## 1. Screens that exist (frontend, `app/src`)

Public: landing story (`/`), onboarding wizard (`/login`), sign-in (`/signin`), shared one-pager (`/share/:token`), supplier quote page opened from an invite link (`/supplier/quote?token=`, `/quote`).
Buyer (login required): requests list (`/app`), new request with chat/voice intake and manual form (`/app/new`), compare (`/app/compare/:id`), decision one-pager (`/app/decision/:id`).
Seller (login required): dashboard with inbox, bell, catalog tab, autopilot toggle (`/supplier`).

## 2. Data (in memory today, `api/app/rfq_store.py`)

`rfqs`, `quotes[rfq][supplier]` (versioned), `targets`, `chats`, `notifications`, `supplier_profiles`, `supplier_products`, `supplier_owner`, `profiles` (one `role` string), `decisions`, `shares`, `autopilot`, `assists`, `ai_log`.
Product fields: name, category, aliases, pack_price, pack_size, moq, usual_lead_days, capacity_cap, unit, stock, freight, price_breaks. No `photo_path`.
RFQ fields: item, qty, **need_in_days** (days, not a date), priority_mode, source, status, decision, owner_id. No window or min_quotes.

## 3. Endpoints (about 55)

Public: health, case-checks, compare, validate/tax, intake status, `GET /api/share/{token}`, all `/api/rfq-by-token/*` (invite links, no login by design).
Buyer (login + ownership): rfqs create/confirm/list/get, targets, decision, summary, share, ai-log, activity, savings, recommendations, supplier click-through, chat thread.
Seller (login + seller ownership): notifications, read, autopilot, profile, products CRUD, `GET /api/suppliers`.
Identity: `POST /api/profile`, `GET /api/me`. AI: `/api/intake/draft`, `/api/intake/transcribe`.

## 4. Auth and roles today

Supabase token checked locally (HS256 secret) or remotely (Auth server); fail-closed if unconfigured. A profile has **one** `role`. The server does **not** check roles: buyer endpoints accept any signed-in user, seller endpoints check that you own the seller record (or it is a demo seller). So "one account, two roles, server-enforced" does not exist yet.

## 5. Brief sections 3 to 9 against the repo

| § | Item | Status | Notes |
|---|---|---|---|
| 3 | Roles `buyer`+`seller` on one account | **missing** | single `role` string |
| 3 | Header role toggle | **missing** | |
| 3 | Server-side role check on every endpoint | **missing** | ownership checks only |
| 4.1 | Request: item, qty, priority | **exists** | |
| 4.1 | Need-by **date** | **partial** | stored as days |
| 4.1 | Quote window | **missing** | |
| 4.2 | Matching (exact + alias) and notifications | **exists** | |
| 4.3 | Quote by hand or catalog draft, versions | **exists** | |
| 4.4 | Anonymous quotes ("Seller 1") | **missing** (see §6) | |
| 4.5 | Reveal, quota, paywall, order handoff | **missing** | |
| 4.6 | Negotiation loop | **exists** | works on seller ids, not aliases |
| 5 | All anonymity rules and their 6 tests | **missing** (see §6) | |
| 6 | Stock → `max_qty` cap | **exists** | partial fill is an exception, split order not built |
| 6 | Priority modes + winner under every mode | **exists** | env var is `BALANCED_THRESHOLD`, brief says `BALANCED_TOLERANCE` |
| 6 | "What you give up" line | **partial** | computed in the browser from engine rows, not by the API |
| 7 | `profiles.roles` | **missing** | |
| 7 | products incl. photo_path | **partial** | no photo |
| 7 | rfqs window_ends_at, min_quotes | **missing** | |
| 7 | quotes origin | **exists** | plus `auto`; **alias** missing |
| 7 | `reveals` | **missing** | |
| 7 | notifications, decisions + input hash | **exists** | fingerprint is in the summary |
| 8 | Reveal, mock upgrade, plan/reveals-left, decline, last-order | **missing** | |
| 8 | AI draft/transcribe endpoints | **exists** | paths are `/api/intake/*`, brief says `/api/ai/*` |
| 8 | Seller verdict endpoint | **exists** | returned inside the inbox and `/assist` |
| 9 | Buyer intake, confirm card, strict schema, 8 s fallback | **exists** | |
| 9 | Voice | **exists** | uses **ElevenLabs**, brief says OpenAI transcription |
| 9 | Seller assistant + number check, item-match warn | **exists** | |
| 9 | Golden tests (15 + 8), invented values = 0 | **exists** | live run: 0 invented |
| 9 | AI logging with request id | **exists** | |
| 9 | Paste WhatsApp text / screenshot input | **missing** | |
| 11 | 1 last-order vs today | **missing** | |
| 11 | 2 savings vs spreadsheet + running total | **exists** | |
| 11 | 3 activity feed | **partial** | no "declined" |
| 11 | 4 decision one-pager | **exists** | |
| 11 | 5 live voice agent | **missing** | |
| 12, 13 | Quote windows, trust items | **missing** | |

## 6. Anonymity: measured leaks today (this is the big job)

Probed against the running API. A buyer's single `GET /api/rfqs/{id}` contains: seller ids (`A`, `B`), supplier names, **seller invite tokens** (a buyer could open the seller quote page as that seller), and the phone number and email a seller typed in notes.
Also leaking to buyers: `GET /api/rfqs/{id}/suppliers/{sid}` returns business name, city, categories and full products; the summary and the **public** share page show supplier names; chat messages carry names; the engine rows carry supplier names.
Leaking to sellers: `GET /api/rfq-by-token/{token}` and the inbox return `buyer_company`, `buyer_name` and `buyer_city`; the quote page prints the buyer's name as "Contact".
Fix needs a server-side serializer for every buyer-facing and seller-facing response, aliases stored per request, and the public share page masked until reveal. Masking must stay out of `engine.py`.

## 7. Honesty-copy problems found

- `VerifiedBadge.tsx` tier "registry" claims "Ministry of Corporate Affairs / GST ledger verified". Nothing like that is checked.
- The wizard's "Verify Now" is a 0.4 s timer, and the summary shows "Demo Registry Verified". GSTIN/PAN checks are format checks only.
- No site-wide "demo data is synthetic" marker yet (sellers and a few notes say it).
- No "customers/revenue/pilot" claims found in the UI.

## 8. Conflicts and decisions the brief needs from you

1. **Voice provider.** You told me earlier to use ElevenLabs; the brief says OpenAI transcription. Current code uses ElevenLabs.
2. **Autopilot vs human negotiation.** Rule from you: no AI/autopilot answers a target or revises a quote. The §17 demo has "a revised quote flips the winner" while sellers are on autopilot. A person has to submit that revision (using the role toggle on a two-role account).
3. **Persistence.** Brief: SQLite WAL. Today: memory. My Supabase Postgres `schema.sql` is now unused.
4. **Backend branch.** `origin/backend` (teammate) is unrelated code, has a hardcoded JWT secret in git, and conflicts with `main`. I am not merging it.
5. **Push.** 19 local commits are not on GitHub.

## 9. Risks to the 11:00 deadline

- Anonymity touches almost every endpoint and screen. It is the largest item.
- Moving the whole store to SQLite is a rewrite of `rfq_store.py`; doing it alongside masking risks breaking the demo path.
- Browser rehearsal has never been run (extension not connected); everything was tested through the API and builds.


---

# Where things stand (updated Sun 18 Oct, ~02:50 IST)

**238 API tests pass** (`cd api && python3 -m pytest -q`); the web app type-checks, lints and builds. A live HTTP rehearsal
(`real server + real HTTP`, including a server restart and the real 30-second clock) passes end to end.
Status key now: **done**, **partial**, **not built**.

## v2 brief, section by section

| § | Item | Now | Notes |
|---|---|---|---|
| 3 | Roles `buyer`+`seller`, header toggle, server-side checks | **done** | toggle only when the account holds both; every route checks the role (403 `role_required`) |
| 4 | Request → inbox → quote → anonymous compare → reveal → order | **done** | personal sample request on the empty state |
| 4.1 | Need-by **date** | **done** | date picker converts to days for the engine |
| 5 | Anonymity (6 required tests and more) | **done** | server-side `views.py`; scan of every buyer/seller response; shared page carries no identity |
| 5 | Reveal: per request+seller, idempotent, logged, repeat seller free, 3 free then 402 | **done** | mock upgrade labelled dev; no payment |
| 6 | Stock cap, priority modes, winner under every mode, what-you-give-up | **done** | `BALANCED_TOLERANCE`; crossover-at-151 now tested |
| 7 | Data model additions | **done** | roles, windows, reveals, notices, delivery, exceptions, known suppliers; photo_path **not built** |
| 8 | API additions | **mostly done** | `/api/ai/*` names added beside the older paths. Quote-by-id reveal uses the alias as id |
| 9 | Buyer intake (chat, voice), confirm card, strict schema, 8 s fallback | **done** | ElevenLabs for speech-to-text (your choice) |
| 9 | Seller assistant + number check, item-match warning | **done** | offers/promises rejected as well as wrong numbers |
| 9 | Golden tests (15 + 8), invented values = 0 | **done** | live model: 0 invented |
| 9 | Paste WhatsApp **text** | **done** | screenshots **not built** |
| 11.1 | Last order vs today | **done** | labelled synthetic history; your own last order replaces it |
| 11.2 | Savings vs spreadsheet + running total | **done** | "on demo data" |
| 11.3 | Seller activity feed incl. declined | **done** | |
| 11.4 | Decision one-pager | **done** | evidence table, JSON download, share link, delivery outcome |
| 11.5 | Live voice agent | **not built** | needs a decision, see below |
| 12 | Quote windows, notifications, reminders, injectable clock | **done** | in-app bell; email not built; demo timing via `DEMO_WINDOW_MINUTES` |
| 13 | Trust items | **partial** | delivery record + pay-on-delivery label done. "Talk to us" and a "checked by Crossover" badge deliberately **not built** (no one to staff them; the badge would claim an inspection nobody performs) |
| 14 | Honesty copy | **done** | badges say what was checked; wizard registry step is labelled simulated; site-wide synthetic marker; no customer/revenue/pilot wording |

## Beyond the v2 brief (from the problem statement and the team brief)

Exception dialog with written reason + named approver (blank refused); spreadsheet mode that shows the naive pick and the rupee
difference; observed / derived / assumed tags; cash tied up in extra units and cost per usable unit; **GST normalisation** (the
brief's worked example is a test); **CSV and JSON import** with row-level errors; SQLite (WAL) persistence with a reset script.

## Decisions made on your behalf (all reversible)

1. Kept our API as the base; the teammate's `origin/backend` is not merged (different data model, no landed-cost fields, a published JWT secret).
2. After a window closes, new sellers cannot start a quote but sellers who already quoted can still revise, so the negotiation loop survives.
3. Negotiation stays human: a pending target stops autopilot; a named person sends targets and seller revisions are manual.
4. Removed the QR / invite-link screen: buyers never receive seller invite links (they would let a buyer act as the seller).
5. The shared demo request is gone. Reveals and quotas are per buyer, so every sample request belongs to one buyer.

## Open items that need a person

1. **Rotate the Supabase JWT secret.** The one in `api/.env` is the value published in the teammate's repo. The app now ignores it by hash and asks Supabase to verify logins, but the secret must still be rotated (Project Settings → JWT Keys).
2. **Push.** Local commits are ahead of `origin/main`; nothing is pushed since the earlier approved push.
3. **Browser rehearsal.** Never run in a real browser (the Chrome extension was not connected). Everything was verified through the API, type-checks, builds and a live HTTP run. Please click through the demo path once.
4. **Live voice agent** would need the ElevenLabs agents SDK (a new dependency) and an agent created in your ElevenLabs account. Not started.
5. Real-model speed varies (2 to 7 seconds). The 8 s limit means an occasional intake call falls back to the form.
6. The teammate's branch has committed `node_modules`, a database file and the leaked secret; ask them to clean it before merging anything.
