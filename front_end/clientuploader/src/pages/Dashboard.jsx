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
  const [conversationInsights, setConversationInsights] = useState(null);
  const [conversationInsightsLoading, setConversationInsightsLoading] = useState(false);
  const [conversationInsightsError, setConversationInsightsError] = useState("");
  const [humanAlertsData, setHumanAlertsData] = useState({ items: [], counts: {}, status_filter: "open" });
  const [humanAlertsFilter, setHumanAlertsFilter] = useState("open");
  const [humanAlertsLoading, setHumanAlertsLoading] = useState(false);
  const [humanAlertsError, setHumanAlertsError] = useState("");
  const [humanAlertUpdatingId, setHumanAlertUpdatingId] = useState(null);
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

  const fetchHumanAlerts = async (statusFilter = humanAlertsFilter) => {
    if (!clientId) return;
    setHumanAlertsLoading(true);
    setHumanAlertsError("");
    try {
      const query = new URLSearchParams({
        client_id: clientId,
        status: statusFilter || "open",
        limit: "20",
      });
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/conversation_alerts?${query.toString()}`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Could not load human intervention alerts");
      }
      setHumanAlertsData({
        items: Array.isArray(data?.items) ? data.items : [],
        counts: data?.counts || {},
        status_filter: data?.status_filter || (statusFilter || "open"),
      });
    } catch (err) {
      setHumanAlertsError(err?.message || "Could not load human intervention alerts");
    } finally {
      setHumanAlertsLoading(false);
    }
  };

  useEffect(() => {
    if (!clientId) return;
    const handoffEnabled = Array.isArray(dashboardData?.plan?.plan_features)
      && dashboardData.plan.plan_features.some((f) => {
        if (typeof f === "string") return String(f).toLowerCase() === "handoff";
        if (!f || typeof f !== "object") return false;
        if (f.is_active === false) return false;
        return String(f.feature || "").toLowerCase() === "handoff";
      });
    if (!handoffEnabled) {
      setHumanAlertsData({ items: [], counts: {}, status_filter: humanAlertsFilter || "open" });
      setHumanAlertsError("");
      setHumanAlertsLoading(false);
      return;
    }
    fetchHumanAlerts(humanAlertsFilter);
  }, [clientId, humanAlertsFilter, dashboardData]);

  useEffect(() => {
    if (!clientId) return;

    const checkWelcomeRequirements = async () => {
      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/should_show_welcome?client_id=${clientId}`
        );
        const data = await res.json();

        if (data.show) {
          console.log("⚠️ Showing onboarding modal:", data.reason, data.missing_fields || []);
          setShowWelcome(true);
        } else {
          console.log("✅ Welcome modal not required");
          setShowWelcome(false);
        }
      } catch (err) {
        console.error("❌ Error checking welcome requirements:", err);
      }
    };

    checkWelcomeRequirements();
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
  const hasConversationInsightsFeature = activeFeatures.includes("conversation_insights");
  const isSpanish = lang === "es";

  useEffect(() => {
    if (!clientId || !dashboardData) return;

    if (!hasConversationInsightsFeature) {
      setConversationInsights(null);
      setConversationInsightsError("");
      setConversationInsightsLoading(false);
      return;
    }

    let isMounted = true;

    const fetchConversationInsights = async () => {
      setConversationInsightsLoading(true);
      setConversationInsightsError("");
      try {
        const params = new URLSearchParams({
          client_id: clientId,
          limit: "120",
          lang: lang || "en",
        });
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/history/insights?${params.toString()}`
        );
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || data?.error || "Could not load conversation insights");
        }
        if (!isMounted) return;
        setConversationInsights(data && typeof data === "object" ? data : null);
      } catch (err) {
        if (!isMounted) return;
        console.error("❌ Error fetching dashboard insights:", err);
        setConversationInsights(null);
        setConversationInsightsError(err?.message || "Could not load conversation insights");
      } finally {
        if (!isMounted) return;
        setConversationInsightsLoading(false);
      }
    };

    fetchConversationInsights();

    return () => {
      isMounted = false;
    };
  }, [clientId, lang, dashboardData, hasConversationInsightsFeature]);

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
        whatsappSetupTitle: "Configura Meta Apps",
        whatsappSetupAction: "Ir a Meta Apps",
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
        whatsappSetupTitle: "Set up Meta Apps",
        whatsappSetupAction: "Go to Meta Apps",
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
  const hasHandoffFeature = activeFeatures.includes("handoff");
  const isFreeOrStarter = ["free", "starter"].includes((plan?.id || "").toLowerCase());
  const humanAlerts = humanAlertsData?.items || [];
  const humanAlertCounts = humanAlertsData?.counts || {};
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
      action: () => navigate("/services/meta-apps"),
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
  ];

  const topFaq = conversationInsights?.faq?.[0] || null;
  const topTopics = Array.isArray(conversationInsights?.top_topics)
    ? conversationInsights.top_topics.slice(0, 3)
    : [];
  const topQuestions = Array.isArray(conversationInsights?.faq)
    ? conversationInsights.faq.slice(0, 3)
    : [];
  const topRecommendation = conversationInsights?.recommendations?.[0] || "";
  const conversationInsightsProviderLabel =
    conversationInsights?.provider === "openai"
      ? t("history_ai_provider") || "AI analyzed"
      : t("history_heuristic_provider") || "Automatic summary";
  const dashboardInsightsTitle =
    t("dashboard_conversation_insights") || (lang === "es" ? "Insights de conversaciones" : "Conversation insights");
  const dashboardInsightsIntro =
    topFaq?.question
      ? `${t("dashboard_common_questions_intro") || (lang === "es" ? "Tus clientes comúnmente preguntan" : "Your customers commonly ask")}: "${topFaq.question}"`
      : t("dashboard_common_questions_fallback") ||
        (lang === "es"
          ? "Todavía no hay suficientes preguntas repetidas para detectar un patrón fuerte."
          : "There are not enough repeated questions yet to detect a strong pattern.");

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

  const updateHumanAlertStatus = async (alertId, status) => {
    if (!clientId || !alertId) return;
    try {
      setHumanAlertUpdatingId(alertId);
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/conversation_alerts/${alertId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, status }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Could not update alert");
      }
      await fetchHumanAlerts(humanAlertsFilter);
    } catch (err) {
      setHumanAlertsError(err?.message || "Could not update alert");
    } finally {
      setHumanAlertUpdatingId(null);
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
          <h2 className="ia-card-title">
            {lang === "es" ? "Alertas de intervención humana" : "Human intervention alerts"}
          </h2>
          <p className="ia-dashboard-subtext" style={{ marginTop: "-0.2rem", marginBottom: "0.8rem" }}>
            {lang === "es"
              ? "Conversaciones que requieren revisión del equipo humano."
              : "Conversations that require human team review."}
          </p>

          {!hasHandoffFeature ? (
            <div
              style={{
                border: "1px solid #F3D28E",
                background: "#FFF8EB",
                color: "#7A5900",
                borderRadius: "12px",
                padding: "0.85rem",
              }}
            >
              <strong style={{ display: "block", marginBottom: "0.35rem" }}>
                {lang === "es" ? "Disponible en Premium" : "Available on Premium"}
              </strong>
              <span>
                {lang === "es"
                  ? "Activa Inbox / Handoff para escalar conversaciones a agentes humanos, gestionar alertas y responder por email o WhatsApp."
                  : "Enable Inbox / Handoff to escalate conversations to human agents, manage alerts, and reply via email or WhatsApp."}
              </span>
            </div>
          ) : (
            <>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.9rem" }}>
            {[
              { id: "open", label: lang === "es" ? "Abiertas" : "Open" },
              { id: "acknowledged", label: lang === "es" ? "En revisión" : "Acknowledged" },
              { id: "resolved", label: lang === "es" ? "Resueltas" : "Resolved" },
              { id: "all", label: lang === "es" ? "Todas" : "All" },
            ].map((opt) => {
              const active = humanAlertsFilter === opt.id;
              const countValue =
                opt.id === "all"
                  ? (humanAlertCounts.open || 0) + (humanAlertCounts.acknowledged || 0) + (humanAlertCounts.resolved || 0)
                  : (humanAlertCounts[opt.id] ?? null);
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setHumanAlertsFilter(opt.id)}
                  className="ia-button"
                  style={{
                    padding: "0.45rem 0.7rem",
                    borderRadius: "999px",
                    border: active ? "1px solid #2EB39A" : "1px solid #EDEDED",
                    background: active ? "#ECFAF5" : "#FFFFFF",
                    color: active ? "#1F7C67" : "#274472",
                    fontWeight: 600,
                  }}
                >
                  {opt.label}
                  {countValue !== null ? ` (${countValue})` : ""}
                </button>
              );
            })}
          </div>

          {humanAlertsError ? (
            <div
              style={{
                marginBottom: "0.8rem",
                padding: "0.65rem 0.8rem",
                borderRadius: "10px",
                border: "1px solid #F1B8B8",
                background: "#FFF6F6",
                color: "#9F2D2D",
              }}
            >
              {humanAlertsError}
            </div>
          ) : null}

          {humanAlertsLoading ? (
            <p>{lang === "es" ? "Cargando alertas..." : "Loading alerts..."}</p>
          ) : humanAlerts.length === 0 ? (
            <p>{lang === "es" ? "No hay alertas para este filtro." : "No alerts for this filter."}</p>
          ) : (
            <div style={{ display: "grid", gap: "0.75rem" }}>
              {humanAlerts.map((alert) => {
                const handoff = alert?.handoff || {};
                const contactLine =
                  handoff.contact_name ||
                  handoff.contact_email ||
                  handoff.contact_phone ||
                  null;
                const isUpdating = humanAlertUpdatingId === alert.id;
                const currentStatus = String(alert.status || "").toLowerCase();
                return (
                  <div
                    key={alert.id}
                    style={{
                      border: "1px solid #EDEDED",
                      borderRadius: "12px",
                      padding: "0.85rem",
                      background: "#FFFFFF",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: "0.75rem",
                        alignItems: "flex-start",
                        flexWrap: "wrap",
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div
                          style={{
                            display: "flex",
                            gap: "0.45rem",
                            alignItems: "center",
                            flexWrap: "wrap",
                            marginBottom: "0.25rem",
                          }}
                        >
                          <strong style={{ color: "#274472" }}>
                            {alert.title || (lang === "es" ? "Intervención humana" : "Human intervention")}
                          </strong>
                          <span
                            style={{
                              fontSize: "0.72rem",
                              lineHeight: 1,
                              padding: "0.2rem 0.45rem",
                              borderRadius: "999px",
                              background: "#F5F8FC",
                              border: "1px solid #DCE7F5",
                              color: "#274472",
                              fontWeight: 700,
                            }}
                          >
                            {currentStatus}
                          </span>
                          {handoff.channel ? (
                            <span
                              style={{
                                fontSize: "0.72rem",
                                lineHeight: 1,
                                padding: "0.2rem 0.45rem",
                                borderRadius: "999px",
                                background: "#FFF7E8",
                                border: "1px solid #F6D58A",
                                color: "#8A6400",
                                fontWeight: 700,
                              }}
                            >
                              {handoff.channel}
                            </span>
                          ) : null}
                        </div>
                        <p className="ia-dashboard-subtext ia-break-anywhere" style={{ margin: 0 }}>
                          {alert.body || handoff.last_user_message || (lang === "es" ? "Sin mensaje" : "No message")}
                        </p>
                        {contactLine ? (
                          <p className="ia-dashboard-subtext ia-break-anywhere" style={{ margin: "0.35rem 0 0" }}>
                            {lang === "es" ? "Contacto" : "Contact"}:{" "}
                            <strong style={{ color: "#274472" }}>{contactLine}</strong>
                          </p>
                        ) : null}
                        {(handoff.contact_email || handoff.contact_phone) && (
                          <p className="ia-dashboard-subtext ia-break-anywhere" style={{ margin: "0.2rem 0 0" }}>
                            {[handoff.contact_email, handoff.contact_phone].filter(Boolean).join(" · ")}
                          </p>
                        )}
                        {(handoff.reason || alert.created_at) && (
                          <p className="ia-dashboard-subtext" style={{ margin: "0.2rem 0 0" }}>
                            {handoff.reason ? `${handoff.reason}` : ""}
                            {handoff.reason && alert.created_at ? " · " : ""}
                            {alert.created_at ? new Date(alert.created_at).toLocaleString() : ""}
                          </p>
                        )}
                      </div>

                      <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
                        {currentStatus !== "acknowledged" && currentStatus !== "resolved" && (
                          <button
                            type="button"
                            className="ia-button"
                            disabled={isUpdating}
                            onClick={() => updateHumanAlertStatus(alert.id, "acknowledged")}
                            style={{
                              border: "1px solid #DCE7F5",
                              background: "#F5F8FC",
                              color: "#274472",
                              borderRadius: "9px",
                              padding: "0.45rem 0.65rem",
                            }}
                          >
                            {isUpdating
                              ? (lang === "es" ? "Guardando..." : "Saving...")
                              : (lang === "es" ? "Marcar en revisión" : "Acknowledge")}
                          </button>
                        )}
                        {currentStatus !== "resolved" && (
                          <button
                            type="button"
                            className="ia-button ia-button-primary"
                            disabled={isUpdating}
                            onClick={() => updateHumanAlertStatus(alert.id, "resolved")}
                            style={{ borderRadius: "9px", padding: "0.45rem 0.65rem" }}
                          >
                            {isUpdating
                              ? (lang === "es" ? "Guardando..." : "Saving...")
                              : (lang === "es" ? "Resolver" : "Resolve")}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
            </>
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
          <p>{t("plan_feature_1_document") || "Upload documents"}</p>

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
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: "0.9rem",
              flexWrap: "wrap",
              marginBottom: "0.8rem",
            }}
          >
            <div style={{ minWidth: 0 }}>
              <h2 className="ia-card-title" style={{ marginBottom: "0.35rem" }}>
                {dashboardInsightsTitle}
              </h2>
              <p className="ia-dashboard-subtext" style={{ margin: 0 }}>
                {conversationInsightsProviderLabel}
                {conversationInsights?.stats?.conversation_count
                  ? ` · ${conversationInsights.stats.conversation_count} ${t("history_conversations") || "Conversations"}`
                  : ""}
              </p>
            </div>
            <button
              type="button"
              className="ia-button ia-button-ghost"
              onClick={() => navigate(hasConversationInsightsFeature ? "/history" : "/settings#plans")}
            >
              {hasConversationInsightsFeature
                ? t("message_history") || "Message History"
                : `${t("upgrade_to") || "Upgrade to"} ${t("premium")}`}
            </button>
          </div>

          {!hasConversationInsightsFeature ? (
            <div
              style={{
                border: "1px solid #F3D28E",
                background: "#FFF8EB",
                color: "#7A5900",
                borderRadius: "14px",
                padding: "0.95rem",
              }}
            >
              <strong style={{ display: "block", marginBottom: "0.35rem" }}>
                {t("dashboard_insights_locked_title") || "Conversation insights available on Premium"}
              </strong>
              <p style={{ margin: 0 }}>
                {t("dashboard_insights_locked_copy") ||
                  "Unlock AI analysis of frequent questions, top topics, and recommendations from your conversations."}
              </p>
              <p style={{ margin: "0.55rem 0 0", fontWeight: 700 }}>
                {(t("current_plan_unavailable") || "Not available on your current plan.").replace(/\s+$/, "")}{" "}
                {t("available_from") || "Available from"} {t("premium")}.
              </p>
            </div>
          ) : conversationInsightsLoading ? (
            <p>{lang === "es" ? "Analizando conversaciones..." : "Analyzing conversations..."}</p>
          ) : conversationInsightsError ? (
            <div
              style={{
                border: "1px solid #F1B8B8",
                background: "#FFF6F6",
                color: "#9F2D2D",
                borderRadius: "12px",
                padding: "0.85rem",
              }}
            >
              {conversationInsightsError}
            </div>
          ) : (
            <>
              <div
                style={{
                  border: "1px solid #DCE7F5",
                  background: "linear-gradient(135deg, #F6FBFF 0%, #FFFFFF 62%, #FFF9ED 100%)",
                  borderRadius: "16px",
                  padding: "1rem",
                  marginBottom: "1rem",
                }}
              >
                <p
                  style={{
                    margin: 0,
                    color: "#18304F",
                    fontWeight: 800,
                    lineHeight: 1.55,
                  }}
                  className="ia-break-anywhere"
                >
                  {dashboardInsightsIntro}
                </p>
                {!!conversationInsights?.summary && (
                  <p className="ia-dashboard-subtext ia-break-anywhere" style={{ margin: "0.5rem 0 0" }}>
                    {conversationInsights.summary}
                  </p>
                )}
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                  gap: "0.85rem",
                }}
              >
                <div
                  style={{
                    border: "1px solid #EDEDED",
                    borderRadius: "14px",
                    padding: "0.95rem",
                    background: "#FFFFFF",
                  }}
                >
                  <h3
                    style={{
                      margin: "0 0 0.65rem",
                      color: "#274472",
                      fontSize: "0.98rem",
                    }}
                  >
                    {t("history_faq") || "Frequent questions"}
                  </h3>
                  {topQuestions.length ? (
                    <ul style={{ margin: 0, paddingLeft: "1.1rem", display: "grid", gap: "0.55rem" }}>
                      {topQuestions.map((item, index) => (
                        <li key={`${item.question}-${index}`} className="ia-dashboard-history-item ia-break-anywhere">
                          {item.question}
                          {typeof item.mentions === "number" ? ` (${item.mentions}x)` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="ia-dashboard-subtext" style={{ margin: 0 }}>
                      {t("history_no_faq") || "No clear repeated questions yet."}
                    </p>
                  )}
                </div>

                <div
                  style={{
                    border: "1px solid #EDEDED",
                    borderRadius: "14px",
                    padding: "0.95rem",
                    background: "#FFFFFF",
                  }}
                >
                  <h3
                    style={{
                      margin: "0 0 0.65rem",
                      color: "#274472",
                      fontSize: "0.98rem",
                    }}
                  >
                    {t("history_top_topics") || "Top topics"}
                  </h3>
                  {topTopics.length ? (
                    <ul style={{ margin: 0, paddingLeft: "1.1rem", display: "grid", gap: "0.55rem" }}>
                      {topTopics.map((item, index) => (
                        <li key={`${item.topic}-${index}`} className="ia-dashboard-history-item ia-break-anywhere">
                          <strong>{item.topic}</strong>
                          {typeof item.mentions === "number" ? ` (${item.mentions}x)` : ""}
                          {item.note ? ` · ${item.note}` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="ia-dashboard-subtext" style={{ margin: 0 }}>
                      {t("history_no_topics") || "No dominant topics detected yet."}
                    </p>
                  )}
                </div>

                <div
                  style={{
                    border: "1px solid #EDEDED",
                    borderRadius: "14px",
                    padding: "0.95rem",
                    background: "#FFFFFF",
                  }}
                >
                  <h3
                    style={{
                      margin: "0 0 0.65rem",
                      color: "#274472",
                      fontSize: "0.98rem",
                    }}
                  >
                    {t("history_recommendations") || "Recommendations"}
                  </h3>
                  {topRecommendation ? (
                    <p className="ia-dashboard-subtext ia-break-anywhere" style={{ margin: 0, color: "#274472" }}>
                      {topRecommendation}
                    </p>
                  ) : (
                    <p className="ia-dashboard-subtext" style={{ margin: 0 }}>
                      {t("history_no_recommendations") || "No recommendations for now."}
                    </p>
                  )}
                </div>
              </div>
            </>
          )}
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
