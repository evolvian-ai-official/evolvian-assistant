from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import jwt

# ✅ Cargar variables locales de entorno
load_dotenv(".env")
print("🔄 Variables de entorno cargadas desde .env")
print("🔍 GOOGLE_CLIENT_ID:", os.getenv("GOOGLE_CLIENT_ID"))
print("🔍 GOOGLE_CLIENT_SECRET:", os.getenv("GOOGLE_CLIENT_SECRET"))
print("🔍 GOOGLE_REDIRECT_URI_LOCAL:", os.getenv("GOOGLE_REDIRECT_URI_LOCAL"))
print("🔍 GOOGLE_REDIRECT_URI_PROD:", os.getenv("GOOGLE_REDIRECT_URI_PROD"))
print("🔍 ENV:", os.getenv("ENV"))

# ✅ Verificar contenido real de la SUPABASE_SERVICE_ROLE_KEY
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not supabase_key:
    print("❌ SUPABASE_SERVICE_ROLE_KEY no está definida en .env")
else:
    print(f"🔑 Prefijo SUPABASE_SERVICE_ROLE_KEY: {supabase_key[:10]}...")
    try:
        decoded = jwt.decode(supabase_key, options={"verify_signature": False})
        role = decoded.get("role")
        print("🔐 Supabase Key Role:", role)
        if role != "service_role":
            print("⚠️ ¡CUIDADO! Estás usando una clave con rol:", role)
        else:
            print("✅ Supabase configurado con la Service Role Key")
    except Exception as e:
        print("❌ Error al decodificar la key:", str(e))

# ✅ Routers principales
from api.upload_document import router as upload_router
from api.history_api import router as history_router
from api.create_client_if_needed import router as client_router
from api.ask_question_api import router as ask_router
from api.twilio_webhook import router as twilio_router
from api.initialize_user import router as initialize_user_router
from api.client_settings_api import router as client_settings_router
from api.link_whatsapp import router as link_whatsapp_router
from api.chat_widget_api import router as chat_widget_router
from api.check_email_exists import router as check_email_router
from api.dashboard_summary import router as dashboard_summary_router
from api.user_flags import router as user_flags_router
from api.widget_consents_api import router as widget_consents_router
from api.terms_api import router as terms_router
from api.clear_new_user_flag import router as clear_new_user_flag_router
from api.client_profile_api import router as client_profile_router
from api.accept_terms_api import router as accept_terms_router
from api.list_files_api import router as list_files_router
from api.list_chunks_api import router as list_chunks_router
from api.delete_chunks_api import router as delete_chunks_router
from api.public.embed import router as embed_router
from api.delete_file import router as delete_file_router

# ✅ Stripe
from api.stripe_webhook import router as stripe_router
from api.stripe_create_checkout_session import router as stripe_checkout_router
from api.stripe_cancel_subscription import router as stripe_cancel_router
from api.stripe_change_plan import router as stripe_change_plan_router

# ✅ Integraciones externas
from api.meta_webhook import router as meta_webhook_router
from api.auth.google_calendar_auth import router as google_auth_router
from api.auth.google_calendar_callback import router as google_callback_router
from api import calendar_status
from api.calendar_routes import router as calendar_router
from api.calendar_booking import router as calendar_booking_router
from api.auth import google_calendar_auth
from api.modules.calendar import init_calendar_auth

print("🚀 Routers importados correctamente")

app = FastAPI()

# ✅ CORS para pruebas locales
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4222",
        "http://localhost:4223",
        "http://localhost:5173",  # Vite default
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Registro de routers con prefijo /api
app.include_router(upload_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(client_router, prefix="/api")
app.include_router(ask_router, prefix="/api")
app.include_router(twilio_router, prefix="/api")
app.include_router(initialize_user_router, prefix="/api")
app.include_router(client_settings_router, prefix="/api")
app.include_router(link_whatsapp_router, prefix="/api")
app.include_router(chat_widget_router, prefix="/api")
app.include_router(check_email_router, prefix="/api")
app.include_router(dashboard_summary_router, prefix="/api")
app.include_router(user_flags_router, prefix="/api")
app.include_router(widget_consents_router, prefix="/api")
app.include_router(terms_router, prefix="/api")
app.include_router(clear_new_user_flag_router, prefix="/api")
app.include_router(client_profile_router, prefix="/api")
app.include_router(accept_terms_router, prefix="/api")
app.include_router(list_files_router, prefix="/api")
app.include_router(list_chunks_router, prefix="/api")
app.include_router(delete_chunks_router, prefix="/api")
app.include_router(embed_router, prefix="/api")
app.include_router(delete_file_router, prefix="/api", tags=["Files"])

# ✅ Stripe
app.include_router(stripe_router, prefix="/api")
app.include_router(stripe_checkout_router, prefix="/api")
app.include_router(stripe_cancel_router, prefix="/api")
app.include_router(stripe_change_plan_router, prefix="/api")

# ✅ Otras integraciones
app.include_router(meta_webhook_router, prefix="/api")
app.include_router(calendar_router, prefix="/api")
app.include_router(google_auth_router, prefix="/api")
app.include_router(google_callback_router, prefix="/api")
app.include_router(calendar_status.router, prefix="/api")
app.include_router(calendar_booking_router, prefix="/api")
app.include_router(google_calendar_auth.router, prefix="/api")
app.include_router(init_calendar_auth.router, prefix="/api")

# ✅ Healthcheck
@app.get("/healthz")
def health_check():
    return {"status": "ok"}

# ✅ Diagnóstico de rutas activas
@app.get("/test_routes")
def test_routes():
    return [route.path for route in app.routes]
