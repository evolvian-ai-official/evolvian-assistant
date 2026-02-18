import { useState } from "react";
import { toast } from "sonner";
import AuthLayout from "../components/ui/AuthLayout";
import { supabase } from "../lib/supabaseClient";
import { useLanguage } from "../contexts/LanguageContext";

export default function VerifyMfa() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSendOtp = async (e) => {
    e.preventDefault();
    setLoading(true);

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        redirectTo: `${window.location.origin}/dashboard`,
      },
    });

    if (error) {
      toast.error(t("error_sending_login_link"));
    } else {
      toast.success(t("check_your_email_login_link"));
      setSuccess(true);
    }

    setLoading(false);
  };

  return (
    <AuthLayout>
      <div className="auth-card auth-card--wide">
        <div className="auth-logo-wrap">
          <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="auth-logo" />
        </div>

        <h1 className="auth-title">{t("access_verification")}</h1>
        <p className="auth-subtitle">{t("confirm_email_to_continue")}</p>

        {success ? (
          <p className="auth-status-success">{t("email_link_sent")}</p>
        ) : (
          <form onSubmit={handleSendOtp} className="auth-form">
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

            <button type="submit" disabled={loading} className="auth-btn auth-btn-primary">
              {loading ? t("sending") : t("send_login_link")}
            </button>
          </form>
        )}
      </div>
    </AuthLayout>
  );
}
