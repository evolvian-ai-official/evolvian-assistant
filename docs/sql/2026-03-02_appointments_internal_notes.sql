-- Optional internal notes/comments for appointments.
-- Internal-use only: not intended for outbound customer messaging.

alter table if exists public.appointments
  add column if not exists internal_notes text;

comment on column public.appointments.internal_notes is
  'Optional internal notes/comments for staff use in appointment history.';
