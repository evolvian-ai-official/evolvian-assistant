// src/pages/Dashboard.jsx
import { useEffect, useState } from "react";
import { useClientId } from "../hooks/useClientId";
import { supabase } from "../lib/supabaseClient";
import { authFetch } from "../lib/authFetch";
import { useLanguage } from "../contexts/LanguageContext";
import WelcomeModal from "../components/WelcomeModal";
import { toast } from "@/components/ui/use-toast";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

export default function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [user, setUser] = useState(null);
  const [showWelcome, setShowWelcome] = useState(false);
  const [reactivating, setReactivating] = useState(false);
  const [showReactivateModal, setShowReactivateModal] = useState(null);
  const clientId = useClientId();
  const { t } = useLanguage();

  // 🧭 Obtener usuario actual
  useEffect(() => {
    const fetchUser = async () => {
      const { data, error } = await supabase.auth.getUser();
      if (error) console.error("❌ Error obteniendo usuario:", error);
      if (data?.user) setUser(data.user);
      else setUser(null);
    };
    fetchUser();
  }, []);

  // 📊 Obtener datos del dashboard
  const fetchDashboardData = async () => {
    if (!clientId) return;
    try {
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/dashboard_summary?client_id=${clientId}`
      );
      const data = await res.json();
      if (res.ok) setDashboardData(data);
      else console.error("❌ Error en respuesta de dashboard_summary:", data);
    } catch (err) {
      console.error("❌ Error de red al obtener dashboard:", err);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [clientId]);

  // ✅ Mostrar modal de bienvenida solo si no ha aceptado T&C o expiró
  useEffect(() => {
    if (!clientId) return;

    const checkTermsAcceptance = async () => {
      try {
        const res = await fetch(
          `${import.meta.env.VITE_API_URL}/accepted_terms?client_id=${clientId}`
        );
        const data = await res.json();

        // Mostrar modal si no ha aceptado o su aceptación expiró
        if (!data.has_accepted) {
          console.log("⚠️ Terms missing or expired:", data.reason);
          setShowWelcome(true);
        } else {
          console.log("✅ Terms are up to date");
        }
      } catch (err) {
        console.error("❌ Error checking accepted terms:", err);
      }
    };

    checkTermsAcceptance();
  }, [clientId]);

  // Loader
  if (!user || !dashboardData) {
    return (
      <div style={loaderContainer}>
        <div style={spinner}></div>
        <p style={{ color: "#274472", marginTop: "1rem" }}>{t("loading")}</p>
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
    subscription_end,
    cancellation_status,
  } = dashboardData;

  const normalize = (str) => str.toLowerCase().replace(/\s+/g, "_");
  const activeFeatures = plan?.plan_features?.map((f) => normalize(f)) || [];

  const chartData = [
    {
      name: t("messages"),
      used: usage.messages_used || 0,
      max: plan.is_unlimited ? usage.messages_used : plan.max_messages,
    },
    {
      name: t("documents"),
      used: usage.documents_uploaded || 0,
      max: plan.max_documents,
    },
  ];

  // 🔁 Reactivar suscripción (se mantiene funcional)
  const handleReactivate = async () => {
    if (!cancellation_status?.reactivate_available) return;
    try {
      setReactivating(true);
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/reactivate-subscription`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ client_id: clientId }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        toast({
          title: `✅ ${t("subscription_reactivated")}`,
          description:
            data.message ||
            `${t("subscription_restored_prefix")} ${plan.name} ${t(
              "subscription_restored_suffix"
            )}`,
        });
        await fetchDashboardData();
        setTimeout(() => window.location.reload(), 1500);
      } else {
        toast({
          title: t("error"),
          description: data.detail || t("reactivate_subscription_error"),
        });
      }
    } catch (err) {
      toast({ title: t("error"), description: err.message || t("unexpected_error") });
    } finally {
      setReactivating(false);
      setShowReactivateModal(null);
    }
  };

  return (
    <div style={pageContainer}>
      {showWelcome && <WelcomeModal onClose={() => setShowWelcome(false)} />}

      {/* 🏷️ Encabezado */}
      <header style={headerContainer}>
        <div style={headerLeft}>
          <img
            src="/logo-evolvian.svg"
            alt="Evolvian Logo"
            style={{ width: 50, height: 50, borderRadius: "50%" }}
          />
          <div>
            <h1 style={pageTitle}>
              👋 {t("welcome")}, {user.email}
            </h1>
            <p style={pageSubtitle}>
              {t("assistant_intro")}{" "}
              <strong style={{ color: "#274472" }}>
                {assistant_config?.assistant_name || t("your_assistant")}
              </strong>
              .
            </p>
          </div>
        </div>
      </header>

      {/* 🧾 Plan Actual */}
      <div style={card}>
        <h2 style={cardTitle}>{t("your_plan")}</h2>
        <p>
          <strong>{plan.name}</strong>
        </p>
        <p>
          {t("messages")}: {plan.is_unlimited ? "∞" : plan.max_messages}
        </p>
        <p>
          {t("documents")}: {plan.max_documents}
        </p>

        {subscription_start && subscription_end && (
          <p style={subtext}>
            {t("subscription_period")}: {subscription_start} – {subscription_end}
          </p>
        )}

        {/* ⏳ Estado de cancelación + Reactivación */}
        {cancellation_status?.is_pending && (
          <div style={cancelNotice}>
            <p style={{ margin: 0 }}>{cancellation_status.message}</p>

            {cancellation_status.reactivate_available && (
              <>
                <button
                  onClick={() =>
                    setShowReactivateModal({
                      planName: plan.name,
                      endDate: subscription_end,
                      label:
                        cancellation_status.reactivate_label || t("reactivate"),
                    })
                  }
                  disabled={reactivating}
                  style={reactivateBtn}
                >
                  {reactivating
                    ? t("reactivating")
                    : cancellation_status.reactivate_label || t("reactivate")}
                </button>

                {showReactivateModal && (
                  <ReactivateModal
                    planName={showReactivateModal.planName}
                    endDate={showReactivateModal.endDate}
                    onCancel={() => setShowReactivateModal(null)}
                    onConfirm={handleReactivate}
                    loading={reactivating}
                  />
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* 📊 Uso */}
      <div style={card}>
        <h2 style={cardTitle}>{t("usage_summary")}</h2>
        <p>
          {t("messages_used")}:{" "}
          <strong style={{ color: "#2EB39A" }}>{usage.messages_used}</strong> /{" "}
          {plan.is_unlimited ? "∞" : plan.max_messages}
          {upgrade_suggestion && (
            <>
              {" "}
              — {t("almost_limit") || "You're close to the limit"} 🚀{" "}
              {upgrade_suggestion.action === "upgrade" && (
                <>
                  {t("upgrade_to") || "Upgrade to"}{" "}
                  <strong>{upgrade_suggestion.to}</strong>
                </>
              )}
              {upgrade_suggestion.action === "contact_support" && (
                <>
                  {" "}
                  {t("contact_support") || "Contact"}{" "}
                  <strong>{upgrade_suggestion.email}</strong>
                </>
              )}
            </>
          )}
        </p>
        <p>
          {t("documents_uploaded")}:{" "}
          <strong style={{ color: "#2EB39A" }}>{usage.documents_uploaded}</strong>{" "}
          / {plan.max_documents}
        </p>

        <div style={{ width: "100%", height: 250, marginTop: "1rem" }}>
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EDEDED" />
              <XAxis dataKey="name" stroke="#274472" />
              <YAxis stroke="#274472" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#FFFFFF",
                  border: "1px solid #EDEDED",
                  color: "#274472",
                }}
              />
              <Bar dataKey="used" fill="#A3D9B1" name={t("used")} />
              <Bar dataKey="max" fill="#4A90E2" name={t("max")} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ⚙️ Funcionalidades */}
      <div style={card}>
        <h2 style={cardTitle}>{t("active_features")}</h2>
        <ul>
          {activeFeatures.length > 0 ? (
            activeFeatures.map((f) => (
              <li key={f} style={featureItem}>
                ✅ {t(f)}
              </li>
            ))
          ) : (
            <li>{t("no_features")}</li>
          )}
        </ul>
      </div>

      {/* 🕑 Historial */}
      <div style={card}>
        <h2 style={cardTitle}>{t("recent_activity")}</h2>
        {history_preview && history_preview.length > 0 ? (
          <ul>
            {history_preview.map((item, idx) => (
              <li key={idx} style={historyItem}>
                {item.question ? item.question.slice(0, 100) : t("no_content")} (
                {new Date(item.timestamp).toLocaleDateString()})
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


/* 🎨 Estilos Evolvian Premium Light */
const pageContainer = {
  backgroundColor: "#FFFFFF",
  minHeight: "100vh",
  padding: "2rem 3rem",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
};

const headerContainer = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: "2rem",
  borderBottom: "1px solid #EDEDED",
  paddingBottom: "1rem",
};

const headerLeft = {
  display: "flex",
  alignItems: "center",
  gap: "1rem",
};

const pageTitle = {
  fontSize: "1.8rem",
  fontWeight: "bold",
  color: "#F5A623",
  marginBottom: "0.3rem",
};

const pageSubtitle = {
  color: "#4A90E2",
  marginBottom: 0,
  fontSize: "1rem",
};

const card = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  padding: "1.5rem",
  marginBottom: "2rem",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
};

const cardTitle = {
  fontSize: "1.3rem",
  color: "#4A90E2",
  marginBottom: "1rem",
  fontWeight: "bold",
};

const featureItem = {
  marginBottom: "0.4rem",
  color: "#274472",
};

const historyItem = {
  marginBottom: "0.4rem",
  color: "#4B5563",
};

const subtext = {
  marginTop: "0.5rem",
  color: "#7A7A7A",
};

const cancelNotice = {
  marginTop: "1rem",
  backgroundColor: "#FFF7E6",
  border: "1px solid #F5A623",
  color: "#7A4A00",
  padding: "12px",
  borderRadius: "10px",
};

const reactivateBtn = {
  marginTop: 10,
  backgroundColor: "#4A90E2",
  color: "#FFFFFF",
  border: "none",
  borderRadius: "8px",
  padding: "8px 16px",
  cursor: "pointer",
  fontWeight: 600,
};

/* Loader */
const loaderContainer = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#FFFFFF",
  minHeight: "100vh",
  fontFamily: "system-ui, sans-serif",
};

const spinner = {
  width: 40,
  height: 40,
  border: "4px solid #EDEDED",
  borderTop: "4px solid #4A90E2",
  borderRadius: "50%",
  animation: "spin 1s linear infinite",
};

/* Modal */
const overlayStyle = {
  position: "fixed",
  inset: 0,
  background: "rgba(17, 24, 39, 0.35)",
  backdropFilter: "blur(4px)",
  WebkitBackdropFilter: "blur(4px)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 9999,
};

const modalStyle = {
  background: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "16px",
  display: "flex",
  maxWidth: 720,
  width: "95%",
  color: "#274472",
  boxShadow: "0 10px 30px rgba(0,0,0,0.12)",
  overflow: "hidden",
};

const leftStyle = {
  background: "#F9FAFB",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 32,
  minWidth: 160,
};

const rightStyle = {
  flex: 1,
  padding: "28px 36px",
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
};

const actionRow = {
  display: "flex",
  justifyContent: "flex-end",
  gap: 10,
  marginTop: 20,
};

const confirmBtn = {
  background: "#F5A623",
  color: "#fff",
  padding: "10px 24px",
  borderRadius: "8px",
  fontWeight: 600,
  border: "none",
  cursor: "pointer",
};

const cancelBtn = {
  background: "#EDEDED",
  color: "#274472",
  padding: "10px 24px",
  borderRadius: "8px",
  fontWeight: 500,
  border: "none",
  cursor: "pointer",
};

const termsText = {
  fontSize: "0.85rem",
  marginTop: 10,
  color: "#6B7280",
};

// keyframes para spinner (solo una vez)
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
