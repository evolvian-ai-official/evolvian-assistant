-- Tenant isolation hardening for Meta approved templates.
-- Goal: prevent cross-client visibility of private WhatsApp campaign templates.

begin;

alter table if exists public.meta_approved_templates
  add column if not exists owner_client_id uuid references public.clients(id) on delete set null;

alter table if exists public.meta_approved_templates
  add column if not exists visibility_scope text;

update public.meta_approved_templates
set visibility_scope = 'global'
where coalesce(trim(visibility_scope), '') = '';

alter table if exists public.meta_approved_templates
  alter column visibility_scope set default 'global';

alter table if exists public.meta_approved_templates
  alter column visibility_scope set not null;

do $$
begin
  if to_regclass('public.meta_approved_templates') is not null then
    alter table public.meta_approved_templates
      drop constraint if exists meta_approved_templates_visibility_scope_chk;

    alter table public.meta_approved_templates
      add constraint meta_approved_templates_visibility_scope_chk
      check (visibility_scope in ('global', 'client_private'));
  end if;
end
$$;

-- Campaign WhatsApp templates are private per client.
update public.meta_approved_templates
set visibility_scope = 'client_private'
where channel = 'whatsapp'
  and coalesce(type, '') like 'campaign_whatsapp%'
  and visibility_scope <> 'client_private';

-- Backfill owner from marketing campaign records (preferred source).
with campaign_owner as (
  select distinct on (mc.meta_template_id)
    mc.meta_template_id,
    mc.client_id
  from public.marketing_campaigns mc
  where mc.meta_template_id is not null
  order by mc.meta_template_id, mc.created_at desc nulls last
)
update public.meta_approved_templates mat
set owner_client_id = co.client_id
from campaign_owner co
where mat.id = co.meta_template_id
  and mat.visibility_scope = 'client_private'
  and mat.owner_client_id is null;

-- Fallback backfill from local message template bindings.
with template_owner as (
  select distinct on (mt.meta_template_id)
    mt.meta_template_id,
    mt.client_id
  from public.message_templates mt
  where mt.channel = 'whatsapp'
    and mt.meta_template_id is not null
    and (
      coalesce(mt.variant_key, '') = 'campaign'
      or coalesce(mt.type, '') like 'campaign_whatsapp%'
    )
  order by mt.meta_template_id, mt.updated_at desc nulls last
)
update public.meta_approved_templates mat
set owner_client_id = towner.client_id
from template_owner towner
where mat.id = towner.meta_template_id
  and mat.visibility_scope = 'client_private'
  and mat.owner_client_id is null;

-- Fail-safe: unresolved private rows are disabled to avoid accidental exposure.
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'meta_approved_templates'
      and column_name = 'provision_enabled'
  ) then
    execute $q$
      update public.meta_approved_templates
      set is_active = false,
          provision_enabled = false
      where visibility_scope = 'client_private'
        and owner_client_id is null
    $q$;
  else
    execute $q$
      update public.meta_approved_templates
      set is_active = false
      where visibility_scope = 'client_private'
        and owner_client_id is null
    $q$;
  end if;
end
$$;

create index if not exists idx_meta_approved_templates_visibility_scope
  on public.meta_approved_templates (channel, is_active, visibility_scope, type, language);

create index if not exists idx_meta_approved_templates_owner_scope
  on public.meta_approved_templates (owner_client_id, channel, is_active, visibility_scope, type, language)
  where owner_client_id is not null;

commit;
