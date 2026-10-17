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
