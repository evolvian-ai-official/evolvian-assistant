
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.responses import Response
from dotenv import load_dotenv
import os
import jwt
import importlib.util, sys
import subprocess

# ======================================
# ✅ Environment
# ======================================
load_dotenv(".env")
print("🔄 Environment variables loaded from .env")

IS_PROD = os.getenv("ENV") == "prod"
if not IS_PROD:
    print("🔍 GOOGLE_CLIENT_ID:", os.getenv("GOOGLE_CLIENT_ID"))

# ✅ Validate Supabase Key
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not supabase_key:
    print("❌ SUPABASE_SERVICE_ROLE_KEY missing in .env")
else:
    print(f"🔑 SUPABASE key prefix: {supabase_key[:10]}...")
    try:
        decoded = jwt.decode(supabase_key, options={"verify_signature": False})
        role = decoded.get("role")
        print("🔐 Supabase Key Role:", role)
        if role != "service_role":
            print("⚠️ Using key with role:", role)
        else:
            print("✅ Supabase service role key verified")
    except Exception as e:
        print("❌ Error decoding key:", str(e))

# ======================================
# ✅ Core Routers
# ======================================
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
from api.channels import router as channels_router
from api.modules.email_integration import disconnect_gmail
# ✅ Widget Consents
from api.register_consent import router as register_consent_router
from api.check_consent import router as check_consent_router
from api.blog.blog_router import router as blog_router



# ✅ Stripe
from api.stripe_webhook import router as stripe_router
from api.create_checkout_session import router as checkout_router
from api.stripe_cancel_subscription import router as stripe_cancel_router
from api.stripe_change_plan import router as stripe_change_plan_router
from api.reactivate_subscription import router as reactivate_subscription_router

# ✅ Appointments with AI
from api.delete_appointment import router as delete_appointment_router
from api.appointments import router as appointments_router

#Appointments manually
from api.appointments.create_appointment import router as create_appointment_router
from api.appointments.show_appointments import router as show_appointments_router
from api.appointments.cancel_appointment import router as cancel_appointment_router



#Whatsapp

from api.modules.whatsapp.webhook import router as whatsapp_webhook_router
from api.appointments.meta_reminder import router as meta_reminder_router
from api.templates.meta_approved_templates import router as meta_templates_router


#Reminders

from api.appointments.routes_update_status import router as update_status_router
from api.appointments.routes_execute_reminders import router as execute_reminders_router
from api.appointments.get_templates import router as appointment_templates_router
from api.appointments.message_templates import router as templates_router








# ======================================
# 🩹 Auto-install Google libs in dev
# ======================================
google_libs = [
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "google-auth-httplib2",
]
if not IS_PROD:
    for lib in google_libs:
        if importlib.util.find_spec(lib) is None:
            print(f"⚙️ Missing library: {lib} → installing at runtime...")
            subprocess.run(["pip", "install", lib], check=False)

# ======================================
# ✅ Optional Modules (protected)
# ======================================
chat_email = None
get_client_by_email_router = None
register_email_channel = None
gmail_webhook = None
gmail_oauth = None
gmail_setup_watch = None
gmail_poll = None
init_calendar_auth = None
calendar_status = None
meta_webhook_router = None
google_auth_router = None
google_callback_router = None
calendar_router = None
calendar_booking_router = None

# --- Assistant RAG
try:
    from api.modules.assistant_rag import chat_email as _chat_email
    chat_email = _chat_email
    print("✅ chat_email imported")
except Exception as e:
    print(f"⚠️ chat_email import failed: {e}")

try:
    from api.modules.assistant_rag.get_client_by_email import router as _get_client_by_email_router
    get_client_by_email_router = _get_client_by_email_router
    print("✅ get_client_by_email imported")
except Exception as e:
    print(f"⚠️ get_client_by_email import failed: {e}")

try:
    from api.routes import register_email_channel as _register_email_channel
    register_email_channel = _register_email_channel
    print("✅ register_email_channel imported")
except Exception as e:
    print(f"⚠️ register_email_channel import failed: {e}")

# --- Gmail
try:
    from api.modules.email_integration import gmail_webhook as _gmail_webhook
    gmail_webhook = _gmail_webhook
    print("✅ gmail_webhook imported")
except Exception as e:
    print(f"⚠️ gmail_webhook import failed: {e}")

try:
    from api.modules.email_integration import gmail_oauth as _gmail_oauth
    gmail_oauth = _gmail_oauth
    print("✅ gmail_oauth imported")
except Exception as e:
    print(f"⚠️ gmail_oauth import failed: {e}")

try:
    gmail_watch_path = os.path.join(os.path.dirname(__file__), "api/modules/email_integration/gmail_setup_watch.py")
    if os.path.exists(gmail_watch_path):
        spec = importlib.util.spec_from_file_location("gmail_setup_watch", gmail_watch_path)
        gmail_watch_module = importlib.util.module_from_spec(spec)
        sys.modules["gmail_setup_watch"] = gmail_watch_module
        spec.loader.exec_module(gmail_watch_module)
        gmail_setup_watch = gmail_watch_module
        print("✅ gmail_setup_watch imported (Render fix)")
    else:
        print(f"⚠️ gmail_setup_watch.py not found at: {gmail_watch_path}")
except Exception as e:
    print(f"⚠️ gmail_setup_watch import failed: {e}")

try:
    from api.modules.email_integration import gmail_poll as _gmail_poll
    gmail_poll = _gmail_poll
    print("✅ gmail_poll imported")
except Exception as e:
    print(f"⚠️ gmail_poll import failed: {e}")


try:
    from api import calendar_status as _calendar_status
    calendar_status = _calendar_status
    print("✅ calendar_status imported")
except Exception as e:
    print(f"⚠️ calendar_status import failed: {e}")

# --- Calendar
try:
    from api.calendar_routes import router as _calendar_router
    calendar_router = _calendar_router
    print("✅ calendar_routes imported and ready")
except Exception as e:
    print(f"⚠️ calendar_routes import failed: {e}")


# --- External Integrations
try:
    from api.meta_webhook import router as _meta_webhook_router
    meta_webhook_router = _meta_webhook_router
    print("✅ meta_webhook imported")
except Exception as e:
    print(f"⚠️ meta_webhook import failed: {e}")

try:
    from api.auth.google_calendar_auth import router as _google_auth_router
    google_auth_router = _google_auth_router
    print("✅ google_calendar_auth imported")
except Exception as e:
    print(f"⚠️ google_calendar_auth import failed: {e}")

try:
    from api.auth.google_calendar_callback import router as _google_callback_router
    google_callback_router = _google_callback_router
    print("✅ google_calendar_callback imported")
except Exception as e:
    print(f"⚠️ google_calendar_callback import failed: {e}")




print("🚀 Imports completed successfully")

# ======================================
# ✅ Create FastAPI app
# ======================================
app = FastAPI(title="Evolvian Assistant API", version="1.0")

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://clientuploader.onrender.com",
        "https://evolvianai.com",
        "https://evolvianai.net",
        "https://www.evolvianai.net",
        "https://evolvian-assistant.onrender.com",
        "http://localhost:4222",
        "http://localhost:4223",
        "http://localhost:5173",
        "http://localhost:5180",
         "http://localhost:5177",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📂 Static
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

# ✅ Frontend React
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "clientuploader/dist")
if os.path.exists(FRONTEND_DIST):
    print(f"🪄 Serving frontend from: {FRONTEND_DIST}")
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    print(f"⚠️ clientuploader/dist not found at: {FRONTEND_DIST}")

# ✅ Routers (core)
routers = [
    upload_router, history_router, client_router, ask_router, twilio_router,
    initialize_user_router, client_settings_router, link_whatsapp_router,
    chat_widget_router, check_email_router, dashboard_summary_router,
    user_flags_router, terms_router,
    clear_new_user_flag_router, client_profile_router, accept_terms_router,
    list_files_router, list_chunks_router, delete_chunks_router,
    embed_router, stripe_router, checkout_router,
    stripe_cancel_router, stripe_change_plan_router,
    reactivate_subscription_router, channels_router, register_consent_router, check_consent_router,
    blog_router,

]

# ✅ Gmail OAuth fallback
gmail_oauth_path = os.path.join(os.path.dirname(__file__), "api/modules/email_integration/gmail_oauth.py")
if os.path.exists(gmail_oauth_path):
    try:
        spec = importlib.util.spec_from_file_location("gmail_oauth_path_mod", gmail_oauth_path)
        gmail_oauth_module = importlib.util.module_from_spec(spec)
        sys.modules["gmail_oauth_path_mod"] = gmail_oauth_module
        spec.loader.exec_module(gmail_oauth_module)
        app.include_router(gmail_oauth_module.router)
        print("✅ Gmail OAuth router registered (Render fix)")
    except Exception as e:
        print(f"⚠️ Error registering Gmail OAuth router: {e}")



# ✅ Optional Routers
if chat_email: app.include_router(chat_email.router)
if get_client_by_email_router: app.include_router(get_client_by_email_router)
if register_email_channel: app.include_router(register_email_channel.router)

# Gmail
if gmail_webhook: app.include_router(gmail_webhook.router)
if gmail_oauth: app.include_router(gmail_oauth.router)
if gmail_poll: app.include_router(gmail_poll.router)

# Integrations
if meta_webhook_router: app.include_router(meta_webhook_router)
if calendar_router: app.include_router(calendar_router)
if calendar_booking_router: app.include_router(calendar_booking_router)
if google_auth_router: app.include_router(google_auth_router)
if google_callback_router: app.include_router(google_callback_router)
if init_calendar_auth: app.include_router(init_calendar_auth.router)
if delete_appointment_router: app.include_router(delete_appointment_router)
if appointments_router: app.include_router(appointments_router)
if whatsapp_webhook_router: app.include_router(whatsapp_webhook_router)

# ✅ Mount Calendar Router (to expose /calendar/book)
if calendar_router:
    app.include_router(calendar_router, prefix="")
    print("✅ Mounted calendar_routes at /calendar/book")


# Core routers
for r in routers:
    app.include_router(r)

# ✅ Appointment status updates (IMPORTANT)
app.include_router(update_status_router, prefix="/api")
app.include_router(execute_reminders_router, prefix="/api")
app.include_router(create_appointment_router)
app.include_router(cancel_appointment_router)
app.include_router(appointment_templates_router)
app.include_router(show_appointments_router)
app.include_router(templates_router,tags=["Message Templates"])


#whats

app.include_router(meta_reminder_router)
app.include_router(meta_templates_router)


# Cron & embed
app.include_router(reset.router, tags=["subscriptions"])
app.include_router(embed.router)

# ✅ Force calendar_routes registration (manual fix)
try:
    import api.calendar_routes as calendar_routes
    app.include_router(calendar_routes.router)
    print("✅ calendar_routes manually registered (fix applied)")
except Exception as e:
    print(f"❌ Failed to register calendar_routes manually: {e}")

try:
    from api.auth import calendar_ui_status
    app.include_router(calendar_ui_status.router)
    print("✅ calendar_ui_status imported")
except Exception as e:
    print(f"⚠️ calendar_ui_status import failed: {e}")

# ============================================================
# 🗓️ Calendar Settings — Load client availability preferences
# ============================================================
try:
    from api import calendar_settings
    app.include_router(calendar_settings.router)
    print("✅ calendar_settings imported")
except Exception as e:
    print(f"⚠️ calendar_settings import failed: {e}")

# ============================================================
# 🧠 Calendar Prompt — Dynamic AI Scheduling Context
# ============================================================
try:
    from api.modules.assistant_rag.prompts import calendar_prompt
    print("✅ calendar_prompt module loaded successfully")
except Exception as e:
    print(f"⚠️ calendar_prompt import failed: {e}")

# ============================================================
# 🤖 LLM — OpenAI Direct Chat Module
# ============================================================
try:
    from api.modules.assistant_rag import llm as _llm
    llm = _llm
    print("✅ llm imported successfully (OpenAI Chat Module)")
except Exception as e:
    print(f"⚠️ llm import failed: {e}")


# Mount all WhatsApp routes
try:
    from api.modules.whatsapp import router as whatsapp_router
    app.include_router(whatsapp_router)
    print("✅ whatsapp_router mounted")
except Exception as e:
    print("⚠️ Failed to mount whatsapp_router:", e)


# --- Calendar
try:
    from api.modules.calendar import init_calendar_auth as _init_calendar_auth
    init_calendar_auth = _init_calendar_auth
    app.include_router(init_calendar_auth.router, prefix="/api")  # ✅ AGREGA ESTO
    print("✅ init_calendar_auth mounted under /api")
except Exception as e:
    print(f"⚠️ init_calendar_auth import failed: {e}")

# CORS preflight handler
from fastapi.responses import JSONResponse

@app.options("/{rest_of_path:path}")
async def options_handler(rest_of_path: str):
    """Allow all OPTIONS requests for CORS preflight."""
    return JSONResponse(content={"status": "ok"})


# ✅ Healthcheck
@app.get("/healthz")
def health_check():
    return {"status": "ok"}

@app.get("/test_routes")
def test_routes():
    return [route.path for route in app.routes]

# ✅ Run local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))