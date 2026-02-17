// src/pages/PrivateWelcomeRoute.jsx
import { Navigate } from "react-router-dom";
import { useInitializeUser } from "../hooks/useInitializeUser";
import { useLanguage } from "../contexts/LanguageContext";

export default function PrivateWelcomeRoute({ children }) {
  const { loading, session, isNewUser } = useInitializeUser();
  const { t } = useLanguage();

  if (loading) {
    return <div style={{ color: "white", padding: "2rem" }}>{t("loading")}</div>;
  }

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  if (isNewUser) {
    return children;
  } else {
    return <Navigate to="/dashboard" replace />;
  }
}
