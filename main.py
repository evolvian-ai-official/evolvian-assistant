from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
import jwt
from starlette.responses import Response

# ✅ Cargar variables de entorno
load_dotenv(".env")
print("🔄 Variables de entorno cargadas desde .env")

# 🔍 Diagnóstico explícito de entorno (solo en desarrollo)
if os.getenv("ENV") != "prod":
    print("🔍 GOOGLE_CLIENT_ID:", os.getenv("GOOGLE_CLIENT_ID"))

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
from api.routes import reset  # Cron
from api.routes import embed
from api.delete_file import router as delete_file_router
from api.modules.assistant_rag import chat_email
from api.modules.assistant_rag import get_client_by_email
from api.routes import register_email_channel

# 🔧 MOVIDO ABAJO — estos dos deben importarse después de crear la app
# from api.modules.email_integration import gmail_webhook
# from api.modules.email_integration import gmail_oauth

# ✅ Stripe
from api.stripe_webhook import router as stripe_router
from api.create_checkout_session import router as checkout_router
from api.stripe_cancel_subscription import router as stripe_cancel_router
from api.stripe_change_plan import router as stripe_change_plan_router

# ✅ NUEVO: Reactivar suscripciones canceladas
from api.reactivate_subscription import router as reactivate_subscription_router

# ✅ Integraciones externas
from api.meta_webhook import router as meta_webhook_router
from api.auth.google_calendar_auth import router as google_auth_router
from api.auth.google_calendar_callback import router as google_callback_router
from api.calendar_routes import router as calendar_router
from api.calendar_booking import router as calendar_booking_router
from api.modules.calendar import init_calendar_auth
from api import calendar_status

print("🚀 Routers importados correctamente")

# ----------------------------------------
# ✅ Crear app antes de incluir routers
# ----------------------------------------
app = FastAPI()

# 🔧 MOVIDO AQUÍ — ahora sí montamos los routers de Gmail correctamente
from api.modules.email_integration import gmail_webhook, gmail_oauth

# ✅ CORS para producción y desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Producción
        "https://clientuploader.onrender.com",
        "https://evolvianai.com",
        "https://evolvianai.net",
        "https://www.evolvianai.net",
        "https://evolvian-assistant.onrender.com",
        # Local
        "http://localhost:4222",
        "http://localhost:4223",
        "http://localhost:5173",
        "http://localhost:4223",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📂 Definir ruta de static antes de montarla
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# 🔧 Static con CORS headers habilitados
class CORSMiddlewareStatic(StaticFiles):
    async def get_response(self, path, scope):
        response: Response = await super().get_response(path, scope)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

# 📂 static completo (embed-floating.js, widget.html, etc.)
app.mount("/static", CORSMiddlewareStatic(directory=STATIC_DIR), name="static")

# 📂 assets compilados por Vite
app.mount("/assets", CORSMiddlewareStatic(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

# ✅ Registro de routers (sin prefijo /api)
app.include_router(upload_router)
app.include_router(history_router)
app.include_router(client_router)
app.include_router(ask_router)
app.include_router(twilio_router)
app.include_router(initialize_user_router)
app.include_router(client_settings_router)
app.include_router(link_whatsapp_router)
app.include_router(chat_widget_router)
app.include_router(check_email_router)
app.include_router(dashboard_summary_router)
app.include_router(user_flags_router)
app.include_router(widget_consents_router)
app.include_router(terms_router)
app.include_router(clear_new_user_flag_router)
app.include_router(client_profile_router)
app.include_router(accept_terms_router)
app.include_router(list_files_router)
app.include_router(list_chunks_router)
app.include_router(delete_chunks_router)
app.include_router(embed_router)
app.include_router(reset.router, tags=["subscriptions"])
app.include_router(delete_file_router)
app.include_router(embed.router)
app.include_router(chat_email.router)
app.include_router(get_client_by_email.router)
app.include_router(register_email_channel.router)

# ✅ Gmail routers correctamente montados
app.include_router(gmail_webhook.router)
app.include_router(gmail_oauth.router)

# ✅ Stripe
app.include_router(stripe_router)
app.include_router(checkout_router)
app.include_router(stripe_cancel_router)
app.include_router(stripe_change_plan_router)

# ✅ NUEVO: Reactivar suscripción
app.include_router(reactivate_subscription_router)

# ✅ Google Calendar & otras integraciones
app.include_router(meta_webhook_router)
app.include_router(calendar_router)
app.include_router(calendar_booking_router)
app.include_router(google_auth_router)
app.include_router(google_callback_router)
app.include_router(init_calendar_auth.router)
app.include_router(calendar_status.router)

# ✅ Healthcheck
@app.get("/healthz")
def health_check():
    return {"status": "ok"}

# ✅ Root endpoint
@app.get("/")
def root():
    return {"message": "Evolvian Assistant API is running"}

# ✅ Diagnóstico de rutas activas
@app.get("/test_routes")
def test_routes():
    return [route.path for route in app.routes]
