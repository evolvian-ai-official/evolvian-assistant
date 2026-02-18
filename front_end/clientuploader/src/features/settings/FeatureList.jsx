import { useLanguage } from "../../contexts/LanguageContext";

export default function FeatureList({ activeTab, plan }) {
  const { t } = useLanguage();

  if (activeTab !== "features") return null;

  // 🔹 Backend ya envía SOLO features activas como array de strings
  const features = Array.isArray(plan?.plan_features) ? plan.plan_features : [];

  return (
    <div
      style={{
        marginTop: "2rem",
        backgroundColor: "#ffffff",
        border: "1px solid #4a90e2",
        borderRadius: "16px",
        padding: "1.5rem",
        boxShadow: "0 4px 10px rgba(0,0,0,0.08)",
      }}
    >
      <h4
        style={{
          fontSize: "1.1rem",
          fontWeight: "bold",
          color: "#274472",
          marginBottom: "1rem",
        }}
      >
        🧩 {t("included_features")}
      </h4>

      {features.length === 0 ? (
        <p style={{ color: "#999" }}>
          {t("no_features_available")}
        </p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            fontSize: "0.95rem",
          }}
        >
          {features.map((featureKey) => (
            <li
              key={featureKey}
              style={{
                display: "flex",
                alignItems: "center",
                marginBottom: "0.6rem",
                color: "#4a90e2",
                fontWeight: 500,
              }}
            >
              <span>✅ {t(featureKey)}</span>

              <span
                style={{
                  marginLeft: "auto",
                  backgroundColor: "#a3d9b1",
                  color: "#1b2a41",
                  fontSize: "0.7rem",
                  padding: "2px 8px",
                  borderRadius: "999px",
                  fontWeight: "bold",
                }}
              >
                {t("included_in_plan")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
