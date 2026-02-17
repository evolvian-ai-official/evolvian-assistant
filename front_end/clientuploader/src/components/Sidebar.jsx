import { useEffect, useState } from "react";
import { useClientId } from "../hooks/useClientId";
import { Link, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import { authFetch } from "../lib/authFetch";
import { useLanguage } from "../contexts/LanguageContext";

export default function Sidebar() {
  const navigate = useNavigate();
  const clientId = useClientId();
  const { t } = useLanguage();
  const [features, setFeatures] = useState([]);
  const [hovered, setHovered] = useState(null);
  const [animateLogo, setAnimateLogo] = useState(false);

  useEffect(() => {
    setAnimateLogo(true);

    const fetchFeatures = async () => {
      if (!clientId) return;

      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`
        );

        const data = await res.json();

        if (res.ok) {
          const normalize = (str) =>
            String(str || "")
              .toLowerCase()
              .trim()
              .replace(/\s+/g, "_");

          const rawFeatures = data.plan?.plan_features || [];

          const featuresArray = rawFeatures
            .map((f) => {
              // Caso 1: backend ya envía string
              if (typeof f === "string") {
                return normalize(f);
              }

              // Caso 2: backend envía objeto { feature, is_active }
              if (typeof f === "object") {
                if (f.is_active === true) {
                  return normalize(f.feature);
                }
                return null; // 🔥 ignorar inactivos
              }

              return null;
            })
            .filter(Boolean);

          setFeatures(featuresArray);
        }
      } catch (error) {
        console.error("❌ Error connecting to backend:", error);
      }
    };

    fetchFeatures();
  }, [clientId]);

  const handleLogout = async () => {
    const persistedLang = localStorage.getItem("lang");
    await supabase.auth.signOut();
    localStorage.removeItem("client_id");
    localStorage.removeItem("public_client_id");
    localStorage.removeItem("user_id");
    localStorage.removeItem("alreadyRedirected");
    if (persistedLang) {
      localStorage.setItem("lang", persistedLang);
    }
    navigate("/login", { replace: true });
    window.location.reload();
  };

  const isEnabled = (feature) => features.includes(feature);

  return (
    <aside style={asideStyle}>
      <div>
        <div style={logoContainer}>
          <div
            style={{
              ...logoCircle,
              transform: animateLogo ? "rotate(360deg)" : "rotate(0deg)",
              opacity: animateLogo ? 1 : 0,
              transition: "all 1s ease-in-out",
            }}
          >
            <img
              src="/logo-evolvian.svg"
              alt="Evolvian Logo"
              style={{
                width: "100%",
                height: "100%",
                borderRadius: "50%",
                objectFit: "cover",
              }}
            />
          </div>
        </div>

        <nav style={navStyle}>
          <HoverLink
            label={`${t("dashboard")}`}
            to="/dashboard"
            hovered={hovered}
            setHovered={setHovered}
            id="dashboard"
          />
          <HoverLink
            label={`${t("upload")}`}
            to="/upload"
            hovered={hovered}
            setHovered={setHovered}
            id="upload"
          />
          <HoverLink
            label={`${t("history")}`}
            to="/history"
            hovered={hovered}
            setHovered={setHovered}
            id="history"
          />

          {[
            { label: `${t("chat_assistant")}`, path: "/services/chat", feature: "chat_widget" },
            { label: `${t("whatsapp")}`, path: "/services/whatsapp", feature: "whatsapp_integration" },
            { label: `${t("email")}`, path: "/services/email", feature: "email_support" },
            { label: `${t("appointments_nav")}`, path: "/services/calendar", feature: "calendar_sync" },
            { label: `${t("templates_nav")}`, path: "/services/templates", feature: "templates" },
          ]
            .filter(({ feature }) => isEnabled(feature)) // 🔥 SOLO mostrar si está activo
            .map(({ label, path, feature }) => {

            const enabled = isEnabled(feature);
            const id = path;

            return (
              <div key={feature} style={navItemBlock}>
                <Link
                  to={enabled ? path : "#"}
                  style={{
                    ...linkStyle,
                    backgroundColor: hovered === id ? "#EAF3FC" : "transparent",
                    color: enabled
                      ? hovered === id
                        ? "#4A90E2"
                        : "#274472"
                      : "#999",
                    pointerEvents: enabled ? "auto" : "none",
                    borderLeft:
                      hovered === id
                        ? "4px solid #F5A623"
                        : "4px solid transparent",
                    paddingLeft: "12px",
                  }}
                  onMouseEnter={() => setHovered(id)}
                  onMouseLeave={() => setHovered(null)}
                >
                  {label}
                </Link>

                {!enabled && (
                  <span style={{ ...premiumBadge, marginLeft: "8px" }}>
                    {t("premium")}
                  </span>
                )}
              </div>
            );
          })}

          <HoverLink
            label={`${t("settings")}`}
            to="/settings"
            hovered={hovered}
            setHovered={setHovered}
            id="settings"
          />
        </nav>
      </div>

      <div style={footerContainer}>
        <button onClick={handleLogout} style={logoutButtonStyle}>
          {t("logout")}
        </button>
      </div>
    </aside>
  );
}

function HoverLink({ to, label, hovered, setHovered, id }) {
  return (
    <div style={navItemBlock}>
      <Link
        to={to}
        onMouseEnter={() => setHovered(id)}
        onMouseLeave={() => setHovered(null)}
        style={{
          ...linkStyle,
          backgroundColor: hovered === id ? "#EAF3FC" : "transparent",
          color: hovered === id ? "#4A90E2" : "#274472",
          borderLeft:
            hovered === id
              ? "4px solid #F5A623"
              : "4px solid transparent",
          paddingLeft: "12px",
        }}
      >
        {label}
      </Link>
    </div>
  );
}

/* 🎨 Styles (unchanged) */

const asideStyle = {
  width: "240px",
  background: "#FFFFFF",
  color: "#274472",
  padding: "2rem 1.5rem",
  minHeight: "100vh",
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  borderRight: "1px solid #EDEDED",
};

const logoContainer = {
  textAlign: "center",
  marginBottom: "2rem",
  marginTop: "1rem",
};

const logoCircle = {
  width: "80px",
  height: "80px",
  borderRadius: "50%",
  backgroundColor: "#A3D9B1",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  margin: "0 auto 1rem",
  boxShadow: "0 0 12px rgba(163, 217, 177, 0.4)",
  border: "2px solid #FFFFFF",
};

const navStyle = {
  display: "flex",
  flexDirection: "column",
};

const navItemBlock = {
  padding: "0.5rem 0.6rem",
  borderBottom: "1px solid #EDEDED",
};

const linkStyle = {
  textDecoration: "none",
  fontWeight: "500",
  fontSize: "1rem",
  transition: "all 0.2s ease",
  display: "block",
  borderRadius: "6px",
  padding: "0.3rem 0.5rem",
};

const premiumBadge = {
  backgroundColor: "#F5A623",
  color: "#FFFFFF",
  fontSize: "0.7rem",
  padding: "2px 6px",
  borderRadius: "999px",
  fontWeight: "bold",
  verticalAlign: "middle",
};

const footerContainer = {
  borderTop: "1px solid #EDEDED",
  paddingTop: "1.5rem",
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  background: "#FFFFFF",
};

const logoutButtonStyle = {
  backgroundColor: "#F5A623",
  color: "white",
  border: "none",
  borderRadius: "8px",
  padding: "0.5rem 1rem",
  cursor: "pointer",
  fontWeight: "bold",
  width: "100%",
  transition: "background 0.3s ease",
};
