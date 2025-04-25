import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabaseClient";
import { useClientId } from "../../hooks/useClientId";

export default function EmailSetup() {
  const [email, setEmail] = useState("");
  const [saved, setSaved] = useState(false);
  const clientId = useClientId();

  useEffect(() => {
    const fetchEmail = async () => {
      if (!clientId) return;
      const { data, error } = await supabase
        .from("clients")
        .select("email_forward")
        .eq("id", clientId)
        .single();

      if (data?.email_forward) setEmail(data.email_forward);
    };

    fetchEmail();
  }, [clientId]);

  const handleSave = async () => {
    if (!clientId || !email) return;

    const { error } = await supabase
      .from("clients")
      .update({ email_forward: email })
      .eq("id", clientId);

    if (!error) setSaved(true);
  };

  return (
    <div style={{
      backgroundColor: "#0f1c2e",
      minHeight: "100vh",
      padding: "2rem",
      fontFamily: "system-ui, sans-serif",
      color: "white",
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
        <h2 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#f5a623", marginBottom: "1.5rem" }}>
          ✉️ Configurar Email Assistant
        </h2>

        <p style={{ marginBottom: "1rem" }}>
          Tu asistente puede responder correos automáticamente si los reenvías a una dirección como esta:
        </p>

        <code style={{
          backgroundColor: "#ededed",
          color: "#274472",
          padding: "0.6rem 1rem",
          borderRadius: "8px",
          display: "block",
          marginBottom: "1.5rem"
        }}>
          contacto@tudominio.com → evolvian@correo.evolvian.app
        </code>

        <p style={{ marginBottom: "1rem" }}>
          Aquí puedes guardar la dirección de correo que deseas conectar con tu asistente Evolvian:
        </p>

        <input
          type="email"
          placeholder="tucorreo@empresa.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setSaved(false);
          }}
          style={{
            width: "100%",
            padding: "0.6rem",
            borderRadius: "8px",
            border: "1px solid #4a90e2",
            marginBottom: "1rem",
            backgroundColor: "#0f1c2e",
            color: "white"
          }}
        />

        <button
          onClick={handleSave}
          style={{
            backgroundColor: "#4a90e2",
            color: "white",
            padding: "0.7rem 1.2rem",
            borderRadius: "8px",
            fontWeight: "bold",
            border: "none",
            cursor: "pointer",
            marginBottom: "1rem"
          }}
        >
          Guardar dirección
        </button>

        {saved && (
          <p style={{ color: "#a3d9b1", fontSize: "0.95rem" }}>
            ✅ Dirección guardada exitosamente.
          </p>
        )}

        <div style={{ marginTop: "2rem", fontSize: "0.9rem", color: "#ededed" }}>
          <p><strong>¿Cómo funciona?</strong></p>
          <ul style={{ marginTop: "0.5rem", paddingLeft: "1.2rem", lineHeight: "1.7" }}>
            <li>1️⃣ Cualquier correo que reenvíes a <strong>evolvian@correo.evolvian.app</strong> será procesado.</li>
            <li>2️⃣ Tu asistente generará una respuesta con inteligencia artificial.</li>
            <li>3️⃣ Puedes personalizar la respuesta o dejar que se envíe automáticamente.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
