// ... imports sin cambios
import { useLanguage } from "../../contexts/LanguageContext";
import { useClientId } from "@/hooks/useClientId";
import { toast } from "@/components/ui/use-toast";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

export default function PlanInfo({ activeTab, formData, refetchSettings }) {
  const { t } = useLanguage();
  const clientId = useClientId();
  const location = useLocation();
  const [loading, setLoading] = useState(false);

  const availablePlans = [
    {
      id: "free",
      name: t("plan_free"),
      price: "$0",
      features: [t("feature_chat_widget"), t("feature_basic_usage")],
    },
    {
      id: "starter",
      name: t("plan_starter"),
      price: "$19/mo",
      features: [t("feature_chat_widget"), t("feature_email_support"), t("feature_higher_limits")],
    },
    {
      id: "premium",
      name: t("plan_premium"),
      price: "$49/mo",
      features: [t("feature_all_starter"), t("feature_whatsapp"), t("feature_googlecalendar"), t("feature_custom_prompt")],
    },
    {
      id: "white_label",
      name: t("plan_white_label"),
      price: "",
      features: [t("feature_all_premium"), t("feature_custom_branding"), t("feature_full_api"), t("feature_custom_needs")],
    },
  ];

  function formatDate(dateString) {
    const options = { year: "numeric", month: "short", day: "numeric" };
    return new Date(dateString).toLocaleDateString(undefined, options);
  }

  if (activeTab !== "plan") return null;

  const plan = formData.plan || { id: "free", name: t("plan_free"), plan_features: [] };
  const currentPlanId = plan?.id?.toLowerCase() || "free";
  const show_powered_by = formData.show_powered_by;
  const subscriptionStart = formData.subscription_start;
  const subscriptionEnd = formData.subscription_end;

  useEffect(() => {
    const query = new URLSearchParams(location.search);
    if (query.get("session_id")) {
      toast({
        title: t("subscription_activated_title"),
        description: t("subscription_activated_desc"),
      });
      if (refetchSettings) {
        refetchSettings().then(() => {
          console.log("✅ Plan actualizado tras sesión Stripe:", formData.plan?.id);
        });
      }
    }
  }, [location]);

  return (
    <div style={{ marginTop: "2rem" }}>
      <div style={{
        backgroundColor: "white",
        border: "1px solid #4a90e2",
        borderRadius: "16px",
        padding: "1.5rem",
        boxShadow: "0 4px 10px rgba(0,0,0,0.08)"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ color: "#274472", fontSize: "1.2rem", fontWeight: "bold" }}>
            🧾 {t("your_current_plan")}
          </h3>
          <span style={{
            backgroundColor: "#4a90e2",
            color: "white",
            padding: "4px 12px",
            borderRadius: "999px",
            fontSize: "0.85rem",
            textTransform: "capitalize"
          }}>
            {plan?.name || currentPlanId}
          </span>
        </div>

        <ul style={{ fontSize: "0.95rem", paddingLeft: "1rem", marginBottom: "1rem", lineHeight: "1.8", color: "#1b2a41" }}>
          <li><strong style={{ color: "#4a90e2" }}>💬 {t("messages")}:</strong> {plan?.is_unlimited ? t("unlimited") : plan?.max_messages ?? "—"}</li>
          <li><strong style={{ color: "#4a90e2" }}>📄 {t("documents")}:</strong> {plan?.is_unlimited ? t("unlimited") : plan?.max_documents ?? "—"}</li>
          <li><strong style={{ color: "#4a90e2" }}>🔖 {t("branding_active")}:</strong> {show_powered_by ? t("yes") : t("no")}</li>
          {subscriptionStart && (
            <li><strong style={{ color: "#4a90e2" }}>📅 {t("start_date")}:</strong> {formatDate(subscriptionStart)}</li>
          )}
          {subscriptionEnd && (
            <li><strong style={{ color: "#4a90e2" }}>⏳ {t("end_date")}:</strong> {formatDate(subscriptionEnd)}</li>
          )}
        </ul>

        {/* ✉️ Mensaje personalizado */}
        <div style={{
          backgroundColor: "#fef3c7",
          border: "1px solid #f5a623",
          padding: "1rem",
          borderRadius: "8px",
          fontSize: "0.95rem",
          color: "#1b2a41"
        }}>
          {t("change_plan_help")}{" "}
          <a href="mailto:support@evolvianai.com" style={{ color: "#4a90e2", textDecoration: "underline" }}>
            support@evolvianai.com
          </a>
        </div>
      </div>

      {/* 🔓 Sección de ver planes (sin botones) */}
      <h4 style={{ fontSize: "1.1rem", marginTop: "2rem", marginBottom: "1rem", color: "#f5a623" }}>
        💡 {t("see_plans")}
      </h4>

      <div style={{ display: "flex", flexDirection: "row", gap: "1rem", overflowX: "auto", paddingBottom: "0.5rem" }}>
        {availablePlans.map(plan => {
          const isCurrent = currentPlanId === plan.id;
          return (
            <div key={plan.id} style={{
              minWidth: "240px",
              flex: "0 0 auto",
              border: isCurrent ? "2px solid #a3d9b1" : "1px solid #ccc",
              borderRadius: "12px",
              padding: "1rem",
              backgroundColor: "#fff",
              color: "#1b2a41"
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h5 style={{ margin: 0, fontSize: "1rem", color: "#1b2a41" }}>{plan.name}</h5>
                {plan.price && <span style={{ fontWeight: "bold" }}>{plan.price}</span>}
              </div>
              <ul style={{ marginTop: "0.5rem", fontSize: "0.9rem", paddingLeft: "1rem" }}>
                {plan.features.map((f, i) => <li key={i}>{f}</li>)}
              </ul>

              {plan.id === "white_label" && (
                <p style={{
                  marginTop: "0.75rem",
                  fontSize: "0.85rem",
                  color: "#4a90e2",
                  fontWeight: "bold"
                }}>
                  {t("contact_for_whitelabel")}{" "}
                  <a href="mailto:support@evolvianai.com" style={{ textDecoration: "underline" }}>
                    support@evolvianai.com
                  </a>
                </p>
              )}

              {isCurrent && (
                <div style={{
                  marginTop: "0.75rem",
                  fontSize: "0.85rem",
                  color: "#4a90e2",
                  fontWeight: "bold"
                }}>
                  ✅ {t("current_plan")}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const btn = (type) => ({
  backgroundColor: type === "cancel" ? "#e74c3c" : type === "downgrade" ? "#a3d9b1" : "#f5a623",
  color: type === "cancel" ? "white" : "#1b2a41",
  padding: "10px 16px",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  cursor: "pointer",
});
