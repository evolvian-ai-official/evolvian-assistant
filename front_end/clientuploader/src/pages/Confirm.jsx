import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLanguage } from "../contexts/LanguageContext";

export default function Confirm() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [animateLogo, setAnimateLogo] = useState(false);

  useEffect(() => {
    setTimeout(() => setAnimateLogo(true), 100);

    const timeout = setTimeout(() => {
      navigate("/login");
    }, 4000);

    if (!document.getElementById("pulseGlow")) {
      const style = document.createElement("style");
      style.id = "pulseGlow";
      style.textContent = `
        @keyframes pulseGlow {
          0%, 100% { box-shadow: 0 0 15px rgba(74,144,226,0.4); }
          50% { box-shadow: 0 0 25px rgba(163,217,177,0.7); }
        }
      `;
      document.head.appendChild(style);
    }

    return () => clearTimeout(timeout);
  }, [navigate]);

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        {/* 🔹 Logo circular degradado */}
        <div style={logoWrapper}>
          <div
            style={{
              ...logoCircle,
              transform: animateLogo ? "rotate(360deg)" : "rotate(0deg)",
              transition: "transform 1s ease-in-out",
              animation: "pulseGlow 4s ease-in-out infinite",
            }}
          >
            <img src="/logo-evolvian.svg" alt="Evolvian Logo" style={logoFull} />
          </div>
        </div>

        <h2 style={titleStyle}>✅ {t("email_confirmed_successfully")}</h2>
        <p style={textStyle}>{t("redirecting_to_login")}</p>
      </div>
    </div>
  );
}

/* 🎨 Estilos Evolvian */
const containerStyle = {
  height: "100vh",
  width: "100vw",
  backgroundColor: "#f9fafb",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "Inter, system-ui, sans-serif",
};

const cardStyle = {
  width: "100%",
  maxWidth: "400px",
  backgroundColor: "#ffffff",
  borderRadius: "20px",
  padding: "2.5rem 2rem",
  boxShadow: "0 8px 40px rgba(39,68,114,0.1)",
  textAlign: "center",
  border: "1px solid #e5e7eb",
};

const logoWrapper = {
  display: "flex",
  justifyContent: "center",
  marginBottom: "1.5rem",
};

const logoCircle = {
  width: "80px",
  height: "80px",
  borderRadius: "50%",
  background: "radial-gradient(circle, #a3d9b1 0%, #4a90e2 100%)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  overflow: "hidden",
};

const logoFull = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
};

const titleStyle = {
  fontSize: "1.3rem",
  fontWeight: "700",
  color: "#274472",
  marginBottom: "0.75rem",
};

const textStyle = {
  fontSize: "0.95rem",
  color: "#6b7280",
};
