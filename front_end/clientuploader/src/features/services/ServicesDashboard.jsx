import { useLanguage } from "../../contexts/LanguageContext";
import "../../components/ui/internal-admin-responsive.css";

export default function ServicesDashboard() {
  const { t } = useLanguage();

  return (
    <div className="ia-page">
      <div className="ia-shell ia-services-shell">
        <section className="ia-card" style={{ marginBottom: 0 }}>
          <h2 className="ia-services-title">🧰 {t("services_available_title")}</h2>
          <p className="ia-services-subtitle">{t("services_use_sidebar")}</p>

          <div className="ia-services-grid">
            <div className="ia-service-item">🧠 {t("chat_assistant")}</div>
            <div className="ia-service-item">✉️ {t("email")}</div>
            <div className="ia-service-item">💬 {t("whatsapp")}</div>
            <div className="ia-service-item">🗓️ {t("appointments_nav")}</div>
          </div>
        </section>
      </div>
    </div>
  );
}
