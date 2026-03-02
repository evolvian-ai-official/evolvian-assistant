-- Soft delete support for appointment_clients (clients directory).

begin;

alter table if exists public.appointment_clients
  add column if not exists deleted_at timestamptz null;

-- Rebuild uniqueness so soft-deleted rows don't block re-creation.
drop index if exists public.appointment_clients_client_email_uidx;
create unique index if not exists appointment_clients_client_email_uidx
  on public.appointment_clients (client_id, normalized_email)
  where normalized_email is not null
    and deleted_at is null;

drop index if exists public.appointment_clients_client_phone_uidx;
create unique index if not exists appointment_clients_client_phone_uidx
  on public.appointment_clients (client_id, normalized_phone)
  where normalized_phone is not null
    and deleted_at is null;

create index if not exists appointment_clients_client_deleted_at_idx
  on public.appointment_clients (client_id, deleted_at);

comment on column public.appointment_clients.deleted_at is
  'Soft delete timestamp for directory contacts. Null means active.';

commit;
