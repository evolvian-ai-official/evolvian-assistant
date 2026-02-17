import os
import httpx

# Cargar .env solo en entorno local
if os.getenv("RENDER") is None:
    from dotenv import load_dotenv
    load_dotenv()

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

# Variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 👉 MODELO DE CHAT (AQUÍ)
DEFAULT_CHAT_MODEL = os.getenv("EVOLVIAN_CHAT_MODEL", "gpt-4o")

# Validaciones básicas
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment variables")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in environment variables")

# Registrar la API key de OpenAI
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Cliente HTTP explícito para evitar inestabilidad en HTTP/2 bajo carga
_supabase_httpx_client = httpx.Client(
    http2=False,
    timeout=httpx.Timeout(12.0, connect=4.0, read=10.0, write=10.0),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=15.0),
)

# Crear cliente Supabase con opciones de timeout y transporte estable
supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    options=SyncClientOptions(
        postgrest_client_timeout=12,
        storage_client_timeout=20,
        function_client_timeout=10,
        httpx_client=_supabase_httpx_client,
    ),
)
