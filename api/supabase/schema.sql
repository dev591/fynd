-- Crossover schema for Supabase (Postgres).
-- Run once: Supabase dashboard -> SQL Editor -> New query -> paste all of this -> Run.
-- Safe to run again: every statement is idempotent.
--
-- Security model: Row Level Security is ON for every table. The API (server side) reads and writes with the
-- service_role key, which bypasses RLS. Browsers only ever get the policies below: read your own rows, nothing else.
-- Invite tokens, share links and the AI log have no client access at all.

create extension if not exists pgcrypto;

-- ─── Profiles: one per login ────────────────────────────────────────────────
create table if not exists public.profiles (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  role       text not null check (role in ('buyer', 'supplier')),
  data       jsonb not null,                       -- wizard profile; the PAN is stored masked only
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ─── Sellers (synthetic demo sellers A..J and real sellers, whose id is their user id) ──
create table if not exists public.sellers (
  supplier_id       text primary key,
  owner_id          uuid references auth.users(id) on delete cascade,   -- null = synthetic demo seller
  business_name     text not null,
  location_city     text not null default '',
  location_state    text not null default '',
  categories        text[] not null default '{}',
  description       text,
  verification_tier text not null default 'none' check (verification_tier in ('none', 'email', 'tax_ids', 'registry')),
  synthetic         boolean not null default true,
  autopilot_enabled boolean not null default false,                      -- off by default
  created_at        timestamptz not null default now()
);
create unique index if not exists sellers_owner_uidx on public.sellers (owner_id) where owner_id is not null;

-- ─── Catalog ────────────────────────────────────────────────────────────────
create table if not exists public.products (
  id              text primary key,
  supplier_id     text not null references public.sellers(supplier_id) on delete cascade,
  name            text not null,
  category        text not null default 'general',
  aliases         text[] not null default '{}',                          -- other names buyers use; matching is exact name or alias
  pack_price      numeric(12, 2) not null check (pack_price >= 0),
  pack_size       integer not null check (pack_size > 0),
  moq             integer not null default 1 check (moq > 0),
  usual_lead_days integer not null default 3 check (usual_lead_days >= 0),
  capacity_cap    integer check (capacity_cap is null or capacity_cap >= 0),
  unit            text not null default 'pc',
  stock           integer check (stock is null or stock >= 0),           -- a snapshot, not reserved
  freight         numeric(12, 2) not null default 0 check (freight >= 0),
  price_breaks    jsonb not null default '[]',                           -- [{"min_qty": 100, "pack_price": 8}]
  created_at      timestamptz not null default now()
);
create index if not exists products_supplier_idx on public.products (supplier_id);

-- ─── Requests ───────────────────────────────────────────────────────────────
create table if not exists public.rfqs (
  id            text primary key,
  owner_id      uuid references auth.users(id) on delete set null,       -- null = the shared demo request
  primary_token text not null,
  item          text not null,
  qty           integer not null check (qty > 0),
  need_in_days  integer not null check (need_in_days > 0),
  buyer_company text not null,
  buyer_name    text not null,
  buyer_city    text not null default '',
  buyer_state   text not null default '',
  note          text,
  priority_mode text not null default 'cheapest' check (priority_mode in ('cheapest', 'fastest', 'balanced')),
  source        text not null default 'form' check (source in ('form', 'chat', 'voice')),
  status        text not null default 'Open' check (status in ('Open', 'Decided', 'Closed')),
  decision      jsonb,                                                   -- winner, reason, named approver, AI calls
  created_at    timestamptz not null default now()
);
create index if not exists rfqs_owner_idx on public.rfqs (owner_id, created_at desc);

-- One unguessable invite token per matched seller. Suppliers quote through these without logging in.
create table if not exists public.rfq_invites (
  token       text primary key,
  rfq_id      text not null references public.rfqs(id) on delete cascade,
  supplier_id text not null references public.sellers(supplier_id) on delete cascade,
  created_at  timestamptz not null default now(),
  unique (rfq_id, supplier_id)
);

-- ─── Quotes: every revision is kept (v1, v2, ...) ───────────────────────────
create table if not exists public.quotes (
  id            uuid primary key default gen_random_uuid(),
  rfq_id        text not null references public.rfqs(id) on delete cascade,
  supplier_id   text not null references public.sellers(supplier_id) on delete cascade,
  version       integer not null check (version > 0),
  supplier_name text not null,
  pack_price    numeric(12, 2) not null check (pack_price >= 0),
  pack_size     integer not null check (pack_size > 0),
  freight       numeric(12, 2) not null default 0 check (freight >= 0),
  lead_days     integer not null check (lead_days >= 0),
  moq           integer,
  max_qty       integer,                                                 -- stock cap; below the need it becomes a partial fill
  notes         text,
  origin        text not null default 'manual' check (origin in ('manual', 'ai_draft_edited', 'ai_draft_sent', 'auto')),
  landed_cost   numeric(14, 2) not null,                                 -- computed by the rules engine, never by AI
  units         integer not null,
  packs         integer not null,
  submitted_at  timestamptz not null default now(),
  unique (rfq_id, supplier_id, version)
);
create index if not exists quotes_rfq_idx on public.quotes (rfq_id, supplier_id, version);

-- ─── Negotiation: a named person sends every target ─────────────────────────
create table if not exists public.targets (
  id              text primary key,
  rfq_id          text not null references public.rfqs(id) on delete cascade,
  supplier_id     text not null references public.sellers(supplier_id) on delete cascade,
  message         text not null,
  cut_needed      numeric(12, 2) not null,
  target_freight  numeric(12, 2),
  target_per_unit numeric(12, 2),
  concession_type text not null check (concession_type in ('freight', 'unit_price')),
  sent_by         text not null check (length(btrim(sent_by)) > 0),
  status          text not null default 'pending' check (status in ('pending', 'accepted', 'declined')),
  sent_at         timestamptz not null default now()
);
create index if not exists targets_rfq_idx on public.targets (rfq_id, supplier_id, sent_at desc);

create table if not exists public.messages (
  id          text primary key,
  rfq_id      text not null references public.rfqs(id) on delete cascade,
  supplier_id text not null references public.sellers(supplier_id) on delete cascade,
  sender      text not null check (sender in ('buyer', 'supplier')),
  sender_name text not null,
  body        text not null,
  target_id   text references public.targets(id) on delete set null,
  created_at  timestamptz not null default now()
);
create index if not exists messages_thread_idx on public.messages (rfq_id, supplier_id, created_at);

-- ─── Seller inbox ───────────────────────────────────────────────────────────
create table if not exists public.notifications (
  id          text primary key,
  rfq_id      text not null references public.rfqs(id) on delete cascade,
  supplier_id text not null references public.sellers(supplier_id) on delete cascade,
  product_id  text not null references public.products(id) on delete cascade,
  token       text not null,
  status      text not null default 'new' check (status in ('new', 'viewed', 'quoting')),
  created_at  timestamptz not null default now(),
  unique (rfq_id, supplier_id)                                           -- one notification per stocking seller
);
create index if not exists notifications_supplier_idx on public.notifications (supplier_id, created_at desc);

-- ─── Share links (created only by an explicit click) and the AI call log ────
create table if not exists public.shares (
  token      text primary key,                                           -- unguessable, read-only link to a decision one-pager
  rfq_id     text not null unique references public.rfqs(id) on delete cascade,
  created_at timestamptz not null default now()
);

create table if not exists public.ai_log (
  id         bigint generated always as identity primary key,
  request_id text not null,
  kind       text not null,                                              -- intake_draft, transcribe, seller_assist, item_match
  rfq_id     text references public.rfqs(id) on delete cascade,
  input      jsonb not null default '{}',
  output     jsonb not null default '{}',
  at         timestamptz not null default now()
);
create index if not exists ai_log_rfq_idx on public.ai_log (rfq_id);

-- ─── Keep updated_at honest ─────────────────────────────────────────────────
create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;
drop trigger if exists profiles_touch on public.profiles;
create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

-- ─── Row Level Security ─────────────────────────────────────────────────────
alter table public.profiles      enable row level security;
alter table public.sellers       enable row level security;
alter table public.products      enable row level security;
alter table public.rfqs          enable row level security;
alter table public.rfq_invites   enable row level security;
alter table public.quotes        enable row level security;
alter table public.targets       enable row level security;
alter table public.messages      enable row level security;
alter table public.notifications enable row level security;
alter table public.shares        enable row level security;
alter table public.ai_log        enable row level security;

-- Signed-out visitors (the anon key) get nothing, anywhere.
revoke all on all tables in schema public from anon;

-- Signed-in users get read-only access to their own rows. All writes go through the API (service_role).
drop policy if exists profiles_own_read on public.profiles;
create policy profiles_own_read on public.profiles for select to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists sellers_read on public.sellers;
create policy sellers_read on public.sellers for select to authenticated
  using (owner_id = (select auth.uid()) or owner_id is null);            -- own seller record + synthetic demo sellers

drop policy if exists products_read on public.products;
create policy products_read on public.products for select to authenticated
  using (exists (select 1 from public.sellers s
                 where s.supplier_id = products.supplier_id
                   and (s.owner_id = (select auth.uid()) or s.owner_id is null)));

drop policy if exists rfqs_owner_read on public.rfqs;
create policy rfqs_owner_read on public.rfqs for select to authenticated
  using (owner_id = (select auth.uid()) or owner_id is null);            -- your requests + the shared demo request

drop policy if exists quotes_read on public.quotes;
create policy quotes_read on public.quotes for select to authenticated
  using (exists (select 1 from public.rfqs r where r.id = quotes.rfq_id and r.owner_id = (select auth.uid()))
      or exists (select 1 from public.sellers s where s.supplier_id = quotes.supplier_id and s.owner_id = (select auth.uid())));

drop policy if exists targets_read on public.targets;
create policy targets_read on public.targets for select to authenticated
  using (exists (select 1 from public.rfqs r where r.id = targets.rfq_id and r.owner_id = (select auth.uid()))
      or exists (select 1 from public.sellers s where s.supplier_id = targets.supplier_id and s.owner_id = (select auth.uid())));

drop policy if exists messages_read on public.messages;
create policy messages_read on public.messages for select to authenticated
  using (exists (select 1 from public.rfqs r where r.id = messages.rfq_id and r.owner_id = (select auth.uid()))
      or exists (select 1 from public.sellers s where s.supplier_id = messages.supplier_id and s.owner_id = (select auth.uid())));

drop policy if exists notifications_read on public.notifications;
create policy notifications_read on public.notifications for select to authenticated
  using (exists (select 1 from public.sellers s where s.supplier_id = notifications.supplier_id and s.owner_id = (select auth.uid())));

-- rfq_invites, shares and ai_log: RLS on, no policy = no client access. Only the API can touch them.
