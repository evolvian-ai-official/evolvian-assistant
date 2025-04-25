from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Routers
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
from api.widget_consents_api import router as widget_consents_router  # ✅ Consentimiento widget
from api.terms_api import router as terms_router  # ✅ NUEVO: Términos para clientes SaaS

print("🚀 Routers importados correctamente")

app = FastAPI()

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambiar a dominios específicos en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de routers
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
app.include_router(terms_router)  # ✅ NUEVO agregado al final
