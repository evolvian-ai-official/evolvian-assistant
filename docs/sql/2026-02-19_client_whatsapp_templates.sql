-- Quick win MVP: per-client WhatsApp template provisioning/status/pricing cache.
-- Apply this migration before enabling template sync endpoints.

create extension if not exists "pgcrypto";

create table if not exists public.client_whatsapp_templates (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id) on delete cascade,
    meta_template_id uuid not null references public.meta_approved_templates(id) on delete cascade,
    canonical_template_name text not null,
    meta_template_name text not null,
    template_type text,
    category text not null default 'UTILITY',
    language text not null default 'es_MX',
    status text not null default 'pending',
    is_active boolean not null default false,
    status_reason text,
    meta_template_remote_id text,
    pricing_currency text not null default 'USD',
    estimated_unit_cost numeric(10, 4) not null default 0,
    billable boolean not null default true,
    pricing_source text not null default 'evolvian_estimate_v1',
    last_synced_at timestamptz,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint client_whatsapp_templates_category_chk
        check (category in ('UTILITY', 'MARKETING', 'AUTHENTICATION', 'SERVICE')),
    constraint client_whatsapp_templates_status_chk
        check (status in ('active', 'pending', 'inactive', 'unknown')),
    unique (client_id, meta_template_id),
    unique (client_id, meta_template_name)
);

create index if not exists idx_client_whatsapp_templates_client_id
    on public.client_whatsapp_templates (client_id);

create index if not exists idx_client_whatsapp_templates_status
    on public.client_whatsapp_templates (client_id, status);

create index if not exists idx_client_whatsapp_templates_meta_template_id
    on public.client_whatsapp_templates (meta_template_id);
