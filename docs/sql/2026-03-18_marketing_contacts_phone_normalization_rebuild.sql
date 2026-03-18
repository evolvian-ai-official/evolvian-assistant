-- Rebuild derived marketing_contacts state with canonical MX-first phone normalization.
-- Safe because marketing_contacts is a derived snapshot from source tables.

begin;

create or replace function pg_temp.normalize_marketing_phone(raw text, client_country text default null)
returns text
language plpgsql
as $$
declare
  cleaned text;
  digits text;
  normalized_country text;
begin
  cleaned := regexp_replace(trim(coalesce(raw, '')), '[^0-9+]', '', 'g');
  if cleaned = '' then
    return null;
  end if;
  if cleaned like '00%' then
    cleaned := '+' || substr(cleaned, 3);
  end if;
  digits := regexp_replace(cleaned, '\D', '', 'g');
  if digits = '' then
    return null;
  end if;
  normalized_country := upper(trim(coalesce(client_country, '')));
  if normalized_country in ('MX', 'MEX', 'MEXICO', 'MÉXICO') and length(digits) = 10 then
    digits := '52' || digits;
  end if;
  if digits like '521%' and length(digits) = 13 then
    digits := '52' || substr(digits, 4);
  end if;
  if length(digits) = 10 then
    return null;
  end if;
  if length(digits) < 10 or length(digits) > 15 then
    return null;
  end if;
  return '+' || digits;
end;
$$;

delete from public.marketing_contacts;

with seed_rows as (
  select
    wc.client_id,
    null::text as name,
    nullif(lower(trim(coalesce(wc.email, ''))), '') as email,
    nullif(lower(trim(coalesce(wc.email, ''))), '') as normalized_email,
    pg_temp.normalize_marketing_phone(wc.phone, cp.country) as phone,
    pg_temp.normalize_marketing_phone(wc.phone, cp.country) as normalized_phone,
    (coalesce(wc.accepted_email_marketing, false) and nullif(trim(coalesce(wc.email, '')), '') is not null) as email_opt_in,
    (coalesce(wc.accepted_email_marketing, false) and pg_temp.normalize_marketing_phone(wc.phone, cp.country) is not null) as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    coalesce(wc.consent_at::timestamptz, now()) as seen_at
  from public.widget_consents wc
  left join public.client_profile cp on cp.client_id = wc.client_id
  where wc.client_id is not null

  union all

  select
    chr.client_id,
    nullif(trim(coalesce(chr.contact_name, '')), '') as name,
    nullif(lower(trim(coalesce(chr.contact_email, ''))), '') as email,
    nullif(lower(trim(coalesce(chr.contact_email, ''))), '') as normalized_email,
    pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) as phone,
    pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) as normalized_phone,
    (coalesce(chr.accepted_email_marketing, false) and nullif(trim(coalesce(chr.contact_email, '')), '') is not null) as email_opt_in,
    (coalesce(chr.accepted_email_marketing, false) and pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) is not null) as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    case
      when lower(trim(coalesce(chr.trigger, ''))) = 'marketing_interest' then 'interested'
      else 'unknown'
    end as interest_status,
    chr.created_at as seen_at
  from public.conversation_handoff_requests chr
  left join public.client_profile cp on cp.client_id = chr.client_id
  where chr.client_id is not null

  union all

  select
    mcr.client_id,
    nullif(trim(coalesce(mcr.recipient_name, '')), '') as name,
    nullif(lower(trim(coalesce(mcr.email, ''))), '') as email,
    nullif(lower(trim(coalesce(mcr.email, ''))), '') as normalized_email,
    pg_temp.normalize_marketing_phone(mcr.phone, cp.country) as phone,
    pg_temp.normalize_marketing_phone(mcr.phone, cp.country) as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    coalesce(mcr.sent_at, mcr.created_at) as seen_at
  from public.marketing_campaign_recipients mcr
  left join public.client_profile cp on cp.client_id = mcr.client_id
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
    pg_temp.normalize_marketing_phone(mcr.phone, cp.country) as phone,
    pg_temp.normalize_marketing_phone(mcr.phone, cp.country) as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    (mce.event_type = 'opt_out' and nullif(lower(trim(coalesce(mcr.email, ''))), '') is not null) as email_unsubscribed,
    (mce.event_type = 'opt_out' and pg_temp.normalize_marketing_phone(mcr.phone, cp.country) is not null) as whatsapp_unsubscribed,
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
  left join public.client_profile cp on cp.client_id = mcr.client_id
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
from email_contacts ec;

with phone_seed_rows as (
  select
    wc.client_id,
    null::text as name,
    null::text as email,
    null::text as normalized_email,
    pg_temp.normalize_marketing_phone(wc.phone, cp.country) as phone,
    pg_temp.normalize_marketing_phone(wc.phone, cp.country) as normalized_phone,
    false as email_opt_in,
    (coalesce(wc.accepted_email_marketing, false) and pg_temp.normalize_marketing_phone(wc.phone, cp.country) is not null) as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    coalesce(wc.consent_at::timestamptz, now()) as seen_at
  from public.widget_consents wc
  left join public.client_profile cp on cp.client_id = wc.client_id
  where wc.client_id is not null
    and nullif(lower(trim(coalesce(wc.email, ''))), '') is null

  union all

  select
    chr.client_id,
    nullif(trim(coalesce(chr.contact_name, '')), '') as name,
    null::text as email,
    null::text as normalized_email,
    pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) as phone,
    pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) as normalized_phone,
    false as email_opt_in,
    (coalesce(chr.accepted_email_marketing, false) and pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) is not null) as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    case
      when lower(trim(coalesce(chr.trigger, ''))) = 'marketing_interest' then 'interested'
      else 'unknown'
    end as interest_status,
    chr.created_at as seen_at
  from public.conversation_handoff_requests chr
  left join public.client_profile cp on cp.client_id = chr.client_id
  where chr.client_id is not null
    and nullif(lower(trim(coalesce(chr.contact_email, ''))), '') is null

  union all

  select
    mcr.client_id,
    nullif(trim(coalesce(mcr.recipient_name, '')), '') as name,
    null::text as email,
    null::text as normalized_email,
    pg_temp.normalize_marketing_phone(mcr.phone, cp.country) as phone,
    pg_temp.normalize_marketing_phone(mcr.phone, cp.country) as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    false as email_unsubscribed,
    false as whatsapp_unsubscribed,
    'unknown'::text as interest_status,
    coalesce(mcr.sent_at, mcr.created_at) as seen_at
  from public.marketing_campaign_recipients mcr
  left join public.client_profile cp on cp.client_id = mcr.client_id
  where mcr.client_id is not null
    and nullif(lower(trim(coalesce(mcr.email, ''))), '') is null

  union all

  select
    mcr.client_id,
    nullif(trim(coalesce(mcr.recipient_name, '')), '') as name,
    null::text as email,
    null::text as normalized_email,
    pg_temp.normalize_marketing_phone(mcr.phone, cp.country) as phone,
    pg_temp.normalize_marketing_phone(mcr.phone, cp.country) as normalized_phone,
    false as email_opt_in,
    false as whatsapp_opt_in,
    false as email_unsubscribed,
    (mce.event_type = 'opt_out' and pg_temp.normalize_marketing_phone(mcr.phone, cp.country) is not null) as whatsapp_unsubscribed,
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
  left join public.client_profile cp on cp.client_id = mcr.client_id
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
  from phone_seed_rows sr
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
