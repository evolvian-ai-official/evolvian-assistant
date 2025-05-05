import os

# Solo cargar .env si NO estás en Render
if os.getenv("RENDER") is None:
    from dotenv import load_dotenv
    load_dotenv()

from supabase import create_client

# 🔑 Leer variables del entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 🛡️ Validaciones
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("❌ Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en las variables de entorno")

# ✅ Confirmación
print(f"✅ Supabase configurado con service_role key (termina en: {SUPABASE_SERVICE_ROLE_KEY[-6:]})")

# 🔁 Set API key de OpenAI para que esté disponible globalmente
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    print("🔐 OPENAI_API_KEY cargada correctamente.")
else:
    raise ValueError("❌ Falta OPENAI_API_KEY en las variables de entorno")

# ☁️ Inicializa el cliente Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
