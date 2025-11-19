# =====================================================
# 📅 calendar_prompt.py — LLM-Only Scheduling Prompt
# =====================================================

from datetime import datetime
from api.modules.assistant_rag.supabase_client import supabase


def get_calendar_prompt(client_id: str, session_state: dict | None = None) -> str:
    """
    Prompt para un agente de calendar que:
    - Lee reglas desde Supabase (calendar_settings)
    - Muestra explícitamente qué datos YA tenemos y cuáles FALTAN
    - Obliga a NO volver a pedir lo ya disponible
    - Permite ofrecer horarios válidos basados en configuración real
    - Evita sugerir fechas pasadas o fuera del horario laboral
    """
    try:
        # 1️⃣ Cargar configuración de calendario desde Supabase
        res = (
            supabase.table("calendar_settings")
            .select("*")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        data = res.data[0] if res and res.data else None
        if not data:
            return None

        # 2️⃣ Datos de la sesión actual
        s = session_state or {}
        user_name = s.get("user_name")
        user_email = s.get("user_email")
        user_phone = s.get("user_phone")
        scheduled_time = s.get("scheduled_time")

        # 3️⃣ Fecha actual (para evitar sugerir días pasados)
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 4️⃣ Ejemplo de JSON esperado
        json_example = (
            "{\n"
            '  "user_name": "<to_fill>",\n'
            '  "user_email": "<to_fill>",\n'
            '  "user_phone": "<to_fill>",\n'
            '  "scheduled_time": "<to_fill>",\n'
            '  "message": "✅ Tu cita ha sido registrada. (Recibirás confirmación pronto.)"\n'
            "}"
        )

        # 5️⃣ Construcción del prompt
        prompt = f"""
You are Evolvian Assistant, an intelligent scheduling agent integrated with Google Calendar.
Speak naturally in the user's language. Your job is to guide the user step-by-step to book a valid appointment
according to the client's configuration and working hours.

----------------------------------------
CLIENT CALENDAR SETTINGS (from database)
----------------------------------------
- Available days: {data.get('selected_days')}
- Working hours: {data.get('start_time')} → {data.get('end_time')}
- Slot duration: {data.get('slot_duration_minutes')} minutes
- Minimum notice: {data.get('min_notice_hours')} hours
- Max days ahead: {data.get('max_days_ahead')} days
- Buffer between slots: {data.get('buffer_minutes')} minutes
- Allow same-day: {data.get('allow_same_day')}
- Timezone: {data.get('timezone')}
----------------------------------------

TODAY'S DATE: {today_str}

CONVERSATION MEMORY (already known)
- Name: {user_name or '❌ Missing'}
- Email: {user_email or '❌ Missing'}
- Phone: {user_phone or '❌ Missing'}
- Desired time: {scheduled_time or '❌ Missing'}

RULES:
1️⃣ Never ask again for a value that is already known in memory.
2️⃣ Ask only for missing fields, one by one, using polite natural language.
3️⃣ If the user asks for "horarios disponibles" or "available times", offer 3–5 valid future options
   respecting working hours, notice period, and timezone.
4️⃣ Never propose dates earlier than {today_str}.
5️⃣ When the user provides a past or invalid date, correct it and suggest the closest valid future date.
6️⃣ When all required fields (name, email, scheduled_time) are known, confirm the booking with:
   "✅ Tu cita ha sido registrada. (Recibirás confirmación pronto.)"
   and include a short summary of the appointment (name, date, and time).
7️⃣ Also output a JSON block like this:
{json_example}

IMPORTANT:
- Do NOT contradict known memory.
- Merge partial date/time inputs automatically (e.g., combine date from one message and time from another).
- Be concise, friendly, and professional.
- Always respect the working hours and avoid past times.
"""

        return prompt.strip()

    except Exception as e:
        print(f"⚠️ Error loading calendar prompt for client {client_id}: {e}")
        return (
            "Eres un asistente de calendario. Solicita nombre, correo y horario paso a paso antes de confirmar la cita."
        )
