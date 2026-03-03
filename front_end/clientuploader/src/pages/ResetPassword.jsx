import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { FaEye, FaEyeSlash } from "react-icons/fa";
import { toast } from "sonner";
import AuthLayout from "../components/ui/AuthLayout";
import { supabase } from "../lib/supabaseClient";
import { useLanguage } from "../contexts/LanguageContext";

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
      return;
    }
    setTokenLoaded(true);
  }, [navigate, t]);

  const handleUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);

    const { error } = await supabase.auth.updateUser({ password });

    if (error) {
      toast.error(`❌ ${t("error_updating_password")}: ${error.message}`);
    } else {
      const persistedLang = localStorage.getItem("lang");
      await supabase.auth.signOut();
      localStorage.removeItem("client_id");
      localStorage.removeItem("public_client_id");
      localStorage.removeItem("user_id");
      localStorage.removeItem("alreadyRedirected");
      if (persistedLang) localStorage.setItem("lang", persistedLang);
      toast.success(`🔒 ${t("password_updated_successfully")}`);
      navigate("/login?password_updated=1", { replace: true });
      window.location.reload();
    }

    setLoading(false);
  };

  if (!tokenLoaded) return null;

  return (
    <AuthLayout>
      <div className="auth-card auth-card--wide">
        <div className="auth-logo-wrap">
          <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="auth-logo auth-logo--spin" />
        </div>

        <h1 className="auth-title">{t("new_password")}</h1>
        <p className="auth-subtitle">{t("enter_new_password")}</p>

        <form onSubmit={handleUpdate} className="auth-form">
          <div className="auth-field">
            <input
              type={showPassword ? "text" : "password"}
              placeholder={t("new_password_placeholder")}
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

          <button type="submit" disabled={loading} className="auth-btn auth-btn-primary">
            {loading ? t("updating") : t("update_password")}
          </button>
        </form>
      </div>
    </AuthLayout>
  );
}
