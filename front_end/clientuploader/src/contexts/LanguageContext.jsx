// src/contexts/LanguageContext.jsx
import { createContext, useContext, useEffect, useState } from "react";
import { translations } from "../lib/i18n";

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState("en"); // Default English

  useEffect(() => {
    const storedLang = localStorage.getItem("lang");
    if (storedLang) {
      setLang(storedLang);
    } else {
      // Detect from browser
      const browserLang = navigator.language.startsWith("es") ? "es" : "en";
      setLang(browserLang);
      localStorage.setItem("lang", browserLang);
    }
  }, []);

  const t = (key) => {
    return translations[lang]?.[key] || key;
  };

  const changeLanguage = (newLang) => {
    setLang(newLang);
    localStorage.setItem("lang", newLang);
  };

  return (
    <LanguageContext.Provider value={{ lang, t, changeLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
