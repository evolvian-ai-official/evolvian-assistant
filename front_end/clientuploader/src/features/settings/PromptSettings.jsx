import { useLanguage } from "../../contexts/LanguageContext";

export default function PromptSettings({
  activeTab,
  custom_prompt,
  hasPromptFeature,
  onChange,
  maxLength,
  defaultPrompt,
  temperature
}) {
  const { t } = useLanguage();
  if (activeTab !== "prompt") return null;

  const prompt = custom_prompt || defaultPrompt;
  const isTooLong = prompt.length > maxLength;

  return (
    <div style={{ marginTop: "2rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* 🧠 Prompt personalizado */}
      <div>
        <label>{t("custom_prompt")}</label>
        <textarea
          name="custom_prompt"
          value={prompt}
          onChange={onChange}
          readOnly={!hasPromptFeature}
          rows={6}
          style={{
            width: "100%",
            padding: "8px",
            borderRadius: "6px",
            border: isTooLong ? "2px solid #e53935" : "1px solid #ccc",
            marginTop: "4px",
            fontFamily: "inherit"
          }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px" }}>
          {!hasPromptFeature && (
            <p style={{ color: "#888", fontSize: "0.85rem" }}>
              {t("custom_prompt_locked")}
            </p>
          )}
          <p style={{ fontSize: "0.85rem", color: isTooLong ? "#e53935" : "#666" }}>
            {prompt.length} / {maxLength} {t("characters")}
          </p>
        </div>
      </div>

      {/* 🌡️ Temperatura del modelo */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <label htmlFor="temperature" style={{ fontWeight: "bold" }}>
          🌡️ {t("temperature_label") || "Model temperature (0.0 - 1.0)"}
        </label>
        <input
          type="number"
          step="0.1"
          min="0"
          max="1"
          name="temperature"
          id="temperature"
          value={temperature}
          onChange={onChange}
          readOnly={!hasPromptFeature}
          style={{
            padding: "0.5rem",
            border: "1px solid #ccc",
            borderRadius: "4px",
            width: "100%",
            backgroundColor: hasPromptFeature ? "white" : "#f5f5f5",
            color: hasPromptFeature ? "#000" : "#999"
          }}
        />
        {!hasPromptFeature && (
          <small style={{ color: "#888" }}>
            {t("upgrade_to_edit_temperature") || "Upgrade your plan to customize temperature."}
          </small>
        )}
      </div>
    </div>
  );
}
