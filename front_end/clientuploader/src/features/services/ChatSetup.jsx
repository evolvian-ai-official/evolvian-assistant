// src/features/services/ChatSetup.jsx
// Chat setup — Guía completa con bloques visuales para GIFs (Branding Evolvian Premium Light)
import { useInitializeUser } from "../../hooks/useInitializeUser";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { useState, useEffect } from "react";
import { trackClientEvent } from "../../lib/tracking";
import WidgetCustomizer from "./WidgetCustomizer"; // 👈 importa tu otro componente

export default function ChatSetup() {
  const { publicClientId, loading } = useInitializeUser();
  const clientId = useClientId();
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState("install");
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );

  // 🌀 Inyectar keyframes para el spinner (solo una vez)
  useEffect(() => {
    if (typeof document !== "undefined" && !document.getElementById("spin-keyframes")) {
      const style = document.createElement("style");
      style.id = "spin-keyframes";
      style.textContent = `
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const handleCopy = (text, installType = null) => {
    navigator.clipboard.writeText(text);
    alert(t("copied_to_clipboard"));

    if (installType && clientId) {
      void trackClientEvent({
        clientId,
        name: "Funnel_Widget_Installed",
        category: "funnel",
        label: installType,
        value: "chat_widget",
        eventKey: "funnel_widget_installed",
        metadata: { install_type: installType },
        dedupeLocal: true,
      });
    }
  };

  const domain = window.location.hostname.includes("localhost")
    ? "http://localhost:5180/static"
    : "https://evolvian-assistant.onrender.com/static";
  const widgetVersion = "2026-02-17-01";

  const scriptCode = `<script
  type="module"
  src="${domain}/embed-floating.js?v=${widgetVersion}"
  data-public-client-id="${publicClientId}"
></script>`;

  const iframeCode = `<iframe
  src="${domain}/widget.html?public_client_id=${publicClientId || "TU_ID_PUBLICO"}"
  style="width:360px;height:520px;border:none;border-radius:12px;"
  allow="clipboard-write; microphone"
  title="Evolvian AI Chat Widget"
></iframe>`;

  // 🌀 Spinner loader mientras carga
  if (loading) {
    return (
      <div style={loaderContainer}>
        <div style={spinner}></div>
        <p style={{ color: "#274472", marginTop: "1rem" }}>{t("loading_setup")}</p>
      </div>
    );
  }

  return (
    <div className="ia-page" style={pageStyle}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        {/* 🔀 Toggle superior */}
        <div style={toggleContainer}>
          <button
            onClick={() => setActiveTab("install")}
            style={{
              ...toggleButton,
              backgroundColor: activeTab === "install" ? "#4A90E2" : "transparent",
              color: activeTab === "install" ? "#FFFFFF" : "#274472",
              borderColor: activeTab === "install" ? "#4A90E2" : "#EDEDED",
              width: isMobile ? "100%" : "auto",
            }}
          >
            {t("installation") || "Installation"}
          </button>
          <button
            onClick={() => setActiveTab("customize")}
            style={{
              ...toggleButton,
              backgroundColor: activeTab === "customize" ? "#F5A623" : "transparent",
              color: activeTab === "customize" ? "#FFFFFF" : "#274472",
              borderColor: activeTab === "customize" ? "#F5A623" : "#EDEDED",
              width: isMobile ? "100%" : "auto",
            }}
          >
            {t("customize_widget") || "Customize Widget"}
          </button>
        </div>

        {/* 🔹 Render dinámico según tab */}
        {activeTab === "install" ? (
          <>
            <div style={headerRow}>
              <img
                src="/logo-evolvian.svg"
                alt="Evolvian Logo"
                style={{
                  width: isMobile ? 46 : 56,
                  height: isMobile ? 46 : 56,
                  borderRadius: "50%",
                  flex: "0 0 auto",
                }}
              />
              <div>
                <h2 style={titleStyle}>{t("setup_evolvian_web")}</h2>
                <p style={descriptionStyle}>
                  {t("setup_description") ||
                    "Embed Evolvian on your website in minutes. Choose floating script or iframe mode."}
                </p>
              </div>
            </div>

            {/* 🔑 Public ID */}
            <div
              style={{
                ...idBoxStyle,
                flexDirection: isMobile ? "column" : "row",
                alignItems: isMobile ? "stretch" : "center",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <strong style={{ color: "#274472" }}>{t("your_public_id")}:</strong>{" "}
                <span style={{ color: "#2EB39A", fontWeight: 700 }}>
                  {publicClientId || t("not_available")}
                </span>
              </div>
              <button
                onClick={() => handleCopy(publicClientId)}
                disabled={!publicClientId}
                style={{
                  ...copyButtonStyle(!!publicClientId),
                  width: isMobile ? "100%" : "auto",
                }}
              >
                {t("copy_id")}
              </button>
            </div>

            {/* 🧩 Opciones */}
            <div
              style={{
                ...optionsContainerStyle,
                gridTemplateColumns: isMobile
                  ? "minmax(0, 1fr)"
                  : optionsContainerStyle.gridTemplateColumns,
              }}
            >
              {/* Option 1 - Script embebido */}
              <div style={{ ...cardStyle, minHeight: isMobile ? "auto" : cardStyle.minHeight }}>
                <h3 style={subtitleStyle}>{t("option1_title") || "Floating Button (Script)"}</h3>
                <p style={hintStyle}>{t("option1_hint") || "Recommended for global floating chat."}</p>
                <ol style={stepsStyle}>
                  <li>{t("copy_script") || "Copy the script"}</li>
                  <li>{t("paste_before_body") || "Paste before </body>"}</li>
                  <li>{t("save_and_reload") || "Save and reload your site"}</li>
                </ol>
                <pre style={codeStyle}>{scriptCode}</pre>
                <button
                  onClick={() => handleCopy(scriptCode, "script")}
                  style={{ ...actionButtonStyle, width: isMobile ? "100%" : "auto" }}
                >
                  {t("copy_script_button") || "Copy script"}
                </button>
              </div>

              {/* Option 2 - Iframe embebido */}
              <div style={{ ...cardStyle, minHeight: isMobile ? "auto" : cardStyle.minHeight }}>
                <h3 style={subtitleStyle}>{t("option2_title") || "Fixed Window (Iframe)"}</h3>
                <p style={hintStyle}>{t("option2_hint") || "Great for dedicated support pages."}</p>
                <ol style={stepsStyle}>
                  <li>{t("copy_code") || "Copy the iframe code"}</li>
                  <li>{t("paste_where_visible") || "Paste where you want it visible"}</li>
                  <li>{t("adjust_size_if_needed") || "Adjust dimensions if needed"}</li>
                </ol>
                <pre style={codeStyle}>{iframeCode}</pre>
                <button
                  onClick={() => handleCopy(iframeCode, "iframe")}
                  style={{ ...actionButtonStyle, width: isMobile ? "100%" : "auto" }}
                >
                  {t("copy_iframe") || "Copy iframe"}
                </button>
              </div>
            </div>

            {/* 📘 Step-by-Step Installation Guide */}
            <div style={guideContainer}>
              <h2 style={guideTitle}>{t("step_by_step_guide") || "Step-by-Step Installation Guide"}</h2>

              {/* STEP 1 */}
              <GuideStep
                title={t("step1_title") || "Step 1 — Get Your Public Client ID"}
                text={
                  t("step1_text") ||
                  "Go to your Evolvian Dashboard → Settings. Copy your public_client_id. You’ll use it in both widget and iframe integrations."
                }
                img="/widgetstep1.png"
                isMobile={isMobile}
              />

              {/* STEP 2 */}
              <GuideStep
                title={t("step2_title") || "Step 2 — Add the Script to Your Site"}
                text={
                  t("step2_text") ||
                  "Insert the script snippet just before the closing </body> tag on your website. This will automatically display the Evolvian floating chat button."
                }
                code={scriptCode}
                img="/widgetstep2.png"
                isMobile={isMobile}
              />

              {/* STEP 3 */}
              <GuideStep
                title={t("step3_title") || "Step 3 — (Alternative) Use Iframe Mode"}
                text={
                  t("step3_text") ||
                  "If you prefer a fixed chat window (e.g., on a Contact page), use the iframe version instead. You can control its position and design freely."
                }
                code={iframeCode}
                img="/widgetstep3.png"
                isMobile={isMobile}
              />

              {/* STEP 4 */}
              <GuideStep
                title={t("step4_title") || "Step 4 — Test and Verify"}
                text={
                  t("step4_text") ||
                  "Once embedded, verify that the chat icon appears, opens correctly, and messages sync with your dashboard."
                }
                img="/widgetstep4.png"
                isMobile={isMobile}
              />

              {/* STEP 5 */}
              <GuideStep
                title={t("step5_title") || "Step 5 — Troubleshooting"}
                text={
                  t("step5_text") ||
                  "If the widget doesn’t appear, check that your public_client_id is correct, no CSP block is active, and you reloaded your site. Contact support@evolvianai.com if it persists."
                }
                img="/widgetstep5.png"
                isMobile={isMobile}
              />
            </div>
          </>
        ) : (
          <WidgetCustomizer /> // 🎨 muestra el otro JSX
        )}
      </div>
    </div>
  );
}

/* 🧩 Reusable guide step component */
function GuideStep({ title, text, img, code, isMobile }) {
  return (
    <div style={{ ...guideRow, flexDirection: isMobile ? "column" : "row" }}>
      <div style={guideLeft}>
        <h3 style={guideStepTitle}>{title}</h3>
        <p style={guideText}>{text}</p>
        {code && <pre style={codeStyle}>{code}</pre>}
      </div>
      <div style={guideRight}>
        <img
          src={img}
          alt={title}
          style={{
            ...gifStyle,
            maxHeight: isMobile ? "340px" : gifStyle.maxHeight,
          }}
        />
      </div>
    </div>
  );
}

/* 🎨 Loader Styles (Light) */
const loaderContainer = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#FFFFFF",
  minHeight: "100%",
  color: "#274472",
  fontFamily: "system-ui, sans-serif",
};

const spinner = {
  width: "40px",
  height: "40px",
  border: "4px solid #EDEDED",
  borderTop: "4px solid #4A90E2",
  borderRadius: "50%",
  animation: "spin 1s linear infinite",
};

/* 🎨 Estilos del toggle */
const toggleContainer = {
  display: "flex",
  justifyContent: "center",
  gap: "0.75rem",
  marginBottom: "1.5rem",
  flexWrap: "wrap",
};

const toggleButton = {
  border: "1px solid #EDEDED",
  borderRadius: "10px",
  color: "#274472",
  padding: "0.6rem 1.1rem",
  cursor: "pointer",
  fontWeight: "bold",
  transition: "all 0.2s ease",
  flex: "1 1 220px",
};

/* 🎨 Estilos generales (Premium Light) */
const pageStyle = {
  padding: "clamp(0.8rem, 0.6rem + 1vw, 1.4rem)",
  fontFamily: "system-ui, sans-serif",
  backgroundColor: "#FFFFFF",
  color: "#274472",
  minHeight: "100%",
};

const headerRow = {
  display: "flex",
  alignItems: "flex-start",
  gap: "1rem",
  marginBottom: "1rem",
  flexWrap: "wrap",
};

const titleStyle = {
  fontSize: "clamp(1.3rem, 1.1rem + 0.9vw, 1.8rem)",
  color: "#F5A623",
  fontWeight: "bold",
  margin: 0,
};

const descriptionStyle = {
  color: "#4A90E2",
  maxWidth: "800px",
  marginTop: "0.25rem",
};

const idBoxStyle = {
  backgroundColor: "#FFFFFF",
  padding: "1rem",
  borderRadius: "12px",
  margin: "1.25rem 0 2rem",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  maxWidth: "100%",
  border: "1px solid #EDEDED",
  boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
  gap: "0.6rem",
};

const copyButtonStyle = (enabled) => ({
  backgroundColor: enabled ? "#4A90E2" : "#E5E7EB",
  color: enabled ? "#FFFFFF" : "#9CA3AF",
  border: "none",
  borderRadius: "10px",
  padding: "0.55rem 1rem",
  fontWeight: "bold",
  cursor: enabled ? "pointer" : "not-allowed",
  transition: "0.2s ease all",
});

const optionsContainerStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: "1.4rem",
  marginTop: "1.4rem",
};

const cardStyle = {
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  padding: "1.2rem",
  borderRadius: "14px",
  minHeight: "420px",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
};

const subtitleStyle = {
  color: "#4A90E2",
  fontSize: "1.15rem",
  marginBottom: "0.75rem",
  fontWeight: "700",
};

const hintStyle = {
  fontSize: "0.9rem",
  color: "#7A7A7A",
  marginBottom: "1rem",
};

const stepsStyle = {
  fontSize: "0.95rem",
  marginBottom: "1rem",
  color: "#274472",
  lineHeight: 1.6,
};

const codeStyle = {
  background: "#FAFAFA",
  color: "#274472",
  padding: "1rem",
  borderRadius: "10px",
  fontSize: "0.78rem",
  overflowX: "auto",
  marginBottom: "0.5rem",
  border: "1px dashed #EDEDED",
};

const actionButtonStyle = {
  backgroundColor: "#F5A623",
  color: "#FFFFFF",
  border: "none",
  borderRadius: "10px",
  padding: "0.6rem 1.1rem",
  fontWeight: "bold",
  fontSize: "0.9rem",
  cursor: "pointer",
  transition: "0.2s ease all",
  alignSelf: "flex-start",
};



/* 📘 Guía — versión estable y alineada */
const guideContainer = {
  marginTop: "2rem",
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "16px",
  padding: "clamp(0.9rem, 0.8rem + 1vw, 1.6rem)",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
};

const guideTitle = {
  color: "#A3D9B1",
  fontSize: "1.6rem",
  fontWeight: "bold",
  marginBottom: "2rem",
  textAlign: "center",
};

/* 🔹 Grid más equilibrado y robusto */
const guideRow = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "stretch",
  gap: "1rem",
  marginBottom: "1.3rem",
};

const guideLeft = {
  flex: "1 1 40%", // 40% texto
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  padding: "1.8rem",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
  minWidth: 0,
};

const guideRight = {
  flex: "1 1 55%", // 55% imagen
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  padding: "1rem",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  minWidth: 0,
};

const guideStepTitle = {
  color: "#F5A623",
  fontSize: "1.1rem",
  fontWeight: "bold",
  marginBottom: "0.6rem",
};

const guideText = {
  color: "#274472",
  fontSize: "0.95rem",
  marginBottom: "1rem",
  lineHeight: "1.6",
};

const gifStyle = {
  width: "100%",
  height: "auto",
  borderRadius: "14px",
  border: "1px solid #EDEDED",
  boxShadow: "0 3px 12px rgba(0,0,0,0.06)",
  objectFit: "contain",
  maxHeight: "500px",
};
