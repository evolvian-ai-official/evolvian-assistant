import { useState } from "react";
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
  const navigate = useNavigate();

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
      const checkRes = await fetch("http://localhost:8000/check_email_exists", {
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

      const initRes = await fetch("http://localhost:8000/initialize_user", {
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
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <img src="/logo-evolvian.svg" alt="Logo Evolvian" style={{ width: "64px", margin: "0 auto 1rem" }} />
          <h1 style={{ fontSize: "1.75rem", fontWeight: "bold" }}>{t("create_account")}</h1>
        </div>

        <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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

          <p style={hintTextStyle}>{t("password_hint")}</p>

          <div style={inputWrapperStyle}>
            <input
              type="password"
              placeholder={t("confirm_password") || "Confirmar contraseña"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              style={{ ...inputStyle, border: "none", flex: 1 }}
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
  background: "transparent",
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

const hintTextStyle = {
  fontSize: "0.75rem",
  color: "#ccc",
  marginTop: "-0.5rem",
  marginBottom: "0.5rem",
  paddingLeft: "0.25rem",
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

const registerLinkStyle = {
  color: "#f5a623",
  fontWeight: "bold",
  textDecoration: "underline",
};
