from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from modules.assistant_rag.supabase_client import supabase

router = APIRouter()

@router.get("/history")
def get_history(client_id: str = Query(...)):
    try:
        print(f"📥 client_id recibido en /history: {client_id}")

        response = supabase.table("history") \
            .select("*") \
            .eq("client_id", client_id) \
            .order("created_at", desc=True) \
            .execute()

        print(f"📦 Resultados encontrados: {len(response.data)}")
        return JSONResponse(content={"history": response.data})

    except Exception as e:
        print(f"❌ Error en /history: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
