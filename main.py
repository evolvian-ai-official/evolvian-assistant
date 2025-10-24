from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
import jwt
from starlette.responses import Response
import importlib.util, sys
import subprocess

# ✅ Cargar variables de entorno
load_dotenv(".env")
print("🔄 Variables de entorno cargadas desde .env")

# 🔍 Diagnóstico explícito de entorno (solo en desarrollo)
IS_PROD = os.getenv("ENV") == "prod"
if not IS_PROD:
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

# ✅ Routers principales (core del sistema)
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
from api.routes import reset, embed  # Cron y embed
from api.delete_file import router as delete_file_router
from api.channels import router as channels_router
from api.modules.email_integration import disconnect_gmail

# ✅ Stripe
from api.stripe_webhook import router as stripe_router
from api.create_checkout_session import router as checkout_router
from api.stripe_cancel_subscription import router as stripe_cancel_router
from api.stripe_change_plan import router as stripe_change_plan_router
from api.reactivate_subscription import router as reactivate_subscription_router

# ✅ Integraciones externas seguras
from api.meta_webhook import router as meta_webhook_router
from api.auth.google_calendar_auth import router as google_auth_router
from api.auth.google_calendar_callback import router as google_callback_router
from api.calendar_routes import router as calendar_router
from api.calendar_booking import router as calendar_booking_router

# 🩹 Auto-fix Render: asegura dependencias de Gmail/Calendar en runtime (solo dev)
google_libs = [
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "google-auth-httplib2",
]
if not IS_PROD:
    for lib in google_libs:
        if importlib.util.find_spec(lib) is None:
            print(f"⚙️ Librería faltante detectada: {lib} → instalando en runtime...")
            subprocess.run(["pip", "install", lib], check=False)

# ✅ Módulos opcionales protegidos
try:
    from api.modules.assistant_rag import chat_email
    print("✅ chat_email importado correctamente")
except Exception as e:
    chat_email = None
    print(f"⚠️ No se pudo importar chat_email: {e}")

try:
    from api.modules.assistant_rag.get_client_by_email import router as get_client_by_email_router
    print("✅ get_client_by_email importado correctamente")
except Exception as e:
    get_client_by_email_router = None
    print(f"⚠️ No se pudo importar get_client_by_email: {e}")

try:
    from api.routes import register_email_channel
    print("✅ register_email_channel importado correctamente")
except Exception as e:
    register_email_channel = None
    print(f"⚠️ No se pudo importar register_email_channel: {e}")

# ==========================
# ✅ Gmail: webhook + oauth
# ==========================
# 1) Intento como paquete
gmail_webhook_router = None
try:
    from api.modules.email_integration import gmail_webhook
    gmail_webhook_router = gmail_webhook.router
    print("✅ gmail_webhook importado como paquete")
except Exception as e:
    print(f"⚠️ No se pudo importar gmail_webhook como paquete: {e}")

gmail_oauth_router = None
try:
    from api.modules.email_integration import gmail_oauth
    gmail_oauth_router = gmail_oauth.router
    print("✅ gmail_oauth importado como paquete")
except Exception as e:
    print(f"⚠️ No se pudo importar gmail_oauth como paquete: {e}")

# 2) Fallback por ruta absoluta (asegura carga en Render)
if gmail_webhook_router is None:
    try:
        gmail_webhook_path = os.path.join(os.path.dirname(__file__), "api/modules/email_integration/gmail_webhook.py")
        if os.path.exists(gmail_webhook_path):
            spec = importlib.util.spec_from_file_location("gmail_webhook_path_mod", gmail_webhook_path)
            gmail_webhook_module = importlib.util.module_from_spec(spec)
            sys.modules["gmail_webhook_path_mod"] = gmail_webhook_module
            spec.loader.exec_module(gmail_webhook_module)
            gmail_webhook_router = gmail_webhook_module.router
            print("✅ gmail_webhook registrado por ruta absoluta (fallback)")
        else:
            print(f"❌ No se encontró gmail_webhook.py en: {gmail_webhook_path}")
    except Exception as ee:
        print(f"❌ Error al registrar gmail_webhook por ruta absoluta: {ee}")

oauth_included = False
if gmail_oauth_router is None:
    gmail_oauth_path = os.path.join(os.path.dirname(__file__), "api/modules/email_integration/gmail_oauth.py")
    if os.path.exists(gmail_oauth_path):
        try:
            spec = importlib.util.spec_from_file_location("gmail_oauth_path_mod", gmail_oauth_path)
            gmail_oauth_module = importlib.util.module_from_spec(spec)
            sys.modules["gmail_oauth_path_mod"] = gmail_oauth_module
            spec.loader.exec_module(gmail_oauth_module)
            gmail_oauth_router = gmail_oauth_module.router
            oauth_included = True
            print("✅ Gmail OAuth router registrado por ruta absoluta (Render fix, path corregido)")
        except Exception as e:
            print(f"⚠️ Error al registrar Gmail OAuth router por ruta absoluta: {e}")
    else:
        print(f"⚠️ No se encontró gmail_oauth.py en: {gmail_oauth_path}")
else:
    oauth_included = True

# ==========================
# ✅ Gmail: Poller (uno solo)
# ==========================
gmail_setup_watch_router = None
try:
    # preferimos import de paquete si está disponible
    from api.modules.email_integration import gmail_setup_watch
    gmail_setup_watch_router = gmail_setup_watch.router
    print("✅ gmail_setup_watch importado como paquete")
except Exception as e:
    print(f"⚠️ No se pudo importar gmail_setup_watch como paquete: {e}")
    try:
        gmail_watch_path = os.path.join(os.path.dirname(__file__), "api/modules/email_integration/gmail_setup_watch.py")
        if os.path.exists(gmail_watch_path):
            spec = importlib.util.spec_from_file_location("gmail_setup_watch", gmail_watch_path)
            gmail_watch_module = importlib.util.module_from_spec(spec)
            sys.modules["gmail_setup_watch"] = gmail_watch_module
            spec.loader.exec_module(gmail_watch_module)
            gmail_setup_watch_router = gmail_watch_module.router
            print("✅ gmail_setup_watch importado por ruta absoluta (fallback)")
        else:
            print(f"⚠️ No se encontró gmail_setup_watch.py en: {gmail_watch_path}")
    except Exception as e2:
        print(f"⚠️ Error al importar gmail_setup_watch: {e2}")

# (Si tienes otro poller, NO lo montes simultáneamente)
# try:
#     from api.modules.email_integration import gmail_poll
#     gmail_poll_router = gmail_poll.router
# except Exception:
#     gmail_poll_router = None

print("🚀 Imports completados correctamente")

# =====================================================
# ✅ Crear app FastAPI
# =====================================================
app = FastAPI(title="Evolvian Assistant API", version="1.0")

# ✅ CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://clientuploader.onrender.com",
        "https://evolvianai.com",
        "https://www.evolvianai.com",
        "https://evolvianai.net",
        "https://www.evolvianai.net",
        "https://evolvian-assistant.onrender.com",
        "http://localhost:4222",
        "http://localhost:4223",
        "http://localhost:5173",
        "http://localhost:5180",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Static files con CORS
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
class CORSMiddlewareStatic(StaticFiles):
    async def get_response(self, path, scope):
        response: Response = await super().get_response(path, scope)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

app.mount("/static", CORSMiddlewareStatic(directory=STATIC_DIR), name="static")
app.mount("/assets", CORSMiddlewareStatic(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

# =====================================================
# ✅ Registro de routers principales
# =====================================================
routers = [
    upload_router,
    history_router,
    client_router,
    ask_router,
    twilio_router,
    initialize_user_router,
    client_settings_router,
    link_whatsapp_router,
    chat_widget_router,
    check_email_router,
    dashboard_summary_router,
    user_flags_router,
    widget_consents_router,
    terms_router,
    clear_new_user_flag_router,
    client_profile_router,
    accept_terms_router,
    list_files_router,
    list_chunks_router,
    delete_chunks_router,
    embed_router,
    delete_file_router,
    stripe_router,
    checkout_router,
    stripe_cancel_router,
    stripe_change_plan_router,
    reactivate_subscription_router,
    meta_webhook_router,
    calendar_router,
    calendar_booking_router,
    google_auth_router,
    google_callback_router,
]

# =====================================================
# ✅ Registro de routers (sin duplicados)
# =====================================================
if chat_email:
    app.include_router(chat_email.router)
if get_client_by_email_router:
    app.include_router(get_client_by_email_router)
if register_email_channel:
    app.include_router(register_email_channel.router)

if gmail_webhook_router:
    app.include_router(
        gmail_webhook_router,
        include_in_schema=True,
        responses={422: {"description": "Validation Error"}},
    )
if gmail_oauth_router and oauth_included:
    app.include_router(
        gmail_oauth_router,
        include_in_schema=True,
        responses={422: {"description": "Validation Error"}},
    )
if gmail_setup_watch_router:
    app.include_router(gmail_setup_watch_router)

# if gmail_poll_router:
#     app.include_router(gmail_poll_router)  # ← NO montar a la vez que setup_watch

if init_calendar_auth:
    app.include_router(init_calendar_auth.router)
if calendar_status:
    app.include_router(calendar_status.router)
if channels_router:
    app.include_router(channels_router)
if disconnect_gmail:
    app.include_router(disconnect_gmail.router)

for r in routers:
    app.include_router(r)

app.include_router(reset.router, tags=["subscriptions"])
app.include_router(embed.router)

# =====================================================
# ✅ Utilidades de diagnóstico
# =====================================================
@app.get("/healthz")
def health_check():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Evolvian Assistant API is running"}

@app.get("/test_routes")
def test_routes():
    return [route.path for route in app.routes]

# =====================================================
# ✅ Ejecución local
# =====================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
