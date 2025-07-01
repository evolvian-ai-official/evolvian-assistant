import { useLanguage } from "../../contexts/LanguageContext";

export default function WidgetSettings({ activeTab, require_email, require_phone, require_terms, onChange }) {
  const { t } = useLanguage();
  if (activeTab !== "widget") return null;

  return (
    <div style={{ marginTop: "2rem" }}>
      <h4 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#274472", marginBottom: "1rem" }}>
        💬 {t("chat_widget")} & IFRAME
      </h4>

      <div>
        <label>
          <input
            type="checkbox"
            name="require_email"
            checked={require_email}
            onChange={onChange}
          /> {t("require_email")}
        </label>
      </div>

      <div>
        <label>
          <input
            type="checkbox"
            name="require_phone"
            checked={require_phone}
            onChange={onChange}
          /> {t("require_phone")}
        </label>
      </div>

      <div>
        <label>
          <input
            type="checkbox"
            name="require_terms"
            checked={require_terms}
            onChange={onChange}
          /> {t("require_terms")}
        </label>
      </div>
    </div>
  );
}
