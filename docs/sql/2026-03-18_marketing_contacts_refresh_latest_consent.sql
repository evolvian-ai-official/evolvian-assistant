-- Recompute marketing_contacts opt-in flags so the latest consent wins.
-- Safe to run after creating marketing_contacts or after changing merge rules.

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

with latest_email_consent as (
  select distinct on (wc.client_id, lower(trim(wc.email)))
    wc.client_id as client_id,
    lower(trim(wc.email)) as normalized_email,
    wc.accepted_email_marketing,
    wc.consent_at::timestamptz as seen_at
  from public.widget_consents wc
  where wc.client_id is not null
    and nullif(lower(trim(coalesce(wc.email, ''))), '') is not null
  order by wc.client_id, lower(trim(wc.email)), wc.consent_at desc nulls last
),
latest_email_handoff as (
  select distinct on (chr.client_id, lower(trim(chr.contact_email)))
    chr.client_id as client_id,
    lower(trim(chr.contact_email)) as normalized_email,
    chr.accepted_email_marketing,
    chr.created_at as seen_at
  from public.conversation_handoff_requests chr
  where chr.client_id is not null
    and nullif(lower(trim(coalesce(chr.contact_email, ''))), '') is not null
  order by chr.client_id, lower(trim(chr.contact_email)), chr.created_at desc nulls last
),
latest_email_choice as (
  select distinct on (client_id, normalized_email)
    client_id,
    normalized_email,
    accepted_email_marketing,
    seen_at
  from (
    select * from latest_email_consent
    union all
    select * from latest_email_handoff
  ) src
  order by client_id, normalized_email, seen_at desc nulls last
),
latest_phone_consent as (
  select distinct on (wc.client_id, pg_temp.normalize_marketing_phone(wc.phone, cp.country))
    wc.client_id as client_id,
    pg_temp.normalize_marketing_phone(wc.phone, cp.country) as normalized_phone,
    wc.accepted_email_marketing,
    wc.consent_at::timestamptz as seen_at
  from public.widget_consents wc
  left join public.client_profile cp on cp.client_id = wc.client_id
  where wc.client_id is not null
    and pg_temp.normalize_marketing_phone(wc.phone, cp.country) is not null
  order by wc.client_id, pg_temp.normalize_marketing_phone(wc.phone, cp.country), wc.consent_at desc nulls last
),
latest_phone_handoff as (
  select distinct on (chr.client_id, pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country))
    chr.client_id as client_id,
    pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) as normalized_phone,
    chr.accepted_email_marketing,
    chr.created_at as seen_at
  from public.conversation_handoff_requests chr
  left join public.client_profile cp on cp.client_id = chr.client_id
  where chr.client_id is not null
    and pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) is not null
  order by chr.client_id, pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country), chr.created_at desc nulls last
),
latest_phone_choice as (
  select distinct on (client_id, normalized_phone)
    client_id,
    normalized_phone,
    accepted_email_marketing,
    seen_at
  from (
    select * from latest_phone_consent
    union all
    select * from latest_phone_handoff
  ) src
  order by client_id, normalized_phone, seen_at desc nulls last
)
update public.marketing_contacts mc
set
  email_opt_in = lec.accepted_email_marketing,
  updated_at = now()
from latest_email_choice lec
where mc.client_id = lec.client_id
  and mc.normalized_email = lec.normalized_email;

with latest_phone_consent as (
  select distinct on (wc.client_id, pg_temp.normalize_marketing_phone(wc.phone, cp.country))
    wc.client_id as client_id,
    pg_temp.normalize_marketing_phone(wc.phone, cp.country) as normalized_phone,
    wc.accepted_email_marketing,
    wc.consent_at::timestamptz as seen_at
  from public.widget_consents wc
  left join public.client_profile cp on cp.client_id = wc.client_id
  where wc.client_id is not null
    and pg_temp.normalize_marketing_phone(wc.phone, cp.country) is not null
  order by wc.client_id, pg_temp.normalize_marketing_phone(wc.phone, cp.country), wc.consent_at desc nulls last
),
latest_phone_handoff as (
  select distinct on (chr.client_id, pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country))
    chr.client_id as client_id,
    pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) as normalized_phone,
    chr.accepted_email_marketing,
    chr.created_at as seen_at
  from public.conversation_handoff_requests chr
  left join public.client_profile cp on cp.client_id = chr.client_id
  where chr.client_id is not null
    and pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country) is not null
  order by chr.client_id, pg_temp.normalize_marketing_phone(chr.contact_phone, cp.country), chr.created_at desc nulls last
),
latest_phone_choice as (
  select distinct on (client_id, normalized_phone)
    client_id,
    normalized_phone,
    accepted_email_marketing,
    seen_at
  from (
    select * from latest_phone_consent
    union all
    select * from latest_phone_handoff
  ) src
  order by client_id, normalized_phone, seen_at desc nulls last
)
update public.marketing_contacts mc
set
  whatsapp_opt_in = lpc.accepted_email_marketing,
  updated_at = now()
from latest_phone_choice lpc
where mc.client_id = lpc.client_id
  and mc.normalized_phone = lpc.normalized_phone;

commit;
