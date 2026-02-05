from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.modules.assistant_rag.supabase_client import supabase
from datetime import datetime, timedelta, timezone

router = APIRouter()

class MakeUpdateStatus(BaseModel):
    appointment_id: str
    status: str
    notes: str | None = None


@router.patch("/make_update_status")
async def make_update_status(data: MakeUpdateStatus):
    try:
        now_utc = datetime.now(timezone.utc)

        # -------------------------------------------------
        # 1️⃣ Update appointment status
        # -------------------------------------------------
        result = (
            supabase
            .table("appointments")
            .update({
                "status": data.status,
                "updated_at": now_utc.isoformat()
            })
            .eq("id", data.appointment_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Appointment not found")

        appointment = result.data[0]
        client_id = appointment["client_id"]
        scheduled_time = appointment.get("scheduled_time")

        # -------------------------------------------------
        # 2️⃣ Log appointment usage (auditoría)
        # -------------------------------------------------
        supabase.table("appointment_usage").insert({
            "appointment_id": data.appointment_id,
            "client_id": client_id,
            "action": f"status_updated_to_{data.status}"
        }).execute()

        # -------------------------------------------------
        # 3️⃣ SOLO si pasa a CONFIRMED → generar reminders
        # -------------------------------------------------
        if data.status == "confirmed" and scheduled_time:
            appointment_time = datetime.fromisoformat(scheduled_time)

            # ⛔ No generar reminders para citas pasadas
            if appointment_time <= now_utc:
                return {"status": "updated", "reminders_created": 0}

            # -------------------------------------------------
            # 3.1️⃣ Obtener templates activos del cliente
            # -------------------------------------------------
            tpl_resp = (
                supabase
                .table("message_templates")
                .select("*")
                .eq("client_id", client_id)
                .eq("type", "appointment_reminder")
                .eq("is_active", True)
                .execute()
            )

            templates = tpl_resp.data or []
            reminders_created = 0

            for tpl in templates:
                channel = tpl["channel"]
                frequency = tpl.get("frequency")

                # ⚠️ Mejora: template sin frecuencia definida
                if not frequency:
                    print(
                        f"⚠️ message_template {tpl['id']} has no frequency defined "
                        f"(client_id={client_id}, channel={channel})"
                    )
                    continue

                offsets = frequency.get("offsets", [])

                # ⚠️ Mejora: frecuencia sin offsets
                if not offsets:
                    print(
                        f"⚠️ message_template {tpl['id']} has empty offsets "
                        f"(client_id={client_id}, channel={channel})"
                    )
                    continue

                for offset in offsets:
                    value = offset.get("value")
                    unit = offset.get("unit")

                    if not value or unit not in ("minutes", "hours", "days"):
                        print(
                            f"⚠️ Invalid offset in template {tpl['id']}: {offset}"
                        )
                        continue

                    scheduled_at = appointment_time - timedelta(**{unit: value})

                    # ⛔ No crear reminders en el pasaddo
                    if scheduled_at <= now_utc:
                        continue

                    # ⛔ Idempotencia: evitar duplicados
                    existing = (
                        supabase
                        .table("appointment_reminders")
                        .select("id")
                        .eq("appointment_id", data.appointment_id)
                        .eq("channel", channel)
                        .eq("scheduled_at", scheduled_at.isoformat())
                        .execute()
                    )

                    if existing.data:
                        continue

                    supabase.table("appointment_reminders").insert({
                        "client_id": client_id,
                        "appointment_id": data.appointment_id,
                        "channel": channel,
                        "scheduled_at": scheduled_at.isoformat(),
                        "status": "pending"
                    }).execute()

                    reminders_created += 1

            return {
                "status": "updated",
                "reminders_created": reminders_created
            }

        return {"status": "updated"}

    except HTTPException:
        raise

    except Exception as e:
        print("❌ Error make_update_status:", e)
        raise HTTPException(status_code=500, detail="Internal error")
