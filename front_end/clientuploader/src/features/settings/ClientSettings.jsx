// src/features/settings/ClientSettings.jsx
import { useState, useEffect, useCallback } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch, getAuthHeaders } from "../../lib/authFetch";

import PlanInfo from "./PlanInfo";
import FeatureList from "./FeatureList";
import PromptSettings from "./PromptSettings";
import WidgetSettings from "./WidgetSettings";
import MyProfile from "./MyProfile";


export default function ClientSettings() {
  const clientId = useClientId();
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState("plan");

  const [formData, setFormData] = useState({
    assistant_name: "",
    language: "en",
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
    "You are an AI assistant designed to help with questions about the client’s uploaded documents.";
  const MAX_PROMPT_LENGTH = 2000;

  // 🌀 Inject Evolvian spinner keyframes only once
  useEffect(() => {
    if (typeof document !== "undefined" && !document.getElementById("spin-keyframes")) {
      const style = document.createElement("style");
      style.id = "spin-keyframes";
      style.textContent = `
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  const fetchSettings = useCallback(async () => {
    if (!clientId) return;

    try {
      console.log("📡 Fetching settings for:", clientId);
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`
      );
      const data = await res.json();
      console.log("📦 Response from /client_settings:", data);

      if (res.ok && data) {
        const safePlan = data.plan || { id: "free", plan_features: [] };
        const language = data.language || "en";

        setFormData((prev) => ({
          ...prev,
          ...data,
          language,
          plan: {
            ...safePlan,
            plan_features: safePlan.plan_features ?? [],
          },
        }));
      } else {
        console.error("❌ Error fetching client settings:", data);
      }
    } catch (err) {
      console.error("❌ Network error in fetchSettings:", err);
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
      language: formData.language || "en",
      temperature: formData.temperature,
      custom_prompt: formData.custom_prompt,
      require_email: formData.require_email,
      require_phone: formData.require_phone,
      require_terms: formData.require_terms,
    };

    try {
      console.log("📤 Sending payload:", payload);
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/client_settings`, {
        method: "POST",
        headers: await getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      console.log("📨 Response /client_settings:", data);

      if (!res.ok) {
        setStatus({
          message: `❌ ${data.error || t("error_saving")}`,
          type: "error",
        });
      } else {
        setStatus({ message: `✅ ${t("settings_saved")}`, type: "success" });
      }
    } catch (err) {
      console.error("❌ Error in handleSubmit:", err);
      setStatus({ message: "❌ Error saving settings.", type: "error" });
    }
  };

  const hasPromptFeature =
    formData.plan?.plan_features?.some((f) =>
      typeof f === "string"
        ? f === "custom_prompt_editing"
        : f?.feature?.toLowerCase()?.replace(/\s+/g, "_") === "custom_prompt_editing"
    ) ?? false;

  // 🌀 Spinner while loading
  if (loading) {
    return (
      <div style={loaderContainer}>
        <div style={spinner}></div>
        <p style={{ color: "#274472", marginTop: "1rem", fontWeight: "500" }}>
          {t("loading_settings")}
        </p>
      </div>
    );
  }

  console.log("📌 Rendering ClientSettings tab:", activeTab);

  return (
    <div style={container}>
      <h2 style={title}>⚙️ {t("client_settings")}</h2>

      <div style={tabContainer}>

        <button
          onClick={() => setActiveTab("profile")}
          style={tabStyle(activeTab === "profile")}
        >
          👤 {t("my_profile")}
        </button>

        <button
          onClick={() => setActiveTab("plan")}
          style={tabStyle(activeTab === "plan")}
        >
          🧾 {t("your_current_plan")}
        </button>
        <button
          onClick={() => setActiveTab("features")}
          style={tabStyle(activeTab === "features")}
        >
          🧩 {t("included_features")}
        </button>
        <button
          onClick={() => setActiveTab("prompt")}
          style={tabStyle(activeTab === "prompt")}
        >
          🎨 {t("custom_prompt")}
        </button>
      </div>

      {activeTab === "profile" && <MyProfile />}


      {activeTab === "plan" && (
        <PlanInfo
          activeTab={activeTab}
          formData={formData}
          refetchSettings={fetchSettings}
        />
      )}

      {activeTab === "features" && (
        <FeatureList activeTab={activeTab} plan={formData.plan} />
      )}

      {activeTab === "prompt" && (
        <form onSubmit={handleSubmit} style={formStyle}>
          <PromptSettings
            activeTab={activeTab}
            custom_prompt={formData.custom_prompt}
            temperature={formData.temperature}
            hasPromptFeature={hasPromptFeature}
            onChange={handleChange}
            maxLength={MAX_PROMPT_LENGTH}
            defaultPrompt={DEFAULT_PROMPT}
          />
          <button type="submit" style={saveButton}>
            {t("save_settings")}
          </button>
        </form>
      )}

      {status.message && (
        <p
          style={{
            marginTop: "1.5rem",
            fontWeight: "bold",
            color: status.type === "error" ? "#e63946" : "#2eb39a",
          }}
        >
          {status.message}
        </p>
      )}
    </div>
  );
}

/* 🎨 Styles */
const container = {
  padding: "2rem",
  maxWidth: "700px",
  margin: "0 auto",
  backgroundColor: "#ffffff",
  borderRadius: "12px",
  boxShadow: "0 4px 16px rgba(39,68,114,0.08)",
  border: "1px solid #ededed",
  color: "#274472",
};

const title = {
  fontSize: "1.5rem",
  fontWeight: "bold",
  marginBottom: "1.5rem",
  color: "#274472",
};

const tabContainer = {
  display: "flex",
  gap: "1rem",
  marginBottom: "2rem",
  flexWrap: "wrap",
};

const formStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "2rem",
};

/* 🌀 Loader sobrepuesto global */
const loaderContainer = {
  position: "fixed", // 🔥 Cubre toda la pantalla
  top: 0,
  left: 0,
  width: "100vw",
  height: "100vh",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#ffffff", // fondo oscuro Evolvian
  zIndex: 9999, // encima de todo
  color: "#a3d9b1",
  fontFamily: "Inter, system-ui, sans-serif",
  transition: "opacity 0.3s ease-in-out",
};

const spinner = {
  width: 40,
  height: 40,
  border: "4px solid #EDEDED",
  borderTop: "4px solid #4A90E2",
  borderRadius: "50%",
  animation: "spin 1s linear infinite",
};

const saveButton = {
  backgroundColor: "#4a90e2",
  color: "white",
  padding: "10px 16px",
  border: "none",
  borderRadius: "6px",
  cursor: "pointer",
  fontWeight: "bold",
  width: "fit-content",
  transition: "background 0.3s ease",
};

const tabStyle = (active) => ({
  padding: "8px 14px",
  backgroundColor: active ? "#a3d9b1" : "#ededed",
  color: active ? "#0f1c2e" : "#274472",
  borderRadius: "999px",
  border: "1px solid transparent",
  cursor: "pointer",
  fontWeight: "500",
  fontSize: "0.9rem",
  transition: "all 0.2s ease-in-out",
});
