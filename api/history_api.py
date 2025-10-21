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

        # Filtra por session_id solo si se envía
        if session_id:
            query = query.eq("session_id", session_id)

        response = query.order("created_at", desc=True).limit(limit).execute()
        raw_data = response.data or []
        print(f"📦 Resultados encontrados (crudos): {len(raw_data)}")

        # 🚧 Limpieza: eliminar filas nulas o corruptas
        results = [r for r in raw_data if isinstance(r, dict) and r.get("content") is not None]

        print(f"📦 Resultados válidos tras limpieza: {len(results)} registros para client_id={client_id}")

        if results:
            first = results[0]
            print(f"🧩 Último mensaje: {first.get('role', 'unknown')} - {first.get('content', '')[:60]}")
        else:
            print("ℹ️ No hay mensajes válidos para mostrar.")

        return JSONResponse(
            content={
                "client_id": client_id,
                "session_id": session_id,
                "count": len(results),
                "history": results
            }
        )

    except Exception as e:
        print(f"❌ Error en /history: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
