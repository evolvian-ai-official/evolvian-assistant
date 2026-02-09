from fastapi import APIRouter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.whatsapp.whatsapp_sender import (
    send_whatsapp_message_for_client
)

router = APIRouter()

# =====================================================
# Timezone fijo (por ahora)
# =====================================================
MEXICO_TZ = ZoneInfo("America/Mexico_City")

CRON_INTERVAL_MINUTES = 5  # 🔒 regla explícita


# =====================================================
# Helpers
# =====================================================
def format_scheduled_time(iso_utc: str) -> str:
    try:
        dt_utc = datetime.fromisoformat(iso_utc)
        dt_local = dt_utc.astimezone(MEXICO_TZ)
        return dt_local.strftime("%A %d de %B, %I:%M %p")
    except Exception:
        return iso_utc


def render_template(body: str, appointment: dict) -> str:
    scheduled_time = appointment.get("scheduled_time")
    if scheduled_time:
        scheduled_time = format_scheduled_time(scheduled_time)

    return (
        body
        .replace("{{user_name}}", appointment.get("user_name", "") or "")
        .replace("{{scheduled_time}}", scheduled_time or "")
        .replace("{{appointment_type}}", appointment.get("appointment_type", "") or "")
    )


def is_aligned_with_cron(dt: datetime) -> bool:
    """Valida que el scheduled_at caiga en múltiplos del cron"""
    return dt.minute % CRON_INTERVAL_MINUTES == 0


# =====================================================
# Endpoint
# =====================================================
@router.post("/reminders/execute")
async def execute_pending_reminders():
    """
    Ejecuta reminders pendientes cuyo scheduled_at <= now()

    - Scheduler trabaja en UTC
    - Mensaje se renderiza en horario México
    - NO se envían reminders fuera de tick de cron
    """

    now = datetime.now(timezone.utc)

    print("\n==============================")
    print(f"⏱️ REMINDER EXECUTION @ {now.isoformat()}")
    print("==============================\n")

    response = (
        supabase
        .table("appointment_reminders")
        .select("*")
        .eq("status", "pending")
        .lte("scheduled_at", now.isoformat())
        .execute()
    )

    reminders = response.data or []

    processed = sent = failed = skipped = 0

    for reminder in reminders:
        processed += 1

        reminder_id = reminder["id"]
        appointment_id = reminder["appointment_id"]
        client_id = reminder["client_id"]
        channel = reminder["channel"]
        scheduled_at = datetime.fromisoformat(reminder["scheduled_at"])

        print("\n------------------------------")
        print(f"🔔 Reminder {reminder_id}")
        print(f"📅 scheduled_at (UTC): {scheduled_at}")

        # -------------------------------------------------
        # 0️⃣ Validar alineación con cron
        # -------------------------------------------------
        if not is_aligned_with_cron(scheduled_at):
            print(
                f"⏭️ SKIPPED — scheduled_at no alineado al cron "
                f"({CRON_INTERVAL_MINUTES}m)"
            )
            skipped += 1
            continue

        try:
            # -------------------------------------------------
            # 1️⃣ Appointment
            # -------------------------------------------------
            appointment = (
                supabase
                .table("appointments")
                .select("*")
                .eq("id", appointment_id)
                .single()
                .execute()
            ).data

            if not appointment:
                raise Exception("Appointment not found")

            print(f"👤 Appointment {appointment_id}")
            print(f"📞 Phone: {appointment.get('user_phone')}")
            print(f"📧 Email: {appointment.get('user_email')}")

            # -------------------------------------------------
            # 2️⃣ Template
            # -------------------------------------------------
            template_id = reminder.get("template_id")
            if not template_id:
                raise Exception("Missing template_id")

            template = (
                supabase
                .table("message_templates")
                .select("*")
                .eq("id", template_id)
                .eq("client_id", client_id)
                .eq("is_active", True)
                .single()
                .execute()
            ).data

            if not template:
                raise Exception("Template not found or inactive")

            message_body = render_template(template["body"], appointment)

            print("📝 Message preview:")
            print(message_body)

            # -------------------------------------------------
            # 3️⃣ Envío
            # -------------------------------------------------
            send_ok = False

            if channel == "whatsapp":
                phone = appointment.get("user_phone")
                if not phone:
                    raise Exception("Missing phone")

                print(f"📤 Sending WhatsApp to {phone}")
                send_ok = await send_whatsapp_message_for_client(
                    client_id=client_id,
                    to_number=phone,
                    message=message_body
                )

            elif channel == "email":
                email = appointment.get("user_email")
                if not email:
                    raise Exception("Missing email")

                print(f"📧 EMAIL → {email}")
                send_ok = True

            else:
                raise Exception(f"Unsupported channel: {channel}")

            if not send_ok:
                raise Exception("Provider send failed")

            # -------------------------------------------------
            # 4️⃣ Mark sent
            # -------------------------------------------------
            supabase.table("appointment_reminders").update({
                "status": "sent",
                "updated_at": now.isoformat()
            }).eq("id", reminder_id).execute()

            sent += 1
            print("✅ SENT")

        except Exception as e:
            failed += 1
            print(f"❌ FAILED — {e}")

            supabase.table("appointment_reminders").update({
                "status": "failed",
                "updated_at": now.isoformat()
            }).eq("id", reminder_id).execute()

    print("\n==============================")
    print("📊 EXECUTION SUMMARY")
    print(f"Processed: {processed}")
    print(f"Sent:      {sent}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")
    print("==============================\n")

    return {
        "processed": processed,
        "sent": sent,
        "skipped": skipped,
        "failed": failed
    }
