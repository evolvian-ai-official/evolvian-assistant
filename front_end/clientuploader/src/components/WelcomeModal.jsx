import { useEffect, useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import countries from "../assets/countries.json";

const industries = ["Software", "Educación", "Salud", "Finanzas", "Retail", "Manufactura", "Consultoría", "Otro"];
const roles = ["Fundador/CEO", "CMO / Marketing Manager", "Customer Support", "Operations Manager", "Sales Executive", "IT Manager", "Product Manager", "Developer / Engineer", "HR / People", "Otro"];
const channels = ["Chat Widget", "WhatsApp", "Email", "Otros"];
const companySizes = ["1-10 empleados", "11-50 empleados", "51-200 empleados", "201-500 empleados", "501-1000 empleados", "Más de 1000 empleados"];

const steps = ["welcome_intro", "personalization", "terms", "plan"];

export default function WelcomeModal({ onClose }) {
  const { t } = useLanguage();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    industry: "",
    role: "",
    country: "",
    channels: [],
    companySize: "",
  });
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchClientSettings() {
      try {
        const clientId = localStorage.getItem("client_id");
        if (!clientId) throw new Error("client_id no encontrado en localStorage");

        const res = await fetch(`${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);

        const data = await res.json();
        setSettings(data);
      } catch (error) {
        console.error("❌ Error cargando configuración:", error);
      }
    }
    fetchClientSettings();
  }, []);

  const handleContinue = async () => {
    try {
      setLoading(true);
      sessionStorage.setItem("alreadyRedirected", "true");
      onClose();
    } catch (error) {
      console.error("❌ Error en handleContinue:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = async () => {
    setError(null);

    if (currentStep === 3) {
      try {
        const clientId = localStorage.getItem("client_id");
        if (!clientId) throw new Error("No se encontró client_id");

        console.log("📝 Guardando perfil del cliente...");
        const profileRes = await fetch(`${import.meta.env.VITE_API_URL}/save_client_profile`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            client_id: clientId,
            industry: formData.industry,
            role: formData.role,
            country: formData.country,
            channels: formData.channels,
            company_size: formData.companySize,
          }),
        });

        const profileData = await profileRes.text();
        console.log("📦 Respuesta perfil:", profileRes.status, profileData);
        if (!profileRes.ok) throw new Error("Error al guardar el perfil del cliente");

        console.log("✅ Perfil guardado. Ahora aceptando términos...");
        const termsRes = await fetch(`${import.meta.env.VITE_API_URL}/accept_terms`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ client_id: clientId }),
        });

        const termsData = await termsRes.text();
        console.log("📦 Respuesta términos:", termsRes.status, termsData);
        if (!termsRes.ok) throw new Error("Error al aceptar los términos y condiciones");

        console.log("✅ Consentimiento completo. Avanzando al paso final...");
        setCurrentStep((prev) => {
          const nextStep = Math.min(prev + 1, steps.length);
          console.log("➡️ Paso actualizado a:", nextStep);
          return nextStep;
        });
      } catch (error) {
        console.error("❌ Error en paso 3:", error);
        setError("Hubo un problema guardando tu consentimiento. Por favor, intenta de nuevo.");
      }
    } else {
      setCurrentStep((prev) => Math.min(prev + 1, steps.length));
    }
  };

  const handleBack = () => setCurrentStep((prev) => Math.max(prev - 1, 1));

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleChannelChange = (channel) => {
    setFormData((prev) => {
      const alreadySelected = prev.channels.includes(channel);
      const newChannels = alreadySelected
        ? prev.channels.filter((ch) => ch !== channel)
        : [...prev.channels, channel];
      return { ...prev, channels: newChannels };
    });
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <>
            <img src="/logo-evolvian.svg" alt="Evolvian Logo" style={{ width: "60px", marginBottom: "1.5rem" }} />
            <h1 style={titleStyle}>{t("welcome_title")}</h1>
            <p style={textStyle}>{t("welcome_description")}</p>
          </>
        );
      case 2:
        return (
          <>
            <h2 style={titleStyle}>{t("personalization_title")}</h2>
            <p style={textStyle}>{t("personalization_description")}</p>
            <div style={formGroupStyle}>
              <select name="industry" value={formData.industry} onChange={handleChange} style={inputStyle}>
                <option value="">{t("select_industry")}</option>
                {industries.map((ind) => <option key={ind} value={ind}>{ind}</option>)}
              </select>
              <select name="role" value={formData.role} onChange={handleChange} style={inputStyle}>
                <option value="">{t("select_role")}</option>
                {roles.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
              <select name="country" value={formData.country} onChange={handleChange} style={inputStyle}>
                <option value="">{t("select_country")}</option>
                {countries.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <div style={{ textAlign: "left", marginTop: "1rem" }}>
                <p style={{ ...textStyle, marginBottom: "0.5rem" }}>{t("interested_channels")}</p>
                {channels.map((ch) => (
                  <label key={ch} style={{ color: "#ededed", fontSize: "0.9rem", display: "block", marginBottom: "0.3rem" }}>
                    <input type="checkbox" checked={formData.channels.includes(ch)} onChange={() => handleChannelChange(ch)} style={{ marginRight: "0.5rem" }} />
                    {ch}
                  </label>
                ))}
              </div>
              <select name="companySize" value={formData.companySize} onChange={handleChange} style={inputStyle}>
                <option value="">{t("select_company_size")}</option>
                {companySizes.map((size) => <option key={size} value={size}>{size}</option>)}
              </select>
            </div>
          </>
        );
      case 3:
        return (
          <>
            <h2 style={titleStyle}>{t("terms_title")}</h2>
            <p style={textStyle}>
              {t("terms_description")} <a href="/terms" target="_blank" rel="noopener noreferrer" style={linkStyle}>{t("terms_and_conditions")}</a>.
            </p>
            {error && <p style={{ color: "red", marginTop: "1rem" }}>{error}</p>}
          </>
        );
      case 4:
        console.log("🧭 Entrando al paso 4 (plan), settings:", settings);
        return settings && (
          <>
            <h2 style={titleStyle}>{t("your_plan_title")}</h2>
            <p style={textStyle}>{t("current_plan")} <strong>{settings.plan?.name || "Free"}</strong></p>
          </>
        );
      default:
        return null;
    }
  };

  return (
    <div style={backdropStyle}>
      <div style={modalStyle}>
        <div style={stepsContainerStyle}>
          {steps.map((step, index) => (
            <div key={index} style={{
              ...stepItemStyle,
              backgroundColor: currentStep === index + 1 ? "#4a90e2" : "#f5a623",
              color: currentStep === index + 1 ? "white" : "#274472"
            }}>
              {t(step)}
              {index !== steps.length - 1 && <span style={arrowStyle}>→</span>}
            </div>
          ))}
        </div>

        {renderStepContent()}

        <div style={{ marginTop: "2rem", display: "flex", justifyContent: "flex-end" }}>
          {currentStep > 1 && <button onClick={handleBack} style={backButtonStyle}>{t("back")}</button>}
          {currentStep < steps.length
            ? <button onClick={handleNext} style={nextButtonStyle}>{t("next")}</button>
            : <button onClick={handleContinue} style={nextButtonStyle} disabled={loading}>
                {loading ? t("loading") : t("start")}
              </button>
          }
        </div>
      </div>
    </div>
  );
}
// Estilos los tienes ya completos como antes, no hay cambios.



// 🎨 Estilos (te los paso en el siguiente mensaje para no cortar)

const backdropStyle = {
  position: "fixed",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
  backgroundColor: "rgba(0, 0, 0, 0.7)",
  backdropFilter: "blur(8px)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
};

const modalStyle = {
  backgroundColor: "#1b2a41",
  padding: "3rem",
  borderRadius: "1.5rem",
  textAlign: "center",
  maxWidth: "700px",
  width: "90%",
  boxShadow: "0 0 30px rgba(0,0,0,0.3)",
  border: "1px solid #274472",
};

const titleStyle = {
  fontSize: "1.8rem",
  color: "#a3d9b1",
  marginBottom: "1rem",
};

const textStyle = {
  fontSize: "1rem",
  color: "#ededed",
  marginBottom: "1.5rem",
};

const formGroupStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  marginTop: "1rem",
};

const inputStyle = {
  padding: "0.8rem",
  borderRadius: "8px",
  border: "1px solid #4a90e2",
  backgroundColor: "#1b2a41",
  color: "white",
  appearance: "none", // 👈 Esto ayuda a quitar la flecha fea del select en navegadores
  WebkitAppearance: "none",
  MozAppearance: "none",
  backgroundImage: "url(\"data:image/svg+xml;charset=UTF-8,%3Csvg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'%3E%3Cpolygon points='70,100 20,40 120,40' fill='%23ffffff'/%3E%3C/svg%3E\")",
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 1rem center",
  backgroundSize: "12px",
};

const nextButtonStyle = {
  backgroundColor: "#2eb39a",
  color: "white",
  padding: "0.8rem 1.6rem",
  border: "none",
  borderRadius: "8px",
  fontWeight: "bold",
  cursor: "pointer",
};

const backButtonStyle = {
  backgroundColor: "#274472",
  color: "white",
  padding: "0.8rem 1.6rem",
  border: "none",
  borderRadius: "8px",
  fontWeight: "bold",
  cursor: "pointer",
};

const plansContainerStyle = {
  marginTop: "1.5rem",
  display: "flex",
  overflowX: "auto",
  gap: "1rem",
  paddingBottom: "1rem",
};

const planCardStyle = {
  minWidth: "180px",
  backgroundColor: "#0f1c2e",
  padding: "1rem",
  borderRadius: "12px",
  flexShrink: 0,
};

const selectedBadgeStyle = {
  marginTop: "0.5rem",
  display: "inline-block",
  backgroundColor: "#4a90e2",
  color: "white",
  padding: "4px 8px",
  borderRadius: "999px",
  fontSize: "0.8rem",
};

const contactButtonStyle = {
  display: "inline-block",
  marginTop: "0.5rem",
  backgroundColor: "#f5a623",
  color: "white",
  padding: "0.5rem 1rem",
  borderRadius: "8px",
  fontWeight: "bold",
  textDecoration: "none",
};

const linkStyle = {
  color: "#4a90e2",
  textDecoration: "underline",
};

const stepsContainerStyle = {
  display: "flex",
  justifyContent: "center",
  gap: "0.8rem",
  marginBottom: "2rem",
  flexWrap: "wrap",
  alignItems: "center",
};

const stepItemStyle = {
  padding: "0.5rem 1rem",
  borderRadius: "999px",
  fontSize: "0.9rem",
  fontWeight: "bold",
  textAlign: "center",
  minWidth: "120px",
};

const arrowStyle = {
  margin: "0 0.5rem",
  color: "#ededed",
  fontSize: "1.2rem",
};
