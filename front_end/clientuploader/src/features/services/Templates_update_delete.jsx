import { useEffect, useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";

/* =========================
   Helpers
========================= */

// UI → DB
const toMinutes = (value, unit) => {
  const v = Number(value);
  if (unit === "hours") return -v * 60;
  if (unit === "days") return -v * 60 * 24;
  if (unit === "weeks") return -v * 60 * 24 * 7;
  return -v;
};

const buildLabel = (value, unit) => {
  const unitLabel =
    unit === "hours"
      ? "hour"
      : unit === "days"
      ? "day"
      : "week";

  return `${value} ${unitLabel}${value > 1 ? "s" : ""} before`;
};

// DB → UI
const fromOffsetMinutes = (offset) => {
  const minutes = Math.abs(offset);

  if (minutes % (60 * 24 * 7) === 0) {
    return { value: minutes / (60 * 24 * 7), unit: "weeks" };
  }

  if (minutes % (60 * 24) === 0) {
    return { value: minutes / (60 * 24), unit: "days" };
  }

  return { value: minutes / 60, unit: "hours" };
};

/* =========================
   Component
========================= */
export default function TemplatesUpdateDelete({
  isOpen,
  mode = "edit",
  initialData = null,
  clientId,
  onClose,
  onSuccess,
}) {
  const { t } = useLanguage();
  const [templateName, setTemplateName] = useState("");
  const [label, setLabel] = useState("");
  const [body, setBody] = useState("");
  const [reminders, setReminders] = useState([{ value: 1, unit: "hours" }]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const isWhatsApp = initialData?.channel === "whatsapp";

  /* =========================
     Prefill
  ========================= */
  useEffect(() => {
    if (!initialData) return;

    setTemplateName(initialData.template_name || "");
    setLabel(initialData.label || "");

    // 🔥 WhatsApp → mostrar preview de Meta
    if (initialData.channel === "whatsapp") {
      setBody(
        initialData.meta_preview_body ||
        initialData.body ||
        t("meta_preview_not_available")
      );
    } else {
      setBody(initialData.body || "");
    }

    if (
      initialData.type === "appointment_reminder" &&
      Array.isArray(initialData.frequency)
    ) {
      setReminders(
        initialData.frequency.map((f) =>
          fromOffsetMinutes(f.offset_minutes)
        )
      );
    }
  }, [initialData]);

  if (!isOpen || !initialData) return null;

  /* =========================
     Reminder handlers
  ========================= */
  const addReminder = () =>
    setReminders([...reminders, { value: 1, unit: "hours" }]);

  const updateReminder = (index, field, value) => {
    const updated = [...reminders];
    updated[index][field] = value;
    setReminders(updated);
  };

  const removeReminder = (index) =>
    setReminders(reminders.filter((_, i) => i !== index));

  /* =========================
     SAVE (EDIT)
  ========================= */
  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    try {
      const frequency =
        initialData.type === "appointment_reminder"
          ? reminders.map((r) => ({
              offset_minutes: toMinutes(r.value, r.unit),
              label: buildLabel(r.value, r.unit),
            }))
          : null;

      const payload = {
        label,
        ...(frequency ? { frequency } : {}),
      };

      // ⛔ WhatsApp → NO body updates
      if (!isWhatsApp) {
        payload.body = body;
        payload.template_name = templateName;
      }

      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/message_templates/${initialData.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || "Update failed");
      }

      onSuccess?.();
      onClose();
    } catch (err) {
      console.error(err);
      setError(t("template_update_failed"));
    } finally {
      setLoading(false);
    }
  };

  /* =========================
     DELETE (SOFT)
  ========================= */
  const handleDelete = async () => {
    const confirmDelete = window.confirm(
      t("template_delete_confirm")
    );

    if (!confirmDelete) return;

    try {
      setLoading(true);

      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/message_templates/${initialData.id}`,
        { method: "DELETE" }
      );

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || "Delete failed");
      }

      onSuccess?.();
      onClose();
    } catch (err) {
      console.error(err);
      alert(t("template_delete_failed"));
    } finally {
      setLoading(false);
    }
  };

  /* =========================
     UI
  ========================= */
  return (
    <div style={overlayStyle}>
      <div style={modalStyle}>
        <div style={headerStyle}>{t("template_edit_title")}</div>

        {error && <div style={{ color: "#D9534F" }}>{error}</div>}

        {/* Template name */}
        <div>
          <div style={labelStyle}>{t("template_name")}</div>
          <input
            style={inputStyle}
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            disabled={isWhatsApp}
          />
        </div>

        {/* Label */}
        <div>
          <div style={labelStyle}>{t("label")}</div>
          <input
            style={inputStyle}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>

        {/* Body */}
        <div>
          <div style={labelStyle}>{t("message_body")}</div>

          {isWhatsApp && (
            <small style={{ color: "#7A7A7A" }}>
              {t("whatsapp_template_managed_meta")}
            </small>
          )}

          <textarea
            style={{
              ...inputStyle,
              minHeight: "120px",
              backgroundColor: isWhatsApp ? "#F5F7FA" : "#FFFFFF",
              cursor: isWhatsApp ? "not-allowed" : "text",
            }}
            value={body}
            onChange={(e) => {
              if (!isWhatsApp) setBody(e.target.value);
            }}
            readOnly={isWhatsApp}
          />
        </div>

        {/* Reminders */}
        {initialData.type === "appointment_reminder" && (
          <>
            <div style={labelStyle}>{t("reminders")}</div>

            {reminders.map((r, idx) => (
              <div key={idx} style={{ display: "flex", gap: "0.5rem" }}>
                <input
                  type="number"
                  min="1"
                  value={r.value}
                  onChange={(e) =>
                    updateReminder(idx, "value", e.target.value)
                  }
                  style={{ ...inputStyle, width: "90px" }}
                />

                <select
                  value={r.unit}
                  onChange={(e) =>
                    updateReminder(idx, "unit", e.target.value)
                  }
                  style={{ ...inputStyle, width: "120px" }}
                >
                  <option value="hours">{t("hours")}</option>
                  <option value="days">{t("days")}</option>
                  <option value="weeks">{t("weeks")}</option>
                </select>

                <button onClick={() => removeReminder(idx)}>✕</button>
              </div>
            ))}

            <button onClick={addReminder}>➕ {t("add_reminder")}</button>
          </>
        )}

        {/* Footer */}
        <div style={footerStyle}>
          <button
            onClick={handleDelete}
            style={{ marginRight: "auto", color: "#D9534F" }}
          >
            🗑 {t("delete_template")}
          </button>

          <button onClick={onClose}>{t("cancel")}</button>
          <button onClick={handleSubmit} disabled={loading}>
            {loading ? t("saving") : t("save_changes")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* =========================
   Styles
========================= */
const overlayStyle = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(0,0,0,0.45)",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  zIndex: 50,
};

const modalStyle = {
  width: "520px",
  backgroundColor: "#FFFFFF",
  borderRadius: "12px",
  padding: "1.5rem 1.75rem",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
};

const headerStyle = {
  fontSize: "1.4rem",
  fontWeight: "bold",
  marginBottom: "1rem",
  color: "#F5A623",
};

const labelStyle = {
  fontSize: "0.9rem",
  fontWeight: 600,
  marginTop: "1rem",
  marginBottom: "0.25rem",
};

const inputStyle = {
  width: "100%",
  padding: "0.55rem 0.6rem",
  borderRadius: "6px",
  border: "1px solid #274472",
};

const footerStyle = {
  display: "flex",
  justifyContent: "flex-end",
  gap: "0.75rem",
  marginTop: "1.5rem",
};
