# Deploying Crossover to one public address

The API serves the built website, so there is one URL, https from the host (needed for the microphone and browser
notifications), no CORS and no second server. Supabase Auth is already hosted, so nothing to deploy there.

## Option A: Render (blueprint included)
1. Push the repo to GitHub, then in Render choose New > Blueprint and pick the repo. It reads `render.yaml`.
2. Fill the secret values in the dashboard (names below). `VITE_*` values are public and only used at build time.
3. Open the URL Render gives you. `/health` should say ok.

## Any Docker host (Fly.io, Railway, a VPS)
`docker build --build-arg VITE_SUPABASE_URL=... --build-arg VITE_SUPABASE_ANON_KEY=... -t crossover .`
`docker run -p 8000:8000 --env-file api/.env -v crossover-data:/data crossover`

## Environment (server)
`SUPABASE_URL`, `SUPABASE_ANON_KEY` (logins are checked against Supabase), `OPENAI_API_KEY`, `MODEL_FAST`,
`ELEVENLABS_API_KEY`, `ELEVENLABS_STT_MODEL`. Optional: `SUPABASE_JWT_SECRET` (a ROTATED one), `DEMO_AUTOPILOT` (off for a
real two-laptop demo), `FREE_REVEALS`, `DELHIVERY_TOKEN`. See `api/.env.example`.

## Things to know
- **Data lives in SQLite at `/data/app.db`.** Without a persistent disk, every redeploy or restart on a free tier wipes it.
  Re-run the seed script after a wipe. Everything else is recreated by using the app.
- **Demo seller logins** (`DEMO_LOGINS=on`) hand a shared password to anyone who opens `/signin`. Turn it on only for the
  demo window, then off again.
- **Seed the ten demo sellers against the public API:**
  `cd api && API_URL=https://<your-url> python3 scripts/seed_demo_sellers.py` (needs `DEMO_SELLER_PASSWORD`,
  `SUPABASE_URL`, `SUPABASE_ANON_KEY` in `api/.env`; "Confirm email" off in Supabase, or `SUPABASE_SERVICE_ROLE_KEY`).
- **Free tiers sleep.** The first request after idle can take 30 to 60 seconds. Open the site once before judges do.
- One uvicorn process only (state is in memory with SQLite write-through).
