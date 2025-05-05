import { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { useNavigate, Link } from "react-router-dom";
import { FaGoogle, FaEye, FaEyeSlash } from "react-icons/fa";
import { useLanguage } from "../contexts/LanguageContext";

export default function Login() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const navigate = useNavigate();

  const handleGoogleLogin = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/dashboard`,
        queryParams: {
          prompt: "select_account",
        },
      },
    });
    if (error) console.error("❌ Google login error:", error);
  };

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    const { data, error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setErrorMsg(t("wrong_credentials"));
      return;
    }

    if (!data.session) {
      setErrorMsg(t("email_not_confirmed"));
      return;
    }

    await fetch("http://localhost:8000/initialize_user", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        auth_user_id: data.session.user.id,
        email: data.session.user.email,
      }),
    });

    navigate("/dashboard");
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <img src="/logo-evolvian.svg" alt="Logo Evolvian" style={{ width: "64px", margin: "0 auto 1rem" }} />
          <h1 style={{ fontSize: "1.75rem", fontWeight: "bold" }}>Evolvian</h1>
        </div>

        <form onSubmit={handleEmailLogin} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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

          <div style={inputWrapperStyle}>
            <input
              type={showPassword ? "text" : "password"}
              placeholder={t("password")}
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

          {errorMsg && (
            <p style={{ color: "#f87171", textAlign: "center", fontSize: "0.875rem" }}>
              {errorMsg}
            </p>
          )}

          <button type="submit" style={primaryButtonStyle}>
            {t("login")}
          </button>

          <div style={optionsContainerStyle}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <input type="checkbox" />
              {t("remember_me")}
            </label>
            <Link to="/forgot-password" style={linkStyle}>
              {t("forgot_password")}
            </Link>
          </div>
        </form>

        <div style={dividerStyle}>
          <div style={lineStyle} />
          <span>{t("or")}</span>
          <div style={lineStyle} />
        </div>

        {/* Desactivado temporalmente
        <button onClick={handleGoogleLogin} style={googleButtonStyle}>
          <FaGoogle />
          {t("login_with_google")}
        </button>
        */}

        {/* Registro deshabilitado para Friends & Family */}
        {/*
        <p style={footerTextStyle}>
          {t("no_account")}{" "}
          <Link to="/register" style={registerLinkStyle}>
            {t("register_here")}
          </Link>
        </p>
        */}
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
  color: "white",
  borderRadius: "1.5rem",
  padding: "2rem",
  boxShadow: "0 15px 40px rgba(0,0,0,0.3)",
  border: "1px solid #274472",
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem 1rem",
  backgroundColor: "transparent",
  borderRadius: "8px",
  color: "white",
  fontSize: "1rem",
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

const eyeIconWrapperStyle = {
  color: "#ccc",
  cursor: "pointer",
  fontSize: "1.1rem",
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

const optionsContainerStyle = {
  display: "flex",
  justifyContent: "space-between",
  fontSize: "0.875rem",
  color: "#ccc",
  marginTop: "0.5rem",
};

const linkStyle = {
  color: "#a3d9b1",
  textDecoration: "underline",
};

const dividerStyle = {
  display: "flex",
  alignItems: "center",
  gap: "1rem",
  margin: "2rem 0",
  color: "#888",
};

const lineStyle = {
  flex: 1,
  height: "1px",
  backgroundColor: "#555",
};

const googleButtonStyle = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "0.5rem",
  padding: "0.7rem",
  border: "1px solid white",
  borderRadius: "8px",
  backgroundColor: "transparent",
  color: "white",
  cursor: "pointer",
  fontSize: "1rem",
};

const footerTextStyle = {
  textAlign: "center",
  fontSize: "0.875rem",
  color: "#bbb",
  marginTop: "2rem",
};

const registerLinkStyle = {
  color: "#f5a623",
  fontWeight: "bold",
  textDecoration: "underline",
};
