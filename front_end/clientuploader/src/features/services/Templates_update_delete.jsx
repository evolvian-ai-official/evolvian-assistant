import { useEffect, useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";
import "../../components/ui/internal-admin-responsive.css";

const toMinutes = (value, unit) => {
  const v = Number(value);
  if (unit === "hours") return -v * 60;
  if (unit === "days") return -v * 60 * 24;
  if (unit === "weeks") return -v * 60 * 24 * 7;
  return -v;
};

const buildLabel = (value, unit) => {
  const unitLabel = unit === "hours" ? "hour" : unit === "days" ? "day" : "week";
  return `${value} ${unitLabel}${value > 1 ? "s" : ""} before`;
};

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
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );

  const isWhatsApp = initialData?.channel === "whatsapp";

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (!initialData) return;

    setTemplateName(initialData.template_name || "");
    setLabel(initialData.label || "");

    if (initialData.channel === "whatsapp") {
      setBody(initialData.meta_preview_body || initialData.body || t("meta_preview_not_available"));
    } else {
      setBody(initialData.body || "");
    }

    if (initialData.type === "appointment_reminder" && Array.isArray(initialData.frequency)) {
      setReminders(initialData.frequency.map((f) => fromOffsetMinutes(f.offset_minutes)));
    }
  }, [initialData]);

  if (!isOpen || !initialData) return null;

  const addReminder = () => setReminders([...reminders, { value: 1, unit: "hours" }]);

  const updateReminder = (index, field, value) => {
    const updated = [...reminders];
    updated[index][field] = value;
    setReminders(updated);
  };

  const removeReminder = (index) => setReminders(reminders.filter((_, i) => i !== index));

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

      if (!isWhatsApp) {
        payload.body = body;
        payload.template_name = templateName;
      }

      const res = await fetch(`${import.meta.env.VITE_API_URL}/message_templates/${initialData.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

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

  const handleDelete = async () => {
    const confirmDelete = window.confirm(t("template_delete_confirm"));
    if (!confirmDelete) return;

    try {
      setLoading(true);

      const res = await fetch(`${import.meta.env.VITE_API_URL}/message_templates/${initialData.id}`, {
        method: "DELETE",
      });

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

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.45)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1200,
        padding: "1rem",
      }}
    >
      <div
        style={{
          width: "min(92vw, 560px)",
          backgroundColor: "#FFFFFF",
          borderRadius: "12px",
          padding: "1rem",
          fontFamily: "system-ui, sans-serif",
          color: "#274472",
          maxHeight: "88dvh",
          overflowY: "auto",
        }}
      >
        <div style={{ fontSize: "1.25rem", fontWeight: 800, marginBottom: "0.8rem", color: "#F5A623" }}>
          {t("template_edit_title")}
        </div>

        {error && <div style={{ color: "#D9534F", marginBottom: "0.6rem" }}>{error}</div>}

        <div>
          <div className="ia-form-label">{t("template_name")}</div>
          <input
            className="ia-form-input"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            disabled={isWhatsApp}
          />
        </div>

        <div>
          <div className="ia-form-label">{t("label")}</div>
          <input className="ia-form-input" value={label} onChange={(e) => setLabel(e.target.value)} />
        </div>

        <div>
          <div className="ia-form-label">{t("message_body")}</div>

          {isWhatsApp && (
            <small style={{ color: "#7A7A7A" }}>{t("whatsapp_template_managed_meta")}</small>
          )}

          <textarea
            className="ia-form-input"
            style={{
              minHeight: "120px",
              backgroundColor: isWhatsApp ? "#F5F7FA" : "#FFFFFF",
              cursor: isWhatsApp ? "not-allowed" : "text",
              resize: "vertical",
            }}
            value={body}
            onChange={(e) => {
              if (!isWhatsApp) setBody(e.target.value);
            }}
            readOnly={isWhatsApp}
          />
        </div>

        {initialData.type === "appointment_reminder" && (
          <>
            <div className="ia-form-label">{t("reminders")}</div>

            {reminders.map((r, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                  marginBottom: "0.4rem",
                }}
              >
                <input
                  type="number"
                  min="1"
                  value={r.value}
                  onChange={(e) => updateReminder(idx, "value", e.target.value)}
                  className="ia-form-input"
                  style={{ width: isMobile ? "100%" : "90px" }}
                />

                <select
                  value={r.unit}
                  onChange={(e) => updateReminder(idx, "unit", e.target.value)}
                  className="ia-form-input"
                  style={{ width: isMobile ? "100%" : "130px" }}
                >
                  <option value="hours">{t("hours")}</option>
                  <option value="days">{t("days")}</option>
                  <option value="weeks">{t("weeks")}</option>
                </select>

                <button
                  type="button"
                  className="ia-button ia-button-ghost"
                  onClick={() => removeReminder(idx)}
                  style={{ width: isMobile ? "100%" : "auto" }}
                >
                  ✕
                </button>
              </div>
            ))}

            <button type="button" onClick={addReminder} className="ia-button ia-button-ghost">
              ➕ {t("add_reminder")}
            </button>
          </>
        )}

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.75rem",
            marginTop: "1rem",
            flexDirection: isMobile ? "column-reverse" : "row",
          }}
        >
          <button type="button" onClick={handleDelete} className="ia-button" style={{ marginRight: "auto", color: "#D9534F", background: "#fff", border: "1px solid #f4c5c0" }}>
            🗑 {t("delete_template")}
          </button>

          <button type="button" onClick={onClose} className="ia-button ia-button-ghost">
            {t("cancel")}
          </button>
          <button type="button" onClick={handleSubmit} disabled={loading} className="ia-button ia-button-primary">
            {loading ? t("saving") : t("save_changes")}
          </button>
        </div>
      </div>
    </div>
  );
}
