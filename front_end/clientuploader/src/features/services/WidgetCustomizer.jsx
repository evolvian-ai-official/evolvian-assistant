// src/features/services/WidgetCustomizer.jsx
import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch, getAuthHeaders } from "../../lib/authFetch";

export default function WidgetCustomizer() {
  const { t } = useLanguage();
  const clientId = useClientId();
  const [saving, setSaving] = useState(false);
  const [planId, setPlanId] = useState("free"); // Detectar plan actual

  const [form, setForm] = useState({
    assistant_name: "Assistant",
    show_logo: true,
    show_powered_by: true,
    header_color: "#fff9f0",
    header_text_color: "#1b2a41",
    background_color: "#ffffff",
    user_message_color: "#a3d9b1",
    bot_message_color: "#f7f7f7",
    button_color: "#f5a623",
    button_text_color: "#ffffff",
    footer_text_color: "#999999",
    font_family: "Inter, sans-serif",
    widget_border_radius: 16,
    widget_height: 520,
    max_messages_per_session: 10,

    show_tooltip: false,
    tooltip_text: t("widget_default_tooltip_text"),
    show_legal_links: false,
    terms_url: "",
    privacy_url: "",
    require_email_consent: false,
    require_terms_consent: false,
    tooltip_bg_color: "#FFF8E1",
    tooltip_text_color: "#5C4B00",
    consent_bg_color: "#FFF8E6",
    consent_text_color: "#7A4F00",

    
  });

  // ✅ Permisos por plan (sin tocar lógica)
  const canSave = ["premium", "white_label"].includes(planId);

  // 🧭 Cargar configuración actual
  useEffect(() => {
    async function loadSettings() {
      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`
        );
        if (!res.ok) throw new Error("Error al obtener configuración");
        const data = await res.json();

        // 🧹 Normalizar fuente
        if (data.font_family) {
          data.font_family = data.font_family.replace(/['"]/g, "").trim();
        }

        setPlanId(data?.plan?.id || "free");
        setForm((prev) => ({ ...prev, ...data }));
      } catch (e) {
        console.error("❌ Error cargando settings:", e);
      }
    }
    if (clientId) loadSettings();
  }, [clientId]);

  // 🪄 Cargar fuentes dinámicamente
  useEffect(() => {
    if (!form.font_family) return;
    const allowedFonts = ["Inter", "Roboto", "Poppins", "Open Sans"];
    const fontName = form.font_family.split(",")[0].replace(/['"]/g, "").trim();

    if (allowedFonts.includes(fontName)) {
      if (!document.getElementById(`font-${fontName}`)) {
        const link = document.createElement("link");
        link.id = `font-${fontName}`;
        link.rel = "stylesheet";
        link.href = `https://fonts.googleapis.com/css2?family=${fontName.replace(
          / /g,
          "+"
        )}:wght@400;500;600;700&display=swap`;
        document.head.appendChild(link);
      }
      document.fonts.ready.then(() => {
        const updatedFont = `${fontName}, sans-serif`;
        setForm((prev) => ({ ...prev, font_family: updatedFont }));
      });
    }
  }, [form.font_family]);

  const handleChange = (key, value) => {
    if (key === "font_family") value = value.replace(/['"]/g, "").trim();
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (!canSave) {
      alert(`⚠️ ${t("widget_premium_notice")}`);
      return;
    }

    try {
      setSaving(true);
      const cleanedForm = {
        ...form,
        font_family: form.font_family.replace(/['"]/g, "").trim(),
      };

      const res = await authFetch(`${import.meta.env.VITE_API_URL}/client_settings`, {
        method: "POST",
        headers: await getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          client_id: clientId,
          ...cleanedForm,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      alert(`✅ ${t("widget_settings_saved_successfully")}`);
    } catch (e) {
      alert(`❌ ${t("widget_error_saving_settings")}: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleUpgrade = () => {
    const target =
      window.location.hostname.includes("localhost")
        ? "http://localhost:4223/settings"
        : "https://evolvianai.net/settings";
    window.open(target, "_blank");
  };

  return (
  <div style={pageStyle}>
    <h2 style={titleStyle}>🎨 {t("widget_customize_title")}</h2>
    <p style={subtitleStyle}>
      {t("widget_customize_subtitle")}
    </p>

    <div style={containerStyle}>
      {/* 🎛️ Configuración */}
      <div style={leftPanel}>
        <div style={formGrid}>
          {/* 🔒 Legal y consentimiento */}
          <h3 style={sectionTitle}>🔒 {t("widget_section_legal_consent")}</h3>

          <label style={labelStyle}>
            {t("widget_show_legal_links")}:
            <input
              type="checkbox"
              checked={form.show_legal_links}
              onChange={(e) =>
                handleChange("show_legal_links", e.target.checked)
              }
              style={{ marginLeft: "8px" }}
            />
          </label>

          {form.show_legal_links && (
            <>
              <label style={labelStyle}>
                {t("widget_terms_url")}:
                <input
                  type="url"
                  placeholder={t("widget_terms_url_placeholder")}
                  value={form.terms_url}
                  onChange={(e) => handleChange("terms_url", e.target.value)}
                  style={textInput}
                />
              </label>

              <label style={labelStyle}>
                {t("widget_privacy_url")}:
                <input
                  type="url"
                  placeholder={t("widget_privacy_url_placeholder")}
                  value={form.privacy_url}
                  onChange={(e) => handleChange("privacy_url", e.target.value)}
                  style={textInput}
                />
              </label>
            </>
          )}

          <label style={labelStyle}>
            {t("widget_require_terms_before_chat")}:
            <input
              type="checkbox"
              checked={form.require_terms_consent}
              onChange={(e) =>
                handleChange("require_terms_consent", e.target.checked)
              }
              style={{ marginLeft: "8px" }}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_require_email_before_chat")}:
            <input
              type="checkbox"
              checked={form.require_email_consent}
              onChange={(e) =>
                handleChange("require_email_consent", e.target.checked)
              }
              style={{ marginLeft: "8px" }}
            />
          </label>

          <h3 style={sectionTitle}>🧾 {t("widget_section_consent_colors")}</h3>

          <label style={labelStyle}>
            {t("widget_consent_bg_color")}:
            <input
              type="color"
              value={form.consent_bg_color}
              onChange={(e) => handleChange("consent_bg_color", e.target.value)}
              style={colorInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_consent_text_color")}:
            <input
              type="color"
              value={form.consent_text_color}
              onChange={(e) =>
                handleChange("consent_text_color", e.target.value)
              }
              style={colorInput}
            />
          </label>

          {/* 🖼️ Apariencia adicional */}
          <h3 style={sectionTitle}>🖼️ {t("widget_section_appearance")}</h3>

          <label style={labelStyle}>
            {t("widget_tooltip")}:
            <input
              type="checkbox"
              checked={form.show_tooltip}
              onChange={(e) => handleChange("show_tooltip", e.target.checked)}
              style={{ marginLeft: "8px" }}
            />
          </label>

          {form.show_tooltip && (
            <>
              <label style={labelStyle}>
                {t("widget_tooltip_text")}:
                <input
                  type="text"
                  value={form.tooltip_text}
                  onChange={(e) => handleChange("tooltip_text", e.target.value)}
                  style={textInput}
                />
              </label>

              <label style={labelStyle}>
                {t("widget_tooltip_bg_color")}:
                <input
                  type="color"
                  value={form.tooltip_bg_color}
                  onChange={(e) =>
                    handleChange("tooltip_bg_color", e.target.value)
                  }
                  style={colorInput}
                />
              </label>

              <label style={labelStyle}>
                {t("widget_tooltip_text_color")}:
                <input
                  type="color"
                  value={form.tooltip_text_color}
                  onChange={(e) =>
                    handleChange("tooltip_text_color", e.target.value)
                  }
                  style={colorInput}
                />
              </label>
            </>
          )}

          <label style={labelStyle}>
            {t("widget_assistant_name")}:
            <input
              type="text"
              value={form.assistant_name}
              onChange={(e) => handleChange("assistant_name", e.target.value)}
              style={textInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_header_color")}:
            <input
              type="color"
              value={form.header_color}
              onChange={(e) => handleChange("header_color", e.target.value)}
              style={colorInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_header_text_color")}:
            <input
              type="color"
              value={form.header_text_color}
              onChange={(e) =>
                handleChange("header_text_color", e.target.value)
              }
              style={colorInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_background_color")}:
            <input
              type="color"
              value={form.background_color}
              onChange={(e) => handleChange("background_color", e.target.value)}
              style={colorInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_user_message_color")}:
            <input
              type="color"
              value={form.user_message_color}
              onChange={(e) =>
                handleChange("user_message_color", e.target.value)
              }
              style={colorInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_bot_message_color")}:
            <input
              type="color"
              value={form.bot_message_color}
              onChange={(e) =>
                handleChange("bot_message_color", e.target.value)
              }
              style={colorInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_button_color")}:
            <input
              type="color"
              value={form.button_color}
              onChange={(e) => handleChange("button_color", e.target.value)}
              style={colorInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_button_text_color")}:
            <input
              type="color"
              value={form.button_text_color}
              onChange={(e) =>
                handleChange("button_text_color", e.target.value)
              }
              style={colorInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_font_family")}:
            <select
              value={form.font_family}
              onChange={(e) => handleChange("font_family", e.target.value)}
              style={selectInput}
            >
              <option value="Inter, sans-serif">Inter</option>
              <option value="Roboto, sans-serif">Roboto</option>
              <option value="Poppins, sans-serif">Poppins</option>
              <option value="Open Sans, sans-serif">Open Sans</option>
            </select>
          </label>

          <label style={labelStyle}>
            {t("widget_border_radius")}:
            <input
              type="range"
              min="0"
              max="30"
              value={form.widget_border_radius}
              onChange={(e) =>
                handleChange("widget_border_radius", Number(e.target.value))
              }
              style={{ width: "100%" }}
            />
            <span>{form.widget_border_radius}px</span>
          </label>

          <label style={labelStyle}>
            {t("widget_height_px")}:
            <input
              type="number"
              min="300"
              max="700"
              value={form.widget_height}
              onChange={(e) =>
                handleChange("widget_height", Number(e.target.value))
              }
              style={textInput}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_show_logo")}:
            <input
              type="checkbox"
              checked={form.show_logo}
              onChange={(e) => handleChange("show_logo", e.target.checked)}
              style={{ marginLeft: "8px" }}
            />
          </label>

          <label style={labelStyle}>
            {t("widget_show_powered_by")}:
            <input
              type="checkbox"
              checked={form.show_powered_by}
              onChange={(e) =>
                handleChange("show_powered_by", e.target.checked)
              }
              style={{ marginLeft: "8px" }}
            />
          </label>

          {/* 💬 Configuración de sesión */}
          <h3 style={sectionTitle}>💬 {t("widget_section_session_behavior")}</h3>

          <label style={labelStyle}>
            {t("widget_max_messages_per_session")}:
            <input
              type="number"
              min="1"
              max="50"
              value={form.max_messages_per_session}
              onChange={(e) =>
                handleChange(
                  "max_messages_per_session",
                  Number(e.target.value)
                )
              }
              style={textInput}
            />
            <small style={{ color: "#999", marginTop: "0.25rem" }}>
              {t("widget_max_messages_helper")}
            </small>
          </label>
        </div>

        {/* 🟡 Botón y mensaje de upgrade */}
        <button
          onClick={handleSave}
          disabled={saving || !canSave}
          style={canSave ? saveButtonStyle : disabledSaveButtonStyle}
        >
          {saving
            ? t("widget_saving")
            : canSave
            ? `💾 ${t("save_changes")}`
            : `🔒 ${t("widget_premium_feature")}`}
        </button>

        {!canSave && (
          <div style={upgradeBox}>
            ⚠️ {t("widget_premium_notice")}
            <br />
            <button style={upgradeButton} onClick={handleUpgrade}>
              🚀 {t("widget_upgrade_to_premium")}
            </button>
          </div>
        )}
      </div>

      {/* 👀 Vista previa */}
      <div style={previewPanel}>
        <div
          style={{
            ...previewWidget,
            borderRadius: `${form.widget_border_radius}px`,
            backgroundColor: form.background_color,
            fontFamily: form.font_family,
            height: `${form.widget_height}px`,
          }}
        >
          <div
            style={{
              ...headerStyle,
              backgroundColor: form.header_color,
              color: form.header_text_color,
            }}
          >
            {form.show_logo && (
              <img
                src="https://evolvian-assistant.onrender.com/static/logo-evolvian.svg"
                alt="Logo"
                style={{ height: "22px", marginRight: "0.6rem" }}
              />
            )}
            <strong>{form.assistant_name}</strong>
          </div>

          {/* 🧩 Tooltip Preview */}
          {form.show_tooltip && (
            <div
              style={{
                backgroundColor: form.tooltip_bg_color,
                color: form.tooltip_text_color,
                fontSize: "0.8rem",
                padding: "0.4rem 0.6rem",
                textAlign: "center",
                borderBottom: "1px solid #EDEDED",
              }}
            >
              💡 {form.tooltip_text}
            </div>
          )}

          <div style={{ ...messagesStyle, backgroundColor: "transparent" }}>
            <div
              style={{
                ...botMessageStyle,
                backgroundColor: form.bot_message_color,
              }}
            >
              {t("widget_preview_bot_message")}
            </div>
            <div
              style={{
                ...userMessageStyle,
                backgroundColor: form.user_message_color,
              }}
            >
              {t("widget_preview_user_message")}
            </div>
          </div>

          {/* 🧾 Consentimiento Preview */}
          {(form.require_email_consent || form.require_terms_consent) && (
            <div
              style={{
                border: "1px dashed #F5A623",
                background: form.consent_bg_color,
                color: form.consent_text_color,
                fontSize: "0.8rem",
                textAlign: "center",
                padding: "0.6rem",
                margin: "0.5rem 1rem",
                borderRadius: "8px",
              }}
            >
              🧾 {t("widget_preview_email_consent_required")}
            </div>
          )}

          <div style={inputContainer}>
            <textarea
              placeholder={t("widget_preview_type_message")}
              style={textareaStyle}
              rows={2}
              disabled
            />
            <button
              style={{
                ...sendButtonStyle,
                backgroundColor: form.button_color,
                color: form.button_text_color,
              }}
            >
              {t("send")}
            </button>
          </div>

          {form.show_powered_by && (
            <div
              style={{
                ...footerStyle,
                color: form.footer_text_color,
              }}
            >
              {t("widget_preview_powered_by")} <strong>Evolvian</strong> — evolvianai.com
            </div>
          )}

          {/* 📄 Legal Links Preview */}
          {form.show_legal_links && (
            <div
              style={{
                textAlign: "center",
                fontSize: "0.75rem",
                color: "#4A90E2",
                padding: "0.4rem",
                borderTop: "1px solid #F0F0F0",
              }}
            >
              {form.terms_url && (
                <a
                  href={form.terms_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    color: "#4A90E2",
                    marginRight: "0.5rem",
                    textDecoration: "underline",
                  }}
                >
                  {t("widget_preview_terms")}
                </a>
              )}
              {form.privacy_url && (
                <a
                  href={form.privacy_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    color: "#4A90E2",
                    textDecoration: "underline",
                  }}
                >
                  {t("widget_preview_privacy")}
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  </div>
);
}


/* 🎨 Rebranding Evolvian Premium Light (solo estilos) */
const pageStyle = {
  color: "#274472",
  padding: "clamp(0.8rem, 0.6rem + 1vw, 1.4rem)",
  backgroundColor: "#FFFFFF", // light
  fontFamily: "system-ui, sans-serif",
  minHeight: "100%",
};
const titleStyle = { fontSize: "clamp(1.35rem, 1.1rem + 1vw, 1.8rem)", color: "#F5A623", marginBottom: "0.5rem" };
const subtitleStyle = { color: "#4A90E2", marginBottom: "2rem" };
const containerStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))",
  gap: "1rem",
  alignItems: "flex-start",
};
const leftPanel = {
  backgroundColor: "#FFFFFF",
  padding: "clamp(0.9rem, 0.8rem + 0.9vw, 1.5rem)",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
  minWidth: 0,
};
const previewPanel = {
  backgroundColor: "#FFFFFF",
  padding: "0.8rem",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
  minWidth: 0,
};
const formGrid = { display: "grid", gap: "1rem" };
const labelStyle = { display: "flex", flexDirection: "column", fontSize: "0.9rem" };
const colorInput = {
  marginTop: "0.3rem",
  height: "34px",
  borderRadius: "8px",
  border: "1px solid #EDEDED",
  background: "#FFFFFF",
  cursor: "pointer",
};
const textInput = {
  marginTop: "0.3rem",
  padding: "0.45rem 0.6rem",
  borderRadius: "10px",
  border: "1px solid #EDEDED",
  backgroundColor: "#FFFFFF",
  color: "#274472",
  outline: "none",
};
const selectInput = {
  marginTop: "0.3rem",
  padding: "0.45rem 0.6rem",
  borderRadius: "10px",
  border: "1px solid #EDEDED",
  backgroundColor: "#FFFFFF",
  color: "#274472",
  outline: "none",
};
const saveButtonStyle = {
  marginTop: "1.5rem",
  backgroundColor: "#2EB39A",
  border: "none",
  color: "white",
  padding: "0.8rem 1.2rem",
  borderRadius: "10px",
  fontWeight: "bold",
  cursor: "pointer",
  width: "100%",
  boxShadow: "0 6px 16px rgba(46,179,154,0.25)",
};
const disabledSaveButtonStyle = {
  ...saveButtonStyle,
  backgroundColor: "#D1D5DB",
  color: "#9CA3AF",
  boxShadow: "none",
  cursor: "not-allowed",
};
const upgradeBox = {
  backgroundColor: "#FFFFFF",
  border: "1px dashed #F5A623",
  color: "#F5A623",
  padding: "1rem",
  borderRadius: "12px",
  marginTop: "1rem",
  textAlign: "center",
  fontSize: "0.9rem",
  fontWeight: "600",
};
const upgradeButton = {
  marginTop: "0.6rem",
  backgroundColor: "#4A90E2",
  color: "#FFFFFF",
  border: "none",
  borderRadius: "8px",
  padding: "0.5rem 0.9rem",
  cursor: "pointer",
  fontWeight: "bold",
};
const previewWidget = {
  width: "min(100%, 360px)",
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
  border: "1px solid #F0F0F0",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
};
const headerStyle = {
  flexShrink: 0,
  height: "56px",
  borderBottom: "1px solid #F0F0F0",
  display: "flex",
  alignItems: "center",
  padding: "0 1rem",
};
const messagesStyle = {
  flex: 1,
  overflowY: "auto",
  padding: "1rem",
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
  // 🔑 Dejar transparente para que se vea form.background_color
  backgroundColor: "transparent",
};
const userMessageStyle = {
  alignSelf: "flex-end",
  padding: "0.75rem 1rem",
  borderRadius: "18px",
  maxWidth: "75%",
  wordBreak: "break-word",
  color: "#1b2a41",
};
const botMessageStyle = {
  alignSelf: "flex-start",
  padding: "0.75rem 1rem",
  borderRadius: "18px",
  maxWidth: "75%",
  wordBreak: "break-word",
  color: "#1b2a41",
};
const inputContainer = {
  flexShrink: 0,
  borderTop: "1px solid #F0F0F0",
  display: "flex",
  gap: "0.5rem",
  padding: "0.8rem",
  background: "#FFFFFF",
};
const textareaStyle = {
  flex: 1,
  resize: "none",
  borderRadius: "10px",
  padding: "0.6rem 0.75rem",
  border: "1px solid #E5E7EB",
  fontSize: "0.95rem",
  outline: "none",
  color: "#1b2a41",
  backgroundColor: "#FFFFFF",
};
const sendButtonStyle = {
  border: "none",
  padding: "0.6rem 1rem",
  borderRadius: "10px",
  fontWeight: "600",
  fontSize: "0.95rem",
  cursor: "pointer",
};
const footerStyle = {
  textAlign: "center",
  fontSize: "0.75rem",
  padding: "0.6rem",
  borderTop: "1px solid #F0F0F0",
  background: "transparent",
};

// 🆕 === Nuevos estilos Evolvian para Widget Customizer ===

const sectionTitle = {
  fontSize: "1rem",
  fontWeight: "600",
  color: "#274472",
  marginTop: "1.4rem",
  marginBottom: "0.6rem",
  borderBottom: "1px solid #EDEDED",
  paddingBottom: "0.3rem",
};
