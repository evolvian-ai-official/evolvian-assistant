-- Directory of end-clients (contacts) used by Appointments.
-- This lets the dashboard store contacts before they have an appointment
-- and keeps them editable independently from appointment rows.

create table if not exists public.appointment_clients (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  user_name text not null,
  user_email text null,
  user_phone text null,
  normalized_email text null,
  normalized_phone text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists appointment_clients_client_id_idx
  on public.appointment_clients (client_id);

create unique index if not exists appointment_clients_client_email_uidx
  on public.appointment_clients (client_id, normalized_email)
  where normalized_email is not null;

create unique index if not exists appointment_clients_client_phone_uidx
  on public.appointment_clients (client_id, normalized_phone)
  where normalized_phone is not null;
