-- Canonical WhatsApp template button definitions (optional but recommended)
-- Safe to run once. Sync code falls back if this column does not exist yet.

alter table public.meta_approved_templates
add column if not exists buttons_json jsonb;

comment on column public.meta_approved_templates.buttons_json is
'Optional canonical button definitions for Meta template sync. Format: [{"type":"QUICK_REPLY","text":"Cancel"}]';

-- Default quick-reply cancel button for appointment confirmation/reminder templates.
-- Only backfills rows that do not already have buttons_json.
update public.meta_approved_templates
set
  buttons_json = case
    when lower(coalesce(language, 'es_MX')) like 'en%' then
      '[{"type":"QUICK_REPLY","text":"Cancel"}]'::jsonb
    else
      '[{"type":"QUICK_REPLY","text":"Cancelar"}]'::jsonb
  end,
  updated_at = now()
where channel = 'whatsapp'
  and coalesce(is_active, true) = true
  and type in ('appointment_confirmation', 'appointment_reminder')
  and buttons_json is null;

-- Inspect canonical button config after backfill
-- select id, template_name, language, type, buttons_json
-- from public.meta_approved_templates
-- where channel='whatsapp'
--   and type in ('appointment_confirmation','appointment_reminder')
-- order by type, language, template_name;

