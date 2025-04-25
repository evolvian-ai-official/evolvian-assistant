import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useTermsAcceptance } from "../hooks/useTermsAcceptance";
import { useClientId } from "../hooks/useClientId";

export default function Welcome() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const clientId = useClientId();
  const { hasAccepted, acceptTerms } = useTermsAcceptance(clientId);

  const handleContinue = async () => {
    setLoading(true);
    const userId = localStorage.getItem("user_id");
    console.log("🧠 Obtenido user_id desde localStorage:", userId);

    try {
      if (userId) {
        const res = await fetch(`http://localhost:8000/clear_new_user_flag?user_id=${userId}`, {
          method: "POST",
        });
        const result = await res.json();
        console.log("✅ Respuesta de clear_new_user_flag:", result);
      } else {
        console.warn("⚠️ user_id no está disponible en localStorage");
      }

      if (!hasAccepted && clientId) {
        console.log("📩 Aceptando términos con client_id:", clientId);
        await acceptTerms();
      }

      console.log("➡️ Redirigiendo a /dashboard...");
      navigate("/dashboard", { replace: true });
      window.location.reload();
    } catch (err) {
      console.error("❌ Error al limpiar flag o aceptar términos:", err);
      navigate("/dashboard");
      window.location.reload();
    }
  };

  if (hasAccepted === null) {
    return <div style={{ color: "white", padding: "2rem" }}>Cargando...</div>;
  }

  return (
    <div style={{
      height: "100vh",
      backgroundColor: "#0f1c2e",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "system-ui, sans-serif",
      padding: "2rem",
      color: "white",
    }}>
      <div style={{
        backgroundColor: "#1b2a41",
        padding: "3rem",
        borderRadius: "1.5rem",
        maxWidth: "600px",
        width: "100%",
        textAlign: "center",
        boxShadow: "0 0 30px rgba(0,0,0,0.2)",
        border: "1px solid #274472"
      }}>
        <img src="/logo-evolvian.svg" alt="Evolvian" style={{ width: "60px", marginBottom: "1.5rem" }} />
        <h1 style={{ fontSize: "1.8rem", color: "#a3d9b1", marginBottom: "1rem" }}>
          Bienvenido a Evolvian, tu nuevo copiloto de conocimiento.
        </h1>
        <p style={{ fontSize: "1rem", color: "#ededed", marginBottom: "1.5rem" }}>
          Has dado el primer paso hacia una forma más rápida, segura y precisa de resolver tus dudas,
          compartir respuestas y empoderar a tus usuarios.<br /><br />
          Evolvian es un asistente de inteligencia artificial que entiende tus documentos y responde como si fueras tú.
          Aquí empieza todo.
        </p>
        <button
          onClick={handleContinue}
          disabled={loading}
          style={{
            backgroundColor: "#2eb39a",
            color: "white",
            fontSize: "1rem",
            padding: "0.8rem 1.6rem",
            border: "none",
            borderRadius: "8px",
            fontWeight: "bold",
            cursor: loading ? "not-allowed" : "pointer"
          }}
        >
          {loading ? "Cargando..." : "Ir al panel"}
        </button>
      </div>
    </div>
  );
}
