import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";
import { useLanguage } from "../contexts/LanguageContext";
import { FaEye, FaEyeSlash } from "react-icons/fa";

export default function ResetPassword() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [tokenLoaded, setTokenLoaded] = useState(false);

  useEffect(() => {
    const hash = window.location.hash;
    const accessToken = hash.includes("access_token");
    if (!accessToken) {
      toast.error(t("invalid_token"));
      navigate("/forgot-password");
    } else {
      setTokenLoaded(true);
    }
  }, [navigate, t]);

  const handleUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);

    const { error } = await supabase.auth.updateUser({ password });

    if (error) {
      toast.error(`❌ ${t("error_updating_password")}: ${error.message}`);
    } else {
      toast.success(`🔒 ${t("password_updated_successfully")}`);
      navigate("/login");
    }

    setLoading(false);
  };

  if (!tokenLoaded) return null;

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <img
            src="/logo-evolvian.svg"
            alt="Logo Evolvian"
            style={{
              width: "64px",
              height: "64px",
              margin: "0 auto 1rem",
              animation: "spin 6s linear infinite",
            }}
          />
          <h1 style={titleStyle}>{t("new_password")}</h1>
          <p style={subtitleStyle}>{t("enter_new_password")}</p>
        </div>

        <form onSubmit={handleUpdate} style={formStyle}>
          <div style={inputWrapperStyle}>
            <input
              type={showPassword ? "text" : "password"}
              placeholder={t("new_password_placeholder")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={inputStyle}
            />
            <div
              style={eyeIconWrapperStyle}
              onClick={() => setShowPassword((prev) => !prev)}
            >
              {showPassword ? <FaEyeSlash /> : <FaEye />}
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              ...buttonStyle,
              opacity: loading ? 0.7 : 1,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? t("updating") : t("update_password")}
          </button>
        </form>
      </div>
    </div>
  );
}

// 🎨 Estilos Evolvian™ 2025
const containerStyle = {
  height: "100vh",
  width: "100vw",
  backgroundColor: "#ffffff", // ✅ Fondo blanco total
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "1rem",
  fontFamily: "Inter, system-ui, sans-serif",
};

const cardStyle = {
  width: "100%",
  maxWidth: "400px",
  backgroundColor: "#f8fafc", // gris muy claro
  borderRadius: "1.5rem",
  padding: "2rem",
  color: "#274472",
  boxShadow: "0 10px 30px rgba(0,0,0,0.08)",
  border: "1px solid #e5e7eb",
  textAlign: "center",
};

const titleStyle = {
  fontSize: "1.6rem",
  fontWeight: "bold",
  color: "#274472",
  marginBottom: "0.5rem",
};

const subtitleStyle = {
  fontSize: "0.9rem",
  color: "#6b7280",
  marginBottom: "1rem",
};

const formStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  textAlign: "left",
};

const inputWrapperStyle = {
  display: "flex",
  alignItems: "center",
  border: "1px solid #274472",
  borderRadius: "8px",
  backgroundColor: "#ffffff",
  height: "42px",
  paddingRight: "0.75rem",
  boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem 1rem",
  background: "transparent",
  border: "none",
  borderRadius: "8px",
  color: "#274472",
  fontSize: "1rem",
  outline: "none",
};

const eyeIconWrapperStyle = {
  color: "#4a90e2",
  cursor: "pointer",
  fontSize: "1.1rem",
  transition: "color 0.2s",
};

const buttonStyle = {
  backgroundColor: "#4a90e2", // azul brillante Evolvian
  padding: "0.7rem",
  color: "#ffffff",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  fontSize: "1rem",
  marginTop: "1rem",
  transition: "background-color 0.3s ease",
};

if (typeof document !== "undefined" && !document.getElementById("spin-keyframes")) {
  const style = document.createElement("style");
  style.id = "spin-keyframes";
  style.textContent = `
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}
