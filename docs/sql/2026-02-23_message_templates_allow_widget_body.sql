-- Allow widget opening-message templates to store body content in message_templates.
-- Existing constraint "body_required_for_email" blocks body for non-email channels in some environments.

do $$
begin
  if to_regclass('public.message_templates') is null then
    raise notice 'public.message_templates does not exist; skipping constraint patch';
    return;
  end if;

  alter table public.message_templates
    drop constraint if exists body_required_for_email;

  -- Require body for channels that are body-driven (email + widget).
  alter table public.message_templates
    add constraint body_required_for_email
    check (
      (channel not in ('email', 'widget'))
      or (body is not null)
    );
end $$;
