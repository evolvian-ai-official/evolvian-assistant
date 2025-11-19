# =====================================================
# 📧 notify_business_owner.py — Notify the business owner
# =====================================================

import os
import requests
import logging
from api.modules.assistant_rag.supabase_client import supabase

logger = logging.getLogger(__name__)


def notify_business_owner(
    client_id: str,
    slot_time: str,
    user_email: str,
    user_name: str,
    user_phone: str | None = None,
):
    """
    Sends an automatic notification to the business owner when a new appointment is booked.
    It tries to retrieve the owner's email from:
      1) calendar_integrations (Google Calendar connection)
      2) a join between clients → users (the platform account)
    If no email is found, a fallback admin address is used.
    The notification includes the customer's name, email, phone, and appointment time.
    """

    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY is not defined")

    owner_email = None

    # === 1️⃣ Try from calendar_integrations ===
    try:
        res = (
            supabase.table("calendar_integrations")
            .select("connected_email")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        if res.data and isinstance(res.data, list) and len(res.data) > 0:
            email_candidate = res.data[0].get("connected_email")
            if email_candidate:
                owner_email = email_candidate
                logger.info(f"📬 Business owner email found in calendar_integrations: {owner_email}")
        else:
            logger.info("ℹ️ No active email in calendar_integrations, trying join with users...")
    except Exception as e:
        logger.warning(f"⚠️ Error retrieving from calendar_integrations: {e}")

    # === 2️⃣ Fallback: join clients → users ===
    if not owner_email:
        try:
            res = (
                supabase.table("clients")
                .select("id, user_id, users(email)")
                .eq("id", client_id)
                .limit(1)
                .execute()
            )

            if res.data and len(res.data) > 0:
                client_record = res.data[0]
                user_data = client_record.get("users")
                if user_data and "email" in user_data:
                    owner_email = user_data["email"]
                    logger.info(f"📬 Business owner email found via clients→users: {owner_email}")
                else:
                    logger.warning(f"⚠️ users.email not found in join for client_id={client_id}")
            else:
                logger.warning(f"⚠️ No client found with id={client_id}")
        except Exception as e:
            logger.error(f"❌ Error executing join clients→users: {e}")

    # === 3️⃣ Fallback if still missing ===
    if not owner_email:
        owner_email = os.getenv("ADMIN_FALLBACK_EMAIL", "support@evolvianai.com")
        logger.warning(f"⚠️ Owner email not found; using fallback {owner_email}")

    # === 4️⃣ Prepare email body ===
    phone_html = f"<li><strong>Customer phone:</strong> {user_phone}</li>" if user_phone else ""

    body = {
        "from": "Evolvian AI <notifications@notifications.evolvianai.com>",
        "to": [owner_email],
        "subject": "📅 New Appointment Scheduled",
        "html": f"""
        <p>Hello 👋,</p>
        <p>A new appointment has been scheduled through your Evolvian Assistant:</p>
        <ul>
          <li><strong>Date & time:</strong> {slot_time}</li>
          <li><strong>Customer name:</strong> {user_name}</li>
          <li><strong>Customer email:</strong> {user_email}</li>
          {phone_html}
        </ul>
        <p>Please check your Google Calendar or Evolvian Dashboard for details.</p>
        <p style='color:#888;font-size:12px;'>Automatically sent by Evolvian AI</p>
        """,
    }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    # === 5️⃣ Send via Resend API ===
    try:
        response = requests.post("https://api.resend.com/emails", headers=headers, json=body)
        if response.status_code >= 400:
            logger.error(f"❌ Failed to send email: {response.status_code} - {response.text}")
            raise Exception(f"Resend error: {response.text}")

        logger.info(f"✅ Notification successfully sent to {owner_email}")
    except Exception as e:
        logger.error(f"❌ Error sending notification to {owner_email}: {e}")
