import { useLanguage } from "../../contexts/LanguageContext";

const featurePlans = {
  chat_widget: ["free", "starter", "premium"],
  email_support: ["starter", "premium"],
  whatsapp_integration: ["premium"],
  custom_greeting: ["starter", "premium"],
  white_labeling: ["white_label"]
};

const planHierarchy = ["free", "starter", "premium", "white_label"];

export default function FeatureList({ activeTab, plan }) {
  const { t } = useLanguage();

  console.log("📢 Render FeatureList");
  console.log("🧾 activeTab:", activeTab);
  console.log("📦 plan prop:", plan);

  if (activeTab !== "features") return null;

  const currentPlanId =
    typeof plan?.id === "string" ? plan.id.toLowerCase() : "free";

  const isFeatureIncludedByPlan = (featureKey, currentPlan) => {
    const allowedPlans = featurePlans[featureKey];
    if (!allowedPlans) return false;
    const currentIndex = planHierarchy.indexOf(currentPlan);
    return allowedPlans.some((p) => planHierarchy.indexOf(p) <= currentIndex);
  };

  const getRequiredPlan = (featureKey) => {
    const plans = featurePlans[featureKey];
    if (!plans || plans.length === 0) return "—";
    if (plans.includes("free")) return t("free");
    if (plans.includes("starter")) return t("starter");
    if (plans.includes("premium")) return t("premium");
    return plans[0];
  };

  return (
    <div
      style={{
        marginTop: "2rem",
        backgroundColor: "white",
        border: "1px solid #4a90e2",
        borderRadius: "16px",
        padding: "1.5rem",
        boxShadow: "0 4px 10px rgba(0,0,0,0.08)"
      }}
    >
      <h4
        style={{
          fontSize: "1.1rem",
          fontWeight: "bold",
          color: "#274472",
          marginBottom: "1rem"
        }}
      >
        🧩 {t("included_features")}
      </h4>

      <ul
        style={{
          listStyle: "none",
          padding: 0,
          margin: 0,
          fontSize: "0.95rem"
        }}
      >
        {[
          { key: "chat_widget", label: t("chat_widget"), icon: "💬" },
          { key: "email_support", label: t("email_support"), icon: "✉️" },
          { key: "whatsapp_integration", label: t("whatsapp_integration"), icon: "📱" },
          { key: "custom_greeting", label: t("custom_greeting"), icon: "👋" },
          { key: "white_labeling", label: t("white_labeling"), icon: "🏷️" }
        ].map((feature) => {
          const isIncluded = isFeatureIncludedByPlan(
            feature.key,
            currentPlanId
          );
          return (
            <li
              key={feature.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "0.5rem",
                color: isIncluded ? "#4a90e2" : "#999"
              }}
            >
              <span>{feature.icon}</span>
              <span>{feature.label}</span>
              <span
                style={{
                  marginLeft: "auto",
                  backgroundColor: isIncluded ? "#a3d9b1" : "#f5a623",
                  color: "#1b2a41",
                  fontSize: "0.7rem",
                  padding: "2px 6px",
                  borderRadius: "999px",
                  fontWeight: "bold"
                }}
              >
                {isIncluded
                  ? t("included_in_plan")
                  : `${t("available_from")} ${getRequiredPlan(feature.key)}`}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
