import { useLanguage } from "../../contexts/LanguageContext";

export default function PromptSettings({
  activeTab,
  custom_prompt,
  hasPromptFeature,
  onChange,
  maxLength,
  defaultPrompt
}) {
  const { t } = useLanguage();
  if (activeTab !== "prompt") return null;

  const prompt = custom_prompt || defaultPrompt;
  const isTooLong = prompt.length > maxLength;

  return (
    <div style={{ marginTop: "2rem" }}>
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
  );
}
