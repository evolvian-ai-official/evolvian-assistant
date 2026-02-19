import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";
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

const EMAIL_VARIABLES = [
  { label: "Empresa", token: "{{company_name}}" },
  { label: "Usuario", token: "{{user_name}}" },
  { label: "Fecha cita", token: "{{appointment_date}}" },
  { label: "Hora cita", token: "{{appointment_time}}" },
  { label: "Fecha actual", token: "{{current_date}}" },
];

const MAX_FOOTER_IMAGE_BYTES = 1024 * 1024;

const insertTokenAtCursor = (currentValue, setValue, inputRef, token) => {
  const nextValue = currentValue || "";
  const node = inputRef?.current;
  if (!node || typeof node.selectionStart !== "number") {
    setValue(`${nextValue}${token}`);
    return;
  }

  const start = node.selectionStart;
  const end = node.selectionEnd;
  const updated = `${nextValue.slice(0, start)}${token}${nextValue.slice(end)}`;
  setValue(updated);

  requestAnimationFrame(() => {
    const caret = start + token.length;
    node.focus();
    node.setSelectionRange(caret, caret);
  });
};

const appendFooterImageToBody = (htmlBody, imageUrl) => {
  if (!imageUrl) return htmlBody;
  const footerBlock = [
    "<div style=\"margin-top:24px;text-align:center;\">",
    `<img src="${imageUrl}" alt="" style="max-width:180px;height:auto;border-radius:10px;display:inline-block;" />`,
    "</div>",
  ].join("");
  return `${htmlBody}\n${footerBlock}`;
};

export default function CreateTemplateModal({ clientId, onClose, onCreated }) {
  const { t } = useLanguage();
  const API = import.meta.env.VITE_API_URL;

  const [type, setType] = useState("appointment_reminder");
  const [templateTypes, setTemplateTypes] = useState([]);
  const [label, setLabel] = useState("");
  const [body, setBody] = useState("");
  const [includeFooterImage, setIncludeFooterImage] = useState(false);
  const [footerImageFile, setFooterImageFile] = useState(null);
  const [footerImageName, setFooterImageName] = useState("");
  const [reminders, setReminders] = useState([{ value: 1, unit: "hours" }]);
  const [loading, setLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );

  const subjectInputRef = useRef(null);
  const bodyTextareaRef = useRef(null);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    authFetch(`${API}/message_templates/types`)
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

  const addReminder = () => setReminders([...reminders, { value: 1, unit: "hours" }]);

  const updateReminder = (index, field, value) => {
    const updated = [...reminders];
    updated[index][field] = value;
    setReminders(updated);
  };

  const removeReminder = (index) => setReminders(reminders.filter((_, i) => i !== index));

  const handleFooterImageChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Please select a valid image file.");
      return;
    }

    if (file.size > MAX_FOOTER_IMAGE_BYTES) {
      alert("Image too large. Max size is 1MB.");
      return;
    }

    setFooterImageFile(file);
    setFooterImageName(file.name);
  };

  const handleSubmit = async () => {
    if (!clientId) {
      alert(t("template_client_not_ready"));
      return;
    }

    if (!body.trim()) {
      alert(t("template_message_required"));
      return;
    }

    if (includeFooterImage && !footerImageFile) {
      alert("Select an image for the footer or disable the footer image option.");
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
      channel: "email",
      type,
      label: label || null,
      ...(frequency ? { frequency } : {}),
    };

    let finalBody = body.trim();
    if (includeFooterImage && footerImageFile) {
      const formData = new FormData();
      formData.append("client_id", clientId);
      formData.append("file", footerImageFile);

      const uploadRes = await authFetch(`${API}/message_templates/footer_image`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        const text = await uploadRes.text();
        throw new Error(text || "Footer image upload failed");
      }

      const uploadData = await uploadRes.json();
      const footerImageUrl = uploadData?.url;
      if (!footerImageUrl) {
        throw new Error("Footer image URL not returned");
      }

      finalBody = appendFooterImageToBody(finalBody, footerImageUrl);
    }
    payload.body = finalBody;

    try {
      setLoading(true);

      const res = await authFetch(`${API}/message_templates`, {
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
        <h2 style={{ color: "#274472", marginTop: 0 }}>Create Email Template</h2>

        <div
          style={{
            marginTop: "0.3rem",
            marginBottom: "0.7rem",
            padding: "0.55rem 0.65rem",
            border: "1px solid #E6EEF8",
            borderRadius: "8px",
            backgroundColor: "#F8FBFF",
            color: "#466286",
            fontSize: "0.82rem",
          }}
        >
          WhatsApp templates are managed by Meta sync and appear automatically in the list.
        </div>

        <label className="ia-form-label">{t("type")}</label>
        <select value={type} onChange={(e) => setType(e.target.value)} className="ia-form-input">
          {templateTypes.map((tplType) => (
            <option key={tplType.id} value={tplType.id}>
              {tplType.description || tplType.id}
            </option>
          ))}
        </select>

        <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>Subject</label>
        <input
          ref={subjectInputRef}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="ia-form-input"
          placeholder="e.g. Confirmación para {{user_name}}"
        />
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.4rem" }}>
          {EMAIL_VARIABLES.map((variable) => (
            <button
              key={`subject-${variable.token}`}
              type="button"
              className="ia-button ia-button-ghost"
              onClick={() =>
                insertTokenAtCursor(label, setLabel, subjectInputRef, variable.token)
              }
              style={{ padding: "0.25rem 0.45rem", fontSize: "0.76rem" }}
            >
              {variable.label}
            </button>
          ))}
        </div>

        <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>Message body</label>
        <textarea
          ref={bodyTextareaRef}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
          className="ia-form-input"
          style={{ resize: "vertical" }}
          placeholder="Hola {{user_name}}, tu cita en {{company_name}} es el {{appointment_date}}."
        />
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.4rem" }}>
          {EMAIL_VARIABLES.map((variable) => (
            <button
              key={`body-${variable.token}`}
              type="button"
              className="ia-button ia-button-ghost"
              onClick={() =>
                insertTokenAtCursor(body, setBody, bodyTextareaRef, variable.token)
              }
              style={{ padding: "0.25rem 0.45rem", fontSize: "0.76rem" }}
            >
              {variable.label}
            </button>
          ))}
        </div>

        <label className="ia-form-label" style={{ marginTop: "0.7rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={includeFooterImage}
            onChange={(e) => {
              setIncludeFooterImage(e.target.checked);
              if (!e.target.checked) {
                setFooterImageFile(null);
                setFooterImageName("");
              }
            }}
          />
          Add company image in footer (optional)
        </label>

        {includeFooterImage && (
          <div style={{ marginTop: "0.3rem" }}>
            <input type="file" accept="image/*" onChange={handleFooterImageChange} />
            {footerImageName && (
              <div style={{ fontSize: "0.78rem", color: "#5f6b7a", marginTop: "0.25rem" }}>
                Selected: {footerImageName}
              </div>
            )}
          </div>
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
            {loading ? t("saving") : "Create Email Template"}
          </button>
        </div>
      </div>
    </div>
  );
}
