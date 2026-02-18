import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { FaEye, FaEyeSlash } from "react-icons/fa";
import AuthLayout from "../components/ui/AuthLayout";
import { supabase } from "../lib/supabaseClient";
import { useLanguage } from "../contexts/LanguageContext";

export default function Register() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

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
        toast.error(`${t("error_creating_account")}: ${error.message}`);
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

      if (!data.session) {
        toast.success(t("account_created_check_email"));
        setTimeout(() => navigate("/login"), 3000);
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
    <AuthLayout>
      <div className="auth-card auth-card--wide">
        <div className="auth-logo-wrap">
          <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="auth-logo" />
        </div>

        <h1 className="auth-title">{t("create_account")}</h1>

        <form onSubmit={handleRegister} className="auth-form">
          <div className="auth-field">
            <input
              type="email"
              placeholder={t("email")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="auth-input"
            />
          </div>

          <div className="auth-field">
            <input
              type={showPassword ? "text" : "password"}
              placeholder={t("password")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="auth-input"
            />
            <button
              type="button"
              className="auth-icon-btn"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((prev) => !prev)}
            >
              {showPassword ? <FaEyeSlash /> : <FaEye />}
            </button>
          </div>

          <p className="auth-help">{t("password_hint")}</p>

          <div className="auth-field">
            <input
              type="password"
              placeholder={t("confirm_password") || "Confirm password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="auth-input"
            />
          </div>

          <button type="submit" className="auth-btn auth-btn-primary">
            {t("create_account")}
          </button>
        </form>

        <p className="auth-note">
          {t("already_have_account")}{" "}
          <Link to="/login" className="auth-note-inline">
            {t("login_here")}
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
