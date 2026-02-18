import { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch, getAuthHeaders } from "../../lib/authFetch";

import PlanInfo from "./PlanInfo";
import FeatureList from "./FeatureList";
import PromptSettings from "./PromptSettings";
import MyProfile from "./MyProfile";
import "../../components/ui/internal-admin-responsive.css";

export default function ClientSettings() {
  const clientId = useClientId();
  const location = useLocation();
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

  const normalizeTab = useCallback((value) => {
    const raw = (value || "")
      .toString()
      .trim()
      .toLowerCase()
      .replace(/^#/, "");

    const tabMap = {
      profile: "profile",
      my_profile: "profile",
      plan: "plan",
      plans: "plan",
      pricing: "plan",
      features: "features",
      prompt: "prompt",
    };

    return tabMap[raw] || null;
  }, []);

  const DEFAULT_PROMPT =
    t("default_prompt") ||
    "You are an AI assistant designed to help with questions about the client's uploaded documents.";
  const MAX_PROMPT_LENGTH = 2000;

  const fetchSettings = useCallback(async () => {
    if (!clientId) return;

    try {
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`
      );
      const data = await res.json();

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

  useEffect(() => {
    const tabFromQuery = new URLSearchParams(location.search).get("tab");
    const nextTab = normalizeTab(tabFromQuery) || normalizeTab(location.hash);
    if (nextTab) setActiveTab(nextTab);
  }, [location.hash, location.search, normalizeTab]);

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
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/client_settings`, {
        method: "POST",
        headers: await getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });

      const data = await res.json();

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

  if (loading) {
    return (
      <div className="ia-page">
        <div className="ia-loader">
          <div className="ia-spinner" />
          <p style={{ color: "#274472", marginTop: "1rem", fontWeight: 500 }}>
            {t("loading_settings")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="ia-page">
      <div className="ia-shell ia-settings-shell">
        <section className="ia-settings-card">
          <h2 className="ia-settings-title">⚙️ {t("client_settings")}</h2>

          <div className="ia-tabs">
            <button
              type="button"
              onClick={() => setActiveTab("profile")}
              className={`ia-tab ${activeTab === "profile" ? "is-active" : ""}`}
            >
              👤 {t("my_profile")}
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("plan")}
              className={`ia-tab ${activeTab === "plan" ? "is-active" : ""}`}
            >
              🧾 {t("your_current_plan")}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("features")}
              className={`ia-tab ${activeTab === "features" ? "is-active" : ""}`}
            >
              🧩 {t("included_features")}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("prompt")}
              className={`ia-tab ${activeTab === "prompt" ? "is-active" : ""}`}
            >
              🎨 {t("custom_prompt")}
            </button>
          </div>

          {activeTab === "profile" && <MyProfile />}

          {activeTab === "plan" && (
            <PlanInfo activeTab={activeTab} formData={formData} refetchSettings={fetchSettings} />
          )}

          {activeTab === "features" && <FeatureList activeTab={activeTab} plan={formData.plan} />}

          {activeTab === "prompt" && (
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.2rem" }}>
              <PromptSettings
                activeTab={activeTab}
                custom_prompt={formData.custom_prompt}
                temperature={formData.temperature}
                hasPromptFeature={hasPromptFeature}
                onChange={handleChange}
                maxLength={MAX_PROMPT_LENGTH}
                defaultPrompt={DEFAULT_PROMPT}
              />
              <button type="submit" className="ia-button ia-button-primary" style={{ width: "fit-content" }}>
                {t("save_settings")}
              </button>
            </form>
          )}

          {status.message && (
            <p
              className="ia-status-line"
              style={{ color: status.type === "error" ? "#e63946" : "#2eb39a" }}
            >
              {status.message}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
