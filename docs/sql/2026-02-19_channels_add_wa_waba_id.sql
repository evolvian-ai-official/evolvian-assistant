-- Cache WABA id on the connected WhatsApp channel
-- so template sync/status refresh does not need to resolve it each time.

ALTER TABLE public.channels
ADD COLUMN IF NOT EXISTS wa_waba_id text;

