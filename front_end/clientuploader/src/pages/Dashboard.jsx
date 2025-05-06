import { useEffect, useState } from "react";
import { useClientId } from "../hooks/useClientId";
import { supabase } from "../lib/supabaseClient";
import { useLanguage } from "../contexts/LanguageContext";
import WelcomeModal from "../components/WelcomeModal";

export default function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [user, setUser] = useState(null);
  const [showWelcome, setShowWelcome] = useState(false);
  const clientId = useClientId();
  const { t } = useLanguage();

  useEffect(() => {
    const fetchUser = async () => {
      const { data, error } = await supabase.auth.getUser();
      if (error) console.error("❌ Error obteniendo usuario:", error);
      if (data?.user) setUser(data.user);
      else setUser(null);
    };
    fetchUser();
  }, []);

  useEffect(() => {
    const fetchDashboardData = async () => {
      if (!clientId) {
        console.warn("⚠️ client_id no disponible aún");
        return;
      }
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL}/dashboard_summary?client_id=${clientId}`);
        const data = await res.json();
        if (res.ok) {
          setDashboardData(data);
        } else {
          console.error("❌ Error en respuesta de dashboard_summary:", data);
        }
      } catch (err) {
        console.error("❌ Error de red al obtener dashboard:", err);
      }
    };

    fetchDashboardData();
  }, [clientId]);

  useEffect(() => {
    if (sessionStorage.getItem("alreadyRedirected") !== "true") {
      setShowWelcome(true);
    }
  }, []);

  if (!user || !dashboardData) {
    return (
      <div style={{ color: "white", padding: "2rem" }}>
        {t("loading")}
      </div>
    );
  }

  const { plan, usage, history_preview, documents_preview, assistant_config } = dashboardData;
  const normalize = (str) => str.toLowerCase().replace(/\s+/g, "_");
  const activeFeatures = plan?.plan_features?.map(f => normalize(f)) || [];

  return (
    <div style={{
      backgroundColor: showWelcome ? "rgba(15,28,46,0.7)" : "#0f1c2e",
      minHeight: "100vh",
      padding: "2rem",
      fontFamily: "system-ui, sans-serif",
      color: "white",
      overflow: "hidden",
    }}>
      {showWelcome && <WelcomeModal onClose={() => setShowWelcome(false)} />}

      <h1 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#f5a623", marginBottom: "0.5rem" }}>
        👋 {t("welcome")}, {user.email}
      </h1>
      <p style={{ color: "#ededed", marginBottom: "2rem" }}>
        {t("assistant_intro")} <strong style={{ color: "#a3d9b1" }}>{assistant_config?.assistant_name || t("your_assistant")}</strong>.
      </p>

      {/* 🧾 Plan Actual */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>{t("your_plan")}</h2>
        <p><strong>{plan.name}</strong></p>
        <p>{t("messages")}: {plan.is_unlimited ? "∞" : plan.max_messages}</p>
        <p>{t("documents")}: {plan.max_documents}</p>
      </div>

      {/* ⚙️ Funcionalidades Activas */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>{t("active_features")}</h2>
        <ul>
          {activeFeatures.length > 0 ? (
            activeFeatures.map(f => (
              <li key={f} style={{ marginBottom: "0.5rem" }}>✅ {t(f)}</li>
            ))
          ) : (
            <li>{t("no_features")}</li>
          )}
        </ul>
      </div>

      {/* 🕑 Historial */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>{t("recent_activity")}</h2>
        {history_preview && history_preview.length > 0 ? (
          <ul>
            {history_preview.map((item, idx) => (
              <li key={idx} style={{ marginBottom: "0.5rem" }}>
                {item.question} ({new Date(item.timestamp).toLocaleDateString()})
              </li>
            ))}
          </ul>
        ) : (
          <p>{t("no_history")}</p>
        )}
      </div>

      {/* 📄 Documentos */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>{t("recent_documents")}</h2>
        {documents_preview && documents_preview.length > 0 ? (
          <ul>
            {documents_preview.map((doc, idx) => (
              <li key={idx} style={{ marginBottom: "0.5rem" }}>
                {doc.filename} {doc.uploaded_at ? `(${new Date(doc.uploaded_at).toLocaleDateString()})` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p>{t("no_documents")}</p>
        )}
      </div>
    </div>
  );
}

// 🎨 Estilos
const cardStyle = {
  backgroundColor: "#1b2a41",
  border: "1px solid #274472",
  borderRadius: "1rem",
  padding: "1.5rem",
  marginBottom: "2rem",
  boxShadow: "0 4px 10px rgba(0,0,0,0.2)",
};

const cardTitle = {
  fontSize: "1.3rem",
  color: "#4a90e2",
  marginBottom: "1rem",
  fontWeight: "bold",
};
