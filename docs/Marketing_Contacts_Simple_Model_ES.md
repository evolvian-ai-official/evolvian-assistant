# Marketing Contacts Simple Model

## Objetivo

Tener un modelo simple y tenant-scoped para responder rápido:

- quién sí puede recibir campañas
- quién hizo unsubscribe
- quién marcó `me interesa`
- quién marcó `no me interesa`
- qué handoff se generó por ese interés

## Tablas

- `public.marketing_contacts`
  - estado actual por persona y `client_id`
  - aquí respondes opt-in / opt-out / interés actual

- `public.public_privacy_requests`
  - ledger legal y operativo de privacy / unsubscribe
  - aquí vive el `marketing_opt_out`

- `public.marketing_campaign_events`
  - historial por campaña
  - aquí respondes `interest_yes`, `interest_no`, `opt_out`

- `public.conversation_handoff_requests`
  - tickets de seguimiento humano

## Importante

`contactame` y `newsletter_subscribers` no tienen `client_id` en el esquema actual.

Eso significa que no se deben mezclar automáticamente con el modelo multiempresa.
Si quieres meter también los leads propios de Evolvian aquí, necesitas un `client_id`
interno para Evolvian y un backfill separado.

## Queries

### 1. Quién sí puede recibir campañas por email

```sql
select *
from public.marketing_contacts
where client_id = :client_id
  and normalized_email is not null
  and email_opt_in = true
  and email_unsubscribed = false
  and interest_status <> 'not_interested'
order by last_seen_at desc;
```

### 2. Quién hizo unsubscribe por email

```sql
select *
from public.marketing_contacts
where client_id = :client_id
  and email_unsubscribed = true
order by last_seen_at desc;
```

### 3. Quién sí puede recibir campañas por WhatsApp

```sql
select *
from public.marketing_contacts
where client_id = :client_id
  and normalized_phone is not null
  and whatsapp_opt_in = true
  and whatsapp_unsubscribed = false
  and interest_status <> 'not_interested'
order by last_seen_at desc;
```

### 4. Quién hizo unsubscribe por WhatsApp

```sql
select *
from public.marketing_contacts
where client_id = :client_id
  and whatsapp_unsubscribed = true
order by last_seen_at desc;
```

### 5. Quién marcó `me interesa` en una campaña de WhatsApp

```sql
select
  e.created_at,
  r.recipient_name,
  r.email,
  r.phone,
  r.recipient_key
from public.marketing_campaign_events e
join public.marketing_campaign_recipients r
  on r.campaign_id = e.campaign_id
 and coalesce(r.recipient_key, '') = coalesce(e.recipient_key, '')
where e.client_id = :client_id
  and e.campaign_id = :campaign_id
  and e.event_type = 'interest_yes'
order by e.created_at desc;
```

### 6. Quién marcó `no me interesa` en una campaña de WhatsApp

```sql
select
  e.created_at,
  r.recipient_name,
  r.email,
  r.phone,
  r.recipient_key
from public.marketing_campaign_events e
join public.marketing_campaign_recipients r
  on r.campaign_id = e.campaign_id
 and coalesce(r.recipient_key, '') = coalesce(e.recipient_key, '')
where e.client_id = :client_id
  and e.campaign_id = :campaign_id
  and e.event_type = 'interest_no'
order by e.created_at desc;
```

### 7. Lo mismo para email

Usa exactamente las mismas queries si tus eventos de email también escriben
`interest_yes` y `interest_no` en `marketing_campaign_events`.

La diferencia no debe ser la tabla; debe ser el valor de `campaign_id` y el canal
guardado en `metadata` si quieres reportarlo.

### 8. Qué handoff humano salió de un `me interesa`

Recomendación operativa:

- cuando entre `interest_yes`
- guarda el evento en `marketing_campaign_events`
- crea el handoff en `conversation_handoff_requests`
- guarda en `metadata` al menos:
  - `campaign_id`
  - `recipient_key`
  - `trigger = marketing_interest`

Entonces la query queda:

```sql
select
  h.id as handoff_id,
  h.created_at,
  h.status,
  h.contact_name,
  h.contact_email,
  h.contact_phone,
  h.metadata
from public.conversation_handoff_requests h
where h.client_id = :client_id
  and lower(coalesce(h.trigger, '')) = 'marketing_interest'
  and coalesce(h.metadata->>'campaign_id', '') = :campaign_id::text
order by h.created_at desc;
```

## Regla simple de producto

- estado actual del contacto: `marketing_contacts`
- evidencia legal / unsubscribe: `public_privacy_requests`
- comportamiento por campaña: `marketing_campaign_events`
- seguimiento humano: `conversation_handoff_requests`
