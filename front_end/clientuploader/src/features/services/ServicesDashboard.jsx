import { useLanguage } from "../../contexts/LanguageContext";

export default function ServicesDashboard() {
  const { t } = useLanguage();

  return (
    <div style={{ padding: "2rem" }}>
      <h2 style={{ color: "#274472" }}>🧰 {t("services_available_title")}</h2>
      <ul style={{ marginTop: "1rem", fontSize: "1.1rem" }}>
        <li>🧠 Chat Assistant</li>
        <li>✉️ Email</li>
        <li>💬 WhatsApp</li>
        <li>🗓️ Appointments</li>
      </ul>
      <p style={{ marginTop: "1rem", color: "#666" }}>
        {t("services_use_sidebar")}
      </p>
    </div>
  );
}
