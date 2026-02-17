import { useEffect, useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";

/* ======================================================
   Helpers
====================================================== */

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

/* ======================================================
   Modal
====================================================== */

export default function CreateTemplateModal({
  clientId,
  onClose,
  onCreated,
}) {
  const { t } = useLanguage();
  const API = import.meta.env.VITE_API_URL;

  const [channel, setChannel] = useState("whatsapp");
  const [type, setType] = useState("appointment_reminder");

  const [templateTypes, setTemplateTypes] = useState([]);
  const [metaTemplates, setMetaTemplates] = useState([]);
  const [selectedMetaTemplateId, setSelectedMetaTemplateId] =
    useState("");

  const [label, setLabel] = useState("");
  const [body, setBody] = useState("");

  const [reminders, setReminders] = useState([
    { value: 1, unit: "hours" },
  ]);

  const [loading, setLoading] = useState(false);

  /* =========================
     Load Template Types
  ========================= */
  useEffect(() => {
    fetch(`${API}/message_templates/types`)
      .then((r) => r.json())
      .then((data) => {
        const types = data || [];
        setTemplateTypes(types);

        // Solo cambiar type si el actual no existe
        const exists = types.some((t) => t.id === type);
        if (!exists && types.length > 0) {
          setType(types[0].id);
        }
      })
      .catch(() => setTemplateTypes([]));
  }, []);

  /* =========================
     Load Meta templates
     FILTRADO POR TYPE + CHANNEL
  ========================= */
  useEffect(() => {
    if (channel !== "whatsapp") {
      setMetaTemplates([]);
      return;
    }

    setSelectedMetaTemplateId("");

    fetch(
      `${API}/meta_approved_templates?type=${type}&channel=${channel}`
    )
      .then((r) => r.json())
      .then((data) => setMetaTemplates(data || []))
      .catch(() => setMetaTemplates([]));
  }, [type, channel]);

  const selectedTemplate = metaTemplates.find(
    (t) => t.id === selectedMetaTemplateId
  );

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
     Submit
  ========================= */
  const handleSubmit = async () => {
    if (!clientId) {
      alert(t("template_client_not_ready"));
      return;
    }

    if (channel === "whatsapp" && !selectedMetaTemplateId) {
      alert(t("template_select_meta"));
      return;
    }

    if (channel === "email" && !body.trim()) {
      alert(t("template_message_required"));
      return;
    }

    const frequency =
      type === "appointment_reminder"
        ? reminders.map((r) => ({
            offset_minutes: toMinutes(r.value, r.unit),
            label: buildLabel(r.value, r.unit),
          }))
        : null;

    const payload = {
      client_id: clientId,
      channel,
      type,
      label: label || null,
      ...(frequency ? { frequency } : {}),
    };

    if (channel === "whatsapp") {
      payload.meta_template_id = selectedMetaTemplateId;
    } else {
      payload.body = body.trim();
    }

    try {
      setLoading(true);

      const res = await fetch(`${API}/message_templates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const t = await res.text();
        throw new Error(t);
      }

      onCreated?.();
      onClose();
    } catch (err) {
      console.error(err);
      alert(t("template_create_failed"));
    } finally {
      setLoading(false);
    }
  };

  /* =========================
     UI
  ========================= */
  return (
    <div style={modalOverlay}>
      <div style={modalCard}>
        <h2 style={{ color: "#274472" }}>
          {t("template_create_title")}
        </h2>

        {/* Channel */}
        <label style={labelStyle}>{t("channel")}</label>
        <select
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
          style={inputStyle}
        >
          <option value="whatsapp">WhatsApp</option>
          <option value="email">Email</option>
        </select>

        {/* Type */}
        <label style={labelStyle}>{t("type")}</label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          style={inputStyle}
        >
          {templateTypes.map((t) => (
            <option key={t.id} value={t.id}>
              {t.description || t.id}
            </option>
          ))}
        </select>

        {/* META TEMPLATE */}
        {channel === "whatsapp" && (
          <>
            <label style={labelStyle}>Meta template</label>
            <select
              value={selectedMetaTemplateId}
              onChange={(e) =>
                setSelectedMetaTemplateId(e.target.value)
              }
              style={inputStyle}
            >
              <option value="">{t("template_select_placeholder")}</option>
              {metaTemplates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.template_name || t("template")}
                </option>
              ))}
            </select>

            {selectedTemplate && (
              <div style={previewBox}>
                <strong>{t("preview")}:</strong>
                <p style={{ marginTop: "0.5rem" }}>
                  {selectedTemplate.preview_body}
                </p>
                <small>
                  {t("parameters_required")}:{" "}
                  {selectedTemplate.parameter_count}
                </small>
              </div>
            )}
          </>
        )}

        {/* LABEL */}
        <label style={labelStyle}>{t("label_optional")}</label>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          style={inputStyle}
        />

        {/* BODY (EMAIL ONLY) */}
        {channel === "email" && (
          <>
            <label style={labelStyle}>Message body</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={4}
              style={inputStyle}
            />
          </>
        )}

        {/* REMINDERS */}
        {type === "appointment_reminder" && (
          <>
            <label style={labelStyle}>{t("reminders")}</label>
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

        {/* ACTIONS */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
          <button onClick={onClose}>{t("cancel")}</button>
          <button onClick={handleSubmit} disabled={loading}>
            {loading ? t("saving") : t("create")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* =========================
   Styles
========================= */

const modalOverlay = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(0,0,0,0.4)",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
};

const modalCard = {
  backgroundColor: "#fff",
  padding: "1.5rem",
  borderRadius: "12px",
  width: "520px",
};

const labelStyle = {
  fontSize: "0.8rem",
  fontWeight: "bold",
  marginTop: "0.75rem",
};

const inputStyle = {
  width: "100%",
  padding: "0.45rem",
  borderRadius: "6px",
  border: "1px solid #ccc",
};

const previewBox = {
  marginTop: "0.5rem",
  padding: "0.75rem",
  backgroundColor: "#f7f7f7",
  borderRadius: "6px",
  fontSize: "0.85rem",
};
