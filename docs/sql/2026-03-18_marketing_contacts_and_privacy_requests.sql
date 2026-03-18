-- Simple marketing source of truth for tenant-scoped campaigns.
-- Adds:
--   1) public_privacy_requests: canonical privacy / unsubscribe ledger expected by the app
--   2) marketing_contacts: current marketing state per contact per client_id
--
-- NOTE:
-- contactame and newsletter_subscribers do not have client_id in the current schema.
-- They are intentionally excluded from the tenant-scoped backfill below.
-- If you want Evolvian's own public leads in this same model, map them manually to a
-- dedicated internal client_id in a separate script.

begin;

create table if not exists public.public_privacy_requests (
  id uuid primary key default gen_random_uuid(),
  client_id uuid null references public.clients(id) on delete set null,
  name text null,
  email text not null,
  request_type text not null,
  details text null,
  language text not null default 'en',
  consent_version text not null default '2026-02',
  source text not null default 'public_page',
  status text not null default 'pending',
  ip_address text null,
  user_agent text null,
  created_at timestamptz not null default now(),
  constraint public_privacy_requests_request_type_chk
    check (request_type in ('access', 'delete', 'correct', 'opt_out_sale_share', 'marketing_opt_out')),
  constraint public_privacy_requests_language_chk
    check (language in ('en', 'es')),
  constraint public_privacy_requests_status_chk
    check (status in ('pending', 'verification_required', 'verified', 'in_progress', 'fulfilled', 'denied', 'withdrawn'))
);

create index if not exists idx_public_privacy_requests_client_email_type_created
  on public.public_privacy_requests (client_id, email, request_type, created_at desc);

create index if not exists idx_public_privacy_requests_email_type_created
  on public.public_privacy_requests (email, request_type, created_at desc);

create index if not exists idx_public_privacy_requests_status_created
  on public.public_privacy_requests (status, created_at desc);

alter table if exists public.public_privacy_requests enable row level security;

-- Backfill older privacy unsubscribe fallback rows that were stored in contactame.
insert into public.public_privacy_requests (
  client_id,
  name,
  email,
  request_type,
  details,
  language,
  consent_version,
  source,
  status,
  ip_address,
  user_agent,
  created_at
)
select
  nullif((regexp_match(coalesce(c.message, ''), 'Client ID:\s*([0-9a-fA-F-]{8,36})'))[1], '')::uuid as client_id,
  c.name,
  lower(trim(c.email)) as email,
  case
    when c.source = 'privacy_unsubscribe_fallback' then 'marketing_opt_out'
    when lower(coalesce((regexp_match(coalesce(c.message, ''), 'Privacy request type:\s*([a-z_]+)'))[1], '')) in
      ('access', 'delete', 'correct', 'opt_out_sale_share', 'marketing_opt_out')
      then lower((regexp_match(coalesce(c.message, ''), 'Privacy request type:\s*([a-z_]+)'))[1])
    else 'access'
  end as request_type,
  c.message as details,
  case
    when lower(coalesce((regexp_match(coalesce(c.message, ''), 'Language:\s*([a-z]{2})'))[1], '')) in ('en', 'es')
      then lower((regexp_match(coalesce(c.message, ''), 'Language:\s*([a-z]{2})'))[1])
    else 'en'
  end as language,
  '2026-02' as consent_version,
  c.source,
  'pending' as status,
  c.ip_address,
  c.user_agent,
  c.created_at
from public.contactame c
where c.source in ('privacy_request', 'privacy_unsubscribe_fallback')
  and lower(trim(coalesce(c.email, ''))) <> ''
  and not exists (
    select 1
    from public.public_privacy_requests p
    where lower(trim(p.email)) = lower(trim(c.email))
      and p.source = c.source
      and p.created_at = c.created_at
  );

create table if not exists public.marketing_contacts (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  name text null,
  email text null,
  normalized_email text null,
  phone text null,
  normalized_phone text null,
  email_opt_in boolean not null default false,
  whatsapp_opt_in boolean not null default false,
  email_unsubscribed boolean not null default false,
  whatsapp_unsubscribed boolean not null default false,
  interest_status text not null default 'unknown',
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint marketing_contacts_interest_status_chk
    check (interest_status in ('interested', 'not_interested', 'unknown')),
  constraint marketing_contacts_identity_chk
    check (normalized_email is not null or normalized_phone is not null)
);

create unique index if not exists ux_marketing_contacts_client_email
  on public.marketing_contacts (client_id, normalized_email);

create unique index if not exists ux_marketing_contacts_client_phone
  on public.marketing_contacts (client_id, normalized_phone);

create index if not exists idx_marketing_contacts_client_email_status
  on public.marketing_contacts (client_id, email_opt_in, email_unsubscribed, interest_status);

create index if not exists idx_marketing_contacts_client_whatsapp_status
  on public.marketing_contacts (client_id, whatsapp_opt_in, whatsapp_unsubscribed, interest_status);

create index if not exists idx_marketing_contacts_client_last_seen
  on public.marketing_contacts (client_id, last_seen_at desc);

alter table if exists public.marketing_contacts enable row level security;

with seed_rows as (
  select
    wc.client_id,
    null::text as name,
    nullif(lower(trim(coalesce(wc.email, ''))), '') as email,
    nullif(lower(trim(coalesce(wc.email, ''))), '') as normalized_email,
    nullif(trim(coalesce(wc.phone, '')), '') as phone,
    nullif(regexp_replace(trim(coalesce(wc.phone, '')), '[^0-9+]', '', 'g'), '') as normalized_phone,
    (coalesce(wc.accepted_email_marketing, false) and nullif(trim(coalesce(wc.email, '')), '') is not null) as email_opt_in,
    (coalesce(wc.accepted_email_marketing, false) and nullif(trim(coalesce(wc.phone, '')), '') is not null) as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    coalesce(wc.consent_at::timestamptz, now()) as seen_at
  from public.widget_consents wc
  where wc.client_id is not null

  union all

  select
    chr.client_id,
    nullif(trim(coalesce(chr.contact_name, '')), '') as name,
    nullif(lower(trim(coalesce(chr.contact_email, ''))), '') as email,
    nullif(lower(trim(coalesce(chr.contact_email, ''))), '') as normalized_email,
    nullif(trim(coalesce(chr.contact_phone, '')), '') as phone,
    nullif(regexp_replace(trim(coalesce(chr.contact_phone, '')), '[^0-9+]', '', 'g'), '') as normalized_phone,
    (coalesce(chr.accepted_email_marketing, false) and nullif(trim(coalesce(chr.contact_email, '')), '') is not null) as email_opt_in,
    (coalesce(chr.accepted_email_marketing, false) and nullif(trim(coalesce(chr.contact_phone, '')), '') is not null) as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    case
      when lower(trim(coalesce(chr.trigger, ''))) = 'marketing_interest' then 'interested'
      else 'unknown'
    end as interest_status,
    chr.created_at as seen_at
  from public.conversation_handoff_requests chr
  where chr.client_id is not null

  union all

  select
    mcr.client_id,
    nullif(trim(coalesce(mcr.recipient_name, '')), '') as name,
    nullif(lower(trim(coalesce(mcr.email, ''))), '') as email,
    nullif(lower(trim(coalesce(mcr.email, ''))), '') as normalized_email,
    nullif(trim(coalesce(mcr.phone, '')), '') as phone,
    nullif(regexp_replace(trim(coalesce(mcr.phone, '')), '[^0-9+]', '', 'g'), '') as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    coalesce(mcr.sent_at, mcr.created_at) as seen_at
  from public.marketing_campaign_recipients mcr
  where mcr.client_id is not null

  union all

  select
    p.client_id,
    null::text as name,
    nullif(lower(trim(coalesce(p.email, ''))), '') as email,
    nullif(lower(trim(coalesce(p.email, ''))), '') as normalized_email,
    null::text as phone,
    null::text as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    (p.request_type = 'marketing_opt_out' and p.source in ('email_unsubscribe_link', 'privacy_unsubscribe_fallback', 'privacy_request')) as email_unsubscribed,
    (p.request_type = 'marketing_opt_out' and p.source = 'whatsapp_campaign_button') as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    p.created_at as seen_at
  from public.public_privacy_requests p
  where p.client_id is not null

  union all

  select
    mcr.client_id,
    nullif(trim(coalesce(mcr.recipient_name, '')), '') as name,
    nullif(lower(trim(coalesce(mcr.email, ''))), '') as email,
    nullif(lower(trim(coalesce(mcr.email, ''))), '') as normalized_email,
    nullif(trim(coalesce(mcr.phone, '')), '') as phone,
    nullif(regexp_replace(trim(coalesce(mcr.phone, '')), '[^0-9+]', '', 'g'), '') as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    (mce.event_type = 'opt_out' and nullif(lower(trim(coalesce(mcr.email, ''))), '') is not null) as email_unsubscribed,
    (mce.event_type = 'opt_out' and nullif(trim(coalesce(mcr.phone, '')), '') is not null) as whatsapp_unsubscribed,
    case
      when mce.event_type in ('interest', 'interest_yes') then 'interested'
      when mce.event_type = 'interest_no' then 'not_interested'
      else 'unknown'
    end as interest_status,
    mce.created_at as seen_at
  from public.marketing_campaign_events mce
  join public.marketing_campaign_recipients mcr
    on mcr.campaign_id = mce.campaign_id
   and coalesce(mcr.recipient_key, '') = coalesce(mce.recipient_key, '')
  where mce.client_id is not null
    and mce.event_type in ('interest', 'interest_yes', 'interest_no', 'opt_out')
),
email_contacts as (
  select
    sr.client_id,
    max(sr.name) filter (where sr.name is not null and sr.name <> '') as name,
    max(sr.email) filter (where sr.email is not null and sr.email <> '') as email,
    sr.normalized_email,
    max(sr.phone) filter (where sr.phone is not null and sr.phone <> '') as phone,
    max(sr.normalized_phone) filter (where sr.normalized_phone is not null and sr.normalized_phone <> '') as normalized_phone,
    bool_or(sr.email_opt_in) as email_opt_in,
    bool_or(sr.whatsapp_opt_in) as whatsapp_opt_in,
    bool_or(sr.email_unsubscribed) as email_unsubscribed,
    bool_or(sr.whatsapp_unsubscribed) as whatsapp_unsubscribed,
    case
      when max(sr.seen_at) filter (where sr.interest_status = 'interested') is not null
        and (
          max(sr.seen_at) filter (where sr.interest_status = 'not_interested') is null
          or max(sr.seen_at) filter (where sr.interest_status = 'interested')
             >= max(sr.seen_at) filter (where sr.interest_status = 'not_interested')
        ) then 'interested'
      when max(sr.seen_at) filter (where sr.interest_status = 'not_interested') is not null then 'not_interested'
      else 'unknown'
    end as interest_status,
    min(sr.seen_at) as first_seen_at,
    max(sr.seen_at) as last_seen_at
  from seed_rows sr
  where sr.normalized_email is not null
  group by sr.client_id, sr.normalized_email
)
insert into public.marketing_contacts (
  client_id,
  name,
  email,
  normalized_email,
  phone,
  normalized_phone,
  email_opt_in,
  whatsapp_opt_in,
  email_unsubscribed,
  whatsapp_unsubscribed,
  interest_status,
  first_seen_at,
  last_seen_at
)
select
  ec.client_id,
  ec.name,
  ec.email,
  ec.normalized_email,
  ec.phone,
  ec.normalized_phone,
  ec.email_opt_in,
  ec.whatsapp_opt_in,
  ec.email_unsubscribed,
  ec.whatsapp_unsubscribed,
  ec.interest_status,
  ec.first_seen_at,
  ec.last_seen_at
from email_contacts ec
on conflict (client_id, normalized_email) do update
set
  name = coalesce(excluded.name, public.marketing_contacts.name),
  email = coalesce(excluded.email, public.marketing_contacts.email),
  phone = coalesce(excluded.phone, public.marketing_contacts.phone),
  normalized_phone = coalesce(excluded.normalized_phone, public.marketing_contacts.normalized_phone),
  email_opt_in = public.marketing_contacts.email_opt_in or excluded.email_opt_in,
  whatsapp_opt_in = public.marketing_contacts.whatsapp_opt_in or excluded.whatsapp_opt_in,
  email_unsubscribed = public.marketing_contacts.email_unsubscribed or excluded.email_unsubscribed,
  whatsapp_unsubscribed = public.marketing_contacts.whatsapp_unsubscribed or excluded.whatsapp_unsubscribed,
  interest_status = case
    when excluded.interest_status = 'unknown' then public.marketing_contacts.interest_status
    else excluded.interest_status
  end,
  first_seen_at = least(public.marketing_contacts.first_seen_at, excluded.first_seen_at),
  last_seen_at = greatest(public.marketing_contacts.last_seen_at, excluded.last_seen_at),
  updated_at = now();

with seed_rows as (
  select
    wc.client_id,
    null::text as name,
    null::text as email,
    null::text as normalized_email,
    nullif(trim(coalesce(wc.phone, '')), '') as phone,
    nullif(regexp_replace(trim(coalesce(wc.phone, '')), '[^0-9+]', '', 'g'), '') as normalized_phone,
    false as email_opt_in,
    (coalesce(wc.accepted_email_marketing, false) and nullif(trim(coalesce(wc.phone, '')), '') is not null) as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    coalesce(wc.consent_at::timestamptz, now()) as seen_at
  from public.widget_consents wc
  where wc.client_id is not null
    and nullif(lower(trim(coalesce(wc.email, ''))), '') is null

  union all

  select
    chr.client_id,
    nullif(trim(coalesce(chr.contact_name, '')), '') as name,
    null::text as email,
    null::text as normalized_email,
    nullif(trim(coalesce(chr.contact_phone, '')), '') as phone,
    nullif(regexp_replace(trim(coalesce(chr.contact_phone, '')), '[^0-9+]', '', 'g'), '') as normalized_phone,
    false as email_opt_in,
    (coalesce(chr.accepted_email_marketing, false) and nullif(trim(coalesce(chr.contact_phone, '')), '') is not null) as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    case
      when lower(trim(coalesce(chr.trigger, ''))) = 'marketing_interest' then 'interested'
      else 'unknown'
    end as interest_status,
    chr.created_at as seen_at
  from public.conversation_handoff_requests chr
  where chr.client_id is not null
    and nullif(lower(trim(coalesce(chr.contact_email, ''))), '') is null

  union all

  select
    mcr.client_id,
    nullif(trim(coalesce(mcr.recipient_name, '')), '') as name,
    null::text as email,
    null::text as normalized_email,
    nullif(trim(coalesce(mcr.phone, '')), '') as phone,
    nullif(regexp_replace(trim(coalesce(mcr.phone, '')), '[^0-9+]', '', 'g'), '') as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    coalesce(mcr.sent_at, mcr.created_at) as seen_at
  from public.marketing_campaign_recipients mcr
  where mcr.client_id is not null
    and nullif(lower(trim(coalesce(mcr.email, ''))), '') is null

  union all

  select
    mcr.client_id,
    nullif(trim(coalesce(mcr.recipient_name, '')), '') as name,
    null::text as email,
    null::text as normalized_email,
    nullif(trim(coalesce(mcr.phone, '')), '') as phone,
    nullif(regexp_replace(trim(coalesce(mcr.phone, '')), '[^0-9+]', '', 'g'), '') as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    false as email_unsubscribed,
    (mce.event_type = 'opt_out' and nullif(trim(coalesce(mcr.phone, '')), '') is not null) as whatsapp_unsubscribed,
    case
      when mce.event_type in ('interest', 'interest_yes') then 'interested'
      when mce.event_type = 'interest_no' then 'not_interested'
      else 'unknown'
    end as interest_status,
    mce.created_at as seen_at
  from public.marketing_campaign_events mce
  join public.marketing_campaign_recipients mcr
    on mcr.campaign_id = mce.campaign_id
   and coalesce(mcr.recipient_key, '') = coalesce(mce.recipient_key, '')
  where mce.client_id is not null
    and mce.event_type in ('interest', 'interest_yes', 'interest_no', 'opt_out')
    and nullif(lower(trim(coalesce(mcr.email, ''))), '') is null
),
phone_contacts as (
  select
    sr.client_id,
    max(sr.name) filter (where sr.name is not null and sr.name <> '') as name,
    max(sr.phone) filter (where sr.phone is not null and sr.phone <> '') as phone,
    sr.normalized_phone,
    bool_or(sr.whatsapp_opt_in) as whatsapp_opt_in,
    bool_or(sr.whatsapp_unsubscribed) as whatsapp_unsubscribed,
    case
      when max(sr.seen_at) filter (where sr.interest_status = 'interested') is not null
        and (
          max(sr.seen_at) filter (where sr.interest_status = 'not_interested') is null
          or max(sr.seen_at) filter (where sr.interest_status = 'interested')
             >= max(sr.seen_at) filter (where sr.interest_status = 'not_interested')
        ) then 'interested'
      when max(sr.seen_at) filter (where sr.interest_status = 'not_interested') is not null then 'not_interested'
      else 'unknown'
    end as interest_status,
    min(sr.seen_at) as first_seen_at,
    max(sr.seen_at) as last_seen_at
  from seed_rows sr
  where sr.normalized_phone is not null
  group by sr.client_id, sr.normalized_phone
)
insert into public.marketing_contacts (
  client_id,
  name,
  phone,
  normalized_phone,
  whatsapp_opt_in,
  whatsapp_unsubscribed,
  interest_status,
  first_seen_at,
  last_seen_at
)
select
  pc.client_id,
  pc.name,
  pc.phone,
  pc.normalized_phone,
  pc.whatsapp_opt_in,
  pc.whatsapp_unsubscribed,
  pc.interest_status,
  pc.first_seen_at,
  pc.last_seen_at
from phone_contacts pc
on conflict (client_id, normalized_phone) do update
set
  name = coalesce(excluded.name, public.marketing_contacts.name),
  phone = coalesce(excluded.phone, public.marketing_contacts.phone),
  whatsapp_opt_in = public.marketing_contacts.whatsapp_opt_in or excluded.whatsapp_opt_in,
  whatsapp_unsubscribed = public.marketing_contacts.whatsapp_unsubscribed or excluded.whatsapp_unsubscribed,
  interest_status = case
    when excluded.interest_status = 'unknown' then public.marketing_contacts.interest_status
    else excluded.interest_status
  end,
  first_seen_at = least(public.marketing_contacts.first_seen_at, excluded.first_seen_at),
  last_seen_at = greatest(public.marketing_contacts.last_seen_at, excluded.last_seen_at),
  updated_at = now();

commit;
