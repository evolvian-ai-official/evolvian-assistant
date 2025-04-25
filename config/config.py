# config.py
import os
from dotenv import load_dotenv

# 👇 Primero carga el archivo .env
load_dotenv()

# 👇 Luego ya puedes leer las variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Asegura que esté activa para cualquier uso posterior
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
else:
    raise ValueError("❌ OPENAI_API_KEY no fue encontrada. Asegúrate de que esté en el archivo .env")
