// src/pages/Welcome.jsx
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { useTermsAcceptance } from "../hooks/useTermsAcceptance";
import { useClientId } from "../hooks/useClientId";
import { supabase } from "../lib/supabaseClient";
import { authFetch } from "../lib/authFetch";
import { useLanguage } from "../contexts/LanguageContext";

export default function Welcome() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const clientId = useClientId();
  const { hasAccepted, acceptTerms } = useTermsAcceptance(clientId);
  const { t } = useLanguage();

  const handleContinue = async () => {
    setLoading(true);

    try {
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/clear_new_user_flag`, {
        method: "POST",
      });
      const result = await res.json();
      console.log("✅ Respuesta de clear_new_user_flag:", result);

      console.log("🔄 Refrescando sesión después de limpiar bandera...");
      await supabase.auth.refreshSession();

      // 🧠 Muy importante: eliminar alreadyRedirected
      sessionStorage.removeItem("alreadyRedirected");

      if (!hasAccepted && clientId) {
        console.log("📩 Aceptando términos con client_id:", clientId);
        await acceptTerms();
      }

      console.log("➡️ Redirigiendo a /dashboard...");
      navigate("/dashboard", { replace: true });

    } catch (err) {
      console.error("❌ Error en Welcome:", err);
      navigate("/dashboard", { replace: true });
    } finally {
      setLoading(false);
    }
  };

  if (hasAccepted === null) {
    return <div style={{ color: "white", padding: "2rem" }}>{t("loading")}</div>;
  }

  return (
    <div style={{
      height: "100vh",
      backgroundColor: "#0f1c2e",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "system-ui, sans-serif",
      padding: "2rem",
      color: "white",
    }}>
      <div style={{
        backgroundColor: "#1b2a41",
        padding: "3rem",
        borderRadius: "1.5rem",
        maxWidth: "600px",
        width: "100%",
        textAlign: "center",
        boxShadow: "0 0 30px rgba(0,0,0,0.2)",
        border: "1px solid #274472"
      }}>
        <img src="/logo-evolvian.svg" alt="Evolvian" style={{ width: "60px", marginBottom: "1.5rem" }} />
        <h1 style={{ fontSize: "1.8rem", color: "#a3d9b1", marginBottom: "1rem" }}>
          {t("welcome_page_title")}
        </h1>
        <p style={{ fontSize: "1rem", color: "#ededed", marginBottom: "1.5rem" }}>
          {t("welcome_page_description_line1")}<br /><br />
          {t("welcome_page_description_line2")}
        </p>
        <button
          onClick={handleContinue}
          disabled={loading}
          style={{
            backgroundColor: "#2eb39a",
            color: "white",
            fontSize: "1rem",
            padding: "0.8rem 1.6rem",
            border: "none",
            borderRadius: "8px",
            fontWeight: "bold",
            cursor: loading ? "not-allowed" : "pointer"
          }}
        >
          {loading ? t("loading") : t("welcome_page_cta")}
        </button>
      </div>
    </div>
  );
}
