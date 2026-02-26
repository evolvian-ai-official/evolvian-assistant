# Direct Scheduling Staging E2E Checklist

Objetivo: validar en `staging` que:
- Los usuarios sí pueden iniciar agenda escribiendo en chat
- Conversaciones no relacionadas NO disparan agenda
- El idioma de respuesta se mantiene en español/inglés

## Alcance

Canales:
- Widget chat
- Email chat
- WhatsApp (Twilio webhook)
- WhatsApp (Meta webhook)

Cobertura mínima recomendada por canal:
- `ES + agenda`
- `EN + agenda`
- `ES + no agenda`
- `EN + no agenda`

Total mínimo: `16` casos (`4 canales x 4 casos`)

## Pre-requisitos (staging)

- Cliente de staging con agenda activa y horarios disponibles
- `public_client_id` del widget
- Canal email ligado al cliente (tabla `channels`)
- Canal WhatsApp ligado al cliente (Twilio/Meta)
- Token interno para `/chat_email`:
  - `EVOLVIAN_INTERNAL_TASK_TOKEN`
- Opcional para validación fuerte por historial:
  - `HISTORY_BEARER_TOKEN` (token de usuario dueño del cliente)
  - `HISTORY_CLIENT_ID`

## Script de smoke test

Archivo:
- `/Users/aldobenitezcortes/Documents/Evolvian_assistant/scripts/qa/direct_scheduling_staging_smoke.py`

Hace:
- Envía casos ES/EN de agenda y no agenda
- Valida respuesta básica (HTTP + heurística)
- Opcional: valida historial (`source_type`, `channel`, `provider`, idioma)

## Ejecución rápida (widget + email)

```bash
export STAGING_BASE_URL="https://tu-staging.example.com"
export WIDGET_PUBLIC_CLIENT_ID="public_client_id_staging"
export EMAIL_CHANNEL_ADDRESS="canal@tu-dominio.com"
export EVOLVIAN_INTERNAL_TASK_TOKEN="..."

python scripts/qa/direct_scheduling_staging_smoke.py
```

## Ejecución con validación por historial (recomendado)

```bash
export STAGING_BASE_URL="https://tu-staging.example.com"
export WIDGET_PUBLIC_CLIENT_ID="public_client_id_staging"
export EMAIL_CHANNEL_ADDRESS="canal@tu-dominio.com"
export EVOLVIAN_INTERNAL_TASK_TOKEN="..."

export HISTORY_BEARER_TOKEN="token_del_usuario_dueno"
export HISTORY_CLIENT_ID="uuid-del-cliente"
export HISTORY_PATH_CANDIDATES="/history,/api/history"

python scripts/qa/direct_scheduling_staging_smoke.py
```

## Habilitar Twilio / Meta en el script (opcional)

Twilio:
```bash
export RUN_TWILIO=true
export TWILIO_WEBHOOK_PATH="/api/twilio-webhook"
export TWILIO_TEST_USER_PHONE="+15557654321"
export TWILIO_AUTH_TOKEN="..."   # si staging valida firma
```

Meta:
```bash
export RUN_META=true
export META_WEBHOOK_PATH="/api/webhooks/meta"
export META_TEST_USER_PHONE_DIGITS="15557654321"
export META_BUSINESS_DISPLAY_PHONE_DIGITS="15551234567"
export META_APP_SECRET="..."     # si staging valida firma
```

Notas:
- En Meta, el script valida aceptación del webhook inbound.
- La respuesta del asistente sale por WhatsApp real; confirmar en el teléfono de prueba.

## Casos manuales mínimos (si no usas el script)

Agenda ES:
- `Quiero agendar una cita para mañana`

Agenda EN:
- `I want to schedule an appointment for tomorrow`

No agenda ES:
- `Qué planes tienen y qué incluye el servicio?`

No agenda EN:
- `What plans do you offer and what is included?`

## Criterios de aceptación

Para casos de agenda:
- Respuesta orientada a disponibilidad/agenda (no respuesta genérica de RAG)
- Idioma coincide con el input (`es` o `en`)
- Si validas historial: `source_type=appointment`

Para casos de no agenda:
- Respuesta comercial/informativa (no abre flujo de agenda)
- Idioma coincide con el input
- Si validas historial: `source_type != appointment` (normalmente `chat`)

## Rutas configurables del script

Defaults:
- Widget: `/api/chat`
- Email: `/chat_email`
- Twilio webhook: `/api/twilio-webhook`
- Meta webhook: `/api/webhooks/meta`
- History (candidatos): `/history,/api/history`

Si tu `staging` usa otras rutas, sobrescribe con variables de entorno.
