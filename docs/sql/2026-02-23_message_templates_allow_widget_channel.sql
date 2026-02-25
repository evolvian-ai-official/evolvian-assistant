-- Allow channel='widget' in message_templates.
-- Some environments enforce a check constraint named message_templates_channel_check
-- with only ('email','whatsapp').

do $$
begin
  if to_regclass('public.message_templates') is null then
    raise notice 'public.message_templates does not exist; skipping channel constraint patch';
    return;
  end if;

  alter table public.message_templates
    drop constraint if exists message_templates_channel_check;

  alter table public.message_templates
    add constraint message_templates_channel_check
    check (channel in ('email', 'whatsapp', 'widget'));
end $$;
