from fastapi import APIRouter, HTTPException
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/api/public", tags=["Public Plans"])

PLAN_ORDER = {
    "free": 1,
    "starter": 2,
    "premium": 3,
    "white_label": 4,
    "enterprise": 4,
}


@router.get("/plans")
def get_public_plans():
    """
    Returns public plan pricing for marketing surfaces.
    White label price is intentionally hidden.
    """
    try:
        res = (
            supabase.table("plans")
            .select("id, name, price_usd")
            .execute()
        )

        rows = res.data or []
        rows.sort(key=lambda p: PLAN_ORDER.get((p.get("id") or "").strip().lower(), 99))

        plans = []
        for row in rows:
            plan_id = (row.get("id") or "").strip().lower()
            normalized_id = "white_label" if plan_id == "enterprise" else plan_id

            price_usd = row.get("price_usd")
            show_price = normalized_id != "white_label"

            plans.append(
                {
                    "id": normalized_id,
                    "name": row.get("name"),
                    "price_usd": price_usd if show_price else None,
                    "show_price": show_price,
                }
            )

        return {"plans": plans}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading public plans: {e}")
