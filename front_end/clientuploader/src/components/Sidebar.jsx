import { useEffect, useState } from "react";
import { useClientId } from "../hooks/useClientId";
import { Link, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import { authFetch } from "../lib/authFetch";
import { useLanguage } from "../contexts/LanguageContext";

const PLAN_ORDER = { free: 0, starter: 1, premium: 2, white_label: 3 };

const normalizeFeature = (str) =>
  String(str || "")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "_");

const normalizePlanId = (str) => {
  const value = String(str || "free").toLowerCase().trim();
  return value === "enterprise" ? "white_label" : (value || "free");
};

const featureMinPlanFromAvailablePlans = (availablePlans, featureKey) => {
  const key = normalizeFeature(featureKey);
  let winner = null;
  for (const planRow of Array.isArray(availablePlans) ? availablePlans : []) {
    const planId = normalizePlanId(planRow?.id);
    const rawFeatures = Array.isArray(planRow?.plan_features) ? planRow.plan_features : [];
    const active = rawFeatures.some((f) => {
      if (typeof f === "string") return normalizeFeature(f) === key;
      return f && typeof f === "object" && f.is_active !== false && normalizeFeature(f.feature) === key;
    });
    if (!active) continue;
    if (!winner || (PLAN_ORDER[planId] ?? 99) < (PLAN_ORDER[winner] ?? 99)) {
      winner = planId;
    }
  }
  return winner;
};

const marketingCopyById = (id, isEs, requiredPlanLabel) => {
  const tier = requiredPlanLabel || (isEs ? "un plan superior" : "a higher plan");
  const map = {
    "inbox-handoff": isEs
      ? `Convierte conversaciones perdidas en ventas y soporte resuelto: IA + agente humano, alertas, notas y seguimiento desde un solo inbox. Disponible en ${tier}.`
      : `Turn unresolved chats into resolved support and revenue: AI + human agent handoff, alerts, notes, and follow-up in one inbox. Available on ${tier}.`,
    "/services/whatsapp": isEs
      ? `Responde clientes donde realmente te escriben. WhatsApp centraliza atención y acelera cierre de ventas. Disponible en ${tier}.`
      : `Reply where customers actually message you. WhatsApp support centralizes conversations and speeds up conversions. Available on ${tier}.`,
    "/services/email": isEs
      ? `Haz seguimiento profesional por email con historial y automatización. Ideal para tickets y leads de mayor intención. Disponible en ${tier}.`
      : `Deliver professional email follow-up with history and automation. Ideal for tickets and high-intent leads. Available on ${tier}.`,
    "/services/calendar": isEs
      ? `Convierte preguntas en citas agendadas automáticamente. Menos fricción, más reservas. Disponible en ${tier}.`
      : `Convert conversations into booked appointments automatically. Less friction, more bookings. Available on ${tier}.`,
    "/services/templates": isEs
      ? `Escala respuestas consistentes con templates reutilizables por canal y caso de uso. Disponible en ${tier}.`
      : `Scale consistent replies with reusable templates by channel and use case. Available on ${tier}.`,
    "/services/marketing-campaigns": isEs
      ? `Lanza campañas de email y WhatsApp con segmentación y tracking de envíos. Disponible en ${tier}.`
      : `Launch Email and WhatsApp campaigns with segmentation and delivery tracking. Available on ${tier}.`,
    "/services/clients": isEs
      ? `Centraliza clientes, citas agendadas y campañas enviadas en una sola vista operativa. Disponible en ${tier}.`
      : `Centralize clients, booked appointments, and sent campaigns in one operational view. Available on ${tier}.`,
    "/services/chat": isEs
      ? `Activa un asistente en tu web para captar y responder 24/7. Disponible en ${tier}.`
      : `Launch a web assistant to capture and answer leads 24/7. Available on ${tier}.`,
  };
  return map[id] || (isEs ? `Disponible en ${tier}.` : `Available on ${tier}.`);
};

export default function Sidebar({ mobile = false, onNavigate }) {
  const navigate = useNavigate();
  const clientId = useClientId();
  const { t, lang } = useLanguage();
  const isEs = lang === "es";
  const [features, setFeatures] = useState([]);
  const [currentPlanId, setCurrentPlanId] = useState("free");
  const [availablePlans, setAvailablePlans] = useState([]);
  const [hovered, setHovered] = useState(null);
  const [animateLogo, setAnimateLogo] = useState(false);

  useEffect(() => {
    setAnimateLogo(true);

    const fetchFeatures = async () => {
      if (!clientId) return;

      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`
        );

        const data = await res.json();

        if (res.ok) {
          const rawFeatures = data.plan?.plan_features || [];
          setCurrentPlanId(normalizePlanId(data?.plan?.id || data?.plan_id || "free"));
          setAvailablePlans(Array.isArray(data?.available_plans) ? data.available_plans : []);

          const featuresArray = rawFeatures
            .map((f) => {
              // Caso 1: backend ya envía string
              if (typeof f === "string") {
                return normalizeFeature(f);
              }

              // Caso 2: backend envía objeto { feature, is_active }
              if (typeof f === "object") {
                if (f.is_active === true) {
                  return normalizeFeature(f.feature);
                }
                return null; // 🔥 ignorar inactivos
              }

              return null;
            })
            .filter(Boolean);

          setFeatures(featuresArray);
        }
      } catch (error) {
        console.error("❌ Error connecting to backend:", error);
      }
    };

    fetchFeatures();
  }, [clientId]);

  const handleLogout = async () => {
    onNavigate?.();
    const persistedLang = localStorage.getItem("lang");
    await supabase.auth.signOut();
    localStorage.removeItem("client_id");
    localStorage.removeItem("public_client_id");
    localStorage.removeItem("user_id");
    localStorage.removeItem("alreadyRedirected");
    if (persistedLang) {
      localStorage.setItem("lang", persistedLang);
    }
    navigate("/login", { replace: true });
    window.location.reload();
  };

  const isEnabled = (feature) => features.includes(feature);

  const hasPlanAccess = (requiredPlanId) => {
    if (!requiredPlanId) return true;
    const current = PLAN_ORDER[normalizePlanId(currentPlanId)] ?? 0;
    const required = PLAN_ORDER[normalizePlanId(requiredPlanId)] ?? 99;
    return current >= required;
  };

  const serviceItems = [
    {
      id: "inbox-handoff",
      label: "Inbox / Handoff",
      path: "/inbox-handoff",
      feature: "handoff",
      fallbackRequiredPlan: "premium",
    },
    { id: "/services/chat", label: `${t("chat_assistant")}`, path: "/services/chat", feature: "chat_widget" },
    {
      id: "/services/whatsapp",
      label: `${t("whatsapp")}`,
      path: "/services/whatsapp",
      feature: "whatsapp_integration",
      fallbackRequiredPlan: "premium",
    },
    {
      id: "/services/email",
      label: `${t("email")}`,
      path: "/services/email",
      feature: "email_support",
      fallbackRequiredPlan: "premium",
    },
    {
      id: "/services/calendar",
      label: `${t("appointments_nav")}`,
      path: "/services/calendar",
      feature: "calendar_sync",
      fallbackRequiredPlan: "starter",
    },
    {
      id: "/services/templates",
      label: `${t("templates_nav")}`,
      path: "/services/templates",
      feature: "templates",
      fallbackRequiredPlan: "starter",
    },
    {
      id: "/services/marketing-campaigns",
      label: "Marketing Campaigns",
      path: "/services/marketing-campaigns",
      feature: "marketing_campaigns",
      fallbackRequiredPlan: "premium",
    },
    {
      id: "/services/clients",
      label: isEs ? "Clientes" : "Clients",
      path: "/services/clients",
      fallbackRequiredPlan: "premium",
    },
  ].map((item) => {
    const inferredPlan = item.feature
      ? featureMinPlanFromAvailablePlans(availablePlans, item.feature)
      : null;
    const requiredPlan = inferredPlan || item.fallbackRequiredPlan || null;
    const featureAccess = item.feature ? isEnabled(item.feature) : true;
    const currentPlanNormalized = normalizePlanId(currentPlanId);
    const currentPlanOrder = PLAN_ORDER[currentPlanNormalized] ?? 0;
    const requiredPlanOrder = PLAN_ORDER[normalizePlanId(requiredPlan)] ?? 99;
    const hiddenByFeatureFlag =
      Boolean(item.feature) &&
      !featureAccess &&
      (!requiredPlan || currentPlanOrder >= requiredPlanOrder);
    const planAccess = hasPlanAccess(requiredPlan);
    const locked = !(featureAccess && planAccess);
    const requiredPlanLabel = requiredPlan
      ? normalizePlanId(requiredPlan) === "starter"
        ? t("starter")
        : t("premium")
      : "";
    const shouldShowUpsell =
      locked &&
      Boolean(requiredPlan) &&
      currentPlanOrder < requiredPlanOrder &&
      ["free", "starter"].includes(currentPlanNormalized);
    return {
      ...item,
      requiredPlan,
      requiredPlanLabel,
      locked,
      hiddenByFeatureFlag,
      showTierBadge: shouldShowUpsell,
      marketingCopy: shouldShowUpsell ? marketingCopyById(item.id, isEs, requiredPlanLabel) : "",
    };
  }).filter((item) => !item.hiddenByFeatureFlag);

  return (
    <aside style={mobile ? asideStyleMobile : asideStyle}>
      <div>
        <div style={logoContainer}>
          <div
            style={{
              ...logoCircle,
              transform: animateLogo ? "rotate(360deg)" : "rotate(0deg)",
              opacity: animateLogo ? 1 : 0,
              transition: "all 1s ease-in-out",
            }}
          >
            <img
              src="/logo-evolvian.svg"
              alt="Evolvian Logo"
              style={{
                width: "100%",
                height: "100%",
                borderRadius: "50%",
                objectFit: "cover",
              }}
            />
          </div>
        </div>

        <nav style={navStyle}>
          <HoverLink
            label={`${t("dashboard")}`}
            to="/dashboard"
            hovered={hovered}
            setHovered={setHovered}
            id="dashboard"
            onNavigate={onNavigate}
          />
          <HoverLink
            label={`${t("upload")}`}
            to="/upload"
            hovered={hovered}
            setHovered={setHovered}
            id="upload"
            onNavigate={onNavigate}
          />
          <HoverLink
            label={`${t("history")}`}
            to="/history"
            hovered={hovered}
            setHovered={setHovered}
            id="history"
            onNavigate={onNavigate}
          />
          {serviceItems.map((item) => (
            <FeatureHoverLink
              key={item.id}
              id={item.id}
              to={item.path}
              label={item.label}
              hovered={hovered}
              setHovered={setHovered}
              onNavigate={onNavigate}
              locked={item.locked}
              badgeLabel={item.requiredPlanLabel}
              marketingCopy={item.marketingCopy}
              showTierBadge={item.showTierBadge}
            />
          ))}

          <HoverLink
            label={`${t("settings")}`}
            to="/settings"
            hovered={hovered}
            setHovered={setHovered}
            id="settings"
            onNavigate={onNavigate}
          />
        </nav>
      </div>

      <div style={footerContainer}>
        <button onClick={handleLogout} style={logoutButtonStyle}>
          {t("logout")}
        </button>
      </div>
    </aside>
  );
}

function HoverLink({ to, label, hovered, setHovered, id, onNavigate }) {
  return (
    <div style={navItemBlock}>
      <Link
        to={to}
        onMouseEnter={() => setHovered(id)}
        onMouseLeave={() => setHovered(null)}
        onClick={() => onNavigate?.()}
        style={{
          ...linkStyle,
          backgroundColor: hovered === id ? "#EAF3FC" : "transparent",
          color: hovered === id ? "#4A90E2" : "#274472",
          borderLeft:
            hovered === id
              ? "4px solid #F5A623"
              : "4px solid transparent",
          paddingLeft: "12px",
        }}
      >
        {label}
      </Link>
    </div>
  );
}

function FeatureHoverLink({
  to,
  label,
  hovered,
  setHovered,
  id,
  onNavigate,
  locked,
  badgeLabel,
  marketingCopy,
  showTierBadge,
}) {
  const isHovered = hovered === id;
  return (
    <div style={{ ...navItemBlock, position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
        <Link
          to={locked ? "#" : to}
          title={locked ? marketingCopy : undefined}
          onMouseEnter={() => setHovered(id)}
          onMouseLeave={() => setHovered(null)}
          onClick={(e) => {
            if (locked) {
              e.preventDefault();
              return;
            }
            onNavigate?.();
          }}
          style={{
            ...linkStyle,
            flex: 1,
            backgroundColor: isHovered ? "#EAF3FC" : "transparent",
            color: locked ? "#8A94A6" : isHovered ? "#4A90E2" : "#274472",
            borderLeft: isHovered ? "4px solid #F5A623" : "4px solid transparent",
            paddingLeft: "12px",
            cursor: locked ? "not-allowed" : "pointer",
          }}
        >
          {label}
        </Link>
        {showTierBadge ? (
          <span
            style={{
              ...(locked ? premiumBadge : tierOutlineBadge),
              marginLeft: "4px",
              opacity: locked ? 1 : 0.7,
            }}
          >
            {badgeLabel}
          </span>
        ) : null}
      </div>

      {locked && isHovered && marketingCopy ? (
        <div style={lockedTooltipStyle}>
          {marketingCopy}
        </div>
      ) : null}
    </div>
  );
}

/* 🎨 Styles (unchanged) */

const asideStyle = {
  width: "240px",
  background: "#FFFFFF",
  color: "#274472",
  padding: "2rem 1.5rem",
  minHeight: "100%",
  height: "100%",
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  borderRight: "1px solid #EDEDED",
  flexShrink: 0,
};

const asideStyleMobile = {
  width: "100%",
  height: "100%",
  minHeight: "100%",
  background: "#FFFFFF",
  color: "#274472",
  padding: "1.25rem 1rem",
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  overflowY: "auto",
};

const logoContainer = {
  textAlign: "center",
  marginBottom: "2rem",
  marginTop: "1rem",
};

const logoCircle = {
  width: "80px",
  height: "80px",
  borderRadius: "50%",
  backgroundColor: "#A3D9B1",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  margin: "0 auto 1rem",
  boxShadow: "0 0 12px rgba(163, 217, 177, 0.4)",
  border: "2px solid #FFFFFF",
};

const navStyle = {
  display: "flex",
  flexDirection: "column",
};

const navItemBlock = {
  padding: "0.5rem 0.6rem",
  borderBottom: "1px solid #EDEDED",
};

const linkStyle = {
  textDecoration: "none",
  fontWeight: "500",
  fontSize: "1rem",
  transition: "all 0.2s ease",
  display: "block",
  borderRadius: "6px",
  padding: "0.3rem 0.5rem",
};

const premiumBadge = {
  backgroundColor: "#F5A623",
  color: "#FFFFFF",
  fontSize: "0.7rem",
  padding: "2px 6px",
  borderRadius: "999px",
  fontWeight: "bold",
  verticalAlign: "middle",
};

const tierOutlineBadge = {
  backgroundColor: "#FFF8EB",
  color: "#9A6A00",
  fontSize: "0.7rem",
  padding: "2px 6px",
  borderRadius: "999px",
  fontWeight: "bold",
  border: "1px solid #F3D28E",
  verticalAlign: "middle",
  whiteSpace: "nowrap",
};

const lockedTooltipStyle = {
  marginTop: "0.45rem",
  marginLeft: "0.5rem",
  marginRight: "0.25rem",
  padding: "0.55rem 0.65rem",
  borderRadius: "10px",
  background: "#FFF8EB",
  border: "1px solid #F3D28E",
  color: "#7A5900",
  fontSize: "0.78rem",
  lineHeight: 1.35,
};

const footerContainer = {
  borderTop: "1px solid #EDEDED",
  paddingTop: "1.5rem",
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  background: "#FFFFFF",
};

const logoutButtonStyle = {
  backgroundColor: "#F5A623",
  color: "white",
  border: "none",
  borderRadius: "8px",
  padding: "0.5rem 1rem",
  cursor: "pointer",
  fontWeight: "bold",
  width: "100%",
  transition: "background 0.3s ease",
};
