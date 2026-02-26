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

const SUBJECT_VARIABLE_TOKENS = [
  { key: "create_template_modal_var_company", token: "{{company_name}}" },
  { key: "create_template_modal_var_user", token: "{{user_name}}" },
  { key: "create_template_modal_var_appointment_date", token: "{{appointment_date}}" },
  { key: "create_template_modal_var_appointment_time", token: "{{appointment_time}}" },
  { key: "create_template_modal_var_current_date", token: "{{current_date}}" },
];

const BODY_EXTRA_VARIABLE_TOKENS = [
  { key: "create_template_modal_var_cancel_button", token: "{{cancel_appointment_button}}" },
];
const EMAIL_LINE_BREAK_TOKEN = "<br />";

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

const normalizeEmailBodyLineBreaks = (value) => {
  const normalized = String(value || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!normalized.includes("\n")) return normalized;

  const lines = normalized.split("\n");
  const isStandaloneHtmlLine = (line) => /^\s*<[^>]+>\s*$/.test(line || "");
  let output = "";

  for (let index = 0; index < lines.length; index += 1) {
    const current = lines[index] ?? "";
    output += current;

    if (index >= lines.length - 1) continue;

    const next = lines[index + 1] ?? "";
    const shouldInsertHtmlBreak = !isStandaloneHtmlLine(current) && !isStandaloneHtmlLine(next);
    output += shouldInsertHtmlBreak ? `${EMAIL_LINE_BREAK_TOKEN}\n` : "\n";
  }

  return output;
};

export default function TemplatesUpdateDelete({
  isOpen,
  initialData = null,
  clientId,
  focusReminderFrequency = false,
  onClose,
  onSuccess,
}) {
  const { t, lang } = useLanguage();
  const isEs = lang === "es";
  const SUBJECT_VARIABLES = SUBJECT_VARIABLE_TOKENS.map((item) => ({
    label: t(item.key),
    token: item.token,
  }));
  const BODY_VARIABLES = [
    ...SUBJECT_VARIABLES,
    ...BODY_EXTRA_VARIABLE_TOKENS.map((item) => ({
      label: t(item.key),
      token: item.token,
    })),
  ];
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
  const reminderSectionRef = useRef(null);
  const firstReminderValueRef = useRef(null);

  const isWhatsApp = initialData?.channel === "whatsapp";
  const isWidget = initialData?.channel === "widget";
  const isEmail = initialData?.channel === "email";
  const supportsReminderFrequency =
    !isWidget && initialData?.type === "appointment_reminder";

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

    if (initialData.type === "appointment_reminder") {
      if (Array.isArray(initialData.frequency) && initialData.frequency.length > 0) {
        setReminders(initialData.frequency.map((f) => fromOffsetMinutes(f.offset_minutes)));
      } else {
        setReminders([{ value: 1, unit: "hours" }]);
      }
    }
    setIncludeFooterImage(false);
    setFooterImageFile(null);
    setFooterImageName("");
  }, [initialData]);

  useEffect(() => {
    if (!isOpen || !supportsReminderFrequency || !focusReminderFrequency) return;
    const id = requestAnimationFrame(() => {
      if (reminderSectionRef.current?.scrollIntoView) {
        reminderSectionRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      if (firstReminderValueRef.current?.focus) {
        firstReminderValueRef.current.focus();
      }
    });
    return () => cancelAnimationFrame(id);
  }, [isOpen, supportsReminderFrequency, focusReminderFrequency, initialData?.id]);

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
      alert(t("create_template_modal_invalid_image_file"));
      return;
    }

    if (file.size > MAX_FOOTER_IMAGE_BYTES) {
      alert(t("create_template_modal_image_too_large"));
      return;
    }

    setFooterImageFile(file);
    setFooterImageName(file.name);
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    try {
      const frequency = supportsReminderFrequency
        ? reminders.map((r) => ({
            offset_minutes: toMinutes(r.value, r.unit),
            label: buildLabel(r.value, r.unit),
          }))
        : null;

      const payload = {
        label,
        ...(frequency ? { frequency } : {}),
      };

      if (isEmail) {
        if (includeFooterImage && !footerImageFile) {
          throw new Error(t("create_template_modal_select_footer_image_or_disable"));
        }
        let finalBody = normalizeEmailBodyLineBreaks(body);
        if (includeFooterImage && footerImageFile) {
          const formData = new FormData();
          formData.append("client_id", clientId || "");
          formData.append("file", footerImageFile);

          const uploadRes = await authFetch(`${import.meta.env.VITE_API_URL}/message_templates/footer_image`, {
            method: "POST",
            body: formData,
          });

          if (!uploadRes.ok) {
            const text = await uploadRes.text();
            throw new Error(text || t("create_template_modal_footer_image_upload_failed"));
          }

          const uploadData = await uploadRes.json();
          const footerImageUrl = uploadData?.url;
          if (!footerImageUrl) {
            throw new Error(t("create_template_modal_footer_image_url_missing"));
          }

          finalBody = appendFooterImageToBody(finalBody, footerImageUrl);
        }

        payload.body = finalBody;
        payload.template_name = templateName;
      } else if (isWidget) {
        payload.body = body;
      }

      const res = await authFetch(`${import.meta.env.VITE_API_URL}/message_templates/${initialData.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || t("template_update_failed"));
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
    if (isWhatsApp) {
      alert(t("template_delete_meta_managed"));
      return;
    }

    const confirmDelete = window.confirm(t("template_delete_confirm"));
    if (!confirmDelete) return;

    try {
      setLoading(true);

      const res = await authFetch(`${import.meta.env.VITE_API_URL}/message_templates/${initialData.id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || "Delete failed");
      }

      let deletedPayload = null;
      try {
        deletedPayload = await res.json();
      } catch {
        deletedPayload = null;
      }

      onSuccess?.({
        action: "deactivated",
        templateId: initialData.id,
        template: deletedPayload?.template || null,
      });
      onClose();
    } catch (err) {
      console.error(err);
      const detail =
        err instanceof Error && err.message
          ? err.message
          : t("template_delete_failed");
      alert(`${t("template_delete_failed")}: ${detail}`);
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

        {focusReminderFrequency && supportsReminderFrequency && (
          <div
            style={{
              marginBottom: "0.8rem",
              padding: "0.6rem 0.7rem",
              borderRadius: 10,
              border: "1px solid #F5D7A8",
              backgroundColor: "#FFF7EA",
              color: "#7A4D00",
              fontSize: "0.86rem",
              lineHeight: 1.4,
            }}
          >
            {isEs
              ? "Configura la frecuencia del reminder para habilitar el envío automático en appointments."
              : "Set the reminder schedule to enable automatic appointment reminder routing."}
          </div>
        )}

        {error && <div style={{ color: "#D9534F", marginBottom: "0.6rem" }}>{error}</div>}

        <div>
          <div className="ia-form-label">
            {isWhatsApp ? t("template_name") : isWidget ? t("create_template_modal_widget_internal_label") : t("create_template_modal_subject_label")}
          </div>
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

        {isEmail && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.4rem" }}>
            {SUBJECT_VARIABLES.map((variable) => (
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

        {isEmail && (
          <>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.35rem" }}>
              <button
                type="button"
                className="ia-button ia-button-ghost"
                onClick={() =>
                  insertTokenAtCursor(body, setBody, bodyTextareaRef, `\n${EMAIL_LINE_BREAK_TOKEN}\n`)
                }
                style={{ padding: "0.25rem 0.45rem", fontSize: "0.76rem" }}
              >
                {t("create_template_modal_line_break")}
              </button>
              {BODY_VARIABLES.map((variable) => (
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
              {t("create_template_modal_add_footer_image")}
            </label>

            {includeFooterImage && (
              <div style={{ marginTop: "0.3rem" }}>
                <input type="file" accept="image/*" onChange={handleFooterImageChange} />
                {footerImageName && (
                  <div style={{ fontSize: "0.78rem", color: "#5f6b7a", marginTop: "0.25rem" }}>
                    {t("create_template_modal_selected_image")}: {footerImageName}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {supportsReminderFrequency && (
          <div
            ref={reminderSectionRef}
            style={{
              marginTop: "0.6rem",
              padding: "0.6rem",
              borderRadius: 10,
              border: focusReminderFrequency ? "1px solid #F5D7A8" : "1px solid #EDEDED",
              background: focusReminderFrequency ? "#FFF7EA" : "transparent",
            }}
          >
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
                  ref={idx === 0 ? firstReminderValueRef : null}
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
          </div>
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
          {!isWhatsApp ? (
            <button
              type="button"
              onClick={handleDelete}
              className="ia-button"
              style={{ marginRight: "auto", color: "#D9534F", background: "#fff", border: "1px solid #f4c5c0" }}
            >
              🗑 {t("delete_template")}
            </button>
          ) : (
            <small style={{ marginRight: "auto", color: "#667085", alignSelf: "center" }}>
              {t("templates_managed_by_meta_sync")}
            </small>
          )}

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
