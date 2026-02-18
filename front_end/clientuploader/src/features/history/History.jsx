import { useEffect, useMemo, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

const normalizeTimezone = (tz) => {
  if (!tz || typeof tz !== "string") return "UTC";
  try {
    Intl.DateTimeFormat(undefined, { timeZone: tz });
    return tz;
  } catch {
    return "UTC";
  }
};

export default function History() {
  const [history, setHistory] = useState([]);
  const [expandedSession, setExpandedSession] = useState(null);
  const [clientTimezone, setClientTimezone] = useState("UTC");
  const [loading, setLoading] = useState(true);
  const clientId = useClientId();
  const { t } = useLanguage();

  useEffect(() => {
    const fetchHistory = async () => {
      if (!clientId) return;
      setLoading(true);
      try {
        const [historyRes, profileRes] = await Promise.all([
          authFetch(`${import.meta.env.VITE_API_URL}/history?client_id=${clientId}`),
          authFetch(`${import.meta.env.VITE_API_URL}/profile/${clientId}`),
        ]);

        const payload = await historyRes.json();
        let normalized = [];
        const d = payload;
        if (Array.isArray(d?.history)) normalized = d.history;
        else if (Array.isArray(d?.history?.history)) normalized = d.history.history;
        else if (Array.isArray(d?.data)) normalized = d.data;
        else console.warn("⚠️ Estructura de historial desconocida:", d);

        setHistory(normalized);

        if (profileRes.ok) {
          const profilePayload = await profileRes.json();
          setClientTimezone(normalizeTimezone(profilePayload?.timezone));
        } else {
          setClientTimezone("UTC");
        }
      } catch (err) {
        console.error("❌ Error cargando historial:", err);
        setHistory([]);
        setClientTimezone("UTC");
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [clientId]);

  const groupedBySession = useMemo(() => {
    return history.reduce((acc, msg) => {
      const sid = msg.session_id || "default";
      if (!acc[sid]) acc[sid] = [];
      acc[sid].push(msg);
      return acc;
    }, {});
  }, [history]);

  const sortedSessions = useMemo(() => {
    const entries = Object.entries(groupedBySession).map(([sessionId, messages]) => {
      const last = messages.reduce((latest, m) => {
        const d = new Date(m.created_at || m.timestamp || 0);
        return d > latest ? d : latest;
      }, new Date(0));
      return { sessionId, messages, lastDate: last };
    });
    entries.sort((a, b) => a.lastDate - b.lastDate);
    return entries;
  }, [groupedBySession]);

  useEffect(() => {
    if (sortedSessions.length > 0 && !expandedSession) {
      setExpandedSession(sortedSessions[sortedSessions.length - 1].sessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortedSessions.length]);

  const toggleSession = (sessionId) => {
    setExpandedSession(expandedSession === sessionId ? null : sessionId);
  };

  const channelBadge = (channel) => {
    const ch = (channel || "chat").toLowerCase();
    const map = {
      chat: { emoji: "💬", text: "Chat" },
      email: { emoji: "✉️", text: "Email" },
      gmail: { emoji: "✉️", text: "Email" },
      whatsapp: { emoji: "🟢", text: "WhatsApp" },
    };
    const item = map[ch] || map.chat;
    return `${item.emoji} ${item.text}`;
  };

  const fmtDateTime = (v) => {
    if (!v) return "";
    try {
      const dateValue = v instanceof Date ? v : new Date(v);
      if (Number.isNaN(dateValue.getTime())) return String(v);
      return dateValue.toLocaleString(undefined, {
        timeZone: clientTimezone,
        timeZoneName: "short",
      });
    } catch {
      return String(v);
    }
  };

  const messageCounters = useMemo(() => {
    const toTzDate = (value) => {
      const dateValue = value instanceof Date ? value : new Date(value);
      if (Number.isNaN(dateValue.getTime())) return null;
      return new Date(
        dateValue.toLocaleString("en-US", {
          timeZone: clientTimezone,
        })
      );
    };

    const nowTz = toTzDate(new Date()) || new Date();
    const startOfDay = new Date(nowTz);
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

    for (const msg of history) {
      const msgDate = toTzDate(msg.created_at || msg.timestamp);
      if (!msgDate) continue;

      if (msgDate >= startOfMonth) month += 1;
      if (msgDate >= startOfWeek) week += 1;
      if (msgDate >= startOfDay) day += 1;
    }

    return {
      total: history.length,
      month,
      week,
      day,
    };
  }, [history, clientTimezone]);

  const noSessions = sortedSessions.length === 0;

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
        <h2 className="ia-history-title">{t("message_history") || "Message History"}</h2>
        <p className="ia-history-timezone">
          {t("timezone") || "Timezone"}: {clientTimezone}
        </p>
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

        {noSessions ? (
          <p className="ia-history-empty">{t("no_messages_yet") || "No messages yet."}</p>
        ) : (
          <div className="ia-history-session-list">
            {sortedSessions.map(({ sessionId, messages, lastDate }) => {
              const first = messages[0] || {};
              const channel = first.channel || "chat";
              const expanded = expandedSession === sessionId;

              return (
                <div key={sessionId} className="ia-history-session-card">
                  <button
                    type="button"
                    onClick={() => toggleSession(sessionId)}
                    className={`ia-history-session-header ${expanded ? "is-open" : ""}`}
                    aria-expanded={expanded}
                  >
                    <div className="ia-history-session-main">
                      <strong className="ia-history-session-name ia-break-anywhere">
                        {sessionId === "default"
                          ? t("main_session") || "Main session"
                          : `${t("session") || "Session"}: ${sessionId.slice(0, 8)}...`}
                      </strong>
                      <div className="ia-history-session-sub ia-break-anywhere">
                        {t("channel") || "Channel"}: {channelBadge(channel)} · {t("messages") || "Messages"}: {messages.length}
                      </div>
                    </div>
                    <div className="ia-history-session-last ia-break-anywhere">
                      <span>
                        {t("last_message") || "Last message"}: {fmtDateTime(lastDate)}
                      </span>
                      <span aria-hidden="true">{expanded ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {expanded && (
                    <div className="ia-history-messages">
                      {messages
                        .slice()
                        .sort(
                          (a, b) =>
                            new Date(a.created_at || a.timestamp || 0) -
                            new Date(b.created_at || b.timestamp || 0)
                        )
                        .map((msg, index) => {
                          const isUser = (msg.role || "").toLowerCase() === "user";
                          return (
                            <div
                              key={`${msg.created_at || msg.timestamp || index}-${index}`}
                              className={`ia-history-message ${isUser ? "user" : ""}`}
                            >
                              <div className="ia-history-message-meta ia-break-anywhere">
                                {fmtDateTime(msg.created_at || msg.timestamp)} · {msg.role || "assistant"}
                                {msg.channel ? ` · ${channelBadge(msg.channel)}` : null}
                              </div>
                              <div className="ia-history-message-body ia-break-anywhere">
                                {msg.content || "(empty message)"}
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
