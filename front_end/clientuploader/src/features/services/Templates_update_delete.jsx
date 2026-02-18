import { useEffect, useRef, useState } from "react";
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

export default function TemplatesUpdateDelete({
  isOpen,
  initialData = null,
  clientId,
  onClose,
  onSuccess,
}) {
  const { t } = useLanguage();
  const [templateName, setTemplateName] = useState("");
  const [label, setLabel] = useState("");
  const [body, setBody] = useState("");
  const [includeFooterImage, setIncludeFooterImage] = useState(false);
  const [footerImageFile, setFooterImageFile] = useState(null);
  const [footerImageName, setFooterImageName] = useState("");
  const [reminders, setReminders] = useState([{ value: 1, unit: "hours" }]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );
  const subjectInputRef = useRef(null);
  const bodyTextareaRef = useRef(null);

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
    setIncludeFooterImage(false);
    setFooterImageFile(null);
    setFooterImageName("");
  }, [initialData]);

  if (!isOpen || !initialData) return null;

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
        if (includeFooterImage && !footerImageFile) {
          throw new Error("Footer image option is enabled but no image is selected.");
        }
        let finalBody = body;
        if (includeFooterImage && footerImageFile) {
          const formData = new FormData();
          formData.append("client_id", clientId || "");
          formData.append("file", footerImageFile);

          const uploadRes = await fetch(`${import.meta.env.VITE_API_URL}/message_templates/footer_image`, {
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
          <div className="ia-form-label">{isWhatsApp ? t("template_name") : "Subject"}</div>
          <input
            ref={subjectInputRef}
            className="ia-form-input"
            value={isWhatsApp ? templateName : label}
            onChange={(e) => {
              if (isWhatsApp) {
                setTemplateName(e.target.value);
              } else {
                setLabel(e.target.value);
              }
            }}
            disabled={isWhatsApp}
          />
        </div>

        {!isWhatsApp && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.4rem" }}>
            {EMAIL_VARIABLES.map((variable) => (
              <button
                key={`edit-subject-${variable.token}`}
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
        )}

        {isWhatsApp && (
          <div>
            <div className="ia-form-label">{t("label")}</div>
            <input className="ia-form-input" value={label} onChange={(e) => setLabel(e.target.value)} />
          </div>
        )}

        <div>
          <div className="ia-form-label">{t("message_body")}</div>

          {isWhatsApp && (
            <small style={{ color: "#7A7A7A" }}>{t("whatsapp_template_managed_meta")}</small>
          )}

          <textarea
            ref={bodyTextareaRef}
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

        {!isWhatsApp && (
          <>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.35rem" }}>
              {EMAIL_VARIABLES.map((variable) => (
                <button
                  key={`edit-body-${variable.token}`}
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
          </>
        )}

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
