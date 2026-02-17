// src/features/settings/PlanInfo.jsx
// ✅ PlanInfo.jsx — con modal de confirmación de upgrade/downgrade
import { useLanguage } from "../../contexts/LanguageContext";
import { useClientId } from "@/hooks/useClientId";
import { toast } from "@/components/ui/use-toast";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { supabase } from "@/lib/supabaseClient";
import { authFetch } from "@/lib/authFetch";
import "./PlanInfo.css";

export default function PlanInfo({ activeTab, formData, refetchSettings }) {
  const { t } = useLanguage();
  const clientId = useClientId();
  const location = useLocation();
  const navigate = useNavigate();

  const [loadingPlan, setLoadingPlan] = useState(null);
  const [userEmail, setUserEmail] = useState("");
  const [reactivating, setReactivating] = useState(false);
  const [confirmModal, setConfirmModal] = useState(null); // 🔹 Abre modal

  // 🔹 Obtener email del usuario autenticado
  useEffect(() => {
    const fetchEmail = async () => {
      const { data } = await supabase.auth.getUser();
      if (data?.user?.email) setUserEmail(data.user.email);
    };
    fetchEmail();
  }, []);

  // 🔹 Planes disponibles (UI/branding; sin tocar lógica)
  const availablePlans = [
    {
      id: "free",
      name: t("plan_free"),
      price: t("plan_price_free"),
      desc: t("plan_free_desc"),
      features: [
        t("plan_feature_100_messages"),
        t("plan_feature_1_document"),
        t("plan_feature_basic_dashboard"),
        t("plan_feature_widget_integration"),
      ],
    },
    {
      id: "starter",
      name: t("plan_starter"),
      price: t("plan_price_starter"),
      desc: t("plan_starter_desc"),
      features: [
        t("plan_feature_1000_messages"),
        t("plan_feature_1_document"),
        t("plan_feature_basic_dashboard"),
        t("plan_feature_widget_integration"),
        t("plan_feature_whatsapp_setup_required"),
        
      ],
    },
    {
      id: "premium",
      name: t("plan_premium"),
      price: t("plan_price_premium"),
      desc: t("plan_premium_desc"),
      features: [
        t("feature_all_starter"),
        t("plan_feature_5000_messages"),
        t("plan_feature_3_documents"),
        t("plan_feature_brand_customization"),
        t("plan_feature_custom_prompt"),
        t("plan_feature_whatsapp_appointments")],
      badge: t("most_popular"),
    },
    {
      id: "white_label",
      name: t("plan_white_label"),
      price: t("custom_price"),
      desc: t("plan_enterprise_desc"),
      features: [
        t("plan_feature_unlimited_messages_docs"),
        t("plan_feature_dedicated_support")],
      contact: "support@evolvianai.com",
    },
  ];

  const planOrder = { free: 1, starter: 2, premium: 3, white_label: 4 };
  const currentPlanId = formData?.plan?.id?.toLowerCase() || "free";
  const currentPlanName = formData?.plan?.name || t("current_plan_label");
  const cancellationRequested = !!formData?.cancellation_requested_at;
  const scheduledPlanId = formData?.scheduled_plan_id || null; // (disponible para banner futuro)
  const subscriptionEnd = formData?.subscription_end;

  const formatDate = (date) =>
    date
      ? new Date(date).toLocaleDateString(undefined, {
          year: "numeric",
          month: "short",
          day: "numeric",
        })
      : "";

  // 🔁 Detectar retorno desde Stripe
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    if (query.get("session_id")) {
      toast({
        title: t("subscription_activated_title"),
        description: t("subscription_activated_desc"),
      });
      refetchSettings?.();
      navigate("/dashboard");
    }
  }, [location]);

  if (activeTab !== "plan") return null;

  // 🔹 Funciones (sin cambios funcionales)
  const handleUpgrade = async (planId) => {
    if (cancellationRequested)
      return toast({
        title: t("plan_change_blocked"),
        description: t("plan_change_blocked_desc"),
      });

    try {
      if (!userEmail) {
        toast({ title: t("missing_email"), description: t("please_sign_in_again") });
        return;
      }
      setLoadingPlan(planId);
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/create-checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, client_id: clientId, email: userEmail }),
      });
      const data = await res.json();
      if (res.ok && data.url) window.location.href = data.url;
      else throw new Error(data.error || t("checkout_session_failed"));
    } catch (err) {
      toast({ title: t("upgrade_failed"), description: err.message });
    } finally {
      setLoadingPlan(null);
    }
  };

  const handleDowngrade = async (planId) => {
    if (cancellationRequested)
      return toast({
        title: t("downgrade_already_scheduled"),
        description: t("downgrade_already_scheduled_desc"),
      });

    try {
      setLoadingPlan(planId);
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/change-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, new_plan_id: planId }),
      });
      const data = await res.json();
      if (res.ok) {
        toast({ title: t("plan_updated"), description: data.message || t("plan_change_scheduled") });
        await refetchSettings?.();
        setTimeout(() => (window.location.href = "/dashboard"), 1000);
      } else throw new Error(data?.error || t("plan_change_failed"));
    } catch (err) {
      toast({ title: t("downgrade_failed"), description: err.message });
    } finally {
      setLoadingPlan(null);
    }
  };

  const handleReactivate = async () => {
    if (!confirm(`${t("reactivate_confirm_prefix")} ${currentPlanName}?`)) return;
    try {
      setReactivating(true);
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/reactivate-subscription`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId }),
      });
      const data = await res.json();
      if (res.ok) {
        toast({
          title: t("subscription_reactivated"),
          description: `${t("subscription_restored_prefix")} ${currentPlanName} ${t("subscription_restored_suffix")}`,
        });
        setTimeout(() => (window.location.href = "/dashboard"), 1000);
      } else throw new Error(data?.error || t("reactivate_subscription_error"));
    } catch (err) {
      toast({ title: t("error"), description: err.message });
    } finally {
      setReactivating(false);
    }
  };

  const comparePlans = (planId) => {
    const current = planOrder[currentPlanId];
    const target = planOrder[planId];
    if (target > current) return "upgrade";
    if (target < current) return "downgrade";
    return "current";
  };

  // 🔹 Modal de confirmación (branding via CSS)
  const ConfirmationModal = ({ type, plan, onConfirm, onCancel }) => {
    const currentPlan = availablePlans.find((p) => p.id === currentPlanId);
    const targetPlan = availablePlans.find((p) => p.id === plan.id);

    const featureDiff =
      type === "upgrade"
        ? targetPlan.features.filter((f) => !currentPlan.features.includes(f))
        : currentPlan.features.filter((f) => !targetPlan.features.includes(f));

    return (
      <div className="confirm-overlay" role="dialog" aria-modal="true">
        <div className="confirm-window">
          <div className="confirm-left">
            <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="confirm-logo" />
          </div>
          <div className="confirm-right">
            <h3 className="confirm-title">
              {type === "upgrade" ? t("upgrade_plan_title") : t("downgrade_plan_title")} — {currentPlan.name} → {targetPlan.name}
            </h3>

            <p className="confirm-desc">
              {type === "upgrade"
                ? t("upgrade_plan_desc")
                : `${t("downgrade_plan_desc_prefix")} ${
                    subscriptionEnd ? `(${formatDate(subscriptionEnd)})` : ""
                  }.`}
            </p>

            {featureDiff.length > 0 && (
              <>
                <h4 className="confirm-diff-title">
                  {type === "upgrade" ? t("you_will_gain") : t("you_will_lose")}
                </h4>
                <ul className="feature-list">
                  {featureDiff.map((f, i) => (
                    <li key={i}>{type === "upgrade" ? "✅ " : "❌ "}{f}</li>
                  ))}
                </ul>
              </>
            )}

            <p className="terms-text">
              {t("by_clicking_accept")}{" "}
              <a href="/terms" target="_blank" rel="noopener noreferrer">{t("terms_and_conditions")}</a> {t("and")}{" "}
              <a href="/PrivacyPolicy" target="_blank" rel="noopener noreferrer">{t("privacy_policy")}</a>.
            </p>

            <div className="confirm-actions">
              <button className="btn cancel" onClick={onCancel}>{t("cancel")}</button>
              <button
                className="btn confirm"
                onClick={() => {
                  onConfirm();
                  setConfirmModal(null);
                }}
              >
                {t("accept")}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // 🔹 Render principal (branding por clases; lógica intacta)
  return (
    <section className="plans-section">
      <h2 className="plans-title">{t("choose_plan_fit_business")}</h2>

      {cancellationRequested && (
        <div className="cancel-banner">
          ⚠️ {t("your_plan_will_be_cancelled_on")} <strong>{currentPlanName}</strong> {t("on_date")}{" "}
          <strong>{formatDate(subscriptionEnd)}</strong>.
          <button onClick={handleReactivate} disabled={reactivating} className="reactivate-btn">
            {reactivating ? t("reactivating") : `🔄 ${t("reactivate")} ${currentPlanName}`}
          </button>
        </div>
      )}

      <div className="plan-grid">
        {availablePlans.map((p) => {
          const relation = comparePlans(p.id);

          return (
            <div
              key={p.id}
              className={`plan-card ${p.badge ? "highlighted" : ""} ${currentPlanId === p.id ? "current" : ""}`}
            >
              <div className="plan-header">
                <h3 className="plan-name">
                  {p.name} {p.badge && <span className="badge">{p.badge}</span>}
                </h3>
                <span className="price">{p.price}</span>
              </div>

              <p className="plan-desc">{p.desc}</p>
              <ul className="plan-features">
                {p.features.map((f, i) => (
                  <li key={i}>✅ {f}</li>
                ))}
              </ul>

              {/* Footer / Acciones */}
              {p.id === "white_label" ? (
                <div className="plan-footer">
                  <p className="contact-text">{t("contact_for_whitelabel")}</p>
                  <a href={`mailto:${p.contact}`} className="contact-link">
                    {p.contact}
                  </a>
                </div>
              ) : relation === "current" ? (
                <button className="btn current">✅ {t("current_plan_label")}</button>
              ) : relation === "upgrade" ? (
                <button
                  onClick={() => setConfirmModal({ type: "upgrade", plan: p })}
                  disabled={loadingPlan === p.id || cancellationRequested}
                  className="btn upgrade"
                >
                  {loadingPlan === p.id ? t("processing") : t("upgrade")}
                </button>
              ) : (
                <button
                  onClick={() => setConfirmModal({ type: "downgrade", plan: p })}
                  disabled={loadingPlan === p.id || cancellationRequested}
                  className="btn downgrade"
                >
                  {loadingPlan === p.id ? t("processing") : t("downgrade")}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Modal */}
      {confirmModal && (
        <ConfirmationModal
          type={confirmModal.type}
          plan={confirmModal.plan}
          onCancel={() => setConfirmModal(null)}
          onConfirm={() =>
            confirmModal.type === "upgrade"
              ? handleUpgrade(confirmModal.plan.id)
              : handleDowngrade(confirmModal.plan.id)
          }
        />
      )}
    </section>
  );
}
