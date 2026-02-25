-- Add reusable opening_message template type for widget/other channels.
-- Compatible with environments where template_types uses either is_active or active.

do $$
declare
  has_is_active boolean := false;
  has_active boolean := false;
begin
  if to_regclass('public.template_types') is null then
    raise notice 'public.template_types does not exist; skipping opening_message seed';
    return;
  end if;

  select exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'template_types'
      and column_name = 'is_active'
  ) into has_is_active;

  select exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'template_types'
      and column_name = 'active'
  ) into has_active;

  if has_is_active then
    insert into public.template_types (id, description, is_active)
    values ('opening_message', 'Opening message shown when a channel session starts', true)
    on conflict (id) do update
      set description = excluded.description,
          is_active = true;
  elsif has_active then
    insert into public.template_types (id, description, active)
    values ('opening_message', 'Opening message shown when a channel session starts', true)
    on conflict (id) do update
      set description = excluded.description,
          active = true;
  else
    insert into public.template_types (id, description)
    values ('opening_message', 'Opening message shown when a channel session starts')
    on conflict (id) do update
      set description = excluded.description;
  end if;
end $$;
