import { useEffect, useState } from "react";
import axios from "axios";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";

export default function History() {
  const [history, setHistory] = useState([]);
  const [expandedSession, setExpandedSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const clientId = useClientId();
  const { t } = useLanguage();

  useEffect(() => {
    const fetchHistory = async () => {
      if (!clientId) return;
      setLoading(true);
      try {
        const res = await axios.get(
          `${import.meta.env.VITE_API_URL}/history?client_id=${clientId}`
        );
        console.log("📦 Historial recibido:", res.data);

        // Normalización robusta (maneja varias estructuras)
        let normalized = [];
        const d = res.data;
        if (Array.isArray(d?.history)) normalized = d.history;
        else if (Array.isArray(d?.history?.history)) normalized = d.history.history;
        else if (Array.isArray(d?.data)) normalized = d.data;
        else console.warn("⚠️ Estructura de historial desconocida:", d);

        setHistory(normalized);
        console.log("✅ Historial normalizado:", normalized);
      } catch (err) {
        console.error("❌ Error cargando historial:", err);
        setHistory([]);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [clientId]);

  // ✅ Agrupar mensajes incluso si no hay session_id
  const groupedBySession = history.reduce((acc, msg) => {
    const sid = msg.session_id || "default"; // usa "default" si no tiene ID
    if (!acc[sid]) acc[sid] = [];
    acc[sid].push(msg);
    return acc;
  }, {});

  const toggleSession = (sessionId) => {
    setExpandedSession(expandedSession === sessionId ? null : sessionId);
  };

  // 🔍 Abrir automáticamente la sesión más reciente
  useEffect(() => {
    const sessionIds = Object.keys(groupedBySession);
    if (sessionIds.length > 0 && !expandedSession) {
      setExpandedSession(sessionIds[sessionIds.length - 1]);
    }
  }, [history]);

  return (
    <div
      style={{
        backgroundColor: "#0f1c2e",
        minHeight: "100vh",
        padding: "2rem",
        color: "white",
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <div
        style={{
          maxWidth: "900px",
          width: "100%",
          backgroundColor: "#1b2a41",
          padding: "2rem",
          borderRadius: "16px",
          boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
          border: "1px solid #274472",
        }}
      >
        <h2
          style={{
            fontSize: "1.8rem",
            fontWeight: "bold",
            color: "#f5a623",
            marginBottom: "1.5rem",
          }}
        >
          {t("message_history") || "Message History"}
        </h2>

        {loading ? (
          <p style={{ color: "#ededed" }}>
            {t("loading_history") || "Loading history..."}
          </p>
        ) : Object.keys(groupedBySession).length === 0 ? (
          <p style={{ color: "#ededed" }}>
            {t("no_messages_yet") || "No messages yet."}
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {Object.entries(groupedBySession).map(([sessionId, messages]) => {
              const first = messages[0];
              const last = messages[messages.length - 1];
              const lastDate = new Date(last.created_at).toLocaleString();
              const channel = first.channel || "chat";

              return (
                <div
                  key={sessionId}
                  style={{
                    backgroundColor: "#ededed",
                    color: "#1b2a41",
                    borderRadius: "12px",
                    boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                    border: "1px solid #a3d9b1",
                    overflow: "hidden",
                  }}
                >
                  {/* Header de la sesión */}
                  <div
                    onClick={() => toggleSession(sessionId)}
                    style={{
                      cursor: "pointer",
                      padding: "1rem 1.2rem",
                      backgroundColor: "#a3d9b1",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      transition: "background 0.2s ease",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#b8e3c4")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "#a3d9b1")}
                  >
                    <div>
                      <strong style={{ color: "#0f1c2e" }}>
                        {sessionId === "default"
                          ? "Main session"
                          : `Session: ${sessionId.slice(0, 8)}...`}
                      </strong>
                      <div style={{ fontSize: "0.85rem", color: "#274472" }}>
                        Channel: {channel} | Messages: {messages.length}
                      </div>
                    </div>
                    <div style={{ color: "#274472", fontSize: "0.85rem" }}>
                      {expandedSession === sessionId ? "▲ Collapse" : "▼ Expand"}
                    </div>
                  </div>

                  {/* Mensajes */}
                  {expandedSession === sessionId && (
                    <div
                      style={{
                        padding: "1rem",
                        backgroundColor: "#f9fafb",
                        borderTop: "1px solid #a3d9b1",
                      }}
                    >
                      {messages
                        .sort(
                          (a, b) => new Date(a.created_at) - new Date(b.created_at)
                        )
                        .map((msg, index) => (
                          <div
                            key={`${msg.created_at}-${index}`} // clave única garantizada
                            style={{
                              marginBottom: "0.8rem",
                              backgroundColor:
                                msg.role === "user" ? "#ffffff" : "#e6eefc",
                              borderLeft: `4px solid ${
                                msg.role === "user" ? "#a3d9b1" : "#4a90e2"
                              }`,
                              padding: "0.8rem 1rem",
                              borderRadius: "8px",
                            }}
                          >
                            <div
                              style={{
                                fontSize: "0.8rem",
                                color: "#64748b",
                                marginBottom: "4px",
                              }}
                            >
                              {new Date(msg.created_at).toLocaleString()} | {msg.role}
                            </div>
                            <div
                              style={{
                                color: "#1b2a41",
                                whiteSpace: "pre-wrap",
                                fontSize: "0.95rem",
                              }}
                            >
                              {msg.content || "(empty message)"}
                            </div>
                          </div>
                        ))}
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "#4a90e2",
                          marginTop: "0.5rem",
                          textAlign: "right",
                        }}
                      >
                        Last message: {lastDate}
                      </div>
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
