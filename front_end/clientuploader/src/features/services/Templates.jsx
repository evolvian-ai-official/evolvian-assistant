import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import CreateTemplateModal from "./CreateTemplateModal";
import TemplatesList from "./TemplatesList";
import { authFetch } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

export default function Templates() {
  const clientId = useClientId();
  const { t, lang } = useLanguage();
  const isEs = lang === "es";
  const [showModal, setShowModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [templateLanguage, setTemplateLanguage] = useState("es");
  const [pendingTemplateLanguage, setPendingTemplateLanguage] = useState(null);
  const [showLanguageConfirmModal, setShowLanguageConfirmModal] = useState(false);
  const [templateLanguageLoading, setTemplateLanguageLoading] = useState(false);
  const [templateLanguageSaving, setTemplateLanguageSaving] = useState(false);
  const API = import.meta.env.VITE_API_URL;

  useEffect(() => {
    if (!clientId) return;
    let active = true;
    const load = async () => {
      setTemplateLanguageLoading(true);
      try {
        const res = await authFetch(`${API}/client_settings?client_id=${clientId}`);
        const data = await res.json().catch(() => ({}));
        if (!active) return;
        const nextLang =
          String(
            data?.appointments_template_language || "es"
          ).toLowerCase().startsWith("en")
            ? "en"
            : "es";
        setTemplateLanguage(nextLang);
      } catch {
        if (active) setTemplateLanguage("es");
      } finally {
        if (active) setTemplateLanguageLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [API, clientId]);

  const persistTemplateLanguage = async (nextLanguage) => {
    if (!clientId) return;
    setTemplateLanguage(nextLanguage);
    setTemplateLanguageSaving(true);
    try {
      const res = await authFetch(`${API}/client_settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          appointments_template_language: nextLanguage,
        }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setRefreshKey((k) => k + 1);
    } catch (err) {
      console.error("Failed saving template language", err);
    } finally {
      setTemplateLanguageSaving(false);
    }
  };

  const languageLabel = (value) => (value === "en" ? "English" : "Español");

  const requestTemplateLanguageChange = (nextLanguage) => {
    if (!nextLanguage || nextLanguage === templateLanguage) return;
    setPendingTemplateLanguage(nextLanguage);
    setShowLanguageConfirmModal(true);
  };

  const cancelTemplateLanguageChange = () => {
    setPendingTemplateLanguage(null);
    setShowLanguageConfirmModal(false);
  };

  const confirmTemplateLanguageChange = async () => {
    if (!pendingTemplateLanguage) return;
    const nextLanguage = pendingTemplateLanguage;
    setShowLanguageConfirmModal(false);
    setPendingTemplateLanguage(null);
    await persistTemplateLanguage(nextLanguage);
  };

  return (
    <div className="ia-page">
      <div className="ia-shell ia-services-shell">
        <section className="ia-card" style={{ marginBottom: 0 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: "0.75rem",
              flexWrap: "wrap",
            }}
          >
            <div>
              <h1 className="ia-header-title">📝 {t("templates_title")}</h1>
              <p className="ia-header-subtitle">
                Email templates are created here. WhatsApp templates are synced from Meta and tracked by status.
              </p>
              <div style={{ marginTop: "0.65rem", display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                <label className="ia-form-label" style={{ margin: 0 }}>
                  Template language
                </label>
                <select
                  className="ia-form-input"
                  style={{ width: "auto", minWidth: 170 }}
                  value={templateLanguage}
                  disabled={templateLanguageLoading || templateLanguageSaving}
                  onChange={(e) => requestTemplateLanguageChange(e.target.value)}
                >
                  <option value="es">Español</option>
                  <option value="en">English</option>
                </select>
                <small style={{ color: "#667085" }}>
                  {templateLanguageSaving
                    ? (isEs ? "Guardando..." : "Saving...")
                    : (isEs
                      ? "Se usa para filtrar templates de Meta y definir el idioma usado por los siguientes appointments."
                      : "Used to filter Meta templates and define the language used for upcoming appointments.")}
                </small>
              </div>
            </div>

            <button onClick={() => setShowModal(true)} className="ia-button ia-button-warning">
              ➕ Create Template
            </button>
          </div>

          <TemplatesList clientId={clientId} refreshKey={refreshKey} selectedLanguage={templateLanguage} />

          {showModal && (
            <CreateTemplateModal
              clientId={clientId}
              selectedLanguage={templateLanguage}
              onClose={() => setShowModal(false)}
              onCreated={() => {
                setShowModal(false);
                setRefreshKey((k) => k + 1);
              }}
            />
          )}

          {showLanguageConfirmModal && (
            <div
              style={{
                position: "fixed",
                inset: 0,
                backgroundColor: "rgba(0,0,0,0.45)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 1200,
                padding: "1rem",
              }}
            >
              <div
                style={{
                  width: "min(92vw, 520px)",
                  background: "#fff",
                  borderRadius: 14,
                  border: "1px solid #E5E7EB",
                  boxShadow: "0 20px 48px rgba(0,0,0,0.18)",
                  padding: "1rem",
                }}
              >
                <h3 style={{ margin: 0, color: "#274472" }}>
                  {isEs ? "¿Seguro que quieres cambiar el idioma?" : "Are you sure you want to change the language?"}
                </h3>
                <p style={{ marginTop: "0.65rem", marginBottom: "0.4rem", color: "#475467", lineHeight: 1.45 }}>
                  {isEs
                    ? "Los siguientes appointments saldrán en el idioma seleccionado. También se filtrarán los templates de Meta por ese idioma."
                    : "The next appointments will use the selected language. Meta templates will also be filtered by that language."}
                </p>
                <div
                  style={{
                    marginTop: "0.6rem",
                    padding: "0.7rem",
                    borderRadius: 10,
                    background: "#F8FAFC",
                    border: "1px solid #E2E8F0",
                    color: "#334155",
                    fontSize: "0.92rem",
                  }}
                >
                  <strong>{isEs ? "Cambio" : "Change"}:</strong> {languageLabel(templateLanguage)} → {languageLabel(pendingTemplateLanguage || templateLanguage)}
                </div>
                <div style={{ marginTop: "0.9rem", display: "flex", justifyContent: "flex-end", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="ia-button ia-button-ghost"
                    onClick={cancelTemplateLanguageChange}
                  >
                    {t("cancel") || (isEs ? "Cancelar" : "Cancel")}
                  </button>
                  <button
                    type="button"
                    className="ia-button ia-button-primary"
                    onClick={confirmTemplateLanguageChange}
                  >
                    {isEs ? "Sí, cambiar idioma" : "Yes, change language"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
