import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";
import { useLanguage } from "../contexts/LanguageContext";
import { FaEye, FaEyeSlash } from "react-icons/fa";

export default function Register() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [animateLogo, setAnimateLogo] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setTimeout(() => setAnimateLogo(true), 100);

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
  }, []);

  const handleRegister = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast.error(t("passwords_do_not_match") || "Las contraseñas no coinciden");
      return;
    }

    const passwordRegex = /^[A-Za-z0-9]{8,}$/;
    if (!passwordRegex.test(password)) {
      toast.error(`${t("invalid_password_format")} ${t("password_hint")}`);
      return;
    }

    try {
      const checkRes = await fetch(`${import.meta.env.VITE_API_URL}/check_email_exists`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      const checkData = await checkRes.json();
      if (checkData.exists) {
        toast.error(`${t("email_already_registered")} ${checkData.provider}`);
        return;
      }

      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) {
        toast.error(t("error_creating_account") + ": " + error.message);
        return;
      }

      if (!data.session) {
        toast.success(t("account_created_check_email"));
        setTimeout(() => navigate("/login"), 3000);
        return;
      }

      const initRes = await fetch(`${import.meta.env.VITE_API_URL}/initialize_user`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auth_user_id: data.user.id,
          email: data.user.email,
        }),
      });

      if (!initRes.ok) {
        toast.error(t("error_initializing_account"));
        return;
      }

      toast.success(t("account_created_redirecting"));
      setTimeout(() => navigate("/dashboard"), 2000);
    } catch (err) {
      console.error(err);
      toast.error(t("unexpected_error"));
    }
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        {/* 🔹 Logo circular degradado con animación */}
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

        <h1 style={titleStyle}>{t("create_account")}</h1>

        <form
          onSubmit={handleRegister}
          style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1.5rem" }}
        >
          <div style={inputWrapperStyle}>
            <input
              type="email"
              placeholder={t("email")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={inputStyle}
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
            />
            <div
              style={eyeIconWrapperStyle}
              onMouseEnter={() => setShowPassword(true)}
              onMouseLeave={() => setShowPassword(false)}
            >
              {showPassword ? <FaEyeSlash /> : <FaEye />}
            </div>
          </div>

          <p style={hintTextStyle}>{t("password_hint")}</p>

          <div style={inputWrapperStyle}>
            <input
              type="password"
              placeholder={t("confirm_password") || "Confirm password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              style={inputStyle}
            />
          </div>

          <button type="submit" style={primaryButtonStyle}>
            {t("create_account")}
          </button>
        </form>

        <p style={footerTextStyle}>
          {t("already_have_account")}{" "}
          <Link to="/login" style={registerLinkStyle}>
            {t("login_here")}
          </Link>
        </p>
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
  marginBottom: "0.5rem",
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

const hintTextStyle = {
  fontSize: "0.75rem",
  color: "#6b7280",
  marginTop: "-0.5rem",
  marginBottom: "0.5rem",
  textAlign: "left",
  paddingLeft: "0.25rem",
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
