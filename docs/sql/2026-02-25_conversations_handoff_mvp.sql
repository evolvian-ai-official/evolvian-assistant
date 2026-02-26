-- Phase 2 foundation: operational conversation layer on top of public.history
-- Keeps history append-only and adds inbox/handoff state for AI -> human workflows.

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  session_id text not null,
  status text not null default 'open',
  primary_channel text not null default 'widget',
  contact_name text null,
  contact_email text null,
  contact_phone text null,
  assigned_user_id uuid null references public.users(id) on delete set null,
  priority text not null default 'normal',
  latest_message_at timestamptz null,
  last_message_preview text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint conversations_status_chk check (status in ('open', 'needs_human', 'human_in_progress', 'ai_resolved', 'resolved', 'closed')),
  constraint conversations_priority_chk check (priority in ('low', 'normal', 'high', 'urgent'))
);

create unique index if not exists conversations_client_session_uidx
  on public.conversations (client_id, session_id);

create index if not exists conversations_client_status_idx
  on public.conversations (client_id, status, latest_message_at desc nulls last);

create table if not exists public.conversation_handoff_requests (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  conversation_id uuid null references public.conversations(id) on delete set null,
  session_id text not null,
  channel text not null default 'widget',
  trigger text not null default 'manual_request',
  reason text not null default 'user_requested_human',
  status text not null default 'open',
  confidence_score numeric null,
  contact_name text not null,
  contact_email text null,
  contact_phone text null,
  accepted_terms boolean not null default false,
  accepted_email_marketing boolean not null default false,
  consent_token uuid null,
  last_user_message text null,
  last_ai_message text null,
  assigned_user_id uuid null references public.users(id) on delete set null,
  internal_resolution_note text null,
  ip_address text null,
  user_agent text null,
  metadata jsonb null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz null,
  constraint conversation_handoff_requests_status_chk
    check (status in ('open', 'assigned', 'in_progress', 'resolved', 'dismissed'))
);

create index if not exists conversation_handoff_requests_client_status_idx
  on public.conversation_handoff_requests (client_id, status, created_at desc);

create index if not exists conversation_handoff_requests_conversation_idx
  on public.conversation_handoff_requests (conversation_id, created_at desc);

create table if not exists public.conversation_internal_notes (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  handoff_request_id uuid null references public.conversation_handoff_requests(id) on delete set null,
  author_user_id uuid null references public.users(id) on delete set null,
  note text not null,
  created_at timestamptz not null default now()
);

create index if not exists conversation_internal_notes_conversation_idx
  on public.conversation_internal_notes (conversation_id, created_at desc);

create table if not exists public.conversation_alerts (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  conversation_id uuid null references public.conversations(id) on delete set null,
  source_handoff_request_id uuid null references public.conversation_handoff_requests(id) on delete set null,
  alert_type text not null default 'human_intervention',
  status text not null default 'open',
  priority text not null default 'normal',
  assigned_user_id uuid null references public.users(id) on delete set null,
  title text not null,
  body text null,
  metadata jsonb null,
  created_at timestamptz not null default now(),
  resolved_at timestamptz null,
  constraint conversation_alerts_status_chk check (status in ('open', 'acknowledged', 'resolved', 'dismissed')),
  constraint conversation_alerts_priority_chk check (priority in ('low', 'normal', 'high', 'urgent'))
);

create index if not exists conversation_alerts_client_status_idx
  on public.conversation_alerts (client_id, status, created_at desc);
