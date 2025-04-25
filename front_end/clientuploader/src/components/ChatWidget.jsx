import { useState, useRef, useEffect } from "react";

export default function ChatWidget({
  clientId,
  requireEmail = false,
  requirePhone = false,
  requireTerms = false,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [showTooltip, setShowTooltip] = useState(false);
  const [showConsentForm, setShowConsentForm] = useState(true);

  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    console.log("📦 Props recibidas:", { clientId, requireEmail, requirePhone, requireTerms });

    const consentKey = `evolvian_consent_${clientId}`;
    const saved = localStorage.getItem(consentKey);
    console.log("🔍 ¿Existe consentimiento previo en localStorage?", saved);

    if (saved) {
      console.log("✅ Consentimiento encontrado. Ocultando formulario.");
      setShowConsentForm(false);
    } else {
      console.log("🧾 No hay consentimiento previo. Mostrando formulario.");
    }
  }, [clientId]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg = { from: "user", text: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    console.log("💬 Enviando mensaje:", input);
    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, message: input }),
      });
      const data = await res.json();
      console.log("🤖 Respuesta del asistente:", data);
      const botMsg = { from: "bot", text: data.answer };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error("❌ Error al enviar mensaje:", err);
      setMessages((prev) => [
        ...prev,
        { from: "bot", text: "⚠️ Error al responder." },
      ]);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleConsentSubmit = async () => {
    if (requireEmail && !email) return alert("Por favor ingresa tu correo.");
    if (requirePhone && !phone) return alert("Por favor ingresa tu teléfono.");
    if (requireTerms && !acceptedTerms)
      return alert("Debes aceptar los Términos y Condiciones.");

    const consentAt = new Date().toISOString();

    const consentData = { email, phone, acceptedTerms, consentAt };
    console.log("📤 Guardando consentimiento en localStorage:", consentData);

    localStorage.setItem(
      `evolvian_consent_${clientId}`,
      JSON.stringify(consentData)
    );

    console.log("📨 Enviando consentimiento al backend...");
    try {
      const res = await fetch("http://localhost:8000/register_consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          email,
          phone,
          accepted_terms: acceptedTerms,
          consent_at: consentAt,
        }),
      });

      if (!res.ok) throw new Error("Error al registrar consentimiento");

      console.log("✅ Consentimiento registrado exitosamente");
      setShowConsentForm(false);
    } catch (err) {
      console.error("❌ Error al enviar consentimiento:", err);
      alert("Hubo un error al registrar tu consentimiento. Intenta nuevamente.");
    }
  };

  if (showConsentForm && (requireEmail || requirePhone || requireTerms)) {
    console.log("✅ Se debe mostrar el formulario de consentimiento");
    return (
      <div style={styles.wrapper}>
        <div style={styles.header}>
          <strong>💬 Asistente Evolvian</strong>
        </div>
        <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
          <p style={{ fontSize: "0.9rem", color: "#333" }}>Por favor proporciona tus datos para iniciar:</p>
          {requireEmail && (
            <input
              type="email"
              placeholder="Tu correo"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={styles.input}
            />
          )}
          {requirePhone && (
            <input
              type="tel"
              placeholder="Tu teléfono"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              style={styles.input}
            />
          )}
          {requireTerms && (
            <label style={{ fontSize: "0.8rem", color: "#555" }}>
              <input
                type="checkbox"
                checked={acceptedTerms}
                onChange={(e) => setAcceptedTerms(e.target.checked)}
              />{" "}
              Acepto los{" "}
              <a href="https://evolvian.app/terms" target="_blank" rel="noopener noreferrer">
                Términos y Condiciones
              </a>
            </label>
          )}
          <button onClick={handleConsentSubmit} style={styles.button}>
            Continuar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", width: "100%", position: "relative" }}>
          <img src="/logo-evolvian.svg" alt="Evolvian" style={{ height: "24px" }} />
          <strong style={{ fontSize: "1rem" }}>Asistente Evolvian</strong>
          <div
            style={{ marginLeft: "auto", position: "relative" }}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <span style={{ fontSize: "1.1rem", color: "#888", cursor: "pointer" }}>ℹ️</span>
            {showTooltip && (
              <div style={styles.tooltip}>
                Este asistente responde con base en documentos proporcionados.
                Puede no cubrir todos los casos.
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={styles.messages}>
        {messages.length === 0 && (
          <div style={styles.emptyState}>
            Escribe tu primer mensaje para iniciar la conversación.
          </div>
        )}
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              ...styles.message,
              ...(msg.from === "user" ? styles.userMessage : styles.botMessage),
            }}
          >
            {msg.text}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div style={styles.inputContainer}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe tu mensaje..."
          style={styles.textarea}
          rows={2}
        />
        <button onClick={sendMessage} style={styles.button}>
          Enviar
        </button>
        <p
          style={{
            fontSize: "0.72rem",
            color: "#888",
            marginTop: "0.5rem",
            textAlign: "center",
          }}
        >
          * Este asistente puede no responder con precisión en todos los casos.
          Usa criterio humano si es necesario.
        </p>
      </div>
    </div>
  );
}

const styles = {
  wrapper: {
    width: "100%",
    height: "100%",
    backgroundColor: "#ffffff",
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    padding: "1rem 1rem 0.8rem",
    borderBottom: "1px solid #ededed",
    color: "#274472",
    backgroundColor: "#f7f9fa",
    zIndex: 2,
  },
  tooltip: {
    position: "absolute",
    top: "130%",
    right: 0,
    width: "240px",
    padding: "0.6rem",
    backgroundColor: "#1b2a41",
    color: "#fff",
    fontSize: "0.75rem",
    borderRadius: "8px",
    boxShadow: "0 4px 8px rgba(0,0,0,0.2)",
    zIndex: 10,
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "1rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
    backgroundColor: "#fafafa",
  },
  emptyState: {
    color: "#999",
    fontSize: "0.9rem",
    textAlign: "center",
    fontStyle: "italic",
    marginTop: "0.5rem",
  },
  message: {
    padding: "0.75rem 1rem",
    borderRadius: "16px",
    maxWidth: "75%",
    wordBreak: "break-word",
    whiteSpace: "pre-line",
    fontSize: "0.95rem",
    lineHeight: "1.4",
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
  inputContainer: {
    borderTop: "1px solid #ededed",
    padding: "1rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
    backgroundColor: "#ffffff",
  },
  textarea: {
    width: "100%",
    resize: "none",
    borderRadius: "10px",
    padding: "0.6rem 0.75rem",
    border: "1px solid #ccc",
    fontSize: "0.95rem",
    fontFamily: "inherit",
    outline: "none",
    color: "#1b2a41",
    backgroundColor: "#ffffff",
  },
  input: {
    padding: "0.5rem",
    borderRadius: "8px",
    border: "1px solid #ccc",
    fontSize: "0.9rem",
  },
  button: {
    backgroundColor: "#4a90e2",
    color: "white",
    border: "none",
    padding: "0.6rem",
    borderRadius: "10px",
    fontWeight: "bold",
    fontSize: "0.95rem",
    cursor: "pointer",
    transition: "background 0.2s ease-in-out",
  },
};
