# Brief for Kiro: live voice agent for buyer requests

You are adding ONE feature to Crossover (repo root `/Volumes/dev/fynd`, GitHub `dev591/fynd`): a real-time voice agent the
buyer can talk to, which asks for anything missing and fills the request. Read this whole file first, then `README.md`,
`DEPLOY.md`, `app/DISCLOSURE.md` and `api/app/intake.py`.

## What already exists (do not break or replace)
- Buyer voice input: tap the mic, ElevenLabs speech-to-text, OpenAI reads it, a confirm card appears, the buyer presses Confirm.
  Files: `app/src/dashboard/IntakePanel.tsx`, `api/app/intake.py`, routes `/api/intake/draft`, `/api/intake/transcribe`,
  `/api/rfqs/confirm` in `api/app/main.py`.
- Seller side: silent OS notifications for new requests and a voice quote bar (`app/src/supplier/hooks/useVoiceAlerts.ts`,
  `VoiceQuoteBar.tsx`). The owner decided there is NO speech output on the seller side. Leave it exactly as it is.
- The rules engine (`api/app/engine.py`, `tax.py`) decides every number. AI only talks. A person confirms every step.
- 320 backend tests (`cd api && python3 -m pytest -q`) and a clean `cd app && npx tsc -b && npm run lint && npm run build`.

## The feature
A "Talk to Crossover" button on the New request page (`app/src/dashboard/NewRequestForm.tsx`, next to `IntakePanel`).
Flow:
1. Buyer taps it and allows the microphone. An ElevenLabs Conversational AI agent greets them and asks what they need.
2. The agent asks for what is missing (item, quantity, need-by date, priority cheapest/fastest/balanced) and may ask short
   follow-ups. It answers out loud in short sentences. English and Hinglish.
3. When it has enough, the agent calls a client tool `propose_request` with the fields. The browser sends those fields plus
   the buyer's spoken turns to our server. The server verifies and returns a draft. The existing confirm card appears,
   prefilled. The agent says "Check the card on screen and press Confirm."
4. The buyer presses Confirm on screen. Only that button creates the request (existing `/api/rfqs/confirm`).
   THE AGENT NEVER CREATES, SENDS OR CHANGES A REQUEST BY ITSELF.

## Hard rules
- The agent has no price, supplier or stock data and must never state one. It must not promise anything ("you will get a
  quote in 5 minutes", discounts, guarantees).
- Invented-value guard (same principle as `intake.py`): every number or date the agent proposes must be supported by what the
  buyer actually said. The browser sends the buyer's transcribed turns with the tool call; the server runs the existing
  checks (`numbers_in_text`, `resolve_need_days`, `snap_item`, `build_draft`) against those turns and drops anything unsupported
  with a warning. Never trust the agent's arguments directly.
- Do not touch `api/app/engine.py`, `tax.py`, `views.py`, `masking.py` or the anonymity behaviour.
- Keys only in environment variables, never in code, logs or the browser. The browser must never see `ELEVENLABS_API_KEY`;
  it gets a short-lived signed URL from our server.
- Everything optional and flagged: with no `ELEVENLABS_AGENT_ID` (or no key) the button does not render and the app behaves
  exactly as today. If the connection drops, show "Voice agent unavailable, use the mic or the form" and keep the form working.
- Needs https or localhost for the microphone (the deployment already serves https).
- No new libraries without asking the owner. Preferred: ElevenLabs' official `@elevenlabs/client` (MIT) because it handles audio
  capture and playback; ask the owner to approve it before installing, then log it in `app/DISCLOSURE.md`. If not approved,
  use the raw WebSocket protocol from the current ElevenLabs docs (read them first; do not rely on memory).

## Backend (`api/app/`)
- New file `voice_agent.py`:
  - `enabled()` is true only if `ELEVENLABS_API_KEY` and `ELEVENLABS_AGENT_ID` are set.
  - `signed_url()` calls ElevenLabs "get signed URL" for the agent with httpx (same style as `ai.py`: timeout, return None on
    any failure, never raise to the caller).
  - `verify(fields, user_turns, catalog_names, today)` reuses `intake.build_draft` so the guard is identical to typed intake.
- Routes in `main.py` (all `buyer_only`):
  - `GET /api/voice-agent/status` returns `{"enabled": bool}`.
  - `GET /api/voice-agent/session` returns `{"signed_url": "..."}` or 503 with a plain message.
  - `POST /api/voice-agent/draft` takes `{ "fields": {...}, "user_turns": ["..."] }`, returns the same draft shape as
    `/api/intake/draft` so the existing confirm card can render it. Log with `store.log_ai("voice_agent_draft", rid, inp, out)`.
- Add `ELEVENLABS_AGENT_ID=` to `api/.env.example` and `render.yaml`, and a line in `DEPLOY.md`.
- Tests in `api/tests/test_voice_agent.py` with a fake httpx (no network): disabled without keys; signed URL passes the key in
  a header and never returns it; `verify` drops a quantity the buyer never said; drops a deadline the buyer never said; resolves
  "by Friday" in code; unknown item gets a warning, not a guess; route needs the buyer role (a seller gets 403); the agent
  cannot create a request (no route does that).

## Frontend (`app/src/`)
- `app/src/dashboard/VoiceAgentPanel.tsx`: the button, connection states (idle, connecting, listening, speaking, error), a live
  transcript line, a "Stop" button. On `propose_request` it calls `/api/voice-agent/draft` with the fields and the user turns,
  then hands the draft to the same confirm-card state `IntakePanel` already uses. Reuse, do not duplicate, that confirm card
  (extract it into a shared component if needed, without changing its behaviour).
- Respect `prefers-reduced-motion`; show a visible state so nobody wonders if the mic is live; end the session when the
  panel unmounts or the user leaves the page.
- Add `getVoiceAgentStatus`, `getVoiceAgentSession`, `draftFromVoiceAgent` to `app/src/api/client.ts`.
- Match the surrounding code style (Tailwind tokens, `label`, `display`, comment density).

## ElevenLabs dashboard setup (the owner does this once; write the exact steps in DEPLOY.md)
1. Create an agent. Voice: any warm clear voice that handles Indian English. Language: English with Hindi/Hinglish allowed.
2. System prompt (paste as is):
   "You are the intake assistant for Crossover, a request-and-quote desk for small manufacturers in India. Your only job is to
   help a buyer describe what they need: the item, the quantity, when they need it by, and whether they prefer the cheapest,
   the fastest or a balance. Ask one short question at a time, only for what is missing. Keep every reply under two short
   sentences. Never mention prices, suppliers, stock or delivery promises, and never say a request has been sent. When you have
   the item and quantity (the date and priority are optional), call propose_request with exactly what the buyer said, using
   the buyer's own words for the deadline. Then say: 'Please check the card on screen and press Confirm.' If the buyer says
   something unrelated, politely steer back to their request."
3. Client tool `propose_request` with parameters: `item` (string), `quantity` (number), `need_by_phrase` (string, optional, the
   buyer's own words), `priority` (one of cheapest, fastest, balanced, optional), `note` (string, optional).
4. First message: "Hi, what do you need to order today?"
5. Put the agent id in `ELEVENLABS_AGENT_ID`.

## Acceptance (all must hold)
- `cd api && python3 -m pytest -q` passes (320 existing + yours). `cd app && npx tsc -b && npm run lint && npm run build` clean.
- With no `ELEVENLABS_AGENT_ID` the New request page is identical to today.
- A buyer can say "I need a hundred M10 bolts by Friday, fastest", hear the agent confirm, see the prefilled card, press Confirm,
  and get a normal request. A quantity or date the buyer never said never reaches the card.
- No speech output was added on the seller side. The existing mic button, form and silent notifications still work.
- README (AI table, "Not built" list), `DEPLOY.md` and `app/DISCLOSURE.md` are updated honestly: say that the agent is tested
  with fake replies unless it was run against the real service, and say what was run live.

## Working rules
One small commit per step, tests before and after, run the suite before every commit (use `&&`, never `;`, so a failing test
stops the commit). Do not print or commit secrets. If anything here is ambiguous or a decision is the owner's, ask instead of
guessing. Time-box: about 2 to 3 hours. If late, cut in this order: live transcript line, error polish, Hinglish tuning.
Never cut: the invented-value guard, the confirm card, the fallback to the form.
