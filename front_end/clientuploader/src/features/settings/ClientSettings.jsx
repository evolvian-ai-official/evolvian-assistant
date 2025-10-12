import { useState, useEffect, useCallback } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";

import PlanInfo from "./PlanInfo";
import FeatureList from "./FeatureList";
import PromptSettings from "./PromptSettings";
import WidgetSettings from "./WidgetSettings";

export default function ClientSettings() {
  const clientId = useClientId();
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState("plan");

  const [formData, setFormData] = useState({
    assistant_name: "",
    language: "es",
    temperature: 0.7,
    plan: null,
    show_powered_by: true,
    custom_prompt: "",
    require_email: false,
    require_phone: false,
    require_terms: false,
  });

  const [status, setStatus] = useState({ message: "", type: "" });
  const [loading, setLoading] = useState(true);

  const DEFAULT_PROMPT =
    t("default_prompt") ||
    "Eres un asistente de IA diseñado para ayudar con preguntas sobre los documentos cargados por el cliente.";
  const MAX_PROMPT_LENGTH = 2000;

  const fetchSettings = useCallback(async () => {
    if (!clientId) return;

    try {
      console.log("📡 Fetching settings for:", clientId);
      const res = await fetch(`${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`);
      const data = await res.json();
      console.log("📦 Response from /client_settings:", data);

      if (res.ok && data) {
        const safePlan = data.plan || { id: "free", plan_features: [] };
        setFormData((prev) => ({
          ...prev,
          ...data,
          plan: {
            ...safePlan,
            plan_features: safePlan.plan_features ?? [],
          },
        }));
        console.log("🧾 Plan actualizado en estado:", safePlan?.id);
      } else {
        console.error("❌ Error al obtener configuración:", data);
      }
    } catch (err) {
      console.error("❌ Error de red en fetchSettings:", err);
    }

    setLoading(false);
  }, [clientId]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleChange = (e) => {
    const { name, type, checked, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if ((formData.custom_prompt || DEFAULT_PROMPT).length > MAX_PROMPT_LENGTH) {
      setStatus({ message: `❌ ${t("prompt_too_long")}`, type: "error" });
      return;
    }

    const payload = {
      client_id: clientId,
      assistant_name: formData.assistant_name,
      language: formData.language,
      temperature: formData.temperature,
      custom_prompt: formData.custom_prompt,
      require_email: formData.require_email,
      require_phone: formData.require_phone,
      require_terms: formData.require_terms,
    };

    try {
      console.log("📤 Enviando payload:", payload);
      const res = await fetch(`${import.meta.env.VITE_API_URL}/client_settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      console.log("📨 Respuesta POST /client_settings:", data);

      if (!res.ok) {
        setStatus({ message: `❌ ${data.error || t("error_saving")}`, type: "error" });
      } else {
        setStatus({ message: `✅ ${t("settings_saved")}`, type: "success" });
      }
    } catch (err) {
      console.error("❌ Error en handleSubmit:", err);
      setStatus({ message: "❌ Error al guardar configuración.", type: "error" });
    }
  };

  const hasPromptFeature =
    formData.plan?.plan_features?.some((f) =>
      typeof f === "string"
        ? f === "custom_prompt_editing"
        : f?.feature?.toLowerCase()?.replace(/\s+/g, "_") === "custom_prompt_editing"
    ) ?? false;

  if (loading) return <p>{t("loading_settings")}</p>;

  console.log("📌 Renderizando ClientSettings con tab:", activeTab);

  return (
    <div style={{ padding: "2rem", maxWidth: "700px", margin: "0 auto" }}>
      <h2>⚙️ {t("client_settings")}</h2>

      <div style={{ display: "flex", gap: "1rem", marginBottom: "2rem", flexWrap: "wrap" }}>
        <button onClick={() => setActiveTab("plan")} style={tabStyle(activeTab === "plan")}>
          🧾 {t("your_current_plan")}
        </button>
        <button onClick={() => setActiveTab("features")} style={tabStyle(activeTab === "features")}>
          🧩 {t("included_features")}
        </button>
        <button onClick={() => setActiveTab("prompt")} style={tabStyle(activeTab === "prompt")}>
          🎨 {t("custom_prompt")}
        </button>
      </div>

      {activeTab === "plan" && (
        <PlanInfo activeTab={activeTab} formData={formData} refetchSettings={fetchSettings} />
      )}

      {activeTab === "features" && (
        <FeatureList activeTab={activeTab} plan={formData.plan} />
      )}

      {activeTab === "prompt" && (
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
          <PromptSettings
            activeTab={activeTab}
            custom_prompt={formData.custom_prompt}
            temperature={formData.temperature}
            hasPromptFeature={hasPromptFeature}
            onChange={handleChange}
            maxLength={MAX_PROMPT_LENGTH}
            defaultPrompt={DEFAULT_PROMPT}
          />
          <button
            type="submit"
            style={{
              backgroundColor: "#4a90e2",
              color: "white",
              padding: "10px 16px",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
              fontWeight: "bold",
              width: "fit-content"
            }}
          >
            {t("save_settings")}
          </button>
        </form>
      )}

      {status.message && (
        <p style={{
          marginTop: "1.5rem",
          fontWeight: "bold",
          color: status.type === "error" ? "#e53935" : "#2e7d32"
        }}>
          {status.message}
        </p>
      )}
    </div>
  );
}

const tabStyle = (active) => ({
  padding: "6px 12px",
  backgroundColor: active ? "#a3d9b1" : "#ededed",
  color: "#274472",
  borderRadius: "999px",
  border: "none",
  cursor: "pointer",
  fontWeight: "500",
  fontSize: "0.9rem"
});
