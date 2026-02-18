import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AuthLayout from "../components/ui/AuthLayout";
import { useLanguage } from "../contexts/LanguageContext";

export default function Confirm() {
  const { t } = useLanguage();
  const navigate = useNavigate();

  useEffect(() => {
    const timeout = setTimeout(() => {
      navigate("/login");
    }, 4000);
    return () => clearTimeout(timeout);
  }, [navigate]);

  return (
    <AuthLayout>
      <div className="auth-card auth-card--wide">
        <div className="auth-logo-wrap">
          <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="auth-logo" />
        </div>

        <h2 className="auth-title">✅ {t("email_confirmed_successfully")}</h2>
        <p className="auth-subtitle" style={{ marginTop: "0.3rem" }}>
          {t("redirecting_to_login")}
        </p>
      </div>
    </AuthLayout>
  );
}
