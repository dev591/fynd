-- Crossover saved state, one row per collection (the API's write-through store).
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run.
create table if not exists public.crossover_state (
  name     text primary key,
  value    text not null,
  saved_at double precision not null
);

-- Row level security on with no policies: browsers (anon key) can neither read nor write it.
-- Only the API, using the service_role key on the server, can.
alter table public.crossover_state enable row level security;
