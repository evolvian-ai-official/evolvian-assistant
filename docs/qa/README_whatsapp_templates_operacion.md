# README Operativo: Templates WhatsApp (Meta) en Producción

Este documento define cómo manejar templates de WhatsApp en producción usando `meta_approved_templates` como fuente de verdad, incluyendo cambios seguros, migración de recordatorios en cola y recomendaciones para evitar incidentes.

## Objetivo

- Centralizar cambios en `meta_approved_templates` (fuente de verdad).
- Evitar cambios manuales por `client_id`.
- Hacer rollout/rollback seguros cuando se cambia un template de WhatsApp.
- Proteger confirmaciones, cancelaciones y reminders en producción.

## Tablas clave y responsabilidades

### `meta_approved_templates` (fuente de verdad canónica)

Define el catálogo global de templates WhatsApp que Evolvian puede usar.

Campos clave:
- `id` (uuid): identidad canónica
- `template_name` (text): nombre técnico que se usa en Meta
- `language` (text): `es_MX`, `en_US`, etc.
- `type` (text): `appointment_confirmation`, `appointment_reminder`, `appointment_cancellation`
- `is_active` (bool): disponibilidad global en runtime/catálogo
- `provision_enabled` (bool): si se puede provisionar/sincronizar a cuentas cliente
- `buttons_json` (jsonb): definición de botones al crear/provisionar templates en Meta

### `message_templates` (binding por cliente)

Representa la configuración usada por cada cliente (incluye WhatsApp, email, widget).

Para WhatsApp:
- Debe apuntar a `meta_template_id` (`FK` a `meta_approved_templates.id`)
- Funciona como binding/cache por cliente (no como fuente de verdad)

### `client_whatsapp_templates` (estado de sync con Meta por cliente)

Cache del estado de cada template canónico en la cuenta Meta del cliente.

Campos útiles:
- `status` (`active`, `pending`, `inactive`, `unknown`)
- `is_active` (bool): estado activo remoto normalizado
- `meta_template_name` (nombre provisionado en Meta para ese cliente)

### `appointment_reminders` (cola)

Cola de recordatorios agendados.

Importante:
- Guarda `template_id` (FK a `message_templates.id`)
- No guarda snapshot del contenido del template
- Al ejecutar, vuelve a validar `message_templates` y `meta_approved_templates`

## Qué campo controla qué

### Visibilidad/uso en runtime

`meta_approved_templates.is_active`

Si está en `false`:
- el template debe considerarse apagado globalmente
- puede dejar de aparecer en catálogos/resolución
- confirmaciones/cancelaciones/reminders nuevos pueden dejar de enviarse si dependían de ese template

### Provisionamiento/sync hacia Meta

`meta_approved_templates.provision_enabled`

Si está en `false`:
- el sync no debe crear/provisionar ese template en nuevas cuentas cliente
- puede mantenerse visible si `is_active = true`

## Reglas de operación (muy importantes)

1. No renombrar (`template_name`) una fila canónica existente en producción si ya está en uso.
2. Para cambios estructurales (botones, texto mayor, formato), crear una nueva fila canónica (`UUID` nuevo + `template_name` nuevo).
3. Esperar aprobación/estado activo en Meta antes de cortar tráfico al template nuevo.
4. Migrar `appointment_reminders` pendientes antes de desactivar el template viejo.
5. Desactivar globalmente desde `meta_approved_templates`, no cliente por cliente.

## Qué pasa si cambias `template_name` en DB

Ejemplo:
- `appointment_cancellation_v1` -> `cancelar_cita_cliente_v2`

Efectos:
- El runtime intentará enviar `cancelar_cita_cliente_v2`
- Si ese nombre no existe/aprobado en Meta para el cliente, el envío puede fallar
- El sync lo tratará como template nuevo (no renombra el existente en Meta)

Conclusión:
- `template_name` es identidad técnica, no solo label

## Qué pasa con el botón "Cancel" en WhatsApp

- El botón no se renderiza desde la app al enviar.
- El envío de template a Meta manda `template_name + language + parámetros`.
- Meta renderiza los botones si la versión del template (aprobada y activa) en la cuenta Meta del cliente ya incluye esos botones.
- `buttons_json` en `meta_approved_templates` se usa para provisionar/crear el template en Meta (no para dibujar el botón localmente al enviar).

Si editaste un template en Meta y quedó en `pending` / `calidad pendiente`, puedes seguir recibiendo una versión activa anterior sin botón.

## Flujos y riesgos por tipo de envío

### Confirmación de cita (inmediato)

- Se envía al crear la cita
- No usa cola `appointment_reminders`
- Si desactivas el template canónico, futuras confirmaciones pueden no enviarse

### Cancelación de cita (inmediato)

- Se envía al cancelar la cita
- No usa cola `appointment_reminders`
- Si desactivas el template canónico, futuras cancelaciones pueden no enviarse

### Reminder (en cola)

- Sí usa `appointment_reminders`
- Al ejecutar, revalida template local + canónico
- Si desactivas un canónico usado por reminders pendientes, esos reminders pueden terminar en `failed`

## Estrategia segura de cambio (sin afectar producción)

### Escenario A: apagar globalmente un template (sin reemplazo)

Usar cuando quieres detener uso inmediato del template.

Riesgo:
- Confirmaciones/cancelaciones nuevas pueden dejar de enviarse
- Reminders pendientes con ese template pueden fallar si no se migran

### Escenario B: dejar de provisionar a nuevos clientes, pero mantener uso actual

Usar cuando no quieres más despliegue pero no quieres apagar runtime.

Acción:
- `is_active = true`
- `provision_enabled = false`

### Escenario C: reemplazar template en producción (recomendado)

Secuencia:
1. Crear nueva fila en `meta_approved_templates` (nuevo `id`, nuevo `template_name`)
2. Esperar sync/aprobación en Meta (`client_whatsapp_templates.status = active`)
3. Migrar reminders pendientes (`appointment_reminders.status = 'pending'`) al nuevo `template_id`
4. Desactivar template viejo en `meta_approved_templates`
5. (Opcional) desactivar bindings viejos en `message_templates`

## Queries: diagnóstico

### 1) Ver plantilla canónica

```sql
SELECT
  id,
  template_name,
  type,
  language,
  is_active,
  provision_enabled,
  buttons_json,
  updated_at
FROM public.meta_approved_templates
WHERE id = 'd3f6a9c1-4b72-4f1d-8e2a-7c9b5a1d3e44'::uuid;
```

### 2) Ver bindings por cliente para una plantilla canónica

```sql
SELECT
  mt.id AS message_template_id,
  mt.client_id,
  mt.channel,
  mt.type,
  mt.language_family,
  mt.locale_code,
  mt.is_active,
  mt.meta_template_id,
  mt.updated_at
FROM public.message_templates mt
WHERE mt.channel = 'whatsapp'
  AND mt.meta_template_id = 'd3f6a9c1-4b72-4f1d-8e2a-7c9b5a1d3e44'::uuid
ORDER BY mt.updated_at DESC;
```

### 3) Ver estado de sync en Meta por cliente

```sql
SELECT
  cwt.client_id,
  cwt.meta_template_id,
  cwt.meta_template_name,
  cwt.status,
  cwt.is_active,
  cwt.status_reason,
  cwt.last_synced_at,
  cwt.updated_at
FROM public.client_whatsapp_templates cwt
WHERE cwt.meta_template_id = 'd3f6a9c1-4b72-4f1d-8e2a-7c9b5a1d3e44'::uuid
ORDER BY cwt.updated_at DESC;
```

### 4) Ver reminders pendientes que dependen de una plantilla canónica

```sql
SELECT
  ar.id AS reminder_id,
  ar.client_id,
  ar.appointment_id,
  ar.channel,
  ar.status,
  ar.scheduled_at,
  ar.template_id,
  mt.meta_template_id,
  mt.type AS template_type
FROM public.appointment_reminders ar
JOIN public.message_templates mt ON mt.id = ar.template_id
WHERE ar.channel = 'whatsapp'
  AND ar.status = 'pending'
  AND mt.meta_template_id = 'd3f6a9c1-4b72-4f1d-8e2a-7c9b5a1d3e44'::uuid
ORDER BY ar.scheduled_at ASC;
```

## Queries: cambios globales

### 5) Apagar template globalmente (runtime + provisioning)

```sql
UPDATE public.meta_approved_templates
SET is_active = false,
    provision_enabled = false,
    updated_at = now()
WHERE id = 'd3f6a9c1-4b72-4f1d-8e2a-7c9b5a1d3e44'::uuid;
```

### 6) Solo dejar de provisionar (mantener uso actual)

```sql
UPDATE public.meta_approved_templates
SET provision_enabled = false,
    updated_at = now()
WHERE id = 'd3f6a9c1-4b72-4f1d-8e2a-7c9b5a1d3e44'::uuid;
```

### 7) Reactivar template globalmente

```sql
UPDATE public.meta_approved_templates
SET is_active = true,
    provision_enabled = true,
    updated_at = now()
WHERE id = 'd3f6a9c1-4b72-4f1d-8e2a-7c9b5a1d3e44'::uuid;
```

## Queries: migración segura de reminders pendientes (template viejo -> nuevo)

Supuestos:
- Ya existe el template nuevo
- Ya está aprobado/activo en Meta para los clientes afectados
- Solo moveremos reminders `pending`

### 8) Preview del mapeo (viejo canónico -> nuevo canónico, por cliente)

Reemplaza:
- `OLD_META_ID`
- `NEW_META_ID`

```sql
WITH old_bindings AS (
  SELECT
    mt.id AS old_template_id,
    mt.client_id,
    mt.type,
    mt.language_family,
    mt.locale_code
  FROM public.message_templates mt
  WHERE mt.channel = 'whatsapp'
    AND mt.meta_template_id = 'OLD_META_ID'::uuid
),
new_bindings AS (
  SELECT
    mt.id AS new_template_id,
    mt.client_id,
    mt.type,
    mt.language_family,
    mt.locale_code
  FROM public.message_templates mt
  WHERE mt.channel = 'whatsapp'
    AND mt.meta_template_id = 'NEW_META_ID'::uuid
    AND coalesce(mt.is_active, true) = true
)
SELECT
  ob.client_id,
  ob.old_template_id,
  nb.new_template_id,
  ob.type,
  ob.language_family,
  ob.locale_code
FROM old_bindings ob
JOIN new_bindings nb
  ON nb.client_id = ob.client_id
 AND nb.type = ob.type
 AND coalesce(nb.language_family, '') = coalesce(ob.language_family, '')
 AND coalesce(nb.locale_code, '') = coalesce(ob.locale_code, '')
ORDER BY ob.client_id;
```

### 9) Contar reminders pendientes que serían migrados

```sql
WITH old_bindings AS (
  SELECT id AS old_template_id, client_id, type, language_family, locale_code
  FROM public.message_templates
  WHERE channel = 'whatsapp'
    AND meta_template_id = 'OLD_META_ID'::uuid
),
new_bindings AS (
  SELECT id AS new_template_id, client_id, type, language_family, locale_code
  FROM public.message_templates
  WHERE channel = 'whatsapp'
    AND meta_template_id = 'NEW_META_ID'::uuid
    AND coalesce(is_active, true) = true
),
mapping AS (
  SELECT ob.old_template_id, nb.new_template_id
  FROM old_bindings ob
  JOIN new_bindings nb
    ON nb.client_id = ob.client_id
   AND nb.type = ob.type
   AND coalesce(nb.language_family, '') = coalesce(ob.language_family, '')
   AND coalesce(nb.locale_code, '') = coalesce(ob.locale_code, '')
)
SELECT count(*) AS pending_reminders_to_migrate
FROM public.appointment_reminders ar
JOIN mapping m ON m.old_template_id = ar.template_id
WHERE ar.channel = 'whatsapp'
  AND ar.status = 'pending';
```

### 10) Migrar reminders pendientes (UPDATE real)

```sql
WITH old_bindings AS (
  SELECT id AS old_template_id, client_id, type, language_family, locale_code
  FROM public.message_templates
  WHERE channel = 'whatsapp'
    AND meta_template_id = 'OLD_META_ID'::uuid
),
new_bindings AS (
  SELECT id AS new_template_id, client_id, type, language_family, locale_code
  FROM public.message_templates
  WHERE channel = 'whatsapp'
    AND meta_template_id = 'NEW_META_ID'::uuid
    AND coalesce(is_active, true) = true
),
mapping AS (
  SELECT ob.old_template_id, nb.new_template_id
  FROM old_bindings ob
  JOIN new_bindings nb
    ON nb.client_id = ob.client_id
   AND nb.type = ob.type
   AND coalesce(nb.language_family, '') = coalesce(ob.language_family, '')
   AND coalesce(nb.locale_code, '') = coalesce(ob.locale_code, '')
)
UPDATE public.appointment_reminders ar
SET template_id = m.new_template_id,
    updated_at = now()
FROM mapping m
WHERE ar.template_id = m.old_template_id
  AND ar.channel = 'whatsapp'
  AND ar.status = 'pending';
```

### 11) Verificar que ya no queden pendientes usando el template viejo

```sql
SELECT count(*) AS pending_old_template
FROM public.appointment_reminders ar
JOIN public.message_templates mt ON mt.id = ar.template_id
WHERE ar.channel = 'whatsapp'
  AND ar.status = 'pending'
  AND mt.meta_template_id = 'OLD_META_ID'::uuid;
```

## Query de contingencia (si el parche de runtime aún no está desplegado)

Mientras se despliega el parche que hace respetar `meta_approved_templates.is_active` en el resolvedor de citas, apagar también los bindings locales evita que se siga usando el template viejo.

### 12) Apagar bindings WhatsApp por plantilla canónica

```sql
UPDATE public.message_templates
SET is_active = false,
    updated_at = now()
WHERE channel = 'whatsapp'
  AND meta_template_id = 'd3f6a9c1-4b72-4f1d-8e2a-7c9b5a1d3e44'::uuid;
```

## Query de rollback (si algo sale mal)

### 13) Revertir reminders pendientes al template viejo

```sql
WITH old_bindings AS (
  SELECT id AS old_template_id, client_id, type, language_family, locale_code
  FROM public.message_templates
  WHERE channel = 'whatsapp'
    AND meta_template_id = 'OLD_META_ID'::uuid
),
new_bindings AS (
  SELECT id AS new_template_id, client_id, type, language_family, locale_code
  FROM public.message_templates
  WHERE channel = 'whatsapp'
    AND meta_template_id = 'NEW_META_ID'::uuid
),
mapping AS (
  SELECT ob.old_template_id, nb.new_template_id
  FROM old_bindings ob
  JOIN new_bindings nb
    ON nb.client_id = ob.client_id
   AND nb.type = ob.type
   AND coalesce(nb.language_family, '') = coalesce(ob.language_family, '')
   AND coalesce(nb.locale_code, '') = coalesce(ob.locale_code, '')
)
UPDATE public.appointment_reminders ar
SET template_id = m.old_template_id,
    updated_at = now()
FROM mapping m
WHERE ar.template_id = m.new_template_id
  AND ar.channel = 'whatsapp'
  AND ar.status = 'pending';
```

## Escalamiento y buenas prácticas para volumen alto

Para tablas grandes (muchos reminders):

1. Ejecutar primero `SELECT count(*)` y `preview`.
2. Migrar solo `status = 'pending'`.
3. Evitar tocar `processing` durante ventanas activas de workers.
4. Ejecutar en ventana de bajo tráfico si esperas locks relevantes.
5. Validar después con métricas:
   - `sent/failed` de reminders
   - `client_whatsapp_templates.status`
   - logs de `Meta template send failed`

## Checklist de cambio seguro (operación)

1. Crear template nuevo en `meta_approved_templates` (fila separada, `UUID` nuevo)
2. Confirmar `is_active = true` y `provision_enabled = true`
3. Confirmar sync y estado `active` en `client_whatsapp_templates`
4. Migrar reminders `pending`
5. Desactivar template viejo en `meta_approved_templates`
6. (Si parche no desplegado) desactivar bindings en `message_templates`
7. Verificar envíos en producción

## Nota de implementación (backend)

El runtime debe respetar `meta_approved_templates.is_active` al resolver templates WhatsApp (fuente de verdad). Si ese parche no está desplegado, `message_templates.is_active` puede seguir permitiendo uso de un canónico apagado.

