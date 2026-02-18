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
import "../components/ui/internal-admin-responsive.css";

export default function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [user, setUser] = useState(null);
  const [showWelcome, setShowWelcome] = useState(false);
  const [reactivating, setReactivating] = useState(false);
  const [showReactivateModal, setShowReactivateModal] = useState(null);
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

  useEffect(() => {
    if (!clientId) return;

    const checkTermsAcceptance = async () => {
      try {
        const res = await fetch(
          `${import.meta.env.VITE_API_URL}/accepted_terms?client_id=${clientId}`
        );
        const data = await res.json();

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

  if (!user || !dashboardData) {
    return (
      <div className="ia-page">
        <div className="ia-loader">
          <div className="ia-spinner" />
          <p style={{ color: "#274472", marginTop: "1rem" }}>{t("loading")}</p>
        </div>
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
    <div className="ia-page">
      <div className="ia-shell">
        {showWelcome && <WelcomeModal onClose={() => setShowWelcome(false)} />}

        <header className="ia-dashboard-header">
          <div className="ia-dashboard-header-left">
            <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="ia-dashboard-logo" />
            <div style={{ minWidth: 0 }}>
              <h1 className="ia-dashboard-title ia-break-anywhere">
                👋 {t("welcome")}, {user.email}
              </h1>
              <p className="ia-dashboard-subtitle">
                {t("assistant_intro")} <strong style={{ color: "#274472" }}>
                  {assistant_config?.assistant_name || t("your_assistant")}
                </strong>
                .
              </p>
            </div>
          </div>
        </header>

        <section className="ia-card">
          <h2 className="ia-card-title">{t("your_plan")}</h2>
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
            <p className="ia-dashboard-subtext">
              {t("subscription_period")}: {subscription_start} - {subscription_end}
            </p>
          )}

          {cancellation_status?.is_pending && (
            <div className="ia-dashboard-cancel-notice">
              <p style={{ margin: 0 }}>{cancellation_status.message}</p>

              {cancellation_status.reactivate_available && (
                <>
                  <button
                    type="button"
                    onClick={() =>
                      setShowReactivateModal({
                        planName: plan.name,
                        endDate: subscription_end,
                        label: cancellation_status.reactivate_label || t("reactivate"),
                      })
                    }
                    disabled={reactivating}
                    className="ia-button ia-button-primary"
                    style={{ marginTop: "0.7rem" }}
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
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">{t("usage_summary")}</h2>
          <p>
            {t("messages_used")}: <strong style={{ color: "#2EB39A" }}>{usage.messages_used}</strong> / {" "}
            {plan.is_unlimited ? "∞" : plan.max_messages}
            {upgrade_suggestion && (
              <>
                {" "}
                - {t("almost_limit") || "You're close to the limit"} 🚀 {" "}
                {upgrade_suggestion.action === "upgrade" && (
                  <>
                    {t("upgrade_to") || "Upgrade to"} <strong>{upgrade_suggestion.to}</strong>
                  </>
                )}
                {upgrade_suggestion.action === "contact_support" && (
                  <>
                    {t("contact_support") || "Contact"} <strong>{upgrade_suggestion.email}</strong>
                  </>
                )}
              </>
            )}
          </p>
          <p>
            {t("documents_uploaded")}: <strong style={{ color: "#2EB39A" }}>{usage.documents_uploaded}</strong> / {" "}
            {plan.max_documents}
          </p>

          <div className="ia-dashboard-chart">
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
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">{t("active_features")}</h2>
          <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {activeFeatures.length > 0 ? (
              activeFeatures.map((f) => (
                <li key={f} className="ia-dashboard-feature-item">
                  ✅ {t(f)}
                </li>
              ))
            ) : (
              <li>{t("no_features")}</li>
            )}
          </ul>
        </section>

        <section className="ia-card" style={{ marginBottom: 0 }}>
          <h2 className="ia-card-title">{t("recent_activity")}</h2>
          {history_preview && history_preview.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {history_preview.map((item, idx) => (
                <li key={idx} className="ia-dashboard-history-item ia-break-anywhere">
                  {item.question ? item.question.slice(0, 100) : t("no_content")} ({new Date(
                    item.timestamp
                  ).toLocaleDateString()})
                </li>
              ))}
            </ul>
          ) : (
            <p>{t("no_history")}</p>
          )}
        </section>
      </div>
    </div>
  );
}

function ReactivateModal({ planName, endDate, onCancel, onConfirm, loading }) {
  const { t } = useLanguage();
  const parsedEndDate = endDate ? new Date(endDate) : null;
  const formattedEndDate =
    parsedEndDate && !Number.isNaN(parsedEndDate.getTime())
      ? parsedEndDate.toLocaleDateString()
      : endDate || "N/A";

  return (
    <div className="ia-modal-overlay" role="dialog" aria-modal="true">
      <div className="ia-modal">
        <div className="ia-modal-side">
          <img
            src="/logo-evolvian.svg"
            alt="Evolvian logo"
            style={{ width: 72, height: 72, borderRadius: "50%" }}
          />
        </div>
        <div className="ia-modal-main">
          <h3 className="ia-modal-title">
            {t("reactivate_subscription") || "Reactivate subscription"}
          </h3>
          <p>
            <strong>{t("your_plan") || "Your plan"}:</strong> {planName}
          </p>
          <p>
            <strong>{t("subscription_end") || "Current end date"}:</strong> {formattedEndDate}
          </p>
          <p className="ia-modal-muted">
            {t("reactivate_subscription_message") ||
              "If you continue, your subscription will be restored immediately."}
          </p>

          <div className="ia-modal-actions">
            <button
              type="button"
              className="ia-button ia-button-ghost"
              onClick={onCancel}
              disabled={loading}
            >
              {t("cancel") || "Cancel"}
            </button>
            <button
              type="button"
              className="ia-button ia-button-warning"
              onClick={onConfirm}
              disabled={loading}
            >
              {loading ? t("reactivating") || "Reactivating..." : t("reactivate") || "Reactivate"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
