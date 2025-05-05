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
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <img
            src="/logo-evolvian.svg"
            alt="Logo Evolvian"
            style={{ width: "64px", margin: "0 auto 1rem" }}
          />
          <h1 style={titleStyle}>{t("new_password")}</h1>
          <p style={subtitleStyle}>{t("enter_new_password")}</p>
        </div>

        <form onSubmit={handleUpdate} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={inputWrapperStyle}>
            <input
              type={showPassword ? "text" : "password"}
              placeholder={t("new_password_placeholder")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{ ...inputStyle, border: "none", flex: 1 }}
            />
            <div
              style={eyeIconWrapperStyle}
              onMouseEnter={() => setShowPassword(true)}
              onMouseLeave={() => setShowPassword(false)}
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

// 🎨 Estilos
const containerStyle = {
  height: "100vh",
  width: "100vw",
  backgroundColor: "#0f1c2e",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "1rem",
  fontFamily: "system-ui, Avenir, Helvetica, Arial, sans-serif",
};

const cardStyle = {
  width: "100%",
  maxWidth: "400px",
  backgroundColor: "#1b2a41",
  borderRadius: "1.5rem",
  padding: "2rem",
  color: "white",
  boxShadow: "0 15px 40px rgba(0,0,0,0.3)",
  border: "1px solid #274472",
};

const titleStyle = {
  fontSize: "1.5rem",
  fontWeight: "bold",
};

const subtitleStyle = {
  fontSize: "0.9rem",
  color: "#ccc",
};

const inputWrapperStyle = {
  display: "flex",
  alignItems: "center",
  border: "1px solid #274472",
  borderRadius: "8px",
  backgroundColor: "transparent",
  height: "40px",
  paddingRight: "0.75rem",
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem 1rem",
  background: "transparent",
  borderRadius: "8px",
  color: "white",
  fontSize: "1rem",
};

const eyeIconWrapperStyle = {
  color: "#ccc",
  cursor: "pointer",
  fontSize: "1.1rem",
};

const buttonStyle = {
  backgroundColor: "#2eb39a",
  padding: "0.7rem",
  color: "white",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  fontSize: "1rem",
};
