import { useEffect, useState } from "react";
import { useClientId } from "../hooks/useClientId";
import { supabase } from "../lib/supabaseClient";
import { useLanguage } from "../contexts/LanguageContext";
import WelcomeModal from "../components/WelcomeModal";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

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
        const res = await fetch(
          `${import.meta.env.VITE_API_URL}/dashboard_summary?client_id=${clientId}`
        );
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
    const redirected = sessionStorage.getItem("alreadyRedirected");
    if (redirected !== "true") {
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

  const { 
    plan, 
    usage, 
    history_preview, 
    assistant_config, 
    upgrade_suggestion, 
    subscription_start, 
    subscription_end 
  } = dashboardData;

  const normalize = (str) => str.toLowerCase().replace(/\s+/g, "_");
  const activeFeatures = plan?.plan_features?.map((f) => normalize(f)) || [];

  // 📊 Datos para la gráfica
  const chartData = [
    {
      name: t("messages"),
      used: usage.messages_used,
      max: plan.is_unlimited ? usage.messages_used : plan.max_messages,
    },
    {
      name: t("documents"),
      used: usage.documents_uploaded,
      max: plan.max_documents,
    },
  ];

  return (
    <div
      style={{
        backgroundColor: showWelcome ? "rgba(15,28,46,0.7)" : "#0f1c2e",
        minHeight: "100vh",
        padding: "2rem",
        fontFamily: "system-ui, sans-serif",
        color: "white",
        overflow: "hidden",
      }}
    >
      {showWelcome && (
        <WelcomeModal
          onClose={() => setShowWelcome(false)}
        />
      )}

      <h1
        style={{
          fontSize: "1.8rem",
          fontWeight: "bold",
          color: "#f5a623",
          marginBottom: "0.5rem",
        }}
      >
        👋 {t("welcome")}, {user.email}
      </h1>
      <p style={{ color: "#ededed", marginBottom: "2rem" }}>
        {t("assistant_intro")}{" "}
        <strong style={{ color: "#a3d9b1" }}>
          {assistant_config?.assistant_name || t("your_assistant")}
        </strong>
        .
      </p>

      {/* 🧾 Plan Actual */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>{t("your_plan")}</h2>
        <p><strong>{plan.name}</strong></p>
        <p>{t("messages")}: {plan.is_unlimited ? "∞" : plan.max_messages}</p>
        <p>{t("documents")}: {plan.max_documents}</p>
        {/* 🗓️ Fechas de suscripción */}
        {subscription_start && subscription_end && (
          <p style={{ marginTop: "0.5rem", color: "#ededed" }}>
            {t("subscription_period")}:{" "}
            <strong>{subscription_start} – {subscription_end}</strong>
          </p>
        )}
      </div>

      {/* 📊 Uso Actual */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>{t("usage_summary")}</h2>
        <p>
          {t("messages_used")}:{" "}
          <strong style={{ color: "#a3d9b1" }}>{usage.messages_used}</strong>{" "}
          / {plan.is_unlimited ? "∞" : plan.max_messages}
          {upgrade_suggestion && (
            <>
              {" "}— {t("almost_limit")} 🚀{" "}
              {upgrade_suggestion.action === "upgrade" && (
                <>
                  {t("upgrade_to")} <strong>{upgrade_suggestion.to}</strong>
                </>
              )}
              {upgrade_suggestion.action === "contact_support" && (
                <> contacting <strong>{upgrade_suggestion.email}</strong></>
              )}
            </>
          )}
        </p>
        <p>
          {t("documents_uploaded")}:{" "}
          <strong style={{ color: "#a3d9b1" }}>{usage.documents_uploaded}</strong>{" "}
          / {plan.max_documents}
        </p>

        {/* 📊 Gráfico de barras */}
        <div style={{ width: "100%", height: 250, marginTop: "1rem" }}>
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#274472" />
              <XAxis dataKey="name" stroke="#ededed" />
              <YAxis stroke="#ededed" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1b2a41",
                  border: "1px solid #274472",
                  color: "#ededed",
                }}
              />
              <Bar dataKey="used" fill="#a3d9b1" name={t("used")} />
              <Bar dataKey="max" fill="#4a90e2" name={t("max")} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ⚙️ Funcionalidades Activas */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>{t("active_features")}</h2>
        <ul>
          {activeFeatures.length > 0 ? (
            activeFeatures.map((f) => (
              <li key={f} style={{ marginBottom: "0.5rem" }}>
                ✅ {t(f)}
              </li>
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
