import { useEffect, useState } from "react";
import { useClientId } from "../hooks/useClientId";
import { Link, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";

export default function Sidebar() {
  const navigate = useNavigate();
  const clientId = useClientId();
  const [features, setFeatures] = useState([]);
  const [hovered, setHovered] = useState(null);

  useEffect(() => {
    const fetchFeatures = async () => {
      if (!clientId) return;
      try {
        const res = await fetch(`http://localhost:8000/client_settings?client_id=${clientId}`);
        const data = await res.json();
        if (res.ok) {
          const normalize = (str) => str.toLowerCase().replace(/\s+/g, "_");
          const featuresArray = data.plan?.plan_features?.map(f => normalize(f.feature)) || [];
          setFeatures(featuresArray);
        }
      } catch (error) {
        console.error("❌ Error al conectar con el backend:", error);
      }
    };

    fetchFeatures();
  }, [clientId]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    localStorage.clear();
    navigate("/login", { replace: true });
    window.location.reload();
  };

  const isEnabled = (feature) => features.includes(feature);

  return (
    <aside style={{
      width: "240px",
      background: "#274472",
      color: "white",
      padding: "2rem 1.5rem",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
    }}>
      <div>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <img
            src="/logo-evolvian.svg"
            alt="Evolvian Logo"
            style={{ width: "60px", margin: "0 auto" }}
          />
        </div>

        <nav style={{ display: "flex", flexDirection: "column" }}>
          <HoverLink label="📊 Dashboard" to="/dashboard" hovered={hovered} setHovered={setHovered} id="dashboard" />
          <HoverLink label="📤 Subir documento" to="/upload" hovered={hovered} setHovered={setHovered} id="upload" />
          <HoverLink label="📚 Ver historial" to="/history" hovered={hovered} setHovered={setHovered} id="history" />

          {[
            { label: "🧠 Chat Assistant", path: "/services/chat", feature: "chat_widget" },
            { label: "✉️ Email", path: "/services/email", feature: "email_support" },
            { label: "💬 WhatsApp", path: "/services/whatsapp", feature: "whatsapp_integration" },
          ].map(({ label, path, feature }) => {
            const enabled = isEnabled(feature);
            const id = path;
            return (
              <div key={feature} style={navItemBlock}>
                <Link
                  to={enabled ? path : "#"}
                  style={{
                    ...linkStyle,
                    backgroundColor: hovered === id ? "#4a90e2" : "transparent",
                    color: enabled ? "white" : "#999",
                    pointerEvents: enabled ? "auto" : "none",
                  }}
                  onMouseEnter={() => setHovered(id)}
                  onMouseLeave={() => setHovered(null)}
                  title={enabled ? "" : "Disponible en planes premium"}
                >
                  {label}
                </Link>
                {!enabled && (
                  <span style={{ ...premiumBadge, marginLeft: "8px" }}>Premium</span>
                )}
              </div>
            );
          })}

          <HoverLink label="⚙️ Configuración" to="/settings" hovered={hovered} setHovered={setHovered} id="settings" />

          <div style={{ ...navItemBlock, marginTop: "1.5rem" }}>
            <button
              onClick={handleLogout}
              style={{
                backgroundColor: "#f5a623",
                color: "white",
                border: "none",
                borderRadius: "8px",
                padding: "0.5rem 1rem",
                cursor: "pointer",
                fontWeight: "bold",
                width: "100%",
              }}
            >
              Cerrar sesión
            </button>
          </div>
        </nav>
      </div>
    </aside>
  );
}

// Link con hover y separación
function HoverLink({ to, label, hovered, setHovered, id }) {
  return (
    <div style={navItemBlock}>
      <Link
        to={to}
        onMouseEnter={() => setHovered(id)}
        onMouseLeave={() => setHovered(null)}
        style={{
          ...linkStyle,
          backgroundColor: hovered === id ? "#4a90e2" : "transparent",
        }}
      >
        {label}
      </Link>
    </div>
  );
}

// Estilos visuales

const navItemBlock = {
  padding: "0.4rem 0.6rem",
  borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
};

const linkStyle = {
  color: "white",
  textDecoration: "none",
  fontWeight: "500",
  fontSize: "1rem",
  transition: "all 0.2s ease",
  display: "block",
  borderRadius: "6px",
};

const premiumBadge = {
  backgroundColor: "#f5a623",
  color: "#1b2a41",
  fontSize: "0.7rem",
  padding: "2px 6px",
  borderRadius: "999px",
  fontWeight: "bold",
  verticalAlign: "middle",
};
