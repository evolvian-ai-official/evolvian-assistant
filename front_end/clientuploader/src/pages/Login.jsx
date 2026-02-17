// src/pages/Login.jsx
import { useEffect, useState } from "react";
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
  const [checkingSession, setCheckingSession] = useState(true);
  const [animateLogo, setAnimateLogo] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const checkSession = async () => {
      const { data } = await supabase.auth.getSession();
      if (data?.session) navigate("/dashboard");
      setCheckingSession(false);
    };
    checkSession();
    setTimeout(() => setAnimateLogo(true), 100);
  }, [navigate]);

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) return setErrorMsg(t("wrong_credentials"));
    if (!data.session) return setErrorMsg(t("email_not_confirmed"));
    await initializeUser(data.session.user);
  };

  const handleGoogleLogin = async () => {
    const redirectTo = `${window.location.origin}/dashboard`;
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo },
    });
    if (error) setErrorMsg(t("login_google_connect_error"));
  };

  const initializeUser = async (user) => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/initialize_user`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auth_user_id: user.id,
          email: user.email,
        }),
      });
      if (!res.ok) throw new Error(t("login_initialize_failed"));
      const initData = await res.json();
      localStorage.setItem("client_id", initData.client_id);
      localStorage.setItem("public_client_id", initData.public_client_id);
      localStorage.setItem("user_id", user.id);
      navigate("/dashboard");
    } catch (err) {
      console.error(err);
      setErrorMsg(t("login_initialize_error"));
    }
  };

  // 🔹 Efecto y media query para ocultar el GIF en mobile
  useEffect(() => {
    if (!document.getElementById("loginResponsiveStyle")) {
      const style = document.createElement("style");
      style.id = "loginResponsiveStyle";
      style.textContent = `
        @keyframes pulseGlow {
          0%, 100% { box-shadow: 0 0 15px rgba(74,144,226,0.4); }
          50% { box-shadow: 0 0 25px rgba(163,217,177,0.7); }
        }
        @media (max-width: 768px) {
          .gif-container { display: none !important; }
          .login-side { width: 100% !important; }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  if (checkingSession)
    return (
      <div style={outerContainer}>
        <p style={{ color: "#274472", fontSize: "1.1rem" }}>{t("loading_session")}</p>
      </div>
    );

  return (
    <div style={outerContainer}>
      <div style={frameContainer}>
        {/* 🔹 GIF Izquierdo */}
        <div className="gif-container" style={gifContainer}>
          <img
            src="/evost1.gif"
            alt="Evolvian illustration"
            style={gifStyle}
          />
        </div>

        {/* 🔹 Login Derecho */}
        <div className="login-side" style={loginSide}>
          <div style={cardStyle}>
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

            <h1 style={titleStyle}>Evolvian</h1>

            <form
              onSubmit={handleEmailLogin}
              style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
            >
              <div style={inputWrapperStyle}>
                <input
                  type="email"
                  placeholder={t("email")}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  style={inputStyle}
                  autoComplete="email"
                />
              </div>

              <div style={inputWrapperStyle}>
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder={t("password")}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  style={inputStyle}
                  autoComplete="current-password"
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
                <p
                  style={{
                    color: "#e63946",
                    textAlign: "center",
                    fontSize: "0.875rem",
                  }}
                >
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

            <p style={footerTextStyle}>
              {t("no_account")}{" "}
              <Link to="/register" style={registerLinkStyle}>
                {t("register_here")}
              </Link>
            </p>

            <div style={dividerStyle}>
              <div style={lineStyle} />
              <span style={{ color: "#6b7280" }}>{t("or")}</span>
              <div style={lineStyle} />
            </div>

            <button onClick={handleGoogleLogin} style={googleButtonStyle}>
              <FaGoogle />
              {t("login_with_google")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* 🎨 Estilos */
const outerContainer = {
  height: "100vh",
  width: "100vw",
  backgroundColor: "#ededed", // gris Evolvian
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "Inter, system-ui, sans-serif",
};

const frameContainer = {
  display: "flex",
  flexDirection: "row",
  width: "200%",
  maxWidth: "1100px",
  height: "700px",
  backgroundColor: "#ffffff",
  borderRadius: "20px",
  overflow: "hidden",
  boxShadow: "0 8px 40px rgba(39,68,114,0.15)",
  border: "1px solid #e5e7eb",
};

const gifContainer = {
  width: "50%",
  backgroundColor: "transparent",
  display: "flex",
  alignItems: "stretch",
  justifyContent: "center",
  padding: "1rem",
};

const gifStyle = {
  width: "130%",
  height: "100%",
  objectFit: "contain",
  borderRadius: "20px 20px 20px 20px",
};

const loginSide = {
  width: "50%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "2rem",
  backgroundColor: "#ffffff",
};

const cardStyle = {
  width: "100%",
  maxWidth: "350px",
  textAlign: "center",
};

const logoWrapper = {
  display: "flex",
  justifyContent: "center",
  marginBottom: "1.2rem",
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
  fontSize: "1.6rem",
  fontWeight: "700",
  color: "#274472",
  marginBottom: "1.8rem",
};

const inputWrapperStyle = {
  display: "flex",
  alignItems: "center",
  borderRadius: "8px",
  border: "1px solid #d1d5db",
  backgroundColor: "#f9fafb",
  height: "42px",
  paddingRight: "0.75rem",
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem 1rem",
  backgroundColor: "transparent",
  border: "none",
  outline: "none",
  color: "#1b2a41",
  fontSize: "1rem",
};

const eyeIconWrapperStyle = {
  color: "#6b7280",
  cursor: "pointer",
  fontSize: "1.1rem",
};

const primaryButtonStyle = {
  backgroundColor: "#4a90e2",
  padding: "0.8rem",
  color: "white",
  borderRadius: "8px",
  fontWeight: "600",
  border: "none",
  cursor: "pointer",
  fontSize: "1rem",
  marginTop: "0.5rem",
};

const optionsContainerStyle = {
  display: "flex",
  justifyContent: "space-between",
  fontSize: "0.875rem",
  color: "#6b7280",
  marginTop: "0.75rem",
};

const linkStyle = {
  color: "#4a90e2",
  textDecoration: "underline",
};

const footerTextStyle = {
  textAlign: "center",
  fontSize: "0.875rem",
  color: "#6b7280",
  marginTop: "2rem",
};

const registerLinkStyle = {
  color: "#f5a623",
  fontWeight: "600",
  textDecoration: "underline",
};

const dividerStyle = {
  display: "flex",
  alignItems: "center",
  gap: "1rem",
  margin: "2rem 0",
};

const lineStyle = {
  flex: 1,
  height: "1px",
  backgroundColor: "#e5e7eb",
};

const googleButtonStyle = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "0.5rem",
  padding: "0.8rem",
  border: "1px solid #4a90e2",
  borderRadius: "8px",
  backgroundColor: "#fff",
  color: "#274472",
  cursor: "pointer",
  fontSize: "1rem",
  fontWeight: "500",
};
