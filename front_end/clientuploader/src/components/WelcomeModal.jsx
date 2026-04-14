import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useLanguage } from "../contexts/LanguageContext";
import countries from "../assets/countries.json";
import { authFetch, getAuthHeaders } from "../lib/authFetch";
import {
  BUSINESS_SECTOR_OPTIONS,
  CHANNEL_OPTIONS,
  COMPANY_SIZE_OPTIONS,
  DISCOVERY_SOURCE_OPTIONS,
  ROLE_OPTIONS,
  WELCOME_INDUSTRY_TEMPLATES,
  findTemplateByIndustry,
  getLocalizedOptions,
} from "../lib/onboardingOptions";

/* ================================
   Data
================================ */

/* ================================
   Styles
================================ */

const overlayStyle = {
  position: "fixed",
  inset: 0,
  background: "rgba(15, 28, 46, 0.75)",
  backdropFilter: "blur(8px)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 9999,
  padding: "1rem",
};

const modalStyle = {
  background: "#1b2a41",
  border: "2px solid #274472",
  borderRadius: "20px",
  padding: "2rem",
  width: "100%",
  maxWidth: "850px",
  maxHeight: "90vh",
  overflowY: "auto",
  color: "#fff",
  boxShadow: "0 12px 32px rgba(0,0,0,0.45)",
};

const progressBarContainer = {
  height: "6px",
  background: "#274472",
  borderRadius: "6px",
  marginBottom: "1.5rem",
};

const progressBar = (step) => ({
  height: "100%",
  width: `${(step / 4) * 100}%`,
  background: "#a3d9b1",
  borderRadius: "6px",
  transition: "width 0.3s ease",
});

const titleStyle = {
  fontSize: "1.8rem",
  color: "#a3d9b1",
  marginBottom: "0.8rem",
};

const textStyle = {
  fontSize: "0.95rem",
  color: "#ededed",
  marginBottom: "1.2rem",
  lineHeight: 1.6,
};

const inputStyle = {
  padding: "0.75rem",
  borderRadius: "10px",
  border: "1px solid #4a90e2",
  backgroundColor: "#0f1c2e",
  color: "white",
  outline: "none",
  width: "100%",
};

const formGrid = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))",
  gap: "1rem",
};

const checkboxLabel = {
  fontSize: "0.9rem",
  marginBottom: "0.6rem",
  display: "block",
  cursor: "pointer",
};

const linkStyle = {
  color: "#4a90e2",
  textDecoration: "underline",
};

const primaryBtn = (disabled=false) => ({
  background: disabled ? "#274472" : "#2eb39a",
  color: disabled ? "#bbb" : "#fff",
  padding: "10px 22px",
  borderRadius: "8px",
  fontWeight: 600,
  border: "none",
  cursor: disabled ? "not-allowed" : "pointer",
});

const secondaryBtn = {
  background: "#4b5563",
  color: "#fff",
  padding: "10px 22px",
  borderRadius: "8px",
  border: "none",
  cursor: "pointer",
};

/* ================================
   Component
================================ */

export default function WelcomeModal({ onClose }) {
  const { t, lang, changeLanguage } = useLanguage();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [settings, setSettings] = useState(null);
  const [selectedLanguage, setSelectedLanguage] = useState(lang || "en");
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  const clientId = localStorage.getItem("client_id");

  const sortedCountries = useMemo(() => {
    if (!Array.isArray(countries)) return [];
    return countries
      .map((c) => (typeof c === "string" ? c : c.name))
      .sort((a, b) => a.localeCompare(b));
  }, []);

  const localizedSectorOptions = useMemo(
    () => getLocalizedOptions(BUSINESS_SECTOR_OPTIONS, selectedLanguage),
    [selectedLanguage]
  );

  const localizedDiscoverySourceOptions = useMemo(
    () => getLocalizedOptions(DISCOVERY_SOURCE_OPTIONS, selectedLanguage),
    [selectedLanguage]
  );

  const [formData, setFormData] = useState({
    contact_name: "",
    company_name: "",
    phone: "",
    industry: "",
    discovery_source: "",
    role: "",
    country: "",
    company_size: "",
    channels: [],
    timezone: "UTC",
  });

  const [agreeTerms, setAgreeTerms] = useState(true);
  const [agreeMarketing, setAgreeMarketing] = useState(true);

  /* ================================
     Load Plan + Verify Onboarding
  ================================= */

  useEffect(() => {
    const init = async () => {
      if (!clientId) return;

      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`
        );
        if (res.ok) {
          const data = await res.json();
          setSettings(data);
          setSelectedLanguage(data?.language || lang || "en");
        }
      } catch (error) {
        console.warn("Unable to load welcome settings", error);
      }

      try {
        const profileRes = await authFetch(
          `${import.meta.env.VITE_API_URL}/profile/${clientId}`
        );
        if (profileRes.ok) {
          const profilePayload = await profileRes.json();
          const profile = profilePayload?.profile || {};
          const terms = profilePayload?.terms || {};

          setFormData((prev) => ({
            ...prev,
            contact_name: profile.contact_name || prev.contact_name,
            company_name: profile.company_name || prev.company_name,
            phone: profile.phone || prev.phone,
            industry: profile.industry || prev.industry,
            discovery_source: profile.discovery_source || prev.discovery_source,
            role: profile.role || prev.role,
            country: profile.country || prev.country,
            company_size: profile.company_size || prev.company_size,
            channels: Array.isArray(profile.channels) ? profile.channels : prev.channels,
            timezone: profilePayload?.timezone || prev.timezone,
          }));

          setSelectedTemplate(findTemplateByIndustry(profile.industry)?.id || null);

          if (typeof terms.accepted === "boolean") {
            setAgreeTerms(Boolean(terms.accepted));
          }
          if (typeof terms.accepted_marketing === "boolean") {
            setAgreeMarketing(Boolean(terms.accepted_marketing));
          }
        }
      } catch (error) {
        console.warn("Unable to load onboarding profile", error);
      }

    };

    init();
  }, [clientId, lang]);

  /* ================================
     Handlers
  ================================= */

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (name === "industry") {
      setSelectedTemplate(findTemplateByIndustry(value)?.id || null);
    }
    setError(null);
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const toggleChannel = (channel) => {
    setFormData((prev) => ({
      ...prev,
      channels: prev.channels.includes(channel)
        ? prev.channels.filter((c) => c !== channel)
        : [...prev.channels, channel],
    }));
  };

  const validateProfile = () => {
    if (!formData.contact_name || formData.contact_name.trim().length < 2) {
      setError(t("welcome_full_name_required"));
      return false;
    }
    return true;
  };

  const validateBusinessSetup = () => {
    if (!formData.industry) {
      setError(
        selectedLanguage === "es"
          ? "Selecciona el sector de tu negocio."
          : "Please select your business sector."
      );
      return false;
    }

    if (!formData.discovery_source) {
      setError(
        selectedLanguage === "es"
          ? "Selecciona por cual medio nos encontraste."
          : "Please select how you found us."
      );
      return false;
    }

    return true;
  };

  const handleNext = () => {
    setError(null);
    if (step === 1 && !validateBusinessSetup()) return;
    if (step === 2 && !validateProfile()) return;
    setStep((prev) => prev + 1);
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError(null);

      if (!clientId) throw new Error("Missing client_id");

      const cleanedProfile = {
        ...formData,
        company_name: formData.company_name?.trim() || null,
        phone: formData.phone?.trim() || null,
        industry: formData.industry || null,
        discovery_source: formData.discovery_source || null,
        role: formData.role || null,
        country: formData.country || null,
        company_size: formData.company_size || null,
        timezone: formData.timezone || "UTC",
      };

      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/complete_onboarding`,
        {
          method: "POST",
          headers: await getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            client_id: clientId,
            profile: cleanedProfile,
            terms: {
              accepted: agreeTerms,
              accepted_marketing: agreeMarketing,
            },
          }),
        }
      );

      if (!res.ok) throw new Error(t("onboarding_failed"));
      const languageRes = await authFetch(
        `${import.meta.env.VITE_API_URL}/client_settings`,
        {
          method: "POST",
          headers: await getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            client_id: clientId,
            language: selectedLanguage,
            timezone: cleanedProfile.timezone || "UTC",
          }),
        }
      );

      if (!languageRes.ok) throw new Error(t("language_update_failed"));

      await changeLanguage(selectedLanguage);

      if (onClose) onClose();
      navigate("/dashboard", { replace: true });

    } catch (err) {
      console.error(err);
      setError(t("something_went_wrong_retry"));
    } finally {
      setLoading(false);
    }
  };

  /* ================================
     Render
  ================================= */

  const renderContent = () => {
    switch (step) {
      case 1:
        return (
          <>
            <img src="/logo-evolvian.svg" style={{ width: "70px", marginBottom: "1rem" }} />
            <h2 style={titleStyle}>{t("welcome_to_evolvian")}</h2>
            <p style={textStyle}>
              {t("welcome_setup_under_2_minutes")}
            </p>
            <div style={{ maxWidth: 320, margin: "0.75rem auto 0", textAlign: "left" }}>
              <label style={{ ...checkboxLabel, marginBottom: "0.5rem" }}>
                {t("preferred_language")}
              </label>
              <select
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                style={inputStyle}
              >
                <option value="en">{t("english")}</option>
                <option value="es">{t("spanish")}</option>
              </select>
            </div>

            <div style={{ marginTop: "2rem", textAlign: "left" }}>
              <p style={{ ...textStyle, fontWeight: 600, marginBottom: "1rem" }}>
                {selectedLanguage === "es" ? "¿En qué sector trabajas?" : "What sector are you in?"}
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "0.75rem" }}>
                {WELCOME_INDUSTRY_TEMPLATES.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => {
                      setError(null);
                      setSelectedTemplate(template.id);
                      setFormData((prev) => ({
                        ...prev,
                        industry: template.industry,
                        channels: template.channels,
                      }));
                    }}
                    style={{
                      background: selectedTemplate === template.id ? "#2eb39a" : "#0f1c2e",
                      border: `2px solid ${selectedTemplate === template.id ? "#2eb39a" : "#274472"}`,
                      borderRadius: "12px",
                      padding: "1rem",
                      cursor: "pointer",
                      textAlign: "left",
                      color: "#fff",
                      transition: "all 0.2s ease",
                    }}
                  >
                    <div style={{ fontSize: "1.5rem", marginBottom: "0.4rem" }}>{template.icon}</div>
                    <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                      {selectedLanguage === "es" ? template.labelEs : template.labelEn}
                    </div>
                    <div style={{ fontSize: "0.78rem", color: selectedTemplate === template.id ? "#e0f5ef" : "#b0c4d8", marginTop: "0.25rem" }}>
                      {selectedLanguage === "es" ? template.descEs : template.descEn}
                    </div>
                  </button>
                ))}
              </div>
              <div style={{ ...formGrid, marginTop: "1rem" }}>
                <div>
                  <label style={{ ...checkboxLabel, marginBottom: "0.5rem" }}>
                    {selectedLanguage === "es" ? "Sector de tu negocio" : "Business sector"}
                  </label>
                  <select
                    name="industry"
                    value={formData.industry}
                    onChange={handleChange}
                    style={inputStyle}
                  >
                    <option value="">
                      {selectedLanguage === "es" ? "Selecciona tu sector" : "Select your sector"}
                    </option>
                    {localizedSectorOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ ...checkboxLabel, marginBottom: "0.5rem" }}>
                    {selectedLanguage === "es" ? "¿Cómo nos encontraste?" : "How did you find us?"}
                  </label>
                  <select
                    name="discovery_source"
                    value={formData.discovery_source}
                    onChange={handleChange}
                    style={inputStyle}
                  >
                    <option value="">
                      {selectedLanguage === "es" ? "Selecciona un medio" : "Select a source"}
                    </option>
                    {localizedDiscoverySourceOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {selectedTemplate && (
                <p style={{ marginTop: "0.75rem", fontSize: "0.82rem", color: "#a3d9b1", textAlign: "center" }}>
                  {selectedLanguage === "es"
                    ? "✓ Perfecto — configuraremos Evolvian para tu negocio"
                    : "✓ Great — we'll configure Evolvian for your business"}
                </p>
              )}
              {error && <p style={{ color: "#f87171", marginTop: "1rem" }}>{error}</p>}
            </div>
          </>
        );

      case 2:
        return (
          <>
            <h2 style={titleStyle}>{t("company_profile")}</h2>

            <div style={formGrid}>
              <input name="contact_name" placeholder={t("full_name")} value={formData.contact_name} onChange={handleChange} style={inputStyle}/>
              <input name="company_name" placeholder={t("company_name_optional")} value={formData.company_name} onChange={handleChange} style={inputStyle}/>
              <input name="phone" placeholder={t("phone_optional")} value={formData.phone} onChange={handleChange} style={inputStyle}/>
              
              <select name="industry" value={formData.industry} onChange={handleChange} style={inputStyle}>
                <option value="">{t("industry")}</option>
                {localizedSectorOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              <select name="role" value={formData.role} onChange={handleChange} style={inputStyle}>
                <option value="">{t("role")}</option>
                {ROLE_OPTIONS.map((role) => <option key={role}>{role}</option>)}
              </select>

              <select name="country" value={formData.country} onChange={handleChange} style={inputStyle}>
                <option value="">{t("country")}</option>
                {sortedCountries.map((c) => <option key={c}>{c}</option>)}
              </select>

              <select name="company_size" value={formData.company_size} onChange={handleChange} style={inputStyle}>
                <option value="">{t("company_size")}</option>
                {COMPANY_SIZE_OPTIONS.map((companySize) => <option key={companySize}>{companySize}</option>)}
              </select>
            </div>

            <div style={{ marginTop: "1.5rem", textAlign: "left" }}>
              <p style={{ marginBottom: "0.5rem" }}>{t("interested_channels")}</p>
              {CHANNEL_OPTIONS.map((channel) => (
                <label key={channel} style={checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={formData.channels.includes(channel)}
                    onChange={() => toggleChannel(channel)}
                    style={{ marginRight: "0.5rem" }}
                  />
                  {channel}
                </label>
              ))}
            </div>
          </>
        );

      case 3:
        return (
          <>
            <h2 style={titleStyle}>{t("terms_and_conditions")}</h2>

            <p style={textStyle}>
              {t("please_review_our")}{" "}
              <a href="https://evolvianai.net/terms" target="_blank" rel="noopener noreferrer" style={linkStyle}>
                {t("terms_and_conditions")}
              </a>.
            </p>

            <label style={checkboxLabel}>
              <input type="checkbox" checked={agreeTerms} onChange={() => setAgreeTerms(!agreeTerms)} />
              {t("agree_terms_conditions")}
            </label>

            <label style={checkboxLabel}>
              <input type="checkbox" checked={agreeMarketing} onChange={() => setAgreeMarketing(!agreeMarketing)} />
              {t("agree_marketing_emails")}
            </label>

            {error && <p style={{ color: "#f87171", marginTop: "1rem" }}>{error}</p>}
          </>
        );

      case 4:
        return settings && (
          <>
            <img src="/logo-evolvian.svg" style={{ width: "60px", marginBottom: "1rem" }} />
            <h2 style={titleStyle}>
              {lang === "es" ? "¡Todo listo! Tu recepcionista AI está configurada" : "All set! Your AI receptionist is ready"}
            </h2>
            <p style={textStyle}>
              {lang === "es"
                ? "Estás en el plan"
                : "You are on the"}{" "}
              <strong style={{ color: "#a3d9b1" }}>{settings.plan?.name}</strong>
              {lang === "es" ? "." : " plan."}
            </p>
            <div style={{ marginTop: "1rem", display: "grid", gap: "0.6rem" }}>
              {[
                lang === "es"
                  ? "📄 Sube los documentos de tu clínica (servicios, precios, FAQ)"
                  : "📄 Upload your clinic documents (services, pricing, FAQ)",
                lang === "es"
                  ? "📱 Conecta tu WhatsApp Business en Configuración → Meta Apps"
                  : "📱 Connect your WhatsApp Business in Settings → Meta Apps",
                lang === "es"
                  ? "🗓️ Activa el agendamiento de citas en Configuración → Citas"
                  : "🗓️ Enable appointment booking in Settings → Appointments",
              ].map((step, i) => (
                <div
                  key={i}
                  style={{
                    background: "#0f1c2e",
                    border: "1px solid #274472",
                    borderRadius: "10px",
                    padding: "0.75rem 1rem",
                    fontSize: "0.88rem",
                    color: "#ededed",
                    textAlign: "left",
                  }}
                >
                  {step}
                </div>
              ))}
            </div>
          </>
        );

      default:
        return null;
    }
  };

  return (
    <div style={overlayStyle}>
      <div style={modalStyle}>
        <div style={progressBarContainer}>
          <div style={progressBar(step)} />
        </div>

        {renderContent()}

        <div style={{ marginTop: "2rem", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
          {step > 1 && (
            <button style={secondaryBtn} onClick={() => setStep(step - 1)}>
              {t("back")}
            </button>
          )}

          {step < 4 ? (
            <button style={primaryBtn()} onClick={handleNext}>
              {t("next")}
            </button>
          ) : (
            <button style={primaryBtn(loading)} disabled={loading} onClick={handleSubmit}>
              {loading ? t("saving") : t("start")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
