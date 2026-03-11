# WhatsApp Embedded Signup Rollout Checklist (SaaS)

Objetivo: estandarizar el onboarding de WhatsApp para todos los clientes de Evolvian con el menor trabajo manual posible, manteniendo visibilidad del progreso y seguridad de credenciales.

## 1. Alcance y resultado esperado

Al finalizar este rollout:
- El cliente conecta su cuenta de Meta desde Evolvian.
- Evolvian obtiene/guarda credenciales por tenant de forma segura (cifrado).
- Evolvian valida el binding `WABA + phone_number_id`.
- Evolvian suscribe la app al WABA (`POST /{waba-id}/subscribed_apps`).
- Evolvian muestra progreso tras bambalinas y estado del numero (`approved` o `pending`).
- Soporte usa un playbook unico para diagnostico y resolucion.

Fuera de alcance:
- Forzar aprobacion de numero en Meta (depende de compliance/verification del cliente en Meta).
- Aprobar templates automaticamente por fuera de los procesos de Meta.

## 2. Roles y responsabilidades

Producto:
- Definir UX final de `Conectar con Meta`.
- Aprobar copy de estados, errores y recomendaciones.

Backend:
- Mantener endpoints y validaciones de setup.
- Mantener redaccion de logs sensibles.

Frontend:
- Mostrar timeline de setup, timeout y sugerencias.
- Soportar reintentos sin romper estado.

QA:
- Ejecutar matriz E2E por escenarios.
- Validar no regresiones en webhook/ruteo por tenant.

Soporte:
- Operar checklist de diagnostico por cliente.
- Escalar solo cuando no sea problema de permisos Meta.

## 3. Pre-requisitos tecnicos (una sola vez)

- [ ] App de Meta con producto WhatsApp habilitado.
- [ ] Permisos disponibles en app: `whatsapp_business_management`, `whatsapp_business_messaging`, `business_management`.
- [ ] Webhook de Meta activo apuntando a Evolvian.
- [ ] Verificacion de firma webhook activa en backend.
- [ ] Cifrado de `wa_token` habilitado en produccion.
- [ ] Redaccion de logs activa para `token`, `waba_id`, `wa_business_account_id`.

## 4. Flujo E2E objetivo por cliente

Paso 1 (Cliente en Evolvian):
- [ ] Clic en `Conectar con Meta`.

Paso 2 (Cliente en Meta):
- [ ] Selecciona negocio, WABA y numero.
- [ ] Acepta permisos requeridos.

Paso 3 (Evolvian automatico):
- [ ] Recibe autorizacion del tenant.
- [ ] Resuelve `waba_id` y `phone_number_id`.
- [ ] Valida binding `WABA + phone`.
- [ ] Ejecuta `POST /{waba-id}/subscribed_apps`.
- [ ] Consulta estado del numero en Meta.
- [ ] Guarda canal activo en `channels` con token cifrado.
- [ ] Expone progreso y recomendaciones en UI.

Paso 4 (Resultado):
- [ ] `setup_complete=true` cuando todo esta listo.
- [ ] Si queda `pending`, UI muestra estado real + accion sugerida.

## 5. Automatizado vs manual

Automatizado por Evolvian:
- [ ] Validacion tecnica de credenciales y binding.
- [ ] Suscripcion de app al WABA.
- [ ] Polling de estado del numero.
- [ ] Diagnostico y timeout con sugerencias.

Requiere accion del cliente en Meta:
- [ ] Verificacion del negocio/numero.
- [ ] Permisos correctos en su entorno Meta.
- [ ] Aprobacion de templates cuando aplique.

## 6. Checklist de QA (staging)

Caso A: Happy path (numero aprobado)
- [ ] Conectar cuenta Meta desde UI.
- [ ] Ver pasos `done` en timeline.
- [ ] Confirmar `setup_complete=true`.
- [ ] Enviar mensaje de prueba inbound y validar respuesta outbound.

Caso B: Numero pendiente
- [ ] Conectar cuenta Meta valida con numero no aprobado.
- [ ] Confirmar pasos tecnicos en `done` y `phone_approval=pending`.
- [ ] Confirmar timeout y sugerencias accionables en UI.

Caso C: Permiso insuficiente (#200)
- [ ] Usar token sin scopes WhatsApp.
- [ ] Confirmar error claro en UI.
- [ ] Confirmar logs sin token/WABA en claro.

Caso D: Cliente desconecta y reconecta
- [ ] Ejecutar `Desconectar WhatsApp`.
- [ ] Confirmar limpieza de estado local de setup.
- [ ] Reconectar y repetir flujo completo.

Caso E: Multi-tenant isolation
- [ ] Conectar dos clientes diferentes.
- [ ] Confirmar que cada tenant usa su propio `phone_number_id`.
- [ ] Confirmar que webhook enruta correctamente por tenant.

## 7. Checklist operativo de soporte

Cuando un cliente reporta "sigue pending":
- [ ] Revisar timeline en UI de Evolvian.
- [ ] Verificar si `waba_subscription` esta en `done`.
- [ ] Verificar estado reportado de `phone_approval`.
- [ ] Confirmar que no hay error de permisos en recomendaciones.
- [ ] Si todo tecnico esta bien, indicar accion en Meta (verification/compliance) y ventana de reintento.

Cuando un cliente reporta "error de permisos":
- [ ] Confirmar que su token tenga scopes WhatsApp.
- [ ] Confirmar que su system user tenga acceso a app y WABA.
- [ ] Confirmar que negocio/WABA correspondan al mismo tenant.
- [ ] Reintentar conexion desde Evolvian.

## 8. Seguridad y observabilidad

- [ ] No loggear tokens ni WABA en claro.
- [ ] Usar solo fingerprint para identificadores sensibles en logs.
- [ ] No exponer `wa_token` en respuestas API.
- [ ] Monitorear tasa de fallos por `permissions_error`, `pending_timeout`, `binding_failed`.

## 9. Rollback plan

Si se detecta regresion en produccion:
- [ ] Deshabilitar CTA de Embedded Signup temporalmente (feature flag o ocultar boton).
- [ ] Mantener flujo manual de credenciales como fallback.
- [ ] Preservar canales ya conectados (no desconectar automaticamente).
- [ ] Registrar incidente y evidencia (cliente afectado, timestamp, error, mitigacion).

## 10. Criterios de Done del rollout

Tecnico:
- [ ] >= 95% de conexiones nuevas completan `waba_subscription=done`.
- [ ] >= 90% de conexiones nuevas completan setup sin intervencion de soporte.
- [ ] 0 hallazgos de logs con token/WABA en claro.

Operacion:
- [ ] Playbook de soporte publicado y usado por el equipo.
- [ ] QA E2E aprobado en staging y en una ventana de smoke en produccion controlada.
- [ ] Dash de metricas de onboarding disponible (al menos exito, timeout, permisos).

Producto:
- [ ] Copy y UX final aprobados.
- [ ] Mensajes de error/sugerencia validados en ES y EN.

## 11. Evidencia minima a guardar por release

- [ ] Fecha de despliegue.
- [ ] Commit/tag de backend y frontend.
- [ ] Resultado de pruebas QA.
- [ ] Capturas del timeline (happy path y pending path).
- [ ] Lista de incidentes del rollout (si existieron) y resolucion.

