import os
from dotenv import load_dotenv
from supabase import create_client

# 📦 Cargar variables del .env
load_dotenv()

# 🔑 Leer variables del entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 🛡️ Validaciones
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("❌ Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el archivo .env")

# ✅ Confirmación
print(f"✅ Supabase configurado con service_role key (termina en: {SUPABASE_SERVICE_ROLE_KEY[-6:]})")

# 🔁 Set API key de OpenAI
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    print("🔐 OPENAI_API_KEY cargada correctamente.")
else:
    raise ValueError("❌ Falta OPENAI_API_KEY en el archivo .env")

# ☁️ Inicializa el cliente Supabase con la service_role
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
