// src/features/services/update_cancel_appointment.jsx
// Evolvian Light — Cancel Appointment Modal (Future: Edit / Reschedule)

import { useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";

/* 🌐 API ENV */
const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8001"
    : "https://evolvian-assistant.onrender.com";

/* =========================
   Styles (Evolvian Light)
   ========================= */
const overlayStyle = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(0,0,0,0.45)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
};

const modalStyle = {
  backgroundColor: "#ffffff",
  borderRadius: "14px",
  width: "100%",
  maxWidth: "420px",
  padding: "1.5rem",
  boxShadow: "0 20px 40px rgba(0,0,0,0.2)",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
};

const titleStyle = {
  fontSize: "1.2rem",
  fontWeight: "bold",
  color: "#F5A623",
  marginBottom: "0.5rem",
};

const textStyle = {
  fontSize: "0.95rem",
  color: "#4A90E2",
  marginBottom: "1.5rem",
};

const actionsStyle = {
  display: "flex",
  justifyContent: "flex-end",
  gap: "0.75rem",
};

const cancelBtn = {
  padding: "0.5rem 1rem",
  borderRadius: "8px",
  border: "1px solid #ccc",
  background: "#f7f7f7",
  cursor: "pointer",
};

const deleteBtn = {
  padding: "0.5rem 1rem",
  borderRadius: "8px",
  border: "none",
  background: "#e5533d",
  color: "#fff",
  cursor: "pointer",
};

/* =========================
   Component
   ========================= */
export default function UpdateCancelAppointmentModal({
  open,
  onClose,
  appointmentId,
  onSuccess,
}) {
  const clientId = useClientId();
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!open) return null;

  /* =========================
     Cancel appointment
     ========================= */
  const handleCancelAppointment = async () => {
    if (!clientId || !appointmentId) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/appointments/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          appointment_id: appointmentId,
          reason: "user_cancelled",
        }),
      });

      if (!res.ok) {
        throw new Error(t("cancel_appointment_failed"));
      }

      const data = await res.json();

      onSuccess?.(data);
      onClose();
    } catch (err) {
      console.error(err);
      setError(t("cancel_appointment_error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={overlayStyle}>
      <div style={modalStyle}>
        <div style={titleStyle}>{t("cancel_appointment_title")}</div>

        <div style={textStyle}>
          {t("cancel_appointment_confirm_line1")}
          <br />
          {t("cancel_appointment_confirm_line2")}
        </div>

        {error && (
          <div style={{ color: "red", fontSize: "0.85rem", marginBottom: "1rem" }}>
            {error}
          </div>
        )}

        <div style={actionsStyle}>
          <button
            style={cancelBtn}
            onClick={onClose}
            disabled={loading}
          >
            {t("cancel_appointment_keep")}
          </button>

          <button
            style={deleteBtn}
            onClick={handleCancelAppointment}
            disabled={loading}
          >
            {loading ? t("cancel_appointment_loading") : t("cancel_appointment_action")}
          </button>
        </div>
      </div>
    </div>
  );
}
