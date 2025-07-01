// src/components/LanguageSwitcher.jsx
import { useLanguage } from "../contexts/LanguageContext";

export default function LanguageSwitcher() {
  const { lang, changeLanguage } = useLanguage();

  return (
    <div style={switcherStyle}>
      <button
        onClick={() => changeLanguage("en")}
        disabled={lang === "en"}
        style={{
          ...buttonStyle,
          backgroundColor: lang === "en" ? "#4a90e2" : "#ededed",
          color: lang === "en" ? "white" : "#274472",
        }}
      >
        English
      </button>
      <button
        onClick={() => changeLanguage("es")}
        disabled={lang === "es"}
        style={{
          ...buttonStyle,
          backgroundColor: lang === "es" ? "#4a90e2" : "#ededed",
          color: lang === "es" ? "white" : "#274472",
        }}
      >
        Español
      </button>
    </div>
  );
}

const switcherStyle = {
  display: "flex",
  justifyContent: "center",
  gap: "0.5rem",
  marginTop: "1rem",
};

const buttonStyle = {
  padding: "0.4rem 0.8rem",
  borderRadius: "8px",
  border: "none",
  fontWeight: "bold",
  cursor: "pointer",
};
