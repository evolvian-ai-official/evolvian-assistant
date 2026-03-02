-- Hardening for environments where marketing tables were created with older/partial schemas.
-- Safe to run multiple times.

begin;

-- -----------------------------------------------------------------------------
-- marketing_campaigns
-- -----------------------------------------------------------------------------
create table if not exists public.marketing_campaigns (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  name text not null,
  channel text not null,
  status text,
  subject text,
  body text,
  image_url text,
  cta_mode text,
  cta_label text,
  cta_url text,
  language_family text,
  template_id uuid,
  meta_template_id uuid,
  meta_template_name text,
  created_by_user_id uuid,
  is_active boolean,
  send_count integer,
  last_sent_at timestamptz,
  created_at timestamptz,
  updated_at timestamptz
);

alter table if exists public.marketing_campaigns add column if not exists status text;
alter table if exists public.marketing_campaigns add column if not exists subject text;
alter table if exists public.marketing_campaigns add column if not exists body text;
alter table if exists public.marketing_campaigns add column if not exists image_url text;
alter table if exists public.marketing_campaigns add column if not exists cta_mode text;
alter table if exists public.marketing_campaigns add column if not exists cta_label text;
alter table if exists public.marketing_campaigns add column if not exists cta_url text;
alter table if exists public.marketing_campaigns add column if not exists language_family text;
alter table if exists public.marketing_campaigns add column if not exists template_id uuid;
alter table if exists public.marketing_campaigns add column if not exists meta_template_id uuid;
alter table if exists public.marketing_campaigns add column if not exists meta_template_name text;
alter table if exists public.marketing_campaigns add column if not exists created_by_user_id uuid;
alter table if exists public.marketing_campaigns add column if not exists is_active boolean;
alter table if exists public.marketing_campaigns add column if not exists send_count integer;
alter table if exists public.marketing_campaigns add column if not exists last_sent_at timestamptz;
alter table if exists public.marketing_campaigns add column if not exists created_at timestamptz;
alter table if exists public.marketing_campaigns add column if not exists updated_at timestamptz;

update public.marketing_campaigns
set status = coalesce(nullif(status, ''), 'draft'),
    language_family = coalesce(nullif(language_family, ''), 'es'),
    is_active = coalesce(is_active, true),
    send_count = coalesce(send_count, 0),
    created_at = coalesce(created_at, now()),
    updated_at = coalesce(updated_at, now())
where true;

alter table if exists public.marketing_campaigns alter column status set default 'draft';
alter table if exists public.marketing_campaigns alter column language_family set default 'es';
alter table if exists public.marketing_campaigns alter column is_active set default true;
alter table if exists public.marketing_campaigns alter column send_count set default 0;
alter table if exists public.marketing_campaigns alter column created_at set default now();
alter table if exists public.marketing_campaigns alter column updated_at set default now();

-- Allow null CTA mode (no button) and keep backwards compatibility with old data.
alter table if exists public.marketing_campaigns alter column cta_mode drop not null;

do $$
begin
  if to_regclass('public.marketing_campaigns') is not null then
    alter table public.marketing_campaigns
      drop constraint if exists marketing_campaigns_channel_check;
    alter table public.marketing_campaigns
      add constraint marketing_campaigns_channel_check
      check (channel in ('email', 'whatsapp'));

    alter table public.marketing_campaigns
      drop constraint if exists marketing_campaigns_status_check;
    alter table public.marketing_campaigns
      add constraint marketing_campaigns_status_check
      check (status in ('draft', 'scheduled', 'active', 'paused', 'sent', 'archived'));

    alter table public.marketing_campaigns
      drop constraint if exists marketing_campaigns_cta_mode_check;
    alter table public.marketing_campaigns
      add constraint marketing_campaigns_cta_mode_check
      check (cta_mode is null or cta_mode in ('url', 'interested'));

    alter table public.marketing_campaigns
      drop constraint if exists marketing_campaigns_language_family_check;
    alter table public.marketing_campaigns
      add constraint marketing_campaigns_language_family_check
      check (language_family in ('es', 'en'));
  end if;
end
$$;

create index if not exists idx_marketing_campaigns_client_created
  on public.marketing_campaigns (client_id, created_at desc);
create index if not exists idx_marketing_campaigns_client_status
  on public.marketing_campaigns (client_id, status);

-- -----------------------------------------------------------------------------
-- marketing_campaign_recipients
-- -----------------------------------------------------------------------------
create table if not exists public.marketing_campaign_recipients (
  id uuid primary key default gen_random_uuid(),
  client_id uuid,
  campaign_id uuid,
  recipient_key text,
  recipient_name text,
  email text,
  phone text,
  segment text,
  send_status text,
  send_error text,
  policy_proof_id text,
  provider_message_id text,
  provider text,
  metadata jsonb,
  sent_at timestamptz,
  created_at timestamptz,
  updated_at timestamptz
);

alter table if exists public.marketing_campaign_recipients add column if not exists send_error text;
alter table if exists public.marketing_campaign_recipients add column if not exists policy_proof_id text;
alter table if exists public.marketing_campaign_recipients add column if not exists provider_message_id text;
alter table if exists public.marketing_campaign_recipients add column if not exists provider text;
alter table if exists public.marketing_campaign_recipients add column if not exists metadata jsonb;
alter table if exists public.marketing_campaign_recipients add column if not exists sent_at timestamptz;
alter table if exists public.marketing_campaign_recipients add column if not exists created_at timestamptz;
alter table if exists public.marketing_campaign_recipients add column if not exists updated_at timestamptz;
alter table if exists public.marketing_campaign_recipients add column if not exists segment text;
alter table if exists public.marketing_campaign_recipients add column if not exists send_status text;

update public.marketing_campaign_recipients
set send_status = coalesce(nullif(send_status, ''), 'pending'),
    created_at = coalesce(created_at, now()),
    updated_at = coalesce(updated_at, now())
where true;

alter table if exists public.marketing_campaign_recipients alter column send_status set default 'pending';
alter table if exists public.marketing_campaign_recipients alter column created_at set default now();
alter table if exists public.marketing_campaign_recipients alter column updated_at set default now();

do $$
begin
  if to_regclass('public.marketing_campaign_recipients') is not null then
    alter table public.marketing_campaign_recipients
      drop constraint if exists marketing_campaign_recipients_segment_check;
    alter table public.marketing_campaign_recipients
      add constraint marketing_campaign_recipients_segment_check
      check (segment is null or segment in ('clients', 'leads'));

    alter table public.marketing_campaign_recipients
      drop constraint if exists marketing_campaign_recipients_send_status_check;
    alter table public.marketing_campaign_recipients
      add constraint marketing_campaign_recipients_send_status_check
      check (send_status in ('pending', 'sent', 'failed', 'blocked_policy', 'skipped'));
  end if;
end
$$;

create unique index if not exists ux_marketing_campaign_recipients_campaign_recipient
  on public.marketing_campaign_recipients (campaign_id, recipient_key);
create index if not exists idx_marketing_campaign_recipients_client_key
  on public.marketing_campaign_recipients (client_id, recipient_key);
create index if not exists idx_marketing_campaign_recipients_campaign_status
  on public.marketing_campaign_recipients (campaign_id, send_status);

-- -----------------------------------------------------------------------------
-- marketing_campaign_events
-- -----------------------------------------------------------------------------
create table if not exists public.marketing_campaign_events (
  id uuid primary key default gen_random_uuid(),
  client_id uuid,
  campaign_id uuid,
  recipient_key text,
  event_type text,
  metadata jsonb,
  created_at timestamptz
);

alter table if exists public.marketing_campaign_events add column if not exists metadata jsonb;
alter table if exists public.marketing_campaign_events add column if not exists created_at timestamptz;

update public.marketing_campaign_events
set created_at = coalesce(created_at, now())
where true;

alter table if exists public.marketing_campaign_events alter column created_at set default now();

create index if not exists idx_marketing_campaign_events_client_campaign
  on public.marketing_campaign_events (client_id, campaign_id, created_at desc);

-- Ensure RLS flag matches app expectations.
alter table if exists public.marketing_campaigns enable row level security;
alter table if exists public.marketing_campaign_recipients enable row level security;
alter table if exists public.marketing_campaign_events enable row level security;

commit;
