ALTER TABLE public.client_settings
ADD COLUMN IF NOT EXISTS launcher_icon_url text;

COMMENT ON COLUMN public.client_settings.launcher_icon_url IS
'Premium widget customization: optional absolute URL for the floating launcher icon. Falls back to the default Evolvian icon when null.';
