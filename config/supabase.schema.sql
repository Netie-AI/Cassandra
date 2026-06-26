-- CASSANDRA — Supabase schema (paste in SQL Editor → Run once)
-- Pairs with src/db/supabase_client.py and api/auth.py JWT wiring (PARKING_LOT P9)

-- Profiles: one row per auth.users id (Supabase Auth handles passwords)
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  display_name text,
  tier text not null default 'free'
    check (tier in ('free', 'report', 'briefing', 'agent')),
  referral_code text unique,
  locale text default 'en',
  timezone text default 'Asia/Kuala_Lumpur',
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Subscriptions (Stripe / Billplz / Airwallex webhook writes here)
create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  provider text not null check (provider in ('stripe', 'billplz', 'airwallex')),
  external_id text not null,
  tier text not null check (tier in ('report', 'briefing', 'agent')),
  status text not null default 'active'
    check (status in ('trialing', 'active', 'past_due', 'canceled')),
  trial_ends_at timestamptz,
  renews_at timestamptz,
  created_at timestamptz not null default now(),
  unique (provider, external_id)
);

-- Per-user watchlist (replaces SQLite watchlists when SUPABASE_URL is set)
create table if not exists public.watchlists (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  tickers text[] not null default array['LEU','NVDA','MSFT','AMZN','TSM'],
  updated_at timestamptz not null default now()
);

-- Newsletter / edition sends (audit + open tracking)
create table if not exists public.report_sends (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  email text not null,
  asof date not null,
  lang text not null default 'en',
  tier text not null default 'free',
  provider text not null default 'resend',
  external_id text,
  sent_at timestamptz not null default now(),
  opened_at timestamptz,
  unique (email, asof, lang)
);

-- Pipeline run log (laptop → office handoff)
create table if not exists public.pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  asof date not null,
  slot text,
  crs real,
  coverage real,
  status text not null check (status in ('started', 'ok', 'failed', 'published')),
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists idx_report_sends_asof on public.report_sends(asof desc);
create index if not exists idx_pipeline_runs_asof on public.pipeline_runs(asof desc);

-- RLS: enable when wiring auth (service role bypasses for pipeline worker)
alter table public.profiles enable row level security;
alter table public.watchlists enable row level security;
alter table public.subscriptions enable row level security;

create policy "profiles_select_own" on public.profiles
  for select using (auth.uid() = id);

create policy "watchlists_all_own" on public.watchlists
  for all using (auth.uid() = user_id);

create policy "subscriptions_select_own" on public.subscriptions
  for select using (auth.uid() = user_id);

-- Auto-create profile row when Supabase Auth registers a user
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, tier)
  values (new.id, coalesce(new.email, ''), 'free')
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
