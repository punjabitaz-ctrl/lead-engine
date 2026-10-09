-- Click / visit log for the lead engine. Written only by the lead-tracker edge function (service role).
create table if not exists public.lead_events (
  id bigint generated always as identity primary key,
  ts timestamptz not null default now(),
  lead_key text not null check (char_length(lead_key) between 1 and 200),
  event text not null check (event in ('link_click', 'page_view', 'form_submit')),
  path text check (path is null or char_length(path) <= 300),
  target text check (target is null or char_length(target) <= 500),
  is_bot boolean not null default false,
  ua text check (ua is null or char_length(ua) <= 300)
);

create index if not exists lead_events_ts_idx on public.lead_events (ts);
create index if not exists lead_events_lead_idx on public.lead_events (lead_key, ts);

-- RLS on with no policies: the public (anon) key can neither read nor write. Only the service role can.
alter table public.lead_events enable row level security;
