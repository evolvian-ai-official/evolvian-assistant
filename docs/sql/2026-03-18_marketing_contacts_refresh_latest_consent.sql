-- Recompute marketing_contacts opt-in flags so the latest consent wins.
-- Safe to run after creating marketing_contacts or after changing merge rules.

begin;

with latest_email_consent as (
  select distinct on (client_id, lower(trim(email)))
    client_id,
    lower(trim(email)) as normalized_email,
    accepted_email_marketing,
    consent_at::timestamptz as seen_at
  from public.widget_consents
  where client_id is not null
    and nullif(lower(trim(coalesce(email, ''))), '') is not null
  order by client_id, lower(trim(email)), consent_at desc nulls last
),
latest_email_handoff as (
  select distinct on (client_id, lower(trim(contact_email)))
    client_id,
    lower(trim(contact_email)) as normalized_email,
    accepted_email_marketing,
    created_at as seen_at
  from public.conversation_handoff_requests
  where client_id is not null
    and nullif(lower(trim(coalesce(contact_email, ''))), '') is not null
  order by client_id, lower(trim(contact_email)), created_at desc nulls last
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
  select distinct on (client_id, regexp_replace(trim(phone), '[^0-9+]', '', 'g'))
    client_id,
    regexp_replace(trim(phone), '[^0-9+]', '', 'g') as normalized_phone,
    accepted_email_marketing,
    consent_at::timestamptz as seen_at
  from public.widget_consents
  where client_id is not null
    and nullif(trim(coalesce(phone, '')), '') is not null
  order by client_id, regexp_replace(trim(phone), '[^0-9+]', '', 'g'), consent_at desc nulls last
),
latest_phone_handoff as (
  select distinct on (client_id, regexp_replace(trim(contact_phone), '[^0-9+]', '', 'g'))
    client_id,
    regexp_replace(trim(contact_phone), '[^0-9+]', '', 'g') as normalized_phone,
    accepted_email_marketing,
    created_at as seen_at
  from public.conversation_handoff_requests
  where client_id is not null
    and nullif(trim(coalesce(contact_phone, '')), '') is not null
  order by client_id, regexp_replace(trim(contact_phone), '[^0-9+]', '', 'g'), created_at desc nulls last
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
  select distinct on (client_id, regexp_replace(trim(phone), '[^0-9+]', '', 'g'))
    client_id,
    regexp_replace(trim(phone), '[^0-9+]', '', 'g') as normalized_phone,
    accepted_email_marketing,
    consent_at::timestamptz as seen_at
  from public.widget_consents
  where client_id is not null
    and nullif(trim(coalesce(phone, '')), '') is not null
  order by client_id, regexp_replace(trim(phone), '[^0-9+]', '', 'g'), consent_at desc nulls last
),
latest_phone_handoff as (
  select distinct on (client_id, regexp_replace(trim(contact_phone), '[^0-9+]', '', 'g'))
    client_id,
    regexp_replace(trim(contact_phone), '[^0-9+]', '', 'g') as normalized_phone,
    accepted_email_marketing,
    created_at as seen_at
  from public.conversation_handoff_requests
  where client_id is not null
    and nullif(trim(coalesce(contact_phone, '')), '') is not null
  order by client_id, regexp_replace(trim(contact_phone), '[^0-9+]', '', 'g'), created_at desc nulls last
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
