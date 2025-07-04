import { createContext, useContext, useEffect, useState } from "react";
import { translations } from "../lib/i18n";

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(null); // ⚠️ null al inicio para evitar render hasta detectar

  const normalizeLang = (l) => {
    if (!l) return "en";
    if (l.startsWith("es")) return "es";
    return "en";
  };

  useEffect(() => {
    const storedLang = localStorage.getItem("lang");
    const browserLang = navigator.language;

    const finalLang = normalizeLang(storedLang || browserLang);
    setLang(finalLang);
    localStorage.setItem("lang", finalLang);
  }, []);

  const t = (key) => {
    const langKey = normalizeLang(lang);
    const value = translations[langKey]?.[key];
    if (typeof value !== "string") {
      console.warn(`⚠️ Traducción inválida o faltante para key "${key}" en idioma "${langKey}"`, value);
      return key;
    }
    return value;
  };

  const changeLanguage = (newLang) => {
    const validLang = normalizeLang(newLang);
    setLang(validLang);
    localStorage.setItem("lang", validLang);
  };

  // Mientras lang está en null, no renderizamos nada (previene parpadeo de idioma)
  if (!lang) return null;

  return (
    <LanguageContext.Provider value={{ lang, t, changeLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
