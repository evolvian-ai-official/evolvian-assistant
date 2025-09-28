// HIGH Este es el componente principal del widget Evolvian
import { useState, useRef, useEffect } from "react";
import { useLanguage } from "../contexts/LanguageContext";

export default function ChatWidget({
  clientId: propClientId,
  requireEmail = false,
  requirePhone = false,
  requireTerms = false,
  assistantName = "Assistant",
  showPoweredBy = true,
}) {
  const languageContext = useLanguage ? useLanguage() : null;
  const { t = (x) => x, lang = "es" } = languageContext || {};

  const [clientId, setClientId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [showConsentForm, setShowConsentForm] = useState(true);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [sending, setSending] = useState(false);
  const [thinkingDots, setThinkingDots] = useState("");

  const messagesEndRef = useRef(null);

  if (!lang) return null;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlClientId = params.get("public_client_id");
    if (propClientId) setClientId(propClientId);
    else if (urlClientId) setClientId(urlClientId);
    else console.error("❌ Client ID no encontrado ni en props ni en URL.");
  }, [propClientId]);

  useEffect(() => {
    if (!clientId) return;
    const consentKey = `evolvian_consent_${clientId}`;
    if (localStorage.getItem(consentKey)) setShowConsentForm(false);
  }, [clientId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    let interval;
    if (sending) {
      interval = setInterval(() => {
        setThinkingDots((prev) => (prev.length >= 3 ? "" : prev + "."));
      }, 400);
    } else {
      setThinkingDots("");
    }
    return () => clearInterval(interval);
  }, [sending]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const sendMessage = async () => {
    if (!input.trim() || !clientId) return;

    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMsg = { from: "user", text: input, timestamp: now };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    try {
      const apiUrl =
        window.location.hostname === "localhost"
          ? "http://localhost:8001"
          : "https://evolvian-assistant.onrender.com";

      const res = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public_client_id: clientId, message: input }),
      });

      const data = await res.json();

      const botMsg = {
        from: "bot",
        text: data.answer || "(respuesta vacía)",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error("❌ Error al enviar mensaje:", err);
      setMessages((prev) => [
        ...prev,
        {
          from: "bot",
          text: t("error_response"),
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleConsentSubmit = () => {
    if ((requireEmail && !email) || (requirePhone && !phone) || (requireTerms && !acceptedTerms)) {
      alert(t("consent_required_fields"));
      return;
    }

    const consentKey = `evolvian_consent_${clientId}`;
    localStorage.setItem(consentKey, "1");
    setShowConsentForm(false);
  };

  if (!clientId) {
    return <div style={{ padding: "2rem", textAlign: "center" }}>{t("loading_assistant")}</div>;
  }

  if (showConsentForm && (requireEmail || requirePhone || requireTerms)) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.header}><strong>💬 {assistantName}</strong></div>
        <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
          {requireEmail && (
            <input type="email" placeholder={t("enter_email")} value={email} onChange={(e) => setEmail(e.target.value)} style={styles.input} />
          )}
          {requirePhone && (
            <input type="tel" placeholder={t("enter_phone")} value={phone} onChange={(e) => setPhone(e.target.value)} style={styles.input} />
          )}
          {requireTerms && (
            <label style={{ fontSize: "0.8rem", color: "#555" }}>
              <input type="checkbox" checked={acceptedTerms} onChange={(e) => setAcceptedTerms(e.target.checked)} /> {t("accept_terms")} <a href="https://evolvian.app/terms" target="_blank" rel="noopener noreferrer">{t("terms_link")}</a>
            </label>
          )}
          <button onClick={handleConsentSubmit} style={styles.button}>{t("continue")}</button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.wrapper}>
      {/* Header fijo */}
      <div style={styles.header}>
        <img src="/logo-evolvian.svg" alt="Evolvian" style={{ height: "22px", marginRight: "0.5rem" }} />
        <strong style={{ fontSize: "1rem", color: "#fff" }}>{assistantName}</strong>
      </div>

      {/* Mensajes con scroll */}
      <div style={styles.messages}>
        {messages.map((msg, idx) => (
          <div key={idx} style={{ display: "flex", flexDirection: "column", alignItems: msg.from === "user" ? "flex-end" : "flex-start" }}>
            <div style={{ ...styles.message, ...(msg.from === "user" ? styles.userMessage : styles.botMessage) }}>
              {msg.text}
            </div>
            <span style={{ fontSize: "0.7rem", color: "#999", marginTop: "0.25rem" }}>
              {msg.timestamp}
            </span>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Bottom fijo con input y footer */}
      <div style={styles.bottomContainer}>
        <div style={styles.inputContainer}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("type_message")}
            style={styles.textarea}
            rows={2}
          />
          <button
            onClick={sendMessage}
            style={{ ...styles.button, opacity: sending ? 0.7 : 1 }}
            disabled={sending}
          >
            {sending ? `${t("thinking")}${thinkingDots}` : t("send")}
          </button>
        </div>

        {showPoweredBy && (
          <div style={styles.footer}>
            <span>Powered by Evolvian</span>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  wrapper: {
    width: "100%",
    height: "100%",         // 🔹 ocupa todo el alto disponible
    display: "flex",
    flexDirection: "column",
    backgroundColor: "#fff",
    borderRadius: "12px",
    overflow: "hidden",     // 🔹 evita fugas de scroll
    fontFamily: "'Inter', sans-serif",
  },

  header: {
    flexShrink: 0,          // 🔹 nunca se mueve
    height: "56px",
    backgroundColor: "#274472",
    borderBottom: "1px solid #ededed",
    display: "flex",
    alignItems: "center",
    padding: "0 1rem",
    color: "#fff",
    fontWeight: "600",
    fontSize: "1rem",
  },

  messages: {
    flex: 1,
    minHeight: "300px",
    overflowY: "auto",
    padding: "1rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
    backgroundColor: "#fafafa",
    fontSize: "0.95rem",
    lineHeight: "1.4",
    color: "#1b2a41",
  },

  bottomContainer: {
    flexShrink: 0,
    display: "flex",
    flexDirection: "column",
    backgroundColor: "#fff",
    borderTop: "1px solid #ededed",
    borderBottomLeftRadius: "12px",  // 🔹 esquinas inferiores
    borderBottomRightRadius: "12px",
  },

  inputContainer: {
    padding: "0.8rem",
    backgroundColor: "#fff",
    display: "flex",
    gap: "0.5rem",
  },

  textarea: {
    flex: 1,
    resize: "none",
    borderRadius: "10px",
    padding: "0.6rem 0.75rem",
    border: "1px solid #ccc",
    fontSize: "0.95rem",
    outline: "none",
    color: "#1b2a41",
    backgroundColor: "#fff",
    maxHeight: "120px",
    overflowY: "auto",
    fontFamily: "'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },

  button: {
    backgroundColor: "#4a90e2",
    color: "white",
    border: "none",
    padding: "0.6rem 1rem",
    borderRadius: "10px",
    fontWeight: "600",
    fontSize: "0.95rem",
    cursor: "pointer",
    transition: "background 0.2s",
    fontFamily: "'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },

  footer: {
    textAlign: "center",
    fontSize: "0.75rem",
    color: "#999",
    padding: "0.5rem",
    borderTop: "1px solid #f0f0f0",
    borderBottomLeftRadius: "12px",
    borderBottomRightRadius: "12px",
    fontFamily: "'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },

  message: {
    padding: "0.75rem 1rem",
    borderRadius: "18px",
    maxWidth: "75%",
    wordBreak: "break-word",
    whiteSpace: "pre-line",
    fontSize: "0.95rem",
    lineHeight: "1.4",
    boxShadow: "0 2px 6px rgba(0,0,0,0.08)",
    fontFamily: "'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },

  userMessage: {
    alignSelf: "flex-end",
    backgroundColor: "#a3d9b1",
    color: "#1b2a41",
  },

  botMessage: {
    alignSelf: "flex-start",
    backgroundColor: "#ededed",
    color: "#1b2a41",
  },

  input: {
    padding: "0.5rem",
    borderRadius: "8px",
    border: "1px solid #ccc",
    fontSize: "0.9rem",
    fontFamily: "'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },
};
