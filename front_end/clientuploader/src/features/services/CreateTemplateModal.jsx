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

export default function CreateTemplateModal({ clientId, onClose, onCreated }) {
  const { t } = useLanguage();
  const API = import.meta.env.VITE_API_URL;

  const [channel, setChannel] = useState("whatsapp");
  const [type, setType] = useState("appointment_reminder");

  const [templateTypes, setTemplateTypes] = useState([]);
  const [metaTemplates, setMetaTemplates] = useState([]);
  const [selectedMetaTemplateId, setSelectedMetaTemplateId] = useState("");

  const [label, setLabel] = useState("");
  const [body, setBody] = useState("");

  const [reminders, setReminders] = useState([{ value: 1, unit: "hours" }]);
  const [loading, setLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    fetch(`${API}/message_templates/types`)
      .then((r) => r.json())
      .then((data) => {
        const types = data || [];
        setTemplateTypes(types);

        const exists = types.some((tplType) => tplType.id === type);
        if (!exists && types.length > 0) {
          setType(types[0].id);
        }
      })
      .catch(() => setTemplateTypes([]));
  }, []);

  useEffect(() => {
    if (channel !== "whatsapp") {
      setMetaTemplates([]);
      return;
    }

    setSelectedMetaTemplateId("");

    fetch(`${API}/meta_approved_templates?type=${type}&channel=${channel}`)
      .then((r) => r.json())
      .then((data) => setMetaTemplates(data || []))
      .catch(() => setMetaTemplates([]));
  }, [type, channel]);

  const selectedTemplate = metaTemplates.find((tpl) => tpl.id === selectedMetaTemplateId);

  const addReminder = () => setReminders([...reminders, { value: 1, unit: "hours" }]);

  const updateReminder = (index, field, value) => {
    const updated = [...reminders];
    updated[index][field] = value;
    setReminders(updated);
  };

  const removeReminder = (index) => setReminders(reminders.filter((_, i) => i !== index));

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
        const text = await res.text();
        throw new Error(text);
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

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.4)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1100,
        padding: "1rem",
      }}
    >
      <div
        style={{
          backgroundColor: "#fff",
          padding: "1rem",
          borderRadius: "12px",
          width: "min(92vw, 560px)",
          maxHeight: "88dvh",
          overflowY: "auto",
        }}
      >
        <h2 style={{ color: "#274472", marginTop: 0 }}>{t("template_create_title")}</h2>

        <label className="ia-form-label">{t("channel")}</label>
        <select value={channel} onChange={(e) => setChannel(e.target.value)} className="ia-form-input">
          <option value="whatsapp">WhatsApp</option>
          <option value="email">Email</option>
        </select>

        <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>{t("type")}</label>
        <select value={type} onChange={(e) => setType(e.target.value)} className="ia-form-input">
          {templateTypes.map((tplType) => (
            <option key={tplType.id} value={tplType.id}>
              {tplType.description || tplType.id}
            </option>
          ))}
        </select>

        {channel === "whatsapp" && (
          <>
            <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>Meta template</label>
            <select
              value={selectedMetaTemplateId}
              onChange={(e) => setSelectedMetaTemplateId(e.target.value)}
              className="ia-form-input"
            >
              <option value="">{t("template_select_placeholder")}</option>
              {metaTemplates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.template_name || t("template")}
                </option>
              ))}
            </select>

            {selectedTemplate && (
              <div
                style={{
                  marginTop: "0.6rem",
                  padding: "0.75rem",
                  backgroundColor: "#f7f7f7",
                  borderRadius: "6px",
                  fontSize: "0.85rem",
                  border: "1px solid #EDEDED",
                }}
              >
                <strong>{t("preview")}:</strong>
                <p style={{ marginTop: "0.5rem", marginBottom: "0.4rem" }}>{selectedTemplate.preview_body}</p>
                <small>
                  {t("parameters_required")}: {selectedTemplate.parameter_count}
                </small>
              </div>
            )}
          </>
        )}

        <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>{t("label_optional")}</label>
        <input value={label} onChange={(e) => setLabel(e.target.value)} className="ia-form-input" />

        {channel === "email" && (
          <>
            <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>Message body</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={4}
              className="ia-form-input"
              style={{ resize: "vertical" }}
            />
          </>
        )}

        {type === "appointment_reminder" && (
          <>
            <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>{t("reminders")}</label>
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
            <button type="button" onClick={addReminder} className="ia-button ia-button-ghost" style={{ marginTop: "0.3rem" }}>
              ➕ {t("add_reminder")}
            </button>
          </>
        )}

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.5rem",
            marginTop: "1rem",
            flexDirection: isMobile ? "column-reverse" : "row",
          }}
        >
          <button type="button" onClick={onClose} className="ia-button ia-button-ghost">
            {t("cancel")}
          </button>
          <button type="button" onClick={handleSubmit} disabled={loading} className="ia-button ia-button-primary">
            {loading ? t("saving") : t("create")}
          </button>
        </div>
      </div>
    </div>
  );
}
