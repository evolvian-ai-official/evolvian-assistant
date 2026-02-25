-- Supabase linter fix: enable RLS on public tables exposed via PostgREST.
-- Safe for this project because backend writes/reads with SUPABASE_SERVICE_ROLE_KEY.
-- Note: enabling RLS without policies denies anon/authenticated access by default.

alter table if exists public.client_whatsapp_templates
  enable row level security;

alter table if exists public.contactame
  enable row level security;

alter table if exists public.appointment_clients
  enable row level security;
