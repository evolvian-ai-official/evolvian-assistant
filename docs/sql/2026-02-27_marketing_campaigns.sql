-- Marketing campaigns module (Premium)
-- Includes campaigns, recipients tracking, and events timeline.

begin;

create table if not exists public.marketing_campaigns (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  name text not null,
  channel text not null check (channel in ('email', 'whatsapp')),
  status text not null default 'draft'
    check (status in ('draft', 'scheduled', 'active', 'paused', 'sent', 'archived')),
  subject text,
  body text not null,
  image_url text,
  cta_mode text not null default 'interested' check (cta_mode in ('url', 'interested')),
  cta_label text,
  cta_url text,
  language_family text default 'es' check (language_family in ('es', 'en')),
  template_id uuid references public.message_templates(id),
  meta_template_id uuid references public.meta_approved_templates(id),
  meta_template_name text,
  created_by_user_id uuid references public.users(id),
  is_active boolean not null default true,
  send_count integer not null default 0,
  last_sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_marketing_campaigns_client_created
  on public.marketing_campaigns (client_id, created_at desc);

create index if not exists idx_marketing_campaigns_client_status
  on public.marketing_campaigns (client_id, status);

create table if not exists public.marketing_campaign_recipients (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  campaign_id uuid not null references public.marketing_campaigns(id) on delete cascade,
  recipient_key text not null,
  recipient_name text,
  email text,
  phone text,
  segment text check (segment in ('clients', 'leads')),
  send_status text not null default 'pending'
    check (send_status in ('pending', 'sent', 'failed', 'blocked_policy', 'skipped')),
  send_error text,
  policy_proof_id text,
  provider_message_id text,
  provider text,
  metadata jsonb,
  sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (campaign_id, recipient_key)
);

create index if not exists idx_marketing_campaign_recipients_client_key
  on public.marketing_campaign_recipients (client_id, recipient_key);

create index if not exists idx_marketing_campaign_recipients_campaign_status
  on public.marketing_campaign_recipients (campaign_id, send_status);

create table if not exists public.marketing_campaign_events (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  campaign_id uuid not null references public.marketing_campaigns(id) on delete cascade,
  recipient_key text,
  event_type text not null,
  metadata jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_marketing_campaign_events_client_campaign
  on public.marketing_campaign_events (client_id, campaign_id, created_at desc);

alter table if exists public.marketing_campaigns enable row level security;
alter table if exists public.marketing_campaign_recipients enable row level security;
alter table if exists public.marketing_campaign_events enable row level security;

commit;
