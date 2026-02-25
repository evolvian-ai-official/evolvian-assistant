import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useClientId } from "../hooks/useClientId";
import { supabase } from "../lib/supabaseClient";
import { authFetch } from "../lib/authFetch";
import { trackClientEvent, trackEvent } from "../lib/tracking";
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
  const [hasAskedForHelp, setHasAskedForHelp] = useState(false);
  const clientId = useClientId();
  const navigate = useNavigate();
  const { t, lang } = useLanguage();

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
        const res = await authFetch(
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

  const {
    plan = {},
    usage = {},
    channels = {},
    onboarding_signals = {},
    history_preview = [],
    assistant_config = {},
    upgrade_suggestion = null,
    subscription_start,
    subscription_end,
    cancellation_status,
  } = dashboardData || {};

  const normalize = (str) => str.toLowerCase().replace(/\s+/g, "_");
  const activeFeatures = plan?.plan_features?.map((f) => normalize(f)) || [];
  const isSpanish = lang === "es";

  useEffect(() => {
    if (!clientId || typeof window === "undefined") {
      setHasAskedForHelp(false);
      return;
    }
    const helpKey = `onboarding_help_requested:${clientId}`;
    setHasAskedForHelp(localStorage.getItem(helpKey) === "1");
  }, [clientId]);

  const onboardingCopy = isSpanish
    ? {
        title: "Checklist de onboarding",
        subtitle: "Completa estos pasos para llevar tu asistente a producción.",
        doneLabel: "Completado",
        pendingLabel: "Pendiente",
        completedState: "✅ Listo",
        progressSuffix: "pasos completados",
        allDone: "🚀 ¡Tu asistente ya está en producción!",
        uploadTitle: "Sube tu primer documento",
        uploadAction: "Ir a Subir documentos",
        widgetMessageTitle: "Obtén tu primera conversación desde el widget web",
        widgetMessageAction: "Configurar widget",
        whatsappSetupTitle: "Configura WhatsApp",
        whatsappSetupAction: "Ir a WhatsApp",
        emailSetupTitle: "Configura Email",
        emailSetupAction: "Ir a Email",
        calendarSyncTitle: "Sincroniza Google Calendar",
        calendarSyncAction: "Ir a Calendar",
        firstAppointmentTitle: "Haz tu primera cita",
        firstAppointmentAction: "Ir a Citas",
        templatesTitle: "Configura tus templates",
        templatesAction: "Ir a Templates",
        featureUpgradeActionPrefix: "Mejorar a",
        featureUpsellPrefix: "Disponible en",
        askHelpTitle: "Si necesitas ayuda, pregúntale a Evolvian",
        askHelpAction: "Abrir ayuda de Evolvian",
      }
    : {
        title: "Onboarding checklist",
        subtitle: "Complete these steps to take your assistant live.",
        doneLabel: "Completed",
        pendingLabel: "Pending",
        completedState: "✅ Done",
        progressSuffix: "steps completed",
        allDone: "🚀 Your assistant is live!",
        uploadTitle: "Upload your first document",
        uploadAction: "Go to Upload",
        widgetMessageTitle: "Get first website widget conversation",
        widgetMessageAction: "Set up widget",
        whatsappSetupTitle: "Set up WhatsApp",
        whatsappSetupAction: "Go to WhatsApp",
        emailSetupTitle: "Set up Email",
        emailSetupAction: "Go to Email",
        calendarSyncTitle: "Sync Google Calendar",
        calendarSyncAction: "Go to Calendar",
        firstAppointmentTitle: "Create your first appointment",
        firstAppointmentAction: "Go to Appointments",
        templatesTitle: "Set up message templates",
        templatesAction: "Go to Templates",
        featureUpgradeActionPrefix: "Upgrade to",
        featureUpsellPrefix: "Available on",
        askHelpTitle: "If you have questions, ask Evolvian for help",
        askHelpAction: "Open Evolvian help",
      };

  const hasUpload = (usage?.documents_uploaded || 0) > 0;
  const hasFirstMessage = (usage?.messages_used || 0) > 0;
  const widgetMessagesCount = onboarding_signals?.widget_messages_count || 0;
  const hasChatWidgetFeature = activeFeatures.includes("chat_widget");
  const hasWidgetConversation = widgetMessagesCount > 0;
  const hasWhatsappFeature = activeFeatures.includes("whatsapp_integration");
  const hasEmailFeature = activeFeatures.includes("email_support");
  const hasCalendarFeature = activeFeatures.includes("calendar_sync");
  const hasTemplatesFeature = activeFeatures.includes("templates");
  const isFreeOrStarter = ["free", "starter"].includes((plan?.id || "").toLowerCase());
  const calendarConnected = Boolean(onboarding_signals?.calendar_connected);
  const templatesActiveCount = Number(onboarding_signals?.templates_active_count || 0);
  const appointmentsCount = Number(onboarding_signals?.appointments_count || 0);

  const getFeatureUpsellLabel = (featureKey) => {
    if (featureKey === "whatsapp_integration") return "Starter/Premium";
    if (["email_support", "calendar_sync", "templates"].includes(featureKey)) return "Premium";
    return "Premium";
  };

  const openSupportWidget = () => {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new Event("evolvian:open-support-widget"));
    if (clientId) {
      const helpKey = `onboarding_help_requested:${clientId}`;
      localStorage.setItem(helpKey, "1");
    }
    setHasAskedForHelp(true);
  };

  const featureSteps = [
    {
      id: "whatsapp_setup",
      featureKey: "whatsapp_integration",
      enabled: hasWhatsappFeature,
      title: onboardingCopy.whatsappSetupTitle,
      done: Boolean(channels?.whatsapp),
      actionLabel: onboardingCopy.whatsappSetupAction,
      action: () => navigate("/services/whatsapp"),
    },
    {
      id: "email_setup",
      featureKey: "email_support",
      enabled: hasEmailFeature,
      title: onboardingCopy.emailSetupTitle,
      done: Boolean(channels?.email),
      actionLabel: onboardingCopy.emailSetupAction,
      action: () => navigate("/services/email"),
    },
    {
      id: "calendar_sync",
      featureKey: "calendar_sync",
      enabled: hasCalendarFeature,
      title: onboardingCopy.calendarSyncTitle,
      done: calendarConnected,
      actionLabel: onboardingCopy.calendarSyncAction,
      action: () => navigate("/services/calendar"),
    },
    {
      id: "first_appointment",
      featureKey: "calendar_sync",
      enabled: hasCalendarFeature,
      title: onboardingCopy.firstAppointmentTitle,
      done: appointmentsCount > 0,
      actionLabel: onboardingCopy.firstAppointmentAction,
      action: () => navigate("/services/calendar"),
    },
    {
      id: "templates_setup",
      featureKey: "templates",
      enabled: hasTemplatesFeature,
      title: onboardingCopy.templatesTitle,
      done: templatesActiveCount > 0,
      actionLabel: onboardingCopy.templatesAction,
      action: () => navigate("/services/templates"),
    },
  ]
    .filter((step) => step.enabled || isFreeOrStarter)
    .map((step) => {
      if (step.enabled) return step;
      const upgradeBadge = getFeatureUpsellLabel(step.featureKey);
      return {
        ...step,
        done: false,
        actionLabel: `${onboardingCopy.featureUpgradeActionPrefix} ${upgradeBadge}`,
        note: `${onboardingCopy.featureUpsellPrefix} ${upgradeBadge}.`,
        badge: upgradeBadge,
        isUpsell: true,
        action: () => navigate("/settings#plans"),
      };
    });

  const onboardingSteps = [
    {
      id: "upload",
      title: onboardingCopy.uploadTitle,
      done: hasUpload,
      actionLabel: onboardingCopy.uploadAction,
      action: () => navigate("/upload"),
    },
    ...(hasChatWidgetFeature
      ? [
          {
            id: "widget_message",
            title: onboardingCopy.widgetMessageTitle,
            done: hasWidgetConversation,
            actionLabel: onboardingCopy.widgetMessageAction,
            action: () => navigate("/services/chat"),
          },
        ]
      : []),
    ...featureSteps,
    {
      id: "ask_help",
      title: onboardingCopy.askHelpTitle,
      done: hasAskedForHelp,
      actionLabel: onboardingCopy.askHelpAction,
      action: openSupportWidget,
    },
  ];

  const completedSteps = onboardingSteps.filter((s) => s.done).length;
  const totalSteps = onboardingSteps.length;
  const onboardingProgressPct = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;
  const onboardingDone = completedSteps === totalSteps;
  const completedStepIds = onboardingSteps.filter((s) => s.done).map((s) => s.id);
  const completedStepIdsKey = completedStepIds.join("|");

  const sendEventToBackend = async ({
    eventName,
    eventCategory = "onboarding",
    eventLabel = "",
    eventValue = "",
    eventKey = null,
    metadata = {},
  }) => {
    if (!clientId) return;
    try {
      await authFetch(`${import.meta.env.VITE_API_URL}/client_event_log`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          event_name: eventName,
          event_category: eventCategory,
          event_label: eventLabel,
          event_value: eventValue,
          event_key: eventKey,
          metadata,
        }),
      });
    } catch (error) {
      if (import.meta.env.DEV) {
        console.warn("⚠️ Failed to persist onboarding event:", error);
      }
    }
  };

  useEffect(() => {
    if (!clientId) return;

    const trackingKey = `onboarding_checklist_tracking:${clientId}`;
    let tracked = {};

    try {
      tracked = JSON.parse(localStorage.getItem(trackingKey) || "{}") || {};
    } catch {
      tracked = {};
    }

    let updated = false;
    for (const stepId of completedStepIds) {
      if (tracked[stepId]) continue;
      trackEvent({
        name: "Onboarding_Step_Completed",
        category: "onboarding",
        label: stepId,
        value: plan?.id || "",
      });
      void sendEventToBackend({
        eventName: "Onboarding_Step_Completed",
        eventCategory: "onboarding",
        eventLabel: stepId,
        eventValue: plan?.id || "",
        eventKey: `onboarding_step_completed:${stepId}`,
        metadata: { plan_id: plan?.id || "", step_id: stepId },
      });
      tracked[stepId] = new Date().toISOString();
      updated = true;
    }

    if (onboardingDone && !tracked.__all_done__) {
      trackEvent({
        name: "Onboarding_Checklist_Completed",
        category: "onboarding",
        label: `${totalSteps}_steps`,
        value: plan?.id || "",
      });
      void sendEventToBackend({
        eventName: "Onboarding_Checklist_Completed",
        eventCategory: "onboarding",
        eventLabel: `${totalSteps}_steps`,
        eventValue: plan?.id || "",
        eventKey: `onboarding_checklist_completed:${totalSteps}`,
        metadata: { plan_id: plan?.id || "", total_steps: totalSteps },
      });
      tracked.__all_done__ = new Date().toISOString();
      updated = true;
    }

    if (updated) {
      localStorage.setItem(trackingKey, JSON.stringify(tracked));
    }
  }, [clientId, completedStepIdsKey, onboardingDone, totalSteps, plan?.id]);

  useEffect(() => {
    if (!clientId || !hasFirstMessage) return;

    void trackClientEvent({
      clientId,
      name: "Funnel_First_Message",
      category: "funnel",
      label: "any_channel",
      value: plan?.id || "",
      eventKey: "funnel_first_message",
      metadata: {
        messages_used: usage?.messages_used || 0,
        plan_id: plan?.id || "",
      },
      dedupeLocal: true,
    });
  }, [clientId, hasFirstMessage, plan?.id, usage?.messages_used]);

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
          <h2 className="ia-card-title">{onboardingCopy.title}</h2>
          <p className="ia-dashboard-subtext" style={{ marginTop: "-0.25rem", marginBottom: "0.9rem" }}>
            {onboardingCopy.subtitle}
          </p>

          <div style={{ marginBottom: "1rem" }}>
            <div
              style={{
                width: "100%",
                height: "10px",
                borderRadius: "999px",
                background: "#EDEDED",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${onboardingProgressPct}%`,
                  height: "100%",
                  background: "#2EB39A",
                  transition: "width 240ms ease",
                }}
              />
            </div>
            <p className="ia-dashboard-subtext" style={{ marginTop: "0.45rem" }}>
              {completedSteps}/{totalSteps} {onboardingCopy.progressSuffix}
            </p>
          </div>

          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.65rem" }}>
            {onboardingSteps.map((step) => (
              <li
                key={step.id}
                style={{
                  display: "flex",
                  gap: "0.75rem",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0.75rem",
                  border:
                    step.isUpsell && !step.done ? "1px solid #F6C453" : "1px solid #EDEDED",
                  background:
                    step.isUpsell && !step.done ? "linear-gradient(180deg, #FFFDF5 0%, #FFFFFF 100%)" : "#FFFFFF",
                  borderRadius: "10px",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <p
                    style={{
                      margin: 0,
                      fontWeight: 600,
                      color: "#274472",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.45rem",
                      flexWrap: "wrap",
                    }}
                  >
                    <span>{step.title}</span>
                    {!!step.badge && (
                      <span
                        style={{
                          fontSize: "0.72rem",
                          lineHeight: 1,
                          padding: "0.2rem 0.45rem",
                          borderRadius: "999px",
                          background: "#FFF2CC",
                          border: "1px solid #F6C453",
                          color: "#8A6400",
                          fontWeight: 700,
                        }}
                      >
                        {step.badge}
                      </span>
                    )}
                  </p>
                  <p className="ia-dashboard-subtext" style={{ margin: "0.2rem 0 0" }}>
                    {step.done ? onboardingCopy.doneLabel : onboardingCopy.pendingLabel}
                  </p>
                  {!!step.note && (
                    <p className="ia-dashboard-subtext" style={{ margin: "0.2rem 0 0", color: "#7A5A00" }}>
                      {step.note}
                    </p>
                  )}
                </div>

                {step.done ? (
                  <span style={{ color: "#2EB39A", fontWeight: 700, whiteSpace: "nowrap" }}>
                    {onboardingCopy.completedState}
                  </span>
                ) : (
                  <button
                    type="button"
                    className="ia-button ia-button-primary"
                    onClick={() => {
                      trackEvent({
                        name: "Onboarding_Action_Click",
                        category: "onboarding",
                        label: step.id,
                        value: plan?.id || "",
                      });
                      void sendEventToBackend({
                        eventName: "Onboarding_Action_Click",
                        eventCategory: "onboarding",
                        eventLabel: step.id,
                        eventValue: plan?.id || "",
                        metadata: { plan_id: plan?.id || "", step_id: step.id },
                      });
                      step.action();
                    }}
                    style={{ whiteSpace: "nowrap" }}
                  >
                    {step.actionLabel}
                  </button>
                )}
              </li>
            ))}
          </ul>

          {onboardingDone && (
            <div
              style={{
                marginTop: "1rem",
                padding: "0.75rem 0.9rem",
                borderRadius: "10px",
                border: "1px solid #A3D9B1",
                background: "#ECFAF5",
                color: "#1F7C67",
                fontWeight: 700,
              }}
            >
              {onboardingCopy.allDone}
            </div>
          )}
        </section>

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
