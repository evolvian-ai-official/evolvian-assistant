// src/widget-app.jsx — Evolvian Widget (Consent + Chat)
import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./components/ChatWidget";
import WidgetConsentScreen from "./components/WidgetConsentScreen";

function WidgetApp() {
  const [publicClientId, setPublicClientId] = useState(null);

  // Estado del consentimiento
  const [hasConsent, setHasConsent] = useState(null); // null = loading
  const [consentData, setConsentData] = useState(null);

  // Para enviar a WidgetConsentScreen
  const [clientSettings, setClientSettings] = useState({});

  // ------------------------------------------
  //  Detectar public_client_id desde query
  // ------------------------------------------
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("public_client_id");
    if (id) setPublicClientId(id);
  }, []);

  // ------------------------------------------
  //  Llamar /client_settings (solo para colores)
  // ------------------------------------------
  useEffect(() => {
    if (!publicClientId) return;

    const fetchSettings = async () => {
      const apiUrl =
        window.location.hostname === "localhost"
          ? "http://localhost:8001"
          : "https://evolvian-assistant.onrender.com";

      try {
        const res = await fetch(`${apiUrl}/client_settings?public_client_id=${publicClientId}`);
        if (!res.ok) return;

        const raw = await res.json();
        const data = Array.isArray(raw) ? raw[0] : raw;
        setClientSettings(data || {});
      } catch (err) {
        console.error("⚠️ Error cargando client_settings:", err);
      }
    };

    fetchSettings();
  }, [publicClientId]);

  // ------------------------------------------
  //  Llamar /check_consent
  // ------------------------------------------
  useEffect(() => {
    if (!publicClientId) return;

    const checkConsent = async () => {
      const apiUrl =
        window.location.hostname === "localhost"
          ? "http://localhost:8001"
          : "https://evolvian-assistant.onrender.com";

      try {
        const res = await fetch(`${apiUrl}/check_consent?public_client_id=${publicClientId}`);
        const data = await res.json();

        console.log("🧾 Resultado de /check_consent:", data);

        setConsentData(data);
        setHasConsent(!!data.valid);
      } catch (err) {
        console.error("❌ Error verificando consentimiento:", err);
        setHasConsent(false);
      }
    };

    checkConsent();
  }, [publicClientId]);

  // ------------------------------------------
  //  Loading inicial
  // ------------------------------------------
  if (!publicClientId || hasConsent === null) {
    return (
      <div style={{ color: "#999", textAlign: "center", padding: "2rem" }}>
        Loading...
      </div>
    );
  }

  // ------------------------------------------
  //  NO TIENE CONSENTIMIENTO → mostrar pantalla
  // ------------------------------------------
  if (!hasConsent) {
    console.log("🪪 Mostrando WidgetConsentScreen (usuario sin consentimiento)");
    return (
      <WidgetConsentScreen
        publicClientId={publicClientId}
        clientSettings={clientSettings}

        // FLAGS reales provenientes del backend
        requireEmailConsent={!!consentData?.require_email}
        requirePhoneConsent={!!consentData?.require_phone}
        requireTermsConsent={!!consentData?.require_terms}

        // Para mostrar links legales si existen
        showLegalLinks={!!clientSettings.show_legal_links}
      />
    );
  }

  // ------------------------------------------
  //  Tiene consentimiento → cargar chat
  // ------------------------------------------
  console.log("✅ Consentimiento válido — Renderizando ChatWidget");

  return <ChatWidget clientId={publicClientId} />;
}

// 🚀 Montar widget
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <WidgetApp />
  </React.StrictMode>
);
