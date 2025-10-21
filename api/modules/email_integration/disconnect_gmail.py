from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/disconnect_gmail", tags=["Email Automation"])

@router.post("")
async def disconnect_gmail(request: Request, client_id: str = Query(..., description="Client ID a desconectar")):
    """
    🔌 Desconecta y elimina completamente los canales Gmail para un cliente.
    - Borra las filas en la tabla `channels` con provider='gmail' y type='email'
    - Limpia tokens y elimina el canal para evitar duplicaciones
    - Redirige dinámicamente al panel correcto según entorno (localhost / producción)
    """
    print(f"🔌 Solicitando eliminación total de Gmail para client_id={client_id}")

    try:
        # Buscar todos los canales Gmail asociados al cliente
        channel_resp = (
            supabase.table("channels")
            .select("id, value")
            .eq("client_id", client_id)
            .eq("type", "email")
            .eq("provider", "gmail")
            .execute()
        )

        if not channel_resp.data or len(channel_resp.data) == 0:
            print("⚠️ No se encontraron canales Gmail para este cliente.")
            raise HTTPException(status_code=404, detail="No se encontraron canales Gmail para este cliente")

        emails = [c["value"] for c in channel_resp.data]
        print(f"📭 Eliminando canales Gmail: {emails}")

        # Eliminar todos los canales Gmail del cliente
        delete_resp = (
            supabase.table("channels")
            .delete()
            .eq("client_id", client_id)
            .eq("type", "email")
            .eq("provider", "gmail")
            .execute()
        )

        count_deleted = len(delete_resp.data or [])
        print(f"✅ {count_deleted} canal(es) Gmail eliminados completamente.")

        # ------------------------------------------------------
        # 🌍 Redirección dinámica según entorno
        # ------------------------------------------------------
        origin = request.headers.get("origin") or ""
        if "localhost" in origin or "127.0.0.1" in origin:
            redirect_url = "http://localhost:4223/services/email"
        else:
            redirect_url = "https://evolvianai.net/services/email"

        print(f"🔁 Redirecting to Evolvian: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔥 Error al eliminar canal Gmail: {e}")
        raise HTTPException(status_code=500, detail=str(e))
