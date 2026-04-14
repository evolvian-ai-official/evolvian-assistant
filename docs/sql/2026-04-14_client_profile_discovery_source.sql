alter table public.client_profile
  add column if not exists discovery_source text null;

comment on column public.client_profile.discovery_source is
  'How the client found Evolvian during onboarding (Instagram, LinkedIn, Google, Facebook, TikTok, Email, etc.).';
