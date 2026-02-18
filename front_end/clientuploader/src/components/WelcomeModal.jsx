import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useLanguage } from "../contexts/LanguageContext";
import countries from "../assets/countries.json";
import { authFetch, getAuthHeaders } from "../lib/authFetch";

/* ================================
   Data
================================ */

const industries = [
  "Software","Education","Healthcare","Finance","Retail",
  "Manufacturing","Consulting","Other",
];

const roles = [
  "Founder / CEO","CMO / Marketing Manager","Customer Support",
  "Operations Manager","Sales Executive","IT Manager",
  "Product Manager","Developer / Engineer","HR / People","Other",
];

const channels = ["Chat Widget","WhatsApp","Email","Others"];

const companySizes = [
  "1-10 employees","11-50 employees","51-200 employees",
  "201-500 employees","501-1000 employees","More than 1000 employees",
];

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

  const clientId = localStorage.getItem("client_id");

  const sortedCountries = useMemo(() => {
    if (!Array.isArray(countries)) return [];
    return countries
      .map((c) => (typeof c === "string" ? c : c.name))
      .sort((a, b) => a.localeCompare(b));
  }, []);

  const [formData, setFormData] = useState({
    contact_name: "",
    company_name: "",
    phone: "",
    industry: "",
    role: "",
    country: "",
    company_size: "",
    channels: [],
  });

  const [agreeTerms, setAgreeTerms] = useState(true);
  const [agreeMarketing, setAgreeMarketing] = useState(true);
  const [selectedLanguage, setSelectedLanguage] = useState(lang || "en");

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

    };

    init();
  }, [clientId, lang]);

  /* ================================
     Handlers
  ================================= */

  const handleChange = (e) => {
    const { name, value } = e.target;
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

  const handleNext = () => {
    setError(null);
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
        role: formData.role || null,
        country: formData.country || null,
        company_size: formData.company_size || null,
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
                <option value="en">English</option>
                <option value="es">Español</option>
              </select>
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
                {industries.map((i) => <option key={i}>{i}</option>)}
              </select>

              <select name="role" value={formData.role} onChange={handleChange} style={inputStyle}>
                <option value="">{t("role")}</option>
                {roles.map((r) => <option key={r}>{r}</option>)}
              </select>

              <select name="country" value={formData.country} onChange={handleChange} style={inputStyle}>
                <option value="">{t("country")}</option>
                {sortedCountries.map((c) => <option key={c}>{c}</option>)}
              </select>

              <select name="company_size" value={formData.company_size} onChange={handleChange} style={inputStyle}>
                <option value="">{t("company_size")}</option>
                {companySizes.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>

            <div style={{ marginTop: "1.5rem", textAlign: "left" }}>
              <p style={{ marginBottom: "0.5rem" }}>{t("interested_channels")}</p>
              {channels.map((c) => (
                <label key={c} style={checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={formData.channels.includes(c)}
                    onChange={() => toggleChannel(c)}
                    style={{ marginRight: "0.5rem" }}
                  />
                  {c}
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
            <h2 style={titleStyle}>{t("your_plan")}</h2>
            <p style={textStyle}>
              {t("you_are_on_plan")} <strong>{settings.plan?.name}</strong>.
            </p>
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
