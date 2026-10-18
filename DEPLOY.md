# Deploying Crossover to one public address

The API serves the built website, so there is one URL, https from the host (needed for the microphone and browser
notifications), no CORS and no second server. Supabase Auth is already hosted, so nothing to deploy there.

## Option A: Render (blueprint included)
1. Push the repo to GitHub, then in Render choose New > Blueprint and pick the repo. It reads `render.yaml`.
2. Fill the secret values in the dashboard (names below). `VITE_*` values are public and only used at build time.
3. Open the URL Render gives you. `/health` should say ok.

## Option B: website on Vercel, API on Railway (two addresses)
The website is static and the API is one process, so they can live on separate hosts. Both are https, which the microphone
and browser notifications need. Because they are different origins, the API must be told which website may call it.

**1. API on Railway** (deploy this first, you need its URL for step 2)
1. New Project > Deploy from GitHub repo, pick this repo, and set **Root Directory** to `api`. Railway reads
   `api/Dockerfile` and `api/railway.json` (health check `/health`).
2. **Add a Volume** to the service, mount path `/data`. Without it SQLite is wiped on every redeploy.
3. Variables: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `OPENAI_API_KEY`, `MODEL_FAST`, `ELEVENLABS_API_KEY`,
   `ELEVENLABS_STT_MODEL=scribe_v2`, `DEMO_AUTOPILOT=off`, `DEMO_LOGINS=off`, `FREE_REVEALS=3`, and
   `CORS_ORIGINS=https://<your-vercel-domain>` (set after step 2; no trailing slash, comma-separate extra domains).
4. Settings > Networking > **Generate Domain**. Open `https://<railway-domain>/health`: it should say ok.
5. Keep **one replica** (state is in memory with SQLite write-through).

**2. Website on Vercel**
1. Add New Project, import this repo, set **Root Directory** to `app`. Vercel reads `app/vercel.json` (Vite build, and every
   route falls back to `index.html` so `/app`, `/supplier` and `/share/...` work on refresh).
2. Environment variables (all public, baked in at build time): `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`,
   `VITE_API_URL=https://<railway-domain>` (no trailing slash).
3. Deploy, then put the Vercel domain into Railway's `CORS_ORIGINS` and redeploy the API. Preview URLs are different
   origins, so add them to `CORS_ORIGINS` only if you need to test on them.

**3. Supabase** > Authentication > URL Configuration: set Site URL to the Vercel domain. Turn off "Confirm email" for the demo.

If the page loads but every call fails with a CORS error in the browser console, `CORS_ORIGINS` does not match the exact
Vercel address. If requests go to the wrong host, `VITE_API_URL` was missing at build time: set it and redeploy.

## Any Docker host (Fly.io, Railway, a VPS)
`docker build --build-arg VITE_SUPABASE_URL=... --build-arg VITE_SUPABASE_ANON_KEY=... -t crossover .`
`docker run -p 8000:8000 --env-file api/.env -v crossover-data:/data crossover`

## Environment (server)
`SUPABASE_URL`, `SUPABASE_ANON_KEY` (logins are checked against Supabase), `OPENAI_API_KEY`, `MODEL_FAST`,
`ELEVENLABS_API_KEY`, `ELEVENLABS_STT_MODEL`. Optional: `SUPABASE_JWT_SECRET` (a ROTATED one), `DEMO_AUTOPILOT` (off for a
real two-laptop demo), `FREE_REVEALS`, `DELHIVERY_TOKEN`. See `api/.env.example`.

## Keep data across restarts: Supabase
1. In Supabase, SQL Editor -> paste `api/supabase/state.sql` -> Run. It creates `crossover_state` with row level security
   on and no policies, so only the server can touch it.
2. In Render, set `SUPABASE_SERVICE_ROLE_KEY` (Supabase -> Project Settings -> API -> service_role) and
   `PERSIST_BACKEND=supabase` (the blueprint already sets this). Never put the service_role key in the app or a browser.
3. Redeploy. Check `/health`: `persistence.backend` should say `supabase` and `saves` should rise as you use the app. If you create the table
   after the server started, it notices within about 30 seconds and starts saving (it never overwrites earlier saved data; in that case restart).
   The log shows nothing special on success. If Supabase cannot be reached at start, the API says so in the log
   and runs WITHOUT saving, so it never overwrites saved data with the seed; fix it and restart.
4. To start over: on your laptop, with `PERSIST_BACKEND=supabase` and the service key in `api/.env`, run
   `python3 -m app.reset`. That empties the table; the next start seeds fresh demo data.

## Payments (Razorpay test mode)
1. In Render, set `RAZORPAY_KEY_ID` (starts `rzp_test_`) and `RAZORPAY_KEY_SECRET`; use the same test keys as the team's Razorpay
   project. They go in Render only. The secret never reaches the browser, and a `rzp_live_` key is refused unless
   `RAZORPAY_ALLOW_LIVE=true`.
2. Redeploy. `/api/payments/config` should now say `"mode": "test"`.
3. Test with card `4111 1111 1111 1111`, any future expiry and CVV, or UPI `success@razorpay`. No real money moves.
4. What is paid for: reveal bundles (1 to 50 reveals, ₹79 to ₹2,699) on `/app/pricing`, and an optional 50% advance on an
   order at `/app/pay/<request id>`. Cash on delivery needs no Razorpay.

## Things to know
- **Without the Supabase step, data lives in SQLite at `/data/app.db`,** and a free tier wipes it on every restart.
- **Demo seller logins** (`DEMO_LOGINS=on`) hand a shared password to anyone who opens `/signin`. Turn it on only for the
  demo window, then off again.
- **Seed the ten demo sellers against the public API:**
  `cd api && API_URL=https://<your-url> python3 scripts/seed_demo_sellers.py` (needs `DEMO_SELLER_PASSWORD`,
  `SUPABASE_URL`, `SUPABASE_ANON_KEY` in `api/.env`; "Confirm email" off in Supabase, or `SUPABASE_SERVICE_ROLE_KEY`).
- **Free tiers sleep.** The first request after idle can take 30 to 60 seconds. Open the site once before judges do.
- One uvicorn process only (state is in memory with SQLite write-through).
