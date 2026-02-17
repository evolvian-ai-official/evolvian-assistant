import { createContext, useContext, useEffect, useState } from "react";
import { translations } from "../lib/i18n";
import { authFetch } from "../lib/authFetch";

const LanguageContext = createContext();
const SUPPORTED_LANGUAGES = ["en", "es"];
const FALLBACK_LANGUAGE = "en";

const normalizeLang = (lang) => {
  if (!lang || typeof lang !== "string") return FALLBACK_LANGUAGE;
  const lowered = lang.toLowerCase();
  return SUPPORTED_LANGUAGES.includes(lowered) ? lowered : FALLBACK_LANGUAGE;
};

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    const stored = localStorage.getItem("lang");
    return normalizeLang(stored);
  });

  useEffect(() => {
    let isMounted = true;

    const resolveLanguage = async () => {
      const storedLang = normalizeLang(localStorage.getItem("lang"));
      const clientId = localStorage.getItem("client_id");

      if (!clientId || clientId === "undefined" || clientId === "null") {
        if (isMounted) {
          setLang(storedLang);
          localStorage.setItem("lang", storedLang);
        }
        return;
      }

      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`
        );

        if (!res.ok) throw new Error("Failed to fetch client settings language");
        const data = await res.json();
        const backendLang = normalizeLang(data?.language);

        if (isMounted) {
          setLang(backendLang);
          localStorage.setItem("lang", backendLang);
        }
      } catch (error) {
        // If there is no active session or backend is unavailable, keep local fallback.
        if (isMounted) {
          setLang(storedLang);
          localStorage.setItem("lang", storedLang);
        }
      }
    };

    resolveLanguage();

    return () => {
      isMounted = false;
    };
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

  const changeLanguage = async (newLang) => {
    const validLang = normalizeLang(newLang);
    setLang(validLang);
    localStorage.setItem("lang", validLang);

    const clientId = localStorage.getItem("client_id");
    if (!clientId || clientId === "undefined" || clientId === "null") return;

    try {
      await authFetch(`${import.meta.env.VITE_API_URL}/client_settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          language: validLang,
        }),
      });
    } catch (error) {
      console.error("❌ Error persisting language:", error);
    }
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
