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

const safeStorageGet = (key) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

const safeStorageSet = (key, value) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    // no-op when storage is unavailable
  }
};

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    const stored = safeStorageGet("lang");
    return normalizeLang(stored);
  });

  useEffect(() => {
    let isMounted = true;

    const resolveLanguage = async () => {
      const storedLang = normalizeLang(safeStorageGet("lang"));
      const clientId = safeStorageGet("client_id");

      if (!clientId || clientId === "undefined" || clientId === "null") {
        if (isMounted) {
          setLang(storedLang);
          safeStorageSet("lang", storedLang);
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
          safeStorageSet("lang", backendLang);
        }
      } catch (error) {
        console.warn("⚠️ Falling back to local language setting:", error);
        // If there is no active session or backend is unavailable, keep local fallback.
        if (isMounted) {
          setLang(storedLang);
          safeStorageSet("lang", storedLang);
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
    safeStorageSet("lang", validLang);

    const clientId = safeStorageGet("client_id");
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
