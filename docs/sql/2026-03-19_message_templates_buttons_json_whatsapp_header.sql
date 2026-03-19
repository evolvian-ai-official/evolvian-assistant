-- Per-client WhatsApp template overrides (header media, future button overrides)
-- Safe to run once.

alter table public.message_templates
add column if not exists buttons_json jsonb;

comment on column public.message_templates.buttons_json is
'Optional per-client WhatsApp template overrides. Example: {"header":{"type":"IMAGE","image_url":"https://..."}}';

