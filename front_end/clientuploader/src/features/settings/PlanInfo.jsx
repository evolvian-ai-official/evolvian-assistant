// src/features/settings/PlanInfo.jsx
// ✅ PlanInfo.jsx — con modal de confirmación de upgrade/downgrade
import { useLanguage } from "../../contexts/LanguageContext";
import { useClientId } from "@/hooks/useClientId";
import { toast } from "@/components/ui/use-toast";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { supabase } from "@/lib/supabaseClient";
import { authFetch } from "@/lib/authFetch";
import { trackClientEvent } from "../../lib/tracking";
import "./PlanInfo.css";

const CHECKOUT_PENDING_PLAN_KEY = "evolvian_checkout_pending_plan";

export default function PlanInfo({ activeTab, formData, refetchSettings }) {
  const { t } = useLanguage();
  const clientId = useClientId();
  const location = useLocation();
  const navigate = useNavigate();

  const [loadingPlan, setLoadingPlan] = useState(null);
  const [userEmail, setUserEmail] = useState("");
  const [reactivating, setReactivating] = useState(false);
  const [confirmModal, setConfirmModal] = useState(null); // 🔹 Abre modal
  const [checkoutSuccessPlan, setCheckoutSuccessPlan] = useState(null);

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
      supportingCopy: t("plan_free_pitch"),
      features: [
        t("plan_feature_500_messages"),
        t("pricing_feature_web_chat_widget"),
        t("pricing_feature_appointment_booking"),
      ],
      badge: t("pricing_position_try_it"),
    },
    {
      id: "starter",
      name: t("plan_starter"),
      price: t("plan_price_starter"),
      desc: t("plan_starter_desc"),
      supportingCopy: t("plan_starter_pitch"),
      features: [
        t("plan_feature_2000_messages"),
        t("pricing_feature_web_chat_widget"),
        t("pricing_feature_appointment_booking"),
        t("pricing_feature_active_whatsapp_ai"),
        t("pricing_feature_appointment_reminders"),
      ],
      badge: t("pricing_position_start_automating"),
    },
    {
      id: "premium",
      name: t("plan_premium"),
      price: t("plan_price_premium"),
      desc: t("plan_premium_desc"),
      supportingCopy: t("plan_premium_pitch"),
      features: [
        t("plan_feature_5000_messages"),
        t("pricing_feature_web_chat_widget"),
        t("pricing_feature_appointment_booking"),
        t("pricing_feature_active_whatsapp_ai"),
        t("pricing_feature_appointment_reminders"),
        t("pricing_feature_client_insights"),
        t("pricing_feature_custom_assistant_behavior"),
        t("pricing_feature_branded_chat_experience"),
        t("pricing_feature_google_calendar_sync"),
        t("pricing_feature_human_handoff"),
        t("pricing_feature_marketing_campaigns"),
        t("pricing_feature_automated_followups"),
      ],
      badge: t("most_popular"),
    },
    {
      id: "white_label",
      name: t("plan_white_label"),
      price: t("plan_price_white_label"),
      desc: t("plan_enterprise_desc"),
      supportingCopy: t("plan_white_label_pitch"),
      features: [
        t("pricing_feature_unlimited_messages"),
        t("pricing_feature_web_chat_widget"),
        t("pricing_feature_appointment_booking"),
        t("pricing_feature_active_whatsapp_ai"),
        t("pricing_feature_appointment_reminders"),
        t("pricing_feature_client_insights"),
        t("pricing_feature_custom_assistant_behavior"),
        t("pricing_feature_branded_chat_experience"),
        t("pricing_feature_google_calendar_sync"),
        t("pricing_feature_human_handoff"),
        t("pricing_feature_marketing_campaigns"),
        t("pricing_feature_automated_followups"),
        t("pricing_feature_white_label"),
        t("pricing_feature_dedicated_onboarding"),
        t("pricing_feature_priority_support"),
        t("pricing_feature_custom_configuration"),
        t("pricing_feature_multi_location_setup"),
      ],
      badge: t("pricing_position_contact_sales"),
      contact: "sales@evolvianai.com",
    },
  ];

  const normalizePlanId = (id) => {
    const normalized = (id || "free").toLowerCase();
    return normalized === "enterprise" ? "white_label" : normalized;
  };

  const planNameById = (planId) => {
    if (planId === "starter") return t("plan_starter");
    if (planId === "premium") return t("plan_premium");
    return t("current_plan_label");
  };

  const planOrder = { free: 1, starter: 2, premium: 3, white_label: 4 };
  const currentPlanId = normalizePlanId(formData?.plan?.id || "free");
  const currentPlanName = formData?.plan?.name || t("current_plan_label");
  const cancellationRequested = !!formData?.cancellation_requested_at;
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
    const sessionId = query.get("session_id");
    if (sessionId) {
      let pendingPlan = null;
      try {
        pendingPlan = normalizePlanId(localStorage.getItem(CHECKOUT_PENDING_PLAN_KEY));
        localStorage.removeItem(CHECKOUT_PENDING_PLAN_KEY);
      } catch {
        pendingPlan = null;
      }

      const validCheckoutPlan =
        pendingPlan === "starter" || pendingPlan === "premium" ? pendingPlan : null;

      setCheckoutSuccessPlan(validCheckoutPlan);
      toast({
        title: t("subscription_activated_title"),
        description: t("subscription_activated_desc"),
      });
      refetchSettings?.();
      query.delete("session_id");
      navigate(
        {
          pathname: location.pathname,
          search: query.toString() ? `?${query.toString()}` : "",
        },
        { replace: true }
      );
    }
  }, [location.pathname, location.search, navigate, refetchSettings, t]);

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
      if (res.ok && data.url) {
        try {
          localStorage.setItem(CHECKOUT_PENDING_PLAN_KEY, normalizePlanId(planId));
        } catch {
          // no-op: si storage falla, seguimos con checkout y mostramos mensaje genérico al volver.
        }
        void trackClientEvent({
          clientId,
          name: "Funnel_Upgrade_Started",
          category: "funnel",
          label: planId,
          value: currentPlanId,
          eventKey: "funnel_upgrade_started",
          metadata: {
            from_plan: currentPlanId,
            to_plan: planId,
          },
          dedupeLocal: true,
        });
        window.location.href = data.url;
      }
      else throw new Error(data?.error || data?.detail || t("checkout_session_failed"));
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
    const target = planOrder[normalizePlanId(planId)];
    if (target > current) return "upgrade";
    if (target < current) return "downgrade";
    return "current";
  };

  const comparisonRows = [
    // Use plain text instead of emoji markers inside Settings.
    {
      id: "messages",
      label: t("pricing_feature_messages_month"),
      values: {
        free: "500",
        starter: "2,000",
        premium: "5,000",
        white_label: t("unlimited"),
      },
    },
    {
      id: "widget",
      label: t("pricing_feature_web_chat_widget"),
      values: {
        free: t("yes"),
        starter: t("yes"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "appointment_booking",
      label: t("pricing_feature_appointment_booking"),
      values: {
        free: t("yes"),
        starter: t("yes"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "active_whatsapp_ai",
      label: t("pricing_feature_active_whatsapp_ai"),
      values: {
        free: t("no"),
        starter: t("yes"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "appointment_reminders",
      label: t("pricing_feature_appointment_reminders"),
      values: {
        free: t("no"),
        starter: t("yes"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "client_insights",
      label: t("pricing_feature_client_insights"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "custom_assistant_behavior",
      label: t("pricing_feature_custom_assistant_behavior"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "branded_chat_experience",
      label: t("pricing_feature_branded_chat_experience"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "google_calendar_sync",
      label: t("pricing_feature_google_calendar_sync"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "human_handoff",
      label: t("pricing_feature_human_handoff"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "marketing_campaigns",
      label: t("pricing_feature_marketing_campaigns"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "automated_followups",
      label: t("pricing_feature_automated_followups"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("yes"),
        white_label: t("yes"),
      },
    },
    {
      id: "dedicated_onboarding",
      label: t("pricing_feature_dedicated_onboarding"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("no"),
        white_label: t("yes"),
      },
    },
    {
      id: "priority_support",
      label: t("pricing_feature_priority_support"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("no"),
        white_label: t("yes"),
      },
    },
    {
      id: "white_label",
      label: t("pricing_feature_white_label"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("no"),
        white_label: t("yes"),
      },
    },
    {
      id: "multi_location_setup",
      label: t("pricing_feature_multi_location_setup"),
      values: {
        free: t("no"),
        starter: t("no"),
        premium: t("no"),
        white_label: t("yes"),
      },
    },
  ];

  const renderPlanAction = (plan) => {
    const relation = comparePlans(plan.id);

    if (plan.id === "white_label") {
      return (
        <div className="plan-footer">
          <p className="contact-text">{t("contact_for_whitelabel")}</p>
          <a href={`mailto:${plan.contact}`} className="contact-link">
            {plan.contact}
          </a>
        </div>
      );
    }

    if (relation === "current") {
      return <button className="btn current">{t("current_plan_label")}</button>;
    }

    if (relation === "upgrade") {
      return (
        <button
          onClick={() => setConfirmModal({ type: "upgrade", plan })}
          disabled={loadingPlan === plan.id || cancellationRequested}
          className="btn upgrade"
        >
          {loadingPlan === plan.id ? t("processing") : t("upgrade")}
        </button>
      );
    }

    return (
      <button
        onClick={() => setConfirmModal({ type: "downgrade", plan })}
        disabled={loadingPlan === plan.id || cancellationRequested}
        className="btn downgrade"
      >
        {loadingPlan === plan.id ? t("processing") : t("downgrade")}
      </button>
    );
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
                    <li key={i}>{type === "upgrade" ? "+ " : "- "}{f}</li>
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

  const CheckoutSuccessModal = ({ planId, onClose }) => (
    <div className="checkout-success-overlay" role="dialog" aria-modal="true">
      <div className="checkout-success-window">
        <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="checkout-success-logo" />
        <h3 className="checkout-success-title">{t("checkout_success_title")}</h3>
        <p className="checkout-success-text">
          {t("checkout_success_message_prefix")} <strong>{planNameById(planId)}</strong>.
        </p>
        <p className="checkout-success-note">
          {planId === "premium"
            ? t("checkout_success_note_premium")
            : t("checkout_success_note_starter")}
        </p>
        <button className="btn confirm checkout-success-btn" onClick={onClose}>
          {t("checkout_success_cta")}
        </button>
      </div>
    </div>
  );

  if (activeTab !== "plan") {
    return checkoutSuccessPlan ? (
      <CheckoutSuccessModal
        planId={checkoutSuccessPlan}
        onClose={() => setCheckoutSuccessPlan(null)}
      />
    ) : null;
  }

  // 🔹 Render principal (branding por clases; lógica intacta)
  return (
    <>
      <section className="plans-section">
        <h2 className="plans-title">{t("choose_plan_fit_business")}</h2>

        {cancellationRequested && (
          <div className="cancel-banner">
            {t("your_plan_will_be_cancelled_on")} <strong>{currentPlanName}</strong> {t("on_date")}{" "}
            <strong>{formatDate(subscriptionEnd)}</strong>.
            <button onClick={handleReactivate} disabled={reactivating} className="reactivate-btn">
              {reactivating ? t("reactivating") : `${t("reactivate")} ${currentPlanName}`}
            </button>
          </div>
        )}

        <section className="plans-compare">
          <h3 className="plans-compare-title">
            {t("change_or_update_plan") || "Change or update plan"}: {t("included_features") || "Included Features"}
          </h3>
          <div className="plans-compare-wrapper">
            <table className="plans-compare-table">
              <thead>
                <tr>
                  <th>{t("included_features") || "Feature"}</th>
                  {availablePlans.map((p) => {
                    const planId = normalizePlanId(p.id);
                    const colClass = [
                      planId === currentPlanId ? "is-current-col" : "",
                      planId === "premium" ? "is-premium-col" : "",
                    ]
                      .filter(Boolean)
                      .join(" ");

                    return (
                      <th key={`head-${p.id}`} className={colClass}>
                        <div className="compare-plan-head">
                          <div className="compare-plan-name-row">
                            <span>{p.name}</span>
                            {p.badge ? <span className="compare-badge">{p.badge}</span> : null}
                          </div>
                          <div className="compare-plan-price">{p.price}</div>
                          <p className="compare-plan-desc">{p.desc}</p>
                          {p.supportingCopy ? <p className="compare-plan-desc">{p.supportingCopy}</p> : null}
                          <div className="compare-plan-cta">{renderPlanAction(p)}</div>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.label}</td>
                    {availablePlans.map((p) => {
                      const planId = normalizePlanId(p.id);
                      const colClass = [
                        planId === currentPlanId ? "is-current-col" : "",
                        planId === "premium" ? "is-premium-col" : "",
                      ]
                        .filter(Boolean)
                        .join(" ");

                      return (
                        <td key={`${row.id}-${p.id}`} className={colClass}>
                          {row.values[planId] || "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

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

      {checkoutSuccessPlan && (
        <CheckoutSuccessModal
          planId={checkoutSuccessPlan}
          onClose={() => setCheckoutSuccessPlan(null)}
        />
      )}
    </>
  );
}
