import os

# Cargar .env solo en entorno local
if os.getenv("RENDER") is None:
    from dotenv import load_dotenv
    load_dotenv()

from supabase import create_client

# Variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validaciones básicas
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment variables")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in environment variables")

# Registrar la API key de OpenAI en el entorno global
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Crear cliente Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
