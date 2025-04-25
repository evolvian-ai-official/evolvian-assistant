import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabaseClient";
import axios from "axios";
import { useClientId } from "../../hooks/useClientId";

export default function WhatsAppSetup() {
  const [phone, setPhone] = useState("");
  const [step, setStep] = useState(1);
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState({ message: "", type: "" });
  const clientId = useClientId();

  const twilioSandbox = "+14155238886";

  useEffect(() => {
    const fetchSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setSession(session);
    };
    fetchSession();
  }, []);

  const handleSubmit = async () => {
    if (!phone || !session) return;

    const payload = {
      auth_user_id: session.user.id,
      email: session.user.email,
      phone,
    };

    try {
      const res = await axios.post("http://localhost:8000/link_whatsapp", payload);
      setStatus({ message: "✅ WhatsApp vinculado correctamente.", type: "success" });
      setStep(3);
    } catch (err) {
      console.error(err);
      setStatus({
        message: "❌ Error al vincular WhatsApp. Intenta de nuevo.",
        type: "error",
      });
    }
  };

  const handleNext = () => setStep(step + 1);
  const handleBack = () => setStep(step - 1);

  return (
    <div style={{
      padding: "2rem",
      fontFamily: "system-ui, sans-serif",
      backgroundColor: "#0f1c2e",
      color: "white",
      minHeight: "100vh",
      display: "flex",
      justifyContent: "center"
    }}>
      <div style={{
        backgroundColor: "#1b2a41",
        padding: "2rem",
        borderRadius: "16px",
        maxWidth: "600px",
        width: "100%",
        boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
        border: "1px solid #274472"
      }}>
        <h2 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#f5a623", marginBottom: "2rem" }}>
          💬 Configurar WhatsApp con Evolvian
        </h2>

        {step === 1 && (
          <>
            <p style={{ marginBottom: "1rem" }}>
              <strong>Paso 1:</strong> Guarda el siguiente número en tu teléfono:
            </p>
            <h3 style={{ fontSize: "1.25rem", fontWeight: "bold", color: "#a3d9b1", marginBottom: "1rem" }}>
              {twilioSandbox}
            </h3>
            <p style={{ marginBottom: "1rem" }}>
              <strong>Paso 2:</strong> Envía el siguiente mensaje desde WhatsApp:
            </p>
            <code style={{
              backgroundColor: "#ededed",
              color: "#274472",
              padding: "0.5rem 1rem",
              borderRadius: "8px",
              display: "inline-block",
              marginBottom: "1.5rem"
            }}>
              join come-science
            </code>
            <br />
            <button onClick={handleNext} style={btnStyle}>✅ Ya lo hice</button>
          </>
        )}

        {step === 2 && (
          <>
            <p style={{ marginBottom: "1rem" }}>
              <strong>Paso 3:</strong> Ingresa el número de WhatsApp que acabas de usar:
            </p>
            <input
              type="text"
              placeholder="+52XXXXXXXXXX"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              style={{
                width: "100%",
                padding: "0.6rem",
                borderRadius: "8px",
                border: "1px solid #4a90e2",
                marginBottom: "1.5rem",
                backgroundColor: "#0f1c2e",
                color: "white"
              }}
            />
            <div style={{ display: "flex", gap: "1rem" }}>
              <button
                onClick={handleSubmit}
                disabled={!phone}
                style={{
                  ...btnStyle,
                  opacity: phone ? 1 : 0.5,
                  cursor: phone ? "pointer" : "not-allowed"
                }}
              >
                📲 Vincular número
              </button>
              <button onClick={handleBack} style={backBtnStyle}>🔙 Atrás</button>
            </div>
            {status.message && (
              <p style={{
                marginTop: "1rem",
                fontWeight: "bold",
                color: status.type === "error" ? "#f87171" : "#a3d9b1"
              }}>
                {status.message}
              </p>
            )}
          </>
        )}

        {step === 3 && (
          <>
            <p style={{ marginBottom: "1rem" }}>🎉 ¡Listo! Tu número está vinculado:</p>
            <p style={{ fontWeight: "bold", color: "#a3d9b1" }}>{phone}</p>
            <p style={{ fontSize: "0.85rem", color: "#ededed", marginTop: "0.75rem" }}>
              Ahora puedes empezar a conversar con tu asistente.
            </p>

            <a
              href={`https://wa.me/${phone.replace("+", "")}?text=Hola,%20quiero%20probar%20mi%20asistente%20Evolvian`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                marginTop: "1.5rem",
                display: "inline-block",
                backgroundColor: "#2eb39a",
                color: "white",
                padding: "0.7rem 1.2rem",
                borderRadius: "8px",
                fontWeight: "bold",
                textDecoration: "none",
                marginRight: "1rem"
              }}
            >
              🔁 Probar asistente en WhatsApp
            </a>

            <button
              onClick={() => setStep(2)}
              style={{ ...backBtnStyle, marginTop: "1.5rem" }}
            >
              ✏️ Cambiar número
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ✅ Estilos de botones
const btnStyle = {
  backgroundColor: "#4a90e2",
  color: "white",
  padding: "0.7rem 1.2rem",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  cursor: "pointer",
};

const backBtnStyle = {
  backgroundColor: "#ededed",
  color: "#1b2a41",
  padding: "0.7rem 1.2rem",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  cursor: "pointer",
};
