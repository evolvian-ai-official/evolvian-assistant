// src/features/history/History.jsx
import { useEffect, useMemo, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";

export default function History() {
  const [history, setHistory] = useState([]);
  const [expandedSession, setExpandedSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const clientId = useClientId();
  const { t } = useLanguage();

  // 🌀 Inject Evolvian spinner keyframes only once
  useEffect(() => {
    if (
      typeof document !== "undefined" &&
      !document.getElementById("spin-keyframes")
    ) {
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
  }, []);

  // 📥 Cargar historial
  useEffect(() => {
    const fetchHistory = async () => {
      if (!clientId) return;
      setLoading(true);
      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/history?client_id=${clientId}`
        );
        const payload = await res.json();
        // Normalización robusta
        let normalized = [];
        const d = payload;
        if (Array.isArray(d?.history)) normalized = d.history;
        else if (Array.isArray(d?.history?.history)) normalized = d.history.history;
        else if (Array.isArray(d?.data)) normalized = d.data;
        else console.warn("⚠️ Estructura de historial desconocida:", d);

        setHistory(normalized);
      } catch (err) {
        console.error("❌ Error cargando historial:", err);
        setHistory([]);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [clientId]);

  // 🧮 Agrupar por sesión (incluyendo fallback "default")
  const groupedBySession = useMemo(() => {
    return history.reduce((acc, msg) => {
      const sid = msg.session_id || "default";
      if (!acc[sid]) acc[sid] = [];
      acc[sid].push(msg);
      return acc;
    }, {});
  }, [history]);

  // 📅 Ordenar sesiones por última actividad (más reciente al final)
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

  // 🔍 Abrir automáticamente la sesión más reciente
  useEffect(() => {
    if (sortedSessions.length > 0 && !expandedSession) {
      setExpandedSession(sortedSessions[sortedSessions.length - 1].sessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortedSessions.length]);

  const toggleSession = (sessionId) => {
    setExpandedSession(expandedSession === sessionId ? null : sessionId);
  };

  // 🧰 Utilidades UI
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
      return new Date(v).toLocaleString();
    } catch {
      return String(v);
    }
  };

  // 🌀 Loader (branding light)
  if (loading) {
    return (
      <div style={loaderContainer}>
        <div style={spinner}></div>
        <p style={{ color: "#274472", marginTop: "1rem" }}>
          {t("loading_history") || "Loading history..."}
        </p>
      </div>
    );
  }

  const noSessions = sortedSessions.length === 0;

  return (
    <div style={pageContainer}>
      <div style={wrap}>
        <h2 style={title}>
          {t("message_history") || "Message History"}
        </h2>

        {noSessions ? (
          <p style={emptyText}>
            {t("no_messages_yet") || "No messages yet."}
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {sortedSessions.map(({ sessionId, messages, lastDate }) => {
              const first = messages[0] || {};
              const channel = first.channel || "chat";
              const expanded = expandedSession === sessionId;

              return (
                <div
                  key={sessionId}
                  style={sessionCard}
                >
                  {/* Header de sesión */}
                  <button
                    onClick={() => toggleSession(sessionId)}
                    style={{
                      ...sessionHeader,
                      background: expanded ? "#B8E3C4" : "#A3D9B1",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#B8E3C4")}
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = expanded ? "#B8E3C4" : "#A3D9B1")
                    }
                    aria-expanded={expanded}
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, textAlign: "left" }}>
                      <strong style={{ color: "#0f1c2e" }}>
                        {sessionId === "default"
                          ? (t("main_session") || "Main session")
                          : `${t("session") || "Session"}: ${sessionId.slice(0, 8)}...`}
                      </strong>
                      <div style={{ fontSize: "0.85rem", color: "#274472" }}>
                        {t("channel") || "Channel"}: {channelBadge(channel)} · {t("messages") || "Messages"}: {messages.length}
                      </div>
                    </div>
                    <div style={{ color: "#274472", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ opacity: 0.8 }}>
                        {t("last_message") || "Last message"}: {fmtDateTime(lastDate)}
                      </span>
                      <span aria-hidden="true">{expanded ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {/* Mensajes */}
                  {expanded && (
                    <div style={messagesWrap}>
                      {messages
                        .slice()
                        .sort((a, b) => new Date(a.created_at || a.timestamp || 0) - new Date(b.created_at || b.timestamp || 0))
                        .map((msg, index) => {
                          const isUser = (msg.role || "").toLowerCase() === "user";
                          return (
                            <div
                              key={`${msg.created_at || msg.timestamp || index}-${index}`}
                              style={{
                                ...messageItem,
                                background: isUser ? "#FFFFFF" : "#EAF3FC",
                                borderLeft: `4px solid ${isUser ? "#A3D9B1" : "#4A90E2"}`,
                              }}
                            >
                              <div style={messageMeta}>
                                {fmtDateTime(msg.created_at || msg.timestamp)} · {msg.role || "assistant"}
                                {msg.channel ? ` · ${channelBadge(msg.channel)}` : null}
                              </div>
                              <div style={messageBody}>
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

/* 🎨 Estilos — Evolvian Premium Light */
const pageContainer = {
  backgroundColor: "#FFFFFF",
  minHeight: "100vh",
  padding: "2rem",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
  display: "flex",
  justifyContent: "center",
};

const wrap = {
  maxWidth: 960,
  width: "100%",
};

const title = {
  fontSize: "1.8rem",
  fontWeight: 800,
  color: "#F5A623",
  marginBottom: "1.2rem",
};

const emptyText = {
  color: "#6B7280",
};

const sessionCard = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "12px",
  overflow: "hidden",
  boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
};

const sessionHeader = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  padding: "0.9rem 1.1rem",
  border: "none",
  cursor: "pointer",
};

const messagesWrap = {
  padding: "1rem",
  backgroundColor: "#F9FAFB",
  borderTop: "1px solid #A3D9B1",
};

const messageItem = {
  marginBottom: "0.8rem",
  padding: "0.85rem 1rem",
  borderRadius: "10px",
  border: "1px solid #EDEDED",
};

const messageMeta = {
  fontSize: "0.8rem",
  color: "#6B7280",
  marginBottom: 6,
};

const messageBody = {
  color: "#1F2937",
  whiteSpace: "pre-wrap",
  fontSize: "0.95rem",
  lineHeight: 1.5,
};

/* 🌀 Loader Styles (light) */
const loaderContainer = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#FFFFFF",
  minHeight: "100vh",
  color: "#274472",
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
