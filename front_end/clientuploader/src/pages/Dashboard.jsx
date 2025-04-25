import { useEffect, useState } from "react";
import { useClientId } from "../hooks/useClientId";
import { supabase } from "../lib/supabaseClient";

export default function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [user, setUser] = useState(null);
  const clientId = useClientId();

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user);
    });
  }, []);

  useEffect(() => {
    const fetchDashboard = async () => {
      if (!clientId) return;
      const res = await fetch(`http://localhost:8000/dashboard_summary?client_id=${clientId}`);
      const data = await res.json();
      if (res.ok) setDashboardData(data);
    };

    fetchDashboard();
  }, [clientId]);

  if (!user || !dashboardData) return null;

  const { plan, usage, history_preview, documents_preview, assistant_config } = dashboardData;

  const normalize = (str) => str.toLowerCase().replace(/\s+/g, "_");
  const activeFeatures = plan.plan_features?.map(f => normalize(f.feature)) || [];

  const isFeatureActive = (featureKey) => activeFeatures.includes(featureKey);

  return (
    <div style={{
      backgroundColor: "#0f1c2e",
      minHeight: "100vh",
      padding: "2rem",
      fontFamily: "system-ui, sans-serif",
      color: "white"
    }}>
      <h1 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#f5a623", marginBottom: "0.25rem" }}>
        👋 Bienvenido, {user.email}
      </h1>
      <p style={{ color: "#ededed", marginBottom: "2rem" }}>
        Soy <strong style={{ color: "#a3d9b1" }}>{assistant_config.assistant_name}</strong>, tu asistente Evolvian.
      </p>

      {/* PLAN */}
      <div style={cardStyle}>
        <h2 style={sectionTitle}>🧾 Tu Plan: <span style={{ color: "#a3d9b1" }}>{plan.name}</span></h2>
        <p>💬 Mensajes usados: <strong>{usage.messages_used}</strong> / {plan.is_unlimited ? "Ilimitados" : plan.max_messages}</p>
        <p>📄 Documentos subidos: <strong>{usage.documents_uploaded}</strong> / {plan.is_unlimited ? "Ilimitados" : plan.max_documents}</p>
        <p>🕒 Último uso: {new Date(usage.last_used_at).toLocaleString()}</p>
      </div>

      {/* FEATURES ACTIVOS */}
      <div style={cardStyle}>
        <h2 style={sectionTitle}>🔧 Funcionalidades Activas</h2>
        <ul style={{ lineHeight: "1.8" }}>
          {[
            { label: "🧠 Chat Widget", key: "chat_widget" },
            { label: "✉️ Soporte por Email", key: "email_support" },
            { label: "💬 WhatsApp", key: "whatsapp_integration" },
            { label: "🚀 Límites aumentados", key: "increased_limits" },
            { label: "❌ Sin Branding", key: "remove_branding" }
          ].map(({ label, key }) => (
            <li key={key}>
              {label}: {isFeatureActive(key) ? "✅ Activo" : "⛔ Inactivo"}
            </li>
          ))}
        </ul>
      </div>

      {/* HISTORIAL PREVIEW */}
      <div style={cardStyle}>
        <h2 style={sectionTitle}>📚 Últimas preguntas</h2>
        {history_preview.length === 0 ? (
          <p style={{ color: "#ededed" }}>Aún no hay preguntas registradas.</p>
        ) : (
          <ul style={{ lineHeight: "1.8" }}>
            {history_preview.map((h, idx) => (
              <li key={idx}>
                <strong>{h.channel}:</strong> {h.question} <br />
                <span style={{ fontSize: "0.8rem", color: "#a3d9b1" }}>
                  {new Date(h.timestamp).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* DOCUMENTOS PREVIEW */}
      <div style={cardStyle}>
        <h2 style={sectionTitle}>📄 Documentos recientes</h2>
        {documents_preview.length === 0 ? (
          <p style={{ color: "#ededed" }}>No se han subido documentos todavía.</p>
        ) : (
          <ul style={{ lineHeight: "1.8" }}>
            {documents_preview.map((doc, idx) => (
              <li key={idx}>
                📄 {doc.filename} <br />
                <span style={{ fontSize: "0.8rem", color: "#a3d9b1" }}>
                  {new Date(doc.uploaded_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ACCIONES RÁPIDAS */}
      <div style={{
        marginTop: "2rem",
        display: "flex",
        justifyContent: "center",
        gap: "1.5rem"
      }}>
        <a
          href="/history"
          style={{
            backgroundColor: "#4a90e2",
            color: "white",
            padding: "0.75rem 1.5rem",
            borderRadius: "10px",
            textDecoration: "none",
            fontWeight: "bold"
          }}
        >
          📚 Ver historial completo
        </a>
        <a
          href="/upload"
          style={{
            backgroundColor: "#f5a623",
            color: "#1b2a41",
            padding: "0.75rem 1.5rem",
            borderRadius: "10px",
            textDecoration: "none",
            fontWeight: "bold"
          }}
        >
          📄 Subir nuevo documento
        </a>
      </div>
    </div>
  );
}

const cardStyle = {
  backgroundColor: "#1b2a41",
  padding: "1.5rem",
  borderRadius: "16px",
  border: "1px solid #274472",
  marginBottom: "2rem"
};

const sectionTitle = {
  fontSize: "1.25rem",
  color: "#4a90e2",
  marginBottom: "1rem"
};
