import { useInitializeUser } from "../../hooks/useInitializeUser";
import { useLanguage } from "../../contexts/LanguageContext"; // ✅ Importar traducción

export default function ChatSetup() {
  const { publicClientId, loading } = useInitializeUser();
  const { t } = useLanguage(); // ✅ Usar traducción

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    alert(`📋 ${t("copied_to_clipboard")}`);
  };

  const domain = window.location.hostname.includes("localhost")
    ? "http://localhost:5173"
    : "https://evolvian.app";

  const scriptCode = `<script>
  (function () {
    const iframe = document.createElement("iframe");
    iframe.src = "${domain}/widget?public_client_id=${publicClientId || "TU_ID_PUBLICO"}";
    iframe.style.position = "fixed";
    iframe.style.bottom = "20px";
    iframe.style.right = "20px";
    iframe.style.width = "360px";
    iframe.style.height = "520px";
    iframe.style.border = "2px solid #4a90e2";
    iframe.style.borderRadius = "16px";
    iframe.style.backgroundColor = "#ededed";
    iframe.style.boxShadow = "0 6px 24px rgba(0,0,0,0.15)";
    iframe.style.zIndex = "9999";
    iframe.setAttribute("title", "Evolvian AI Widget");
    iframe.setAttribute("allow", "clipboard-write; microphone");
    document.body.appendChild(iframe);
  })();
</script>`;

  const iframeCode = `<iframe
  src="${domain}/widget?public_client_id=${publicClientId || "TU_ID_PUBLICO"}"
  style="width:360px;height:520px;border:2px solid #4a90e2;border-radius:16px;background-color:#ededed;box-shadow:0 6px 24px rgba(0,0,0,0.15);position:fixed;bottom:20px;right:20px;z-index:9999;"
  allow="clipboard-write; microphone"
  title="Evolvian AI Chat Widget"
></iframe>`;

  if (loading) {
    return (
      <div style={pageStyle}>
        <div style={{ color: "#ededed" }}>🔄 {t("loading_setup")}</div>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <div style={{ maxWidth: "1400px", margin: "0 auto" }}>
        <h2 style={titleStyle}>🧠 {t("setup_evolvian_web")}</h2>
        <p style={descriptionStyle}>{t("setup_description")}</p>

        <div style={idBoxStyle}>
          <div>
            <strong>{t("your_public_id")}:</strong>{" "}
            <span style={{ color: "#a3d9b1" }}>{publicClientId || t("not_available")}</span>
          </div>
          <button
            onClick={() => handleCopy(publicClientId)}
            disabled={!publicClientId}
            style={copyButtonStyle(publicClientId)}
          >
            {t("copy_id")}
          </button>
        </div>

        <div style={optionsContainerStyle}>
          <div style={cardStyle}>
            <h3 style={subtitleStyle}>🔹 {t("option1_title")}</h3>
            <p style={hintStyle}>💡 {t("option1_hint")}</p>
            <ol style={stepsStyle}>
              <li>1. {t("copy_script")}</li>
              <li>2. {t("paste_before_body")}</li>
            </ol>
            <pre style={codeStyle}>{scriptCode}</pre>
            <button onClick={() => handleCopy(scriptCode)} style={actionButtonStyle}>
              {t("copy_script_button")}
            </button>
          </div>

          <div style={cardStyle}>
            <h3 style={subtitleStyle}>🔹 {t("option2_title")}</h3>
            <p style={hintStyle}>💡 {t("option2_hint")}</p>
            <ol style={stepsStyle}>
              <li>1. {t("copy_code")}</li>
              <li>2. {t("paste_before_body")}</li>
            </ol>
            <pre style={codeStyle}>{iframeCode}</pre>
            <button onClick={() => handleCopy(iframeCode)} style={actionButtonStyle}>
              {t("copy_iframe")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// 🎨 Estilos (sin cambios)
const pageStyle = {
  padding: "2rem 3rem",
  fontFamily: "system-ui, sans-serif",
  backgroundColor: "#0f1c2e",
  color: "#ffffff",
  minHeight: "100vh",
};

const titleStyle = {
  fontSize: "2rem",
  color: "#f5a623",
  fontWeight: "bold",
  marginBottom: "1rem",
};

const descriptionStyle = {
  color: "#ffffff",
  maxWidth: "800px",
  marginBottom: "2rem",
};

const idBoxStyle = {
  backgroundColor: "#1b2a41",
  padding: "1rem",
  borderRadius: "12px",
  marginBottom: "2rem",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  maxWidth: "600px",
};

const copyButtonStyle = (enabled) => ({
  backgroundColor: "#4a90e2",
  color: "white",
  border: "none",
  borderRadius: "8px",
  padding: "0.5rem 1rem",
  fontWeight: "bold",
  cursor: enabled ? "pointer" : "not-allowed",
  opacity: enabled ? 1 : 0.5,
});

const optionsContainerStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
  gap: "2rem",
  marginTop: "2rem",
};

const cardStyle = {
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  backgroundColor: "#1b2a41",
  padding: "1.5rem",
  borderRadius: "12px",
  minHeight: "460px",
};

const subtitleStyle = {
  color: "#f5a623",
  fontSize: "1.2rem",
  marginBottom: "0.75rem",
};

const hintStyle = {
  fontSize: "0.85rem",
  color: "#a3d9b1",
  marginBottom: "1rem",
};

const stepsStyle = {
  fontSize: "0.85rem",
  marginBottom: "1rem",
};

const codeStyle = {
  background: "#ededed",
  color: "#274472",
  padding: "1rem",
  borderRadius: "8px",
  fontSize: "0.75rem",
  overflowX: "auto",
  marginBottom: "0.5rem",
};

const actionButtonStyle = {
  backgroundColor: "#f5a623",
  color: "#1b2a41",
  border: "none",
  borderRadius: "8px",
  padding: "0.5rem 1rem",
  fontWeight: "bold",
  fontSize: "0.85rem",
  cursor: "pointer",
};
