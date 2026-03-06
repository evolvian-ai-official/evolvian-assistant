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
  src="${domain}/widget.html?public_client_id=${publicClientId || t("chat_setup_public_id_placeholder")}"
  style="width:360px;height:520px;border:none;border-radius:12px;"
  allow="clipboard-write; microphone"
  title="${t("chat_widget_iframe_title")}"
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

            <WidgetInstallPlaybook
              publicClientId={publicClientId}
              scriptCode={scriptCode}
              iframeCode={iframeCode}
              isMobile={isMobile}
              onCopy={handleCopy}
            />
          </>
        ) : (
          <WidgetCustomizer /> // 🎨 muestra el otro JSX
        )}
      </div>
    </div>
  );
}

function WidgetInstallPlaybook({ publicClientId, scriptCode, iframeCode, isMobile, onCopy }) {
  const { t } = useLanguage();
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedOption, setSelectedOption] = useState("floating");
  const [selectedPlatform, setSelectedPlatform] = useState("wordpress");
  const [checkedItems, setCheckedItems] = useState({
    visible: false,
    open: false,
    reply: false,
    history: false,
  });
  const [openTrouble, setOpenTrouble] = useState(null);
  const [copiedState, setCopiedState] = useState({
    id: false,
    codeFloating: false,
    codeIframe: false,
  });

  const ui = {
    placeholderId: t("playbook_placeholder_id"),
    title: t("playbook_title"),
    subtitle: t("playbook_subtitle"),
    progress: [
      t("playbook_progress_1"),
      t("playbook_progress_2"),
      t("playbook_progress_3"),
      t("playbook_progress_4"),
      t("playbook_progress_5"),
    ],
    step1Title: t("playbook_step1_title"),
    step1Desc: t("playbook_step1_desc"),
    idLabel: t("playbook_id_label"),
    copyId: t("playbook_copy_id"),
    copied: t("playbook_copied"),
    step1Hint: t("playbook_step1_hint"),
    step1Alt: t("playbook_step1_alt"),
    chooseTypeCta: t("playbook_choose_type_cta"),
    step2Title: t("playbook_step2_title"),
    step2Desc: t("playbook_step2_desc"),
    recommended: t("playbook_recommended"),
    advanced: t("playbook_advanced"),
    floatingTitle: t("playbook_floating_title"),
    floatingDesc: t("playbook_floating_desc"),
    embeddedTitle: t("playbook_embedded_title"),
    embeddedDesc: t("playbook_embedded_desc"),
    floatingHint: t("playbook_floating_hint"),
    iframeHint: t("playbook_iframe_hint"),
    back: t("playbook_back"),
    getCode: t("playbook_get_code"),
    step3Title: t("playbook_step3_title"),
    step3Desc: t("playbook_step3_desc"),
    codeLabelFloating: t("playbook_code_label_floating"),
    codeLabelIframe: t("playbook_code_label_iframe"),
    copyCode: t("playbook_copy_code"),
    keepIdHint: t("playbook_keep_id_hint"),
    platformTitle: t("playbook_platform_title"),
    platforms: {
      wordpress: t("playbook_platform_wordpress"),
      shopify: t("playbook_platform_shopify"),
      wix: t("playbook_platform_wix"),
      squarespace: t("playbook_platform_squarespace"),
      webflow: t("playbook_platform_webflow"),
      html: t("playbook_platform_html"),
    },
    platformInstructions: {
      wordpress: [
        t("playbook_platform_wordpress_step_1"),
        t("playbook_platform_wordpress_step_2"),
        t("playbook_platform_wordpress_step_3"),
        t("playbook_platform_wordpress_step_4"),
      ],
      shopify: [
        t("playbook_platform_shopify_step_1"),
        t("playbook_platform_shopify_step_2"),
        t("playbook_platform_shopify_step_3"),
        t("playbook_platform_shopify_step_4"),
      ],
      wix: [
        t("playbook_platform_wix_step_1"),
        t("playbook_platform_wix_step_2"),
        t("playbook_platform_wix_step_3"),
        t("playbook_platform_wix_step_4"),
      ],
      squarespace: [
        t("playbook_platform_squarespace_step_1"),
        t("playbook_platform_squarespace_step_2"),
        t("playbook_platform_squarespace_step_3"),
      ],
      webflow: [
        t("playbook_platform_webflow_step_1"),
        t("playbook_platform_webflow_step_2"),
        t("playbook_platform_webflow_step_3"),
        t("playbook_platform_webflow_step_4"),
      ],
      html: [
        t("playbook_platform_html_step_1"),
        t("playbook_platform_html_step_2"),
        t("playbook_platform_html_step_3"),
        t("playbook_platform_html_step_4"),
      ],
    },
    step2Alt: t("playbook_step2_alt"),
    step3Alt: t("playbook_step3_alt"),
    pastedCta: t("playbook_pasted_cta"),
    step4Title: t("playbook_step4_title"),
    step4Desc: t("playbook_step4_desc"),
    checks: [
      ["visible", t("playbook_check_visible")],
      ["open", t("playbook_check_open")],
      ["reply", t("playbook_check_reply")],
      ["history", t("playbook_check_history")],
    ],
    liveTitle: t("playbook_live_title"),
    liveDesc: t("playbook_live_desc"),
    step4Alt: t("playbook_step4_alt"),
    needHelpCta: t("playbook_need_help_cta"),
    step5Title: t("playbook_step5_title"),
    step5Desc: t("playbook_step5_desc"),
    troubles: [
      {
        key: "not-visible",
        q: t("playbook_trouble_not_visible_q"),
        a: t("playbook_trouble_not_visible_a"),
      },
      {
        key: "no-reply",
        q: t("playbook_trouble_no_reply_q"),
        a: t("playbook_trouble_no_reply_a"),
      },
      {
        key: "platform-limits",
        q: t("playbook_trouble_platform_limits_q"),
        a: t("playbook_trouble_platform_limits_a"),
      },
      {
        key: "browser-error",
        q: t("playbook_trouble_browser_error_q"),
        a: t("playbook_trouble_browser_error_a"),
      },
    ],
    step5Alt: t("playbook_step5_alt"),
    supportTitle: t("playbook_support_title"),
    supportText: t("playbook_support_text"),
    contactSupport: t("playbook_contact_support"),
    backToVerify: t("playbook_back_to_verify"),
    restartGuide: t("playbook_restart_guide"),
  };

  const safeClientId = String(publicClientId || ui.placeholderId);
  const allChecksDone = Object.values(checkedItems).every(Boolean);

  const copyWithFeedback = (value, installType, key) => {
    onCopy(value, installType);
    setCopiedState((prev) => ({ ...prev, [key]: true }));
    setTimeout(() => {
      setCopiedState((prev) => ({ ...prev, [key]: false }));
    }, 1800);
  };

  const goToStep = (step) => {
    const normalized = Math.max(0, Math.min(4, step));
    setCurrentStep(normalized);
  };

  const toggleCheck = (key) => {
    setCheckedItems((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleTrouble = (key) => {
    setOpenTrouble((prev) => (prev === key ? null : key));
  };

  const selectedCode = selectedOption === "floating" ? scriptCode : iframeCode;
  const selectedInstallType = selectedOption === "floating" ? "script" : "iframe";
  const currentCodeLabel = selectedOption === "floating" ? ui.codeLabelFloating : ui.codeLabelIframe;
  const codeCopied = selectedOption === "floating" ? copiedState.codeFloating : copiedState.codeIframe;
  const platformEntries = Object.entries(ui.platforms);

  return (
    <div style={playbookContainer}>
      <h2 style={playbookTitle}>{ui.title}</h2>
      <p style={playbookSubtitle}>{ui.subtitle}</p>

      <div style={{ ...playbookProgressBar, gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(5, 1fr)" }}>
        {ui.progress.map((label, index) => (
          <button
            key={label}
            type="button"
            onClick={() => goToStep(index)}
            style={{
              ...playbookProgressStep,
              ...(currentStep === index ? playbookProgressActive : {}),
              ...(index < currentStep ? playbookProgressDone : {}),
            }}
          >
            {index < currentStep ? `✓ ${label}` : label}
          </button>
        ))}
      </div>

      {currentStep === 0 && (
        <div style={playbookPanel}>
          <div style={playbookCard}>
            <h3 style={playbookCardTitle}>{ui.step1Title}</h3>
            <p style={playbookText}>{ui.step1Desc}</p>
            <div
              style={{
                ...playbookIdBox,
                flexDirection: isMobile ? "column" : "row",
                alignItems: isMobile ? "stretch" : "center",
              }}
            >
              <div>
                <p style={playbookIdLabel}>{ui.idLabel}</p>
                <p style={playbookIdValue}>{safeClientId}</p>
              </div>
              <button
                type="button"
                onClick={() => copyWithFeedback(safeClientId, null, "id")}
                style={playbookCopyButton}
              >
                {copiedState.id ? ui.copied : ui.copyId}
              </button>
            </div>
            <div style={playbookHint}>{ui.step1Hint}</div>
          </div>

          <div style={playbookImageCard}>
            <img src="/widgetstep1.png" alt={ui.step1Alt} style={playbookImage} />
          </div>

          <div style={playbookNavRow}>
            <span />
            <button type="button" onClick={() => goToStep(1)} style={playbookPrimaryButton}>
              {ui.chooseTypeCta}
            </button>
          </div>
        </div>
      )}

      {currentStep === 1 && (
        <div style={playbookPanel}>
          <div style={playbookCard}>
            <h3 style={playbookCardTitle}>{ui.step2Title}</h3>
            <p style={playbookText}>{ui.step2Desc}</p>
            <div style={{ ...playbookOptionGrid, gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr" }}>
              <button
                type="button"
                onClick={() => setSelectedOption("floating")}
                style={{
                  ...playbookOptionCard,
                  ...(selectedOption === "floating" ? playbookOptionSelected : {}),
                }}
              >
                <span style={playbookOptionTag}>{ui.recommended}</span>
                <strong>{ui.floatingTitle}</strong>
                <p style={playbookOptionText}>{ui.floatingDesc}</p>
              </button>
              <button
                type="button"
                onClick={() => setSelectedOption("iframe")}
                style={{
                  ...playbookOptionCard,
                  ...(selectedOption === "iframe" ? playbookOptionSelected : {}),
                }}
              >
                <span style={{ ...playbookOptionTag, backgroundColor: "rgba(74,144,226,0.14)", color: "#4A90E2" }}>
                  {ui.advanced}
                </span>
                <strong>{ui.embeddedTitle}</strong>
                <p style={playbookOptionText}>{ui.embeddedDesc}</p>
              </button>
            </div>
            <div style={playbookHint}>{selectedOption === "floating" ? ui.floatingHint : ui.iframeHint}</div>
          </div>

          <div style={playbookNavRow}>
            <button type="button" onClick={() => goToStep(0)} style={playbookGhostButton}>
              {ui.back}
            </button>
            <button type="button" onClick={() => goToStep(2)} style={playbookPrimaryButton}>
              {ui.getCode}
            </button>
          </div>
        </div>
      )}

      {currentStep === 2 && (
        <div style={playbookPanel}>
          <div style={playbookCard}>
            <h3 style={playbookCardTitle}>{ui.step3Title}</h3>
            <p style={playbookText}>{ui.step3Desc}</p>
            <div style={playbookCodeBlock}>
              <div style={playbookCodeHeader}>
                <span>{currentCodeLabel}</span>
                <button
                  type="button"
                  onClick={() =>
                    copyWithFeedback(
                      selectedCode,
                      selectedInstallType,
                      selectedOption === "floating" ? "codeFloating" : "codeIframe"
                    )
                  }
                  style={playbookCopyButtonSmall}
                >
                  {codeCopied ? ui.copied : ui.copyCode}
                </button>
              </div>
              <pre style={playbookCodePre}>{selectedCode}</pre>
            </div>
            <div style={playbookHint}>{ui.keepIdHint}</div>
          </div>

          <div style={playbookCard}>
            <h4 style={playbookMiniTitle}>{ui.platformTitle}</h4>
            <div style={{ ...playbookTabs, justifyContent: isMobile ? "flex-start" : "space-between" }}>
              {platformEntries.map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSelectedPlatform(key)}
                  style={{
                    ...playbookTabButton,
                    ...(selectedPlatform === key ? playbookTabButtonActive : {}),
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <ol style={playbookOrderedList}>
              {(ui.platformInstructions[selectedPlatform] || []).map((line) => (
                <li key={line} style={playbookText}>{line}</li>
              ))}
            </ol>
          </div>

          <div style={{ ...playbookImageGrid, gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr" }}>
            <div style={playbookImageCard}>
              <img src="/widgetstep2.png" alt={ui.step2Alt} style={playbookImage} />
            </div>
            <div style={playbookImageCard}>
              <img src="/widgetstep3.png" alt={ui.step3Alt} style={playbookImage} />
            </div>
          </div>

          <div style={playbookNavRow}>
            <button type="button" onClick={() => goToStep(1)} style={playbookGhostButton}>
              {ui.back}
            </button>
            <button type="button" onClick={() => goToStep(3)} style={playbookPrimaryButton}>
              {ui.pastedCta}
            </button>
          </div>
        </div>
      )}

      {currentStep === 3 && (
        <div style={playbookPanel}>
          <div style={playbookCard}>
            <h3 style={playbookCardTitle}>{ui.step4Title}</h3>
            <p style={playbookText}>{ui.step4Desc}</p>
            <div style={playbookChecklist}>
              {ui.checks.map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleCheck(key)}
                  style={{
                    ...playbookCheckItem,
                    ...(checkedItems[key] ? playbookCheckItemActive : {}),
                  }}
                >
                  <span style={playbookCheckBox}>{checkedItems[key] ? "✓" : ""}</span>
                  <span>{label}</span>
                </button>
              ))}
            </div>

            {allChecksDone && (
              <div style={playbookSuccess}>
                <strong>{ui.liveTitle}</strong>
                <p style={{ margin: "0.3rem 0 0", color: "#2E7D6A" }}>{ui.liveDesc}</p>
              </div>
            )}
          </div>

          <div style={playbookImageCard}>
            <img src="/widgetstep5.png" alt={ui.step4Alt} style={playbookImage} />
          </div>

          <div style={playbookNavRow}>
            <button type="button" onClick={() => goToStep(2)} style={playbookGhostButton}>
              {ui.back}
            </button>
            <button type="button" onClick={() => goToStep(4)} style={playbookPrimaryButton}>
              {ui.needHelpCta}
            </button>
          </div>
        </div>
      )}

      {currentStep === 4 && (
        <div style={playbookPanel}>
          <div style={playbookCard}>
            <h3 style={playbookCardTitle}>{ui.step5Title}</h3>
            <p style={playbookText}>{ui.step5Desc}</p>

            {ui.troubles.map((item) => (
              <div key={item.key} style={playbookTroubleItem}>
                <button
                  type="button"
                  onClick={() => toggleTrouble(item.key)}
                  style={playbookTroubleQuestion}
                >
                  <span>{item.q}</span>
                  <span style={{ color: "#4A90E2" }}>{openTrouble === item.key ? "▲" : "▼"}</span>
                </button>
                {openTrouble === item.key && <p style={playbookTroubleAnswer}>{item.a}</p>}
              </div>
            ))}
          </div>

          <div style={playbookImageCard}>
            <img src="/widgetstep4.png" alt={ui.step5Alt} style={playbookImage} />
          </div>

          <div style={playbookHelpStrip}>
            <div>
              <p style={{ margin: 0, fontWeight: 700, color: "#274472" }}>{ui.supportTitle}</p>
              <p style={{ margin: "0.2rem 0 0", color: "#4A90E2" }}>{ui.supportText}</p>
            </div>
            <a href="mailto:sales@evolvianai.com" style={playbookHelpLink}>{ui.contactSupport}</a>
          </div>

          <div style={playbookNavRow}>
            <button type="button" onClick={() => goToStep(3)} style={playbookGhostButton}>
              {ui.backToVerify}
            </button>
            <button type="button" onClick={() => goToStep(0)} style={playbookPrimaryButton}>
              {ui.restartGuide}
            </button>
          </div>
        </div>
      )}
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

/* 📘 Full HTML Playbook */
const playbookContainer = {
  marginTop: "2rem",
  background: "linear-gradient(180deg, #F8FAFF 0%, #FFFFFF 100%)",
  border: "1px solid #DCE7F7",
  borderRadius: "16px",
  padding: "clamp(0.9rem, 0.9rem + 1vw, 1.8rem)",
  boxShadow: "0 6px 22px rgba(39, 68, 114, 0.08)",
};

const playbookTitle = {
  color: "#274472",
  fontSize: "1.5rem",
  fontWeight: "bold",
  marginBottom: "0.35rem",
  textAlign: "center",
};

const playbookSubtitle = {
  color: "#4A90E2",
  fontSize: "0.92rem",
  textAlign: "center",
  margin: "0 auto 1rem",
  maxWidth: "760px",
};

const playbookProgressBar = {
  display: "grid",
  gap: "0.5rem",
  marginBottom: "1.2rem",
};

const playbookProgressStep = {
  border: "1px solid #DCE7F7",
  backgroundColor: "#FFFFFF",
  color: "#4A90E2",
  borderRadius: "999px",
  fontSize: "0.77rem",
  fontWeight: 600,
  padding: "0.44rem 0.5rem",
  cursor: "pointer",
  textAlign: "center",
};

const playbookProgressActive = {
  backgroundColor: "#F5A623",
  color: "#FFFFFF",
  borderColor: "#F5A623",
};

const playbookProgressDone = {
  color: "#2EB39A",
};

const playbookPanel = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
};

const playbookCard = {
  border: "1px solid #DCE7F7",
  backgroundColor: "#FFFFFF",
  borderRadius: "14px",
  padding: "1rem",
  boxShadow: "0 2px 12px rgba(39,68,114,0.06)",
};

const playbookCardTitle = {
  color: "#274472",
  margin: 0,
  fontSize: "1.08rem",
  fontWeight: 700,
};

const playbookText = {
  color: "#274472",
  fontSize: "0.93rem",
  lineHeight: 1.6,
  margin: "0.55rem 0",
};

const playbookIdBox = {
  backgroundColor: "#F8FAFF",
  border: "1px solid #DCE7F7",
  borderRadius: "10px",
  padding: "0.9rem",
  display: "flex",
  justifyContent: "space-between",
  gap: "0.8rem",
};

const playbookIdLabel = {
  margin: 0,
  color: "#4A90E2",
  fontSize: "0.76rem",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const playbookIdValue = {
  margin: "0.2rem 0 0",
  color: "#F5A623",
  fontWeight: 700,
  fontFamily: "monospace",
};

const playbookCopyButton = {
  backgroundColor: "#F5A623",
  color: "#FFFFFF",
  border: "none",
  borderRadius: "9px",
  padding: "0.52rem 0.95rem",
  fontWeight: 700,
  cursor: "pointer",
};

const playbookCopyButtonSmall = {
  backgroundColor: "#F5A623",
  color: "#FFFFFF",
  border: "none",
  borderRadius: "8px",
  padding: "0.36rem 0.7rem",
  fontSize: "0.75rem",
  fontWeight: 700,
  cursor: "pointer",
};

const playbookHint = {
  marginTop: "0.8rem",
  backgroundColor: "rgba(74, 144, 226, 0.08)",
  border: "1px solid rgba(74, 144, 226, 0.2)",
  color: "#274472",
  borderRadius: "8px",
  padding: "0.7rem 0.8rem",
  fontSize: "0.84rem",
};

const playbookImageCard = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #DCE7F7",
  borderRadius: "14px",
  padding: "0.8rem",
  boxShadow: "0 2px 12px rgba(39,68,114,0.05)",
};

const playbookImage = {
  width: "100%",
  height: "auto",
  borderRadius: "12px",
  border: "1px solid #E5ECF8",
};

const playbookNavRow = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "0.6rem",
  flexWrap: "wrap",
};

const playbookPrimaryButton = {
  backgroundColor: "#F5A623",
  color: "#FFFFFF",
  border: "none",
  borderRadius: "9px",
  padding: "0.6rem 1rem",
  fontWeight: 700,
  cursor: "pointer",
};

const playbookGhostButton = {
  backgroundColor: "transparent",
  color: "#274472",
  border: "1px solid #DCE7F7",
  borderRadius: "9px",
  padding: "0.56rem 0.95rem",
  fontWeight: 600,
  cursor: "pointer",
};

const playbookOptionGrid = {
  display: "grid",
  gap: "0.85rem",
  marginTop: "0.65rem",
};

const playbookOptionCard = {
  textAlign: "left",
  border: "1px solid #DCE7F7",
  borderRadius: "12px",
  backgroundColor: "#FFFFFF",
  padding: "0.9rem",
  cursor: "pointer",
};

const playbookOptionSelected = {
  borderColor: "#F5A623",
  boxShadow: "0 0 0 2px rgba(245,166,35,0.18) inset",
};

const playbookOptionTag = {
  display: "inline-block",
  backgroundColor: "rgba(245,166,35,0.14)",
  color: "#F5A623",
  borderRadius: "6px",
  fontSize: "0.66rem",
  padding: "0.18rem 0.45rem",
  marginBottom: "0.4rem",
  fontWeight: 700,
  textTransform: "uppercase",
};

const playbookOptionText = {
  color: "#4A90E2",
  fontSize: "0.84rem",
  margin: "0.35rem 0 0",
};

const playbookCodeBlock = {
  border: "1px solid #DCE7F7",
  borderRadius: "10px",
  overflow: "hidden",
  marginTop: "0.65rem",
};

const playbookCodeHeader = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "0.6rem",
  backgroundColor: "#F8FAFF",
  padding: "0.55rem 0.7rem",
  color: "#4A90E2",
  fontSize: "0.78rem",
  fontWeight: 700,
};

const playbookCodePre = {
  margin: 0,
  padding: "0.85rem",
  backgroundColor: "#FFFFFF",
  color: "#274472",
  overflowX: "auto",
  fontSize: "0.75rem",
  lineHeight: 1.55,
};

const playbookMiniTitle = {
  color: "#274472",
  margin: 0,
  fontSize: "0.96rem",
  fontWeight: "bold",
};

const playbookTabs = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.45rem",
  margin: "0.8rem 0",
};

const playbookTabButton = {
  border: "1px solid #DCE7F7",
  backgroundColor: "#FFFFFF",
  color: "#4A90E2",
  borderRadius: "8px",
  padding: "0.33rem 0.62rem",
  fontSize: "0.77rem",
  cursor: "pointer",
};

const playbookTabButtonActive = {
  borderColor: "#F5A623",
  color: "#F5A623",
  backgroundColor: "rgba(245,166,35,0.08)",
};

const playbookOrderedList = {
  margin: 0,
  paddingLeft: "1.1rem",
  display: "grid",
  gap: "0.35rem",
};

const playbookImageGrid = {
  display: "grid",
  gap: "1rem",
};

const playbookChecklist = {
  display: "grid",
  gap: "0.55rem",
  marginTop: "0.7rem",
};

const playbookCheckItem = {
  border: "1px solid #DCE7F7",
  borderRadius: "10px",
  backgroundColor: "#FFFFFF",
  padding: "0.62rem 0.72rem",
  display: "flex",
  alignItems: "center",
  gap: "0.55rem",
  color: "#274472",
  cursor: "pointer",
  textAlign: "left",
};

const playbookCheckItemActive = {
  borderColor: "#2EB39A",
  backgroundColor: "rgba(46,179,154,0.08)",
};

const playbookCheckBox = {
  width: "19px",
  height: "19px",
  borderRadius: "6px",
  border: "1px solid #DCE7F7",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  color: "#2EB39A",
  fontWeight: 800,
};

const playbookSuccess = {
  marginTop: "0.75rem",
  border: "1px solid rgba(46,179,154,0.3)",
  backgroundColor: "rgba(46,179,154,0.1)",
  borderRadius: "10px",
  padding: "0.7rem 0.8rem",
  color: "#274472",
};

const playbookTroubleItem = {
  border: "1px solid #DCE7F7",
  borderRadius: "10px",
  marginBottom: "0.55rem",
  overflow: "hidden",
};

const playbookTroubleQuestion = {
  width: "100%",
  border: "none",
  backgroundColor: "#FFFFFF",
  color: "#274472",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  textAlign: "left",
  padding: "0.62rem 0.72rem",
  fontWeight: 600,
  cursor: "pointer",
};

const playbookTroubleAnswer = {
  margin: 0,
  backgroundColor: "#F8FAFF",
  borderTop: "1px solid #E5ECF8",
  color: "#274472",
  fontSize: "0.86rem",
  lineHeight: 1.55,
  padding: "0.7rem 0.72rem",
};

const playbookHelpStrip = {
  border: "1px solid #DCE7F7",
  borderRadius: "12px",
  backgroundColor: "#FFFFFF",
  padding: "0.8rem",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "0.7rem",
  flexWrap: "wrap",
};

const playbookHelpLink = {
  display: "inline-block",
  textDecoration: "none",
  color: "#F5A623",
  border: "1px solid rgba(245,166,35,0.42)",
  borderRadius: "8px",
  padding: "0.48rem 0.8rem",
  fontWeight: 700,
};
