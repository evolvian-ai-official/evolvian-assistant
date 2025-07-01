
## 📦 2025-05-27 – Sync QA → Producción

Este despliegue sincroniza los entornos de QA y Producción en Evolvian con los siguientes cambios clave:

### ✅ Backend (FastAPI)
- Nuevos endpoints Stripe:
  - `create_checkout_session.py`
  - `stripe_cancel_subscription.py`
  - `stripe_change_plan.py`
  - `stripe_webhook.py`
- Modularización en `utils/stripe_plan_utils.py`
- Actualización de `client_settings_api.py` y `supabase_client.py`:
  - Se soportan los campos `subscription_id`, `subscription_start`, `subscription_end`
  - Se asegura la integración de `public_client_id` para el widget

### ✅ Frontend (React)
- Nuevos componentes en `settings/`:
  - `PlanInfo.jsx`
  - `PromptSettings.jsx`
  - `WidgetSettings.jsx`
  - `FeatureList.jsx`
- Refactor en `ClientSettings.jsx` para reflejar plan, prompt y branding
- Nuevo módulo de toast: `use-toast.ts`
- Mejoras en hooks (`useClientId.js`) e internacionalización (`i18n.js`)
- Se asegura compatibilidad con control de planes y permisos por feature

---


