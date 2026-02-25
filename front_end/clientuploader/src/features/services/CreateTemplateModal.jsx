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

export default function CreateTemplateModal({ clientId, onClose, onCreated }) {
  const { t } = useLanguage();
  const API = import.meta.env.VITE_API_URL;
  const SUBJECT_VARIABLES = SUBJECT_VARIABLE_TOKENS.map((item) => ({
    label: t(item.key),
    token: item.token,
  }));
  const BODY_VARIABLES = [...SUBJECT_VARIABLES, ...BODY_EXTRA_VARIABLE_TOKENS.map((item) => ({
    label: t(item.key),
    token: item.token,
  }))];

  const [channel, setChannel] = useState("email");
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
  const isEmailTemplate = channel === "email";
  const isWidgetTemplate = channel === "widget";
  const emailTemplateTypes = templateTypes.filter((tplType) => tplType?.id !== "opening_message");

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
        const types = (data || []).filter((tplType) => {
          if (!tplType?.id) return false;
          if (tplType.is_active === false) return false;
          if (tplType.active === false) return false;
          return true;
        });
        setTemplateTypes(types);
        const exists = types.some((tplType) => tplType.id === type);
        if (!exists && types.length > 0) {
          setType(types[0].id);
        }
      })
      .catch(() => setTemplateTypes([]));
  }, []);

  useEffect(() => {
    if (isWidgetTemplate) {
      setType("opening_message");
      setIncludeFooterImage(false);
      setFooterImageFile(null);
      setFooterImageName("");
      return;
    }

    if (type === "opening_message") {
      const fallbackType =
        templateTypes.find((tplType) => tplType?.id && tplType.id !== "opening_message")?.id ||
        "appointment_reminder";
      setType(fallbackType);
    }
  }, [isWidgetTemplate, templateTypes, type]);

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
    if (!clientId) {
      alert(t("template_client_not_ready"));
      return;
    }

    if (!body.trim()) {
      alert(t("template_message_required"));
      return;
    }

    if (isEmailTemplate && includeFooterImage && !footerImageFile) {
      alert(t("create_template_modal_select_footer_image_or_disable"));
      return;
    }

    const frequency =
      isEmailTemplate && type === "appointment_reminder"
        ? reminders.map((r) => ({
            offset_minutes: toMinutes(r.value, r.unit),
            label: buildLabel(r.value, r.unit),
          }))
        : null;

    const payload = {
      client_id: clientId,
      channel,
      type: isWidgetTemplate ? "opening_message" : type,
      label: label || null,
      ...(frequency ? { frequency } : {}),
    };

    if (isEmailTemplate) {
      let finalBody = normalizeEmailBodyLineBreaks(body.trim());
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
    } else {
      payload.body = body.trim();
    }

    try {
      setLoading(true);

        const res = await authFetch(`${API}/message_templates`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || t("template_create_failed"));
      }

      onCreated?.();
      onClose();
    } catch (err) {
      console.error(err);
      const detail = err instanceof Error && err.message ? err.message : t("template_create_failed");
      alert(detail);
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
        <h2 style={{ color: "#274472", marginTop: 0 }}>
          {isWidgetTemplate ? t("create_template_modal_widget_title") : t("create_template_modal_title")}
        </h2>

        {isEmailTemplate && (
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
            {t("create_template_modal_meta_sync_note")}
          </div>
        )}

        <label className="ia-form-label">{t("channel")}</label>
        <select value={channel} onChange={(e) => setChannel(e.target.value)} className="ia-form-input">
          <option value="email">{t("email") || "Email"}</option>
          <option value="widget">{t("widget")}</option>
        </select>

        <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>{t("type")}</label>
        {isEmailTemplate ? (
          <select value={type} onChange={(e) => setType(e.target.value)} className="ia-form-input">
            {emailTemplateTypes.map((tplType) => (
              <option key={tplType.id} value={tplType.id}>
                {tplType.description || tplType.id}
              </option>
            ))}
          </select>
        ) : (
          <input className="ia-form-input" value="opening_message" readOnly />
        )}

        <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>
          {isWidgetTemplate ? t("create_template_modal_widget_internal_label") : t("create_template_modal_subject_label")}
        </label>
        <input
          ref={subjectInputRef}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="ia-form-input"
          placeholder={isWidgetTemplate ? t("create_template_modal_widget_subject_placeholder") : t("create_template_modal_subject_placeholder")}
        />
        {isEmailTemplate && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.4rem" }}>
            {SUBJECT_VARIABLES.map((variable) => (
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
        )}

        <label className="ia-form-label" style={{ marginTop: "0.6rem" }}>{t("create_template_modal_message_body_label")}</label>
        <textarea
          ref={bodyTextareaRef}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
          className="ia-form-input"
          style={{ resize: "vertical" }}
          placeholder={
            isWidgetTemplate
              ? t("create_template_modal_widget_body_placeholder")
              : t("create_template_modal_body_placeholder")
          }
        />
        {isEmailTemplate && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.4rem" }}>
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
        )}

        {isEmailTemplate && (
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
        )}

        {isEmailTemplate && includeFooterImage && (
          <div style={{ marginTop: "0.3rem" }}>
            <input type="file" accept="image/*" onChange={handleFooterImageChange} />
            {footerImageName && (
              <div style={{ fontSize: "0.78rem", color: "#5f6b7a", marginTop: "0.25rem" }}>
                {t("create_template_modal_selected_image")}: {footerImageName}
              </div>
            )}
          </div>
        )}

        {isEmailTemplate && type === "appointment_reminder" && (
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
            {loading ? t("saving") : (isWidgetTemplate ? t("create_template_modal_widget_title") : t("create_template_modal_title"))}
          </button>
        </div>
      </div>
    </div>
  );
}
