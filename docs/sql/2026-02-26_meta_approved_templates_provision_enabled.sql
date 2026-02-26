-- Separate catalog/runtime activation from provisioning behavior for WhatsApp canonical templates.
-- `is_active` keeps template available in catalog/runtime.
-- `provision_enabled` controls whether sync should create/provision this canonical template in client Meta accounts.

alter table public.meta_approved_templates
add column if not exists provision_enabled boolean;

update public.meta_approved_templates
set provision_enabled = true
where provision_enabled is null;

alter table public.meta_approved_templates
alter column provision_enabled set default true;

alter table public.meta_approved_templates
alter column provision_enabled set not null;

create index if not exists idx_meta_approved_templates_whatsapp_provision
on public.meta_approved_templates (channel, is_active, provision_enabled, type, language);

comment on column public.meta_approved_templates.provision_enabled is
'When false, canonical template stays in catalog/runtime but is excluded from WhatsApp sync provisioning for new clients.';

