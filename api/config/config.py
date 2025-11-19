import os

# Cargar .env solo en entorno local
if os.getenv("RENDER") is None:
    from dotenv import load_dotenv
    load_dotenv()

from supabase import create_client
import httpx  # necesario para HTTP/1.1

# Variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validaciones básicas
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment variables")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in environment variables")

# Registrar la API key de OpenAI
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# 🚑 FIX Render — Forzar HTTP/1.1
transport = httpx.HTTPTransport(http2=False)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    http_client=httpx.Client(transport=transport)  # 👈 esto sí funciona
)
