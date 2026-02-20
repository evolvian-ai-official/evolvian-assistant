-- Cache WABA id on WhatsApp channel.
-- Preferred column name: wa_business_account_id

ALTER TABLE public.channels
ADD COLUMN IF NOT EXISTS wa_business_account_id text;

