import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import AuthLayout from "../components/ui/AuthLayout";
import { supabase } from "../lib/supabaseClient";
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
      console.error("Error sending reset email:", error.message);
      toast.error(t("error_sending_reset_email"));
      return;
    }

    toast.success(t("check_your_email"));
  };

  return (
    <AuthLayout>
      <div className="auth-card auth-card--wide">
        <div className="auth-logo-wrap">
          <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="auth-logo" />
        </div>

        <h1 className="auth-title">{t("recover_password")}</h1>
        <p className="auth-subtitle">{t("enter_your_email")}</p>

        <form onSubmit={handleReset} className="auth-form">
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

          <button type="submit" className="auth-btn auth-btn-primary">
            {t("send_email")}
          </button>
        </form>

        <p className="auth-note">
          {t("already_have_access")}{" "}
          <Link to="/login" className="auth-note-inline">
            {t("login")}
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
