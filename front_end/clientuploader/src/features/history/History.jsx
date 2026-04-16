import { useEffect, useMemo, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";
import {
  extractActivePlanFeatures,
  minPlanForFeatures,
  normalizeFeature,
  normalizePlanId,
} from "../../lib/planEntitlements";
import "../../components/ui/internal-admin-responsive.css";

const API_URL = import.meta.env.VITE_API_URL;

const CHANNEL_META = {
  chat: { label: "Chat", emoji: "💬" },
  widget: { label: "Widget", emoji: "💬" },
  email: { label: "Email", emoji: "✉️" },
  gmail: { label: "Email", emoji: "✉️" },
  whatsapp: { label: "WhatsApp", emoji: "🟢" },
  messenger: { label: "Messenger", emoji: "🔵" },
  instagram: { label: "Instagram DM", emoji: "📷" },
};

const normalizeTimezone = (tz) => {
  if (!tz || typeof tz !== "string") return "UTC";
  try {
    Intl.DateTimeFormat(undefined, { timeZone: tz });
    return tz;
  } catch {
    return "UTC";
  }
};

const normalizeHistoryPayload = (payload) => {
  if (Array.isArray(payload?.history)) return payload.history;
  if (Array.isArray(payload?.history?.history)) return payload.history.history;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
};

const normalizeInsightsPayload = (payload) => {
  if (!payload || typeof payload !== "object") return null;
  return payload;
};

const buildFetchError = async (res, fallbackMessage) => {
  const payload = await res.json().catch(() => ({}));
  const error = new Error(payload?.detail || payload?.error || fallbackMessage);
  error.status = res.status;
  return error;
};

const previewText = (value, limit = 120) => {
  const normalized = String(value || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "(empty message)";
  if (normalized.length <= limit) return normalized;
  return `${normalized.slice(0, limit - 1)}...`;
};

const channelBadge = (channel) => {
  const normalized = String(channel || "chat").trim().toLowerCase();
  return CHANNEL_META[normalized] || CHANNEL_META.chat;
};

const isUserMessage = (message) => String(message?.role || "").trim().toLowerCase() === "user";

const toTimestamp = (value) => {
  const dateValue = value instanceof Date ? value : new Date(value || 0);
  const time = dateValue.getTime();
  return Number.isNaN(time) ? 0 : time;
};

const buildSessionLabel = (sessionId, t) => {
  if (!sessionId || sessionId === "default") return t("main_session") || "Main session";
  return `${t("history_visitor_label") || "Visitor"} · ${String(sessionId).slice(0, 8)}`;
};

const loadHistory = async (clientId) => {
  const params = new URLSearchParams({ client_id: clientId, limit: "200" });
  const res = await authFetch(`${API_URL}/history?${params.toString()}`);
  if (!res.ok) throw await buildFetchError(res, "Could not load history");
  const payload = await res.json();
  return normalizeHistoryPayload(payload);
};

const loadProfileTimezone = async (clientId) => {
  const res = await authFetch(`${API_URL}/profile/${clientId}`);
  if (!res.ok) return "UTC";
  const payload = await res.json();
  return normalizeTimezone(payload?.timezone);
};

const loadEntitlements = async (clientId) => {
  const res = await authFetch(`${API_URL}/client_settings?client_id=${clientId}`);
  if (!res.ok) throw await buildFetchError(res, "Could not load plan entitlements");
  const payload = await res.json();
  return {
    currentPlanId: normalizePlanId(payload?.plan?.id || payload?.plan_id || "free"),
    activePlanFeatures: extractActivePlanFeatures(payload?.plan?.plan_features),
    availablePlans: Array.isArray(payload?.available_plans) ? payload.available_plans : [],
  };
};

const loadInsights = async (clientId, lang) => {
  const params = new URLSearchParams({
    client_id: clientId,
    limit: "180",
    lang: lang || "en",
  });
  const res = await authFetch(`${API_URL}/history/insights?${params.toString()}`);
  if (!res.ok) throw await buildFetchError(res, "Could not load insights");
  const payload = await res.json();
  return normalizeInsightsPayload(payload);
};

export default function History() {
  const [history, setHistory] = useState([]);
  const [insights, setInsights] = useState(null);
  const [activePlanFeatures, setActivePlanFeatures] = useState([]);
  const [availablePlans, setAvailablePlans] = useState([]);
  const [currentPlanId, setCurrentPlanId] = useState("free");
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [clientTimezone, setClientTimezone] = useState("UTC");
  const [loading, setLoading] = useState(true);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [insightsError, setInsightsError] = useState("");
  const clientId = useClientId();
  const { t, lang } = useLanguage();

  const planLabelForId = (planId) => {
    const normalized = normalizePlanId(planId);
    if (normalized === "free" || normalized === "starter" || normalized === "premium") return t(normalized);
    if (normalized === "white_label") return t("plan_white_label");
    return normalized.replace(/_/g, " ");
  };

  const hasAllPlanFeatures = (featureKeys) =>
    (Array.isArray(featureKeys) ? featureKeys : [featureKeys])
      .map((featureKey) => normalizeFeature(featureKey))
      .filter(Boolean)
      .every((featureKey) => activePlanFeatures.includes(featureKey));

  const getFeatureGate = (featureKeys, fallbackPlanId = "premium") => {
    const normalizedKeys = (Array.isArray(featureKeys) ? featureKeys : [featureKeys])
      .map((featureKey) => normalizeFeature(featureKey))
      .filter(Boolean);
    const suggestedPlanId =
      minPlanForFeatures(availablePlans, normalizedKeys) || normalizePlanId(fallbackPlanId);

    return {
      allowed: hasAllPlanFeatures(normalizedKeys),
      requiredPlanId: suggestedPlanId,
      requiredPlanLabel: planLabelForId(suggestedPlanId),
    };
  };

  const buildLockedMessage = (planLabel) =>
    `${t("current_plan_unavailable")} ${t("available_from")} ${planLabel}.`;

  const conversationInsightsGate = getFeatureGate("conversation_insights", "premium");
  const currentPlanLabel = planLabelForId(currentPlanId);

  useEffect(() => {
    let isMounted = true;

    const fetchPageData = async () => {
      if (!clientId) return;

      setLoading(true);
      setInsightsLoading(true);
      setHistoryError("");
      setInsightsError("");

      try {
        const [historyResult, timezoneResult, entitlementsResult] = await Promise.allSettled([
          loadHistory(clientId),
          loadProfileTimezone(clientId),
          loadEntitlements(clientId),
        ]);

        if (historyResult.status !== "fulfilled") {
          throw historyResult.reason;
        }

        if (!isMounted) return;

        setHistory(Array.isArray(historyResult.value) ? historyResult.value : []);
        setClientTimezone(
          timezoneResult.status === "fulfilled" ? timezoneResult.value || "UTC" : "UTC"
        );
        if (entitlementsResult.status === "fulfilled") {
          setCurrentPlanId(entitlementsResult.value.currentPlanId || "free");
          setActivePlanFeatures(
            Array.isArray(entitlementsResult.value.activePlanFeatures)
              ? entitlementsResult.value.activePlanFeatures
              : []
          );
          setAvailablePlans(
            Array.isArray(entitlementsResult.value.availablePlans)
              ? entitlementsResult.value.availablePlans
              : []
          );
        } else {
          setCurrentPlanId("free");
          setActivePlanFeatures([]);
          setAvailablePlans([]);
        }

        const entitlements =
          entitlementsResult.status === "fulfilled"
            ? entitlementsResult.value
            : { activePlanFeatures: [], availablePlans: [], currentPlanId: "free" };
        const canUseInsights = Array.isArray(entitlements.activePlanFeatures)
          && entitlements.activePlanFeatures.includes("conversation_insights");

        if (!canUseInsights) {
          setInsights(null);
          setInsightsError("");
        } else {
          try {
            const insightsPayload = await loadInsights(clientId, lang);
            if (!isMounted) return;
            setInsights(insightsPayload);
            setInsightsError("");
          } catch (error) {
            if (!isMounted) return;
            setInsights(null);
            setInsightsError(error?.message || "Could not load insights");
          }
        }
      } catch (error) {
        if (!isMounted) return;
        console.error("Error loading history inbox:", error);
        setHistory([]);
        setInsights(null);
        setActivePlanFeatures([]);
        setAvailablePlans([]);
        setCurrentPlanId("free");
        setClientTimezone("UTC");
        setHistoryError(error?.message || "Could not load history");
      } finally {
        if (!isMounted) return;
        setLoading(false);
        setInsightsLoading(false);
      }
    };

    fetchPageData();

    return () => {
      isMounted = false;
    };
  }, [clientId, lang]);

  const refreshInsights = async () => {
    if (!clientId || !conversationInsightsGate.allowed) return;
    setInsightsLoading(true);
    setInsightsError("");

    try {
      const payload = await loadInsights(clientId, lang);
      setInsights(payload);
    } catch (error) {
      console.error("Error refreshing history insights:", error);
      setInsightsError(error?.message || "Could not load insights");
    } finally {
      setInsightsLoading(false);
    }
  };

  const threads = useMemo(() => {
    const grouped = history.reduce((accumulator, message) => {
      const sessionId = message?.session_id || "default";
      if (!accumulator[sessionId]) accumulator[sessionId] = [];
      accumulator[sessionId].push(message);
      return accumulator;
    }, {});

    return Object.entries(grouped)
      .map(([sessionId, messages]) => {
        const orderedMessages = [...messages].sort(
          (a, b) => toTimestamp(a?.created_at || a?.timestamp) - toTimestamp(b?.created_at || b?.timestamp)
        );
        const lastMessage = orderedMessages[orderedMessages.length - 1] || {};
        const lastDate = new Date(lastMessage?.created_at || lastMessage?.timestamp || 0);
        const channel = lastMessage?.channel || orderedMessages[0]?.channel || "chat";
        return {
          sessionId,
          title: buildSessionLabel(sessionId, t),
          shortId: String(sessionId || "default").slice(0, 8),
          messages: orderedMessages,
          messageCount: orderedMessages.length,
          waitingOnReply: isUserMessage(lastMessage),
          channel,
          lastMessage,
          lastDate,
          lastPreview: previewText(lastMessage?.content),
        };
      })
      .sort((a, b) => toTimestamp(b.lastDate) - toTimestamp(a.lastDate));
  }, [history, t]);

  useEffect(() => {
    if (!threads.length) {
      setSelectedSessionId(null);
      return;
    }

    const stillExists = threads.some((thread) => thread.sessionId === selectedSessionId);
    if (!selectedSessionId || !stillExists) {
      setSelectedSessionId(threads[0].sessionId);
    }
  }, [threads, selectedSessionId]);

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.sessionId === selectedSessionId) || null,
    [threads, selectedSessionId]
  );

  const timelineItems = useMemo(() => {
    if (!selectedThread) return [];

    const items = [];
    let previousDayKey = "";

    for (const [index, message] of selectedThread.messages.entries()) {
      const rawDate = message?.created_at || message?.timestamp;
      const dayKey = new Date(rawDate || 0).toLocaleDateString("en-CA", { timeZone: clientTimezone });
      if (dayKey !== previousDayKey) {
        items.push({
          type: "divider",
          id: `divider-${dayKey}-${index}`,
          label: new Date(rawDate || 0).toLocaleDateString(undefined, {
            timeZone: clientTimezone,
            weekday: "short",
            month: "short",
            day: "numeric",
          }),
        });
        previousDayKey = dayKey;
      }

      items.push({
        type: "message",
        id: `${rawDate || index}-${index}`,
        message,
      });
    }

    return items;
  }, [selectedThread, clientTimezone]);

  const fmtDateTime = (value, options) => {
    if (!value) return "";
    try {
      const dateValue = value instanceof Date ? value : new Date(value);
      if (Number.isNaN(dateValue.getTime())) return String(value);
      return dateValue.toLocaleString(undefined, {
        timeZone: clientTimezone,
        ...(options || {}),
      });
    } catch {
      return String(value);
    }
  };

  const messageCounters = useMemo(() => {
    const toTimezoneDate = (value) => {
      const dateValue = value instanceof Date ? value : new Date(value);
      if (Number.isNaN(dateValue.getTime())) return null;
      return new Date(
        dateValue.toLocaleString("en-US", {
          timeZone: clientTimezone,
        })
      );
    };

    const nowInTimezone = toTimezoneDate(new Date()) || new Date();
    const startOfDay = new Date(nowInTimezone);
    startOfDay.setHours(0, 0, 0, 0);

    const startOfWeek = new Date(startOfDay);
    const dayIndex = startOfWeek.getDay();
    const diffToMonday = (dayIndex + 6) % 7;
    startOfWeek.setDate(startOfWeek.getDate() - diffToMonday);

    const startOfMonth = new Date(startOfDay);
    startOfMonth.setDate(1);

    let day = 0;
    let week = 0;
    let month = 0;

    for (const message of history) {
      const messageDate = toTimezoneDate(message?.created_at || message?.timestamp);
      if (!messageDate) continue;
      if (messageDate >= startOfMonth) month += 1;
      if (messageDate >= startOfWeek) week += 1;
      if (messageDate >= startOfDay) day += 1;
    }

    return {
      total: history.length,
      month,
      week,
      day,
    };
  }, [history, clientTimezone]);

  if (loading) {
    return (
      <div className="ia-page">
        <div className="ia-loader">
          <div className="ia-spinner" />
          <p style={{ color: "#274472", marginTop: "1rem" }}>
            {t("loading_history") || "Loading history..."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="ia-page">
      <div className="ia-shell ia-history-shell">
        <div className="ia-history-head">
          <div>
            <h2 className="ia-history-title">{t("message_history") || "Message History"}</h2>
            <p className="ia-history-subtitle">
              {t("history_inbox_subtitle") ||
                "Chat-style view of recent conversations with automatic insights."}
            </p>
          </div>
          <div className="ia-history-head-meta">
            <span className="ia-history-counter">
              {t("timezone") || "Timezone"}: {clientTimezone}
            </span>
          </div>
        </div>

        <div className="ia-history-counter-row">
          <span className="ia-history-counter">
            {t("messages") || "Messages"} · Total: {messageCounters.total}
          </span>
          <span className="ia-history-counter">
            {t("messages") || "Messages"} · {t("month") || "Month"}: {messageCounters.month}
          </span>
          <span className="ia-history-counter">
            {t("messages") || "Messages"} · {t("week") || "Week"}: {messageCounters.week}
          </span>
          <span className="ia-history-counter">
            {t("messages") || "Messages"} · {t("day") || "Day"}: {messageCounters.day}
          </span>
        </div>

        {historyError ? <p className="ia-history-error">{historyError}</p> : null}

        {!threads.length ? (
          <p className="ia-history-empty">{t("no_messages_yet") || "No messages yet."}</p>
        ) : (
          <div className="ia-history-grid">
            <aside className="ia-history-pane ia-history-pane-left">
              <div className="ia-history-pane-header">
                <div>
                  <h3 className="ia-history-pane-title">
                    {t("history_conversations") || "Conversations"}
                  </h3>
                  <p className="ia-history-pane-copy">
                    {threads.length} {t("history_conversations") || "Conversations"}
                  </p>
                </div>
              </div>

              <div className="ia-history-thread-list">
                {threads.map((thread) => {
                  const channel = channelBadge(thread.channel);
                  const isActive = thread.sessionId === selectedSessionId;
                  return (
                    <button
                      type="button"
                      key={thread.sessionId}
                      className={`ia-history-thread-card ${isActive ? "is-active" : ""}`}
                      onClick={() => setSelectedSessionId(thread.sessionId)}
                    >
                      <div className="ia-history-thread-card-top">
                        <div className="ia-history-thread-avatar">{thread.shortId.slice(0, 2).toUpperCase()}</div>
                        <div className="ia-history-thread-main">
                          <div className="ia-history-thread-row">
                            <strong className="ia-history-thread-name ia-break-anywhere">
                              {thread.title}
                            </strong>
                            {thread.waitingOnReply ? (
                              <span className="ia-history-thread-status">
                                {t("history_customer_waiting") || "Customer waiting for reply"}
                              </span>
                            ) : null}
                          </div>
                          <div className="ia-history-thread-meta">
                            <span>{`${channel.emoji} ${channel.label}`}</span>
                            <span>
                              {thread.messageCount} {t("history_messages_label") || "messages"}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="ia-history-thread-preview ia-break-anywhere">
                        {thread.lastPreview}
                      </div>

                      <div className="ia-history-thread-footer">
                        <span>
                          {t("last_message") || "Last message"}:{" "}
                          {fmtDateTime(thread.lastDate, {
                            month: "short",
                            day: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </aside>

            <section className="ia-history-pane ia-history-pane-center">
              {selectedThread ? (
                <>
                  <div className="ia-history-chat-header">
                    <div>
                      <div className="ia-history-thread-row">
                        <h3 className="ia-history-chat-title ia-break-anywhere">{selectedThread.title}</h3>
                        {selectedThread.waitingOnReply ? (
                          <span className="ia-history-thread-status">
                            {t("history_customer_waiting") || "Customer waiting for reply"}
                          </span>
                        ) : null}
                      </div>
                      <div className="ia-history-chat-meta ia-break-anywhere">
                        <span>
                          {t("history_thread_identity") || "Session ID"}: {selectedThread.sessionId}
                        </span>
                        <span>
                          {t("channel") || "Channel"}: {channelBadge(selectedThread.channel).label}
                        </span>
                        <span>
                          {t("messages") || "Messages"}: {selectedThread.messageCount}
                        </span>
                        <span>
                          {t("last_message") || "Last message"}: {fmtDateTime(selectedThread.lastDate)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="ia-history-chat-stream">
                    {timelineItems.map((item) => {
                      if (item.type === "divider") {
                        return (
                          <div key={item.id} className="ia-history-day-divider">
                            <span>{item.label}</span>
                          </div>
                        );
                      }

                      const message = item.message;
                      const userMessage = isUserMessage(message);
                      return (
                        <div
                          key={item.id}
                          className={`ia-history-bubble-row ${userMessage ? "is-user" : "is-assistant"}`}
                        >
                          <div className={`ia-history-bubble ${userMessage ? "is-user" : "is-assistant"}`}>
                            <div className="ia-history-bubble-meta ia-break-anywhere">
                              <span>
                                {userMessage
                                  ? t("history_customer_label") || "Customer"
                                  : t("history_ai_label") || "Assistant"}
                              </span>
                              <span>
                                {fmtDateTime(message?.created_at || message?.timestamp, {
                                  hour: "numeric",
                                  minute: "2-digit",
                                })}
                              </span>
                            </div>
                            <div className="ia-history-bubble-body ia-break-anywhere">
                              {message?.content || "(empty message)"}
                            </div>
                            <div className="ia-history-bubble-submeta ia-break-anywhere">
                              {message?.channel ? channelBadge(message.channel).label : channelBadge(selectedThread.channel).label}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : (
                <div className="ia-history-empty-panel">
                  {t("history_empty_thread") || "Select a conversation to view its details."}
                </div>
              )}
            </section>

            <aside className="ia-history-pane ia-history-pane-right">
              <div className="ia-history-pane-header ia-history-pane-header-right">
                <div>
                  <h3 className="ia-history-pane-title">{t("history_insights") || "Insights"}</h3>
                  <p className="ia-history-pane-copy">
                    {t("history_insights_hint") ||
                      "Summary and insights generated from recent conversation history."}
                  </p>
                </div>
                <button
                  type="button"
                  className="ia-button ia-button-ghost ia-history-refresh"
                  onClick={refreshInsights}
                  disabled={insightsLoading || !conversationInsightsGate.allowed}
                >
                  {!conversationInsightsGate.allowed
                    ? `${t("available_from")} ${conversationInsightsGate.requiredPlanLabel}`
                    : insightsLoading
                    ? t("loading") || "Loading..."
                    : t("history_refresh_insights") || "Refresh insights"}
                </button>
              </div>

              {insightsError ? <p className="ia-history-error">{insightsError}</p> : null}

              <div className="ia-history-insights-scroll">
                {!conversationInsightsGate.allowed ? (
                  <div className="ia-history-empty-panel">
                    <div>
                      <strong style={{ color: "#18304F", display: "block", marginBottom: "0.55rem" }}>
                        {t("history_insights_locked_title") || "Insights available on Premium"}
                      </strong>
                      <p className="ia-history-muted" style={{ marginBottom: "0.6rem" }}>
                        {t("history_insights_locked_copy") ||
                          "Analyze frequent questions, dominant topics, and customer friction with AI."}
                      </p>
                      <p className="ia-history-muted">
                        {buildLockedMessage(conversationInsightsGate.requiredPlanLabel)}
                      </p>
                      <p className="ia-history-muted" style={{ marginTop: "0.45rem" }}>
                        {(t("your_current_plan") || "Your current plan")}: {currentPlanLabel}
                      </p>
                    </div>
                  </div>
                ) : insights ? (
                  <>
                    <div className="ia-history-insight-meta">
                      <span
                        className={`ia-history-provider-pill ${
                          insights.provider === "openai" ? "is-ai" : "is-heuristic"
                        }`}
                      >
                        {insights.provider === "openai"
                          ? t("history_ai_provider") || "AI analyzed"
                          : t("history_heuristic_provider") || "Automatic summary"}
                      </span>
                      {insights.generated_at ? (
                        <span className="ia-history-generated-at">
                          {t("history_generated_at") || "Generated"}: {fmtDateTime(insights.generated_at)}
                        </span>
                      ) : null}
                    </div>

                    <div className="ia-history-stat-grid">
                      <div className="ia-history-stat-card">
                        <span className="ia-history-stat-label">
                          {t("history_conversation_count") || "Conversations analyzed"}
                        </span>
                        <strong>{insights?.stats?.conversation_count || threads.length}</strong>
                      </div>
                      <div className="ia-history-stat-card">
                        <span className="ia-history-stat-label">
                          {t("history_average_messages") || "Average per conversation"}
                        </span>
                        <strong>{insights?.stats?.avg_messages_per_conversation || 0}</strong>
                      </div>
                      <div className="ia-history-stat-card">
                        <span className="ia-history-stat-label">{t("messages") || "Messages"}</span>
                        <strong>{insights?.stats?.message_count || history.length}</strong>
                      </div>
                    </div>

                    <section className="ia-history-insight-card">
                      <h4 className="ia-history-insight-title">{t("history_summary") || "Summary"}</h4>
                      <p className="ia-history-insight-copy">
                        {insights.summary || t("history_no_insights") || "There is not enough history yet."}
                      </p>
                    </section>

                    <section className="ia-history-insight-card">
                      <h4 className="ia-history-insight-title">
                        {t("history_active_channels") || "Active channels"}
                      </h4>
                      <div className="ia-history-chip-row">
                        {(insights?.stats?.active_channels || []).length ? (
                          insights.stats.active_channels.map((item) => {
                            const channel = channelBadge(item.channel);
                            return (
                              <span key={`${item.channel}-${item.count}`} className="ia-history-chip">
                                {channel.emoji} {channel.label} · {item.count}
                              </span>
                            );
                          })
                        ) : (
                          <span className="ia-history-muted">{t("history_no_insights") || "No insights yet."}</span>
                        )}
                      </div>
                    </section>

                    <section className="ia-history-insight-card">
                      <h4 className="ia-history-insight-title">{t("history_faq") || "Frequent questions"}</h4>
                      {(insights?.faq || []).length ? (
                        <ul className="ia-history-insight-list">
                          {insights.faq.map((item, index) => (
                            <li key={`${item.question}-${index}`} className="ia-history-insight-item">
                              <strong className="ia-break-anywhere">{item.question}</strong>
                              <span>{item.mentions}x</span>
                              {item.note ? (
                                <p className="ia-history-insight-note ia-break-anywhere">{item.note}</p>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="ia-history-muted">
                          {t("history_no_faq") || "No clear repeated questions yet."}
                        </p>
                      )}
                    </section>

                    <section className="ia-history-insight-card">
                      <h4 className="ia-history-insight-title">{t("history_top_topics") || "Top topics"}</h4>
                      {(insights?.top_topics || []).length ? (
                        <ul className="ia-history-insight-list">
                          {insights.top_topics.map((item, index) => (
                            <li key={`${item.topic}-${index}`} className="ia-history-insight-item">
                              <strong className="ia-break-anywhere">{item.topic}</strong>
                              <span>{item.mentions}x</span>
                              {item.note ? (
                                <p className="ia-history-insight-note ia-break-anywhere">{item.note}</p>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="ia-history-muted">
                          {t("history_no_topics") || "No dominant topics detected yet."}
                        </p>
                      )}
                    </section>

                    <section className="ia-history-insight-card">
                      <h4 className="ia-history-insight-title">
                        {t("history_customer_goals") || "What customers want"}
                      </h4>
                      {(insights?.customer_goals || []).length ? (
                        <ul className="ia-history-bullet-list">
                          {insights.customer_goals.map((item, index) => (
                            <li key={`${item}-${index}`} className="ia-break-anywhere">
                              {item}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="ia-history-muted">
                          {t("history_no_insights") || "There is not enough history yet to show insights."}
                        </p>
                      )}
                    </section>

                    <section className="ia-history-insight-card">
                      <h4 className="ia-history-insight-title">
                        {t("history_friction_points") || "Friction points"}
                      </h4>
                      {(insights?.friction_points || []).length ? (
                        <ul className="ia-history-bullet-list">
                          {insights.friction_points.map((item, index) => (
                            <li key={`${item}-${index}`} className="ia-break-anywhere">
                              {item}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="ia-history-muted">
                          {t("history_no_insights") || "There is not enough history yet to show insights."}
                        </p>
                      )}
                    </section>

                    <section className="ia-history-insight-card">
                      <h4 className="ia-history-insight-title">
                        {t("history_recommendations") || "Recommendations"}
                      </h4>
                      {(insights?.recommendations || []).length ? (
                        <ul className="ia-history-bullet-list">
                          {insights.recommendations.map((item, index) => (
                            <li key={`${item}-${index}`} className="ia-break-anywhere">
                              {item}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="ia-history-muted">
                          {t("history_no_recommendations") || "No recommendations for now."}
                        </p>
                      )}
                    </section>

                    <section className="ia-history-insight-card">
                      <h4 className="ia-history-insight-title">
                        {t("history_unresolved_sessions") || "Conversations to review"}
                      </h4>
                      {(insights?.unresolved_sessions || []).length ? (
                        <ul className="ia-history-insight-list">
                          {insights.unresolved_sessions.map((item, index) => (
                            <li key={`${item.session_id}-${index}`} className="ia-history-insight-item">
                              <strong className="ia-break-anywhere">
                                {buildSessionLabel(item.session_id, t)}
                              </strong>
                              <span>{fmtDateTime(item.last_message_at)}</span>
                              <p className="ia-history-insight-note ia-break-anywhere">{item.reason}</p>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="ia-history-muted">
                          {t("history_no_unresolved") || "No open conversations need review right now."}
                        </p>
                      )}
                    </section>
                  </>
                ) : (
                  <div className="ia-history-empty-panel">
                    {t("history_no_insights") || "There is not enough history yet to show insights."}
                  </div>
                )}
              </div>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
