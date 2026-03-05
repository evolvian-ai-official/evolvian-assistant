import { useEffect, useMemo, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";
import AppointmentClients from "./AppointmentClients";
import "../../components/ui/internal-admin-responsive.css";

const PLAN_ORDER = { free: 0, starter: 1, premium: 2, white_label: 3, enterprise: 3 };

const normalizePlanId = (value) => {
  const normalized = String(value || "free").trim().toLowerCase();
  return normalized === "enterprise" ? "white_label" : normalized;
};

export default function ClientsHub() {
  const clientId = useClientId();
  const { lang } = useLanguage();
  const isEs = lang === "es";

  const [loadingPlan, setLoadingPlan] = useState(true);
  const [planId, setPlanId] = useState("free");
  const [planError, setPlanError] = useState("");

  useEffect(() => {
    if (!clientId) return;
    let active = true;

    const loadPlan = async () => {
      setLoadingPlan(true);
      setPlanError("");
      try {
        const res = await authFetch(`${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data?.detail || "Failed loading plan.");
        if (!active) return;
        setPlanId(normalizePlanId(data?.plan?.id || data?.plan_id || "free"));
      } catch (e) {
        if (!active) return;
        setPlanError(String(e?.message || ""));
        setPlanId("free");
      } finally {
        if (active) setLoadingPlan(false);
      }
    };

    loadPlan();
    return () => {
      active = false;
    };
  }, [clientId]);

  const hasPremiumAccess = useMemo(() => {
    const current = PLAN_ORDER[normalizePlanId(planId)] ?? 0;
    return current >= PLAN_ORDER.premium;
  }, [planId]);

  return (
    <div className="ia-page">
      <div className="ia-shell ia-services-shell">
        <section className="ia-card">
          <h1 className="ia-header-title">👥 {isEs ? "Clientes" : "Clients"}</h1>
          <p className="ia-header-subtitle">
            {isEs
              ? "Administra clientes, revisa citas agendadas y consulta campañas enviadas desde un solo lugar."
              : "Manage clients, review booked appointments, and check sent campaigns in one place."}
          </p>
        </section>

        {loadingPlan ? (
          <section className="ia-card" style={{ marginBottom: 0 }}>
            <p style={{ margin: 0, color: "#274472" }}>{isEs ? "Cargando..." : "Loading..."}</p>
          </section>
        ) : !hasPremiumAccess ? (
          <section className="ia-card" style={{ marginBottom: 0 }}>
            <h2 className="ia-card-title">🔒 {isEs ? "Función Premium" : "Premium feature"}</h2>
            <p style={{ color: "#274472", lineHeight: 1.55 }}>
              {isEs
                ? "El módulo Clients con campañas enviadas está disponible solo en plan Premium o superior."
                : "The Clients module with sent campaigns is available only on Premium plan or higher."}
            </p>
            {planError ? <p style={{ color: "#B91C1C" }}>{planError}</p> : null}
            <button
              type="button"
              className="ia-button ia-button-primary"
              onClick={() => (window.location.href = "/settings#plans")}
            >
              {isEs ? "Ver planes" : "See plans"}
            </button>
          </section>
        ) : (
          <section className="ia-card" style={{ marginBottom: 0 }}>
            <AppointmentClients
              showCampaignHistory
              appointmentsCtaHref="/services/calendar"
              appointmentsCtaLabel={isEs ? "Crear Appointment" : "Create Appointment"}
            />
          </section>
        )}
      </div>
    </div>
  );
}
