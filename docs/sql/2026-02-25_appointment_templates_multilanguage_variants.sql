-- Support multiple message templates per type with language-aware routing (EN/ES)
-- for appointments confirmations, reminders, and cancellations.
--
-- Apply before deploying/using the multilingual appointment template resolver.

begin;

alter table if exists public.message_templates
  add column if not exists language_family text;

alter table if exists public.message_templates
  add column if not exists locale_code text;

alter table if exists public.message_templates
  add column if not exists variant_key text;

alter table if exists public.message_templates
  add column if not exists priority integer;

alter table if exists public.message_templates
  add column if not exists is_default_for_language boolean;

alter table if exists public.client_settings
  add column if not exists appointments_template_language text;

alter table if exists public.appointments
  add column if not exists recipient_language text;

alter table if exists public.appointments
  add column if not exists recipient_locale text;

alter table if exists public.appointment_clients
  add column if not exists preferred_language text;

alter table if exists public.appointment_clients
  add column if not exists preferred_locale text;

-- Backfill WhatsApp template language from canonical Meta catalog.
update public.message_templates mt
set
  locale_code = coalesce(nullif(mt.locale_code, ''), mat.language),
  language_family = coalesce(
    nullif(mt.language_family, ''),
    case
      when lower(coalesce(mat.language, '')) like 'en%' then 'en'
      else 'es'
    end
  )
from public.meta_approved_templates mat
where mt.meta_template_id = mat.id
  and mt.channel = 'whatsapp';

-- Backfill email/widget template language from client default language.
update public.message_templates mt
set
  language_family = coalesce(
    nullif(mt.language_family, ''),
    case
      when lower(coalesce(cs.language, 'es')) like 'en%' then 'en'
      else 'es'
    end
  ),
  locale_code = coalesce(
    nullif(mt.locale_code, ''),
    case
      when lower(coalesce(cs.language, 'es')) like 'en%' then 'en_US'
      else 'es_MX'
    end
  )
from public.client_settings cs
where mt.client_id = cs.client_id
  and mt.channel in ('email', 'widget');

update public.message_templates
set
  variant_key = coalesce(nullif(variant_key, ''), 'default'),
  priority = coalesce(priority, 0),
  is_default_for_language = coalesce(is_default_for_language, true)
where true;

update public.client_settings
set appointments_template_language = coalesce(
  nullif(appointments_template_language, ''),
  case
    when lower(coalesce(language, 'es')) like 'en%' then 'en'
    else 'es'
  end
)
where true;

-- Snapshot language on legacy appointments so reminders/cancellations have a stable fallback.
update public.appointments a
set
  recipient_language = coalesce(
    nullif(a.recipient_language, ''),
    case
      when lower(coalesce(cs.language, 'es')) like 'en%' then 'en'
      else 'es'
    end
  ),
  recipient_locale = coalesce(
    nullif(a.recipient_locale, ''),
    case
      when lower(coalesce(cs.language, 'es')) like 'en%' then 'en_US'
      else 'es_MX'
    end
  )
from public.client_settings cs
where a.client_id = cs.client_id;

-- Default appointment directory contacts to client language until they are edited.
update public.appointment_clients ac
set
  preferred_language = coalesce(
    nullif(ac.preferred_language, ''),
    case
      when lower(coalesce(cs.language, 'es')) like 'en%' then 'en'
      else 'es'
    end
  ),
  preferred_locale = coalesce(
    nullif(ac.preferred_locale, ''),
    case
      when lower(coalesce(cs.language, 'es')) like 'en%' then 'en_US'
      else 'es_MX'
    end
  )
from public.client_settings cs
where ac.client_id = cs.client_id;

-- Lightweight checks (nullable-compatible to avoid hard failures on old rows).
do $$
begin
  if to_regclass('public.message_templates') is not null then
    alter table public.message_templates
      drop constraint if exists message_templates_language_family_chk;
    alter table public.message_templates
      add constraint message_templates_language_family_chk
      check (language_family is null or language_family in ('es', 'en'));
  end if;

  if to_regclass('public.appointments') is not null then
    alter table public.appointments
      drop constraint if exists appointments_recipient_language_chk;
    alter table public.appointments
      add constraint appointments_recipient_language_chk
      check (recipient_language is null or recipient_language in ('es', 'en'));
  end if;

  if to_regclass('public.appointment_clients') is not null then
    alter table public.appointment_clients
      drop constraint if exists appointment_clients_preferred_language_chk;
    alter table public.appointment_clients
      add constraint appointment_clients_preferred_language_chk
      check (preferred_language is null or preferred_language in ('es', 'en'));
  end if;

  if to_regclass('public.client_settings') is not null then
    alter table public.client_settings
      drop constraint if exists client_settings_appointments_template_language_chk;
    alter table public.client_settings
      add constraint client_settings_appointments_template_language_chk
      check (appointments_template_language is null or appointments_template_language in ('es', 'en'));
  end if;
end $$;

create index if not exists idx_message_templates_client_channel_type_lang_active
  on public.message_templates (client_id, channel, type, language_family, is_active);

create index if not exists idx_message_templates_locale_lookup
  on public.message_templates (client_id, channel, type, locale_code);

create unique index if not exists ux_message_templates_default_per_language
  on public.message_templates (client_id, channel, type, language_family)
  where coalesce(is_active, true) = true
    and coalesce(is_default_for_language, false) = true
    and language_family is not null;

create index if not exists idx_appointments_client_recipient_language
  on public.appointments (client_id, recipient_language);

create index if not exists idx_appointment_clients_client_preferred_language
  on public.appointment_clients (client_id, preferred_language);

commit;
