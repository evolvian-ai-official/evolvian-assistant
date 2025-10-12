from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()

@router.get("/history")
def get_history(
    client_id: str = Query(...),
    session_id: str = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Devuelve el historial de un cliente, opcionalmente filtrado por session_id.
    Los resultados se devuelven en orden descendente (más recientes primero).
    """
    try:
        print(f"📥 client_id recibido en /history: {client_id}, session_id={session_id}")

        query = (
            supabase.table("history")
            .select("role, content, created_at, session_id, channel")
            .eq("client_id", client_id)
        )

        # ✅ Filtra por session_id solo si se envía
        if session_id:
            query = query.eq("session_id", session_id)

        # ✅ Ordenar y limitar correctamente (solo una vez)
        response = query.order("created_at", desc=True).limit(limit).execute()

        results = response.data or []
        print(f"📦 Resultados encontrados: {len(results)} registros para client_id={client_id}")
        if results:
            print(f"🧩 Último mensaje: {results[0].get('role')} - {results[0].get('content')[:60]}")

        return JSONResponse(content={"history": results})

    except Exception as e:
        print(f"❌ Error en /history: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
