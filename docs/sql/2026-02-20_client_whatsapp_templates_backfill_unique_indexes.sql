-- Ensure client_whatsapp_templates supports upsert(on_conflict=client_id,meta_template_id)
-- in environments where the original create-table migration was partially applied.

-- 1) Deduplicate by (client_id, meta_template_id), keeping the most recently updated row.
with ranked as (
  select
    id,
    row_number() over (
      partition by client_id, meta_template_id
      order by updated_at desc nulls last, created_at desc nulls last, id desc
    ) as rn
  from public.client_whatsapp_templates
)
delete from public.client_whatsapp_templates t
using ranked r
where t.id = r.id
  and r.rn > 1;

-- 2) Deduplicate by (client_id, meta_template_name), keeping the most recently updated row.
with ranked as (
  select
    id,
    row_number() over (
      partition by client_id, meta_template_name
      order by updated_at desc nulls last, created_at desc nulls last, id desc
    ) as rn
  from public.client_whatsapp_templates
)
delete from public.client_whatsapp_templates t
using ranked r
where t.id = r.id
  and r.rn > 1;

-- 3) Add unique indexes required by upsert conflict targets.
create unique index if not exists ux_client_whatsapp_templates_client_meta
  on public.client_whatsapp_templates (client_id, meta_template_id);

create unique index if not exists ux_client_whatsapp_templates_client_meta_name
  on public.client_whatsapp_templates (client_id, meta_template_name);
