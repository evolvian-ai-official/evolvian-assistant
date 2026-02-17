// src/pages/NotFound.jsx
import { useLanguage } from "../contexts/LanguageContext";

export default function NotFound() {
  const { t } = useLanguage();
  return (
    <div style={{ padding: "2rem" }}>
      <h2>{t("not_found_title")}</h2>
      <p>{t("not_found_description")}</p>
    </div>
  );
}
