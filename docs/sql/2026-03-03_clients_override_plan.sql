ALTER TABLE public.clients
ADD COLUMN IF NOT EXISTS override_plan text;

ALTER TABLE public.clients
DROP CONSTRAINT IF EXISTS clients_override_plan_check;

ALTER TABLE public.clients
ADD CONSTRAINT clients_override_plan_check
CHECK (
    override_plan IS NULL
    OR lower(trim(override_plan)) IN ('free', 'starter', 'premium', 'white_label', 'enterprise')
);

COMMENT ON COLUMN public.clients.override_plan IS
'Internal plan override used to bypass Stripe billing logic for strategic partners.';

CREATE INDEX IF NOT EXISTS idx_clients_override_plan_not_null
ON public.clients (override_plan)
WHERE override_plan IS NOT NULL;
