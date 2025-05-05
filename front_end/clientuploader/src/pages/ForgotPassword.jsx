import { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { useLanguage } from "../contexts/LanguageContext";

export default function ForgotPassword() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");

  const handleReset = async (e) => {
    e.preventDefault();

    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });

    if (error) {
      console.error("❌ Error al enviar reset:", error.message);
      toast.error(t("error_sending_reset_email"));
    } else {
      toast.success(t("check_your_email"));
    }
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <img src="/logo-evolvian.svg" alt="Logo Evolvian" style={{ width: "64px", margin: "0 auto 1rem" }} />
          <h1 style={titleStyle}>{t("recover_password")}</h1>
          <p style={subtitleStyle}>{t("enter_your_email")}</p>
        </div>

        <form onSubmit={handleReset} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={inputWrapperStyle}>
            <input
              type="email"
              placeholder={t("email")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{ ...inputStyle, border: "none", flex: 1 }}
            />
          </div>
          <button type="submit" style={primaryButtonStyle}>
            {t("send_email")}
          </button>
        </form>

        <p style={footerTextStyle}>
          {t("already_have_access")}{" "}
          <Link to="/login" style={linkStyle}>
            {t("login")}
          </Link>
        </p>
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

const primaryButtonStyle = {
  backgroundColor: "#2eb39a",
  padding: "0.7rem",
  color: "white",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  cursor: "pointer",
  fontSize: "1rem",
};

const footerTextStyle = {
  textAlign: "center",
  fontSize: "0.875rem",
  color: "#bbb",
  marginTop: "2rem",
};

const linkStyle = {
  color: "#f5a623",
  fontWeight: "bold",
  textDecoration: "underline",
};
