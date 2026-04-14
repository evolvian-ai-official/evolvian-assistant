begin;

update public.plans
set
  price_usd = 0,
  max_messages = 500,
  max_documents = 3,
  is_unlimited = false
where lower(trim(id)) = 'free';

update public.plans
set
  price_usd = 19,
  max_messages = 2000,
  max_documents = 3,
  is_unlimited = false
where lower(trim(id)) = 'starter';

update public.plans
set
  price_usd = 49,
  max_messages = 5000,
  max_documents = 3,
  is_unlimited = false
where lower(trim(id)) = 'premium';

commit;
