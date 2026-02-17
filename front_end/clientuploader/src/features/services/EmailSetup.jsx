// src/features/services/EmailSetup.jsx
import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { toast } from "@/components/ui/use-toast";
import { authFetch } from "../../lib/authFetch";

export default function EmailSetup() {
  const clientId = useClientId();
  const { t } = useLanguage();

  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connectedEmail, setConnectedEmail] = useState(null);
  const [lastSync, setLastSync] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  // 🎞️ Animaciones mínimas (sin dependencias)
  useEffect(() => {
    const styleId = "email-setup-inline-animations";
    if (!document.getElementById(styleId)) {
      const style = document.createElement("style");
      style.id = styleId;
      style.innerHTML = `
        @keyframes fadeUp { 0% { opacity: 0; transform: translateY(12px); } 100% { opacity: 1; transform: translateY(0); } }
        .ev-fadeUp { animation: fadeUp .45s ease-out forwards; opacity: 0; }
        .ev-delay-1 { animation-delay: .05s; }
        .ev-delay-2 { animation-delay: .10s; }
        .ev-delay-3 { animation-delay: .15s; }
        .ev-delay-4 { animation-delay: .20s; }
        .ev-delay-5 { animation-delay: .25s; }

        @keyframes ev-spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  // 🧠 1) Cargar dashboard/plan
  useEffect(() => {
    const fetchDashboard = async () => {
      if (!clientId) return;
      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/dashboard_summary?client_id=${clientId}`
        );
        const data = await res.json();
        if (!res.ok) throw new Error("Failed to load dashboard data");
        setDashboardData(data);
      } catch (err) {
        console.error("❌ Error loading dashboard:", err);
        toast({
          title: t("error"),
          description: t("failed_load_plan") || "Failed to load plan information.",
        });
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, [clientId, t]);

  // 📨 2) Leer canal Gmail
  const fetchChannel = async () => {
    if (!clientId) return;
    try {
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/channels?client_id=${clientId}&type=email&provider=gmail`
      );
      if (res.status === 404) {
        setConnectedEmail(null);
        setIsConnected(false);
        setLastSync(null);
        return;
      }
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        const validChannel =
          data.find((ch) => ch.active || ch.is_active) || data[0];
        setConnectedEmail(validChannel?.value || null);
        setIsConnected(Boolean(validChannel?.active || validChannel?.is_active));
        setLastSync(validChannel?.updated_at || null);
      } else {
        setConnectedEmail(null);
        setIsConnected(false);
        setLastSync(null);
      }
    } catch (err) {
      console.error("❌ Error fetching Gmail channel:", err);
    }
  };

  useEffect(() => {
    fetchChannel();
  }, [clientId]);

  // 🔁 3) Detectar redirect tras OAuth
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail_connected") === "true") {
      toast({
        title: t("gmail_connected_title"),
        description: t("gmail_connected_ok") || "Your Gmail account has been successfully linked.",
      });
      fetchChannel();
      params.delete("gmail_connected");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [t]);

  // 🔗 4) Conectar Gmail (OAuth)
  const handleConnect = async () => {
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/gmail_oauth/authorize?client_id=${clientId}`
      );
      // Puede regresar 404 si el endpoint no existe en prod
      if (res.status === 404) {
        toast({
          title: t("not_found_404"),
          description: t("gmail_oauth_not_found") || "Authorization endpoint not found.",
        });
        return;
      }
      const data = await res.json();
      if (data?.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        toast({
          title: t("error"),
          description: t("gmail_oauth_start_fail") || "Failed to start Gmail authorization.",
        });
      }
    } catch (err) {
      console.error("❌ Gmail connect error:", err);
      toast({
        title: t("error"),
        description: t("gmail_connect_error") || "Could not connect Gmail. Try again.",
      });
    }
  };

  // ❌ 5) Desconectar Gmail
  const handleDisconnect = async () => {
    try {
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/disconnect_gmail?client_id=${clientId}`,
        { method: "POST" }
      );
      if (res.ok) {
        toast({
          title: t("gmail_disconnected_title"),
          description: t("gmail_disconnected_ok") || "The account has been removed successfully.",
        });
        await fetchChannel();
      } else {
        toast({
          title: t("error"),
          description: t("gmail_disconnect_fail") || "Failed to disconnect Gmail.",
        });
      }
    } catch (err) {
      console.error("❌ Disconnect error:", err);
      toast({
        title: t("error"),
        description: t("gmail_disconnect_error") || "Unexpected error while disconnecting.",
      });
    }
  };

  // 🧮 6) Permisos por plan
  const plan = dashboardData?.plan || {};
  const supportsEmail = plan?.supports_email === true;
  const planName = plan?.name || "Free";

  // 🧱 7) UI
  if (loading || !dashboardData) {
    return (
      <div style={pageStyle}>
        <div style={wrap}>
          <section style={card}>
            <div style={centerBox}>
              <div style={spinner}></div>
              <p style={{ color: "#274472", marginTop: "1rem" }}>
                {t("loading") || "Loading..."}
              </p>
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <div style={wrap}>
        {/* 🟨 Intro */}
        <section style={card} className="ev-fadeUp ev-delay-1">
          <div style={headerRow}>
            <img
              src="/logo-evolvian.svg"
              alt="Evolvian Logo"
              style={{ width: 56, height: 56, borderRadius: "50%" }}
            />
            <div>
              <h1 style={title}>📧 {t("email_automation") || "Email Automation with Evolvian"}</h1>
              <p style={subtitle}>
                {t("email_intro") ||
                  "Let Evolvian automatically send replies, confirmations, and follow-ups using your Gmail account — securely and seamlessly."}
              </p>
            </div>
          </div>
         
        </section>

        {/* 🟩 Estado */}
        <section style={card} className="ev-fadeUp ev-delay-2">
          <h2 style={sectionTitle}>🔍 {t("connection_status") || "Connection Status"}</h2>
          <div style={statusGrid}>
            <div>
              <p><strong>{t("plan") || "Plan"}:</strong> {planName}</p>
              <p>
                <strong>{t("status") || "Status"}:</strong>{" "}
                {isConnected ? (
                  <span style={{ color: "#2EB39A", fontWeight: 600 }}>
                    🟢 {t("connected_as") || "Connected as"} {connectedEmail}
                  </span>
                ) : (
                  <span style={{ color: "#F5A623", fontWeight: 600 }}>
                    🟡 {t("not_connected") || "Not connected"}
                  </span>
                )}
              </p>
              {lastSync && (
                <p style={{ color: "#7A7A7A", fontSize: "0.9rem" }}>
                  {t("last_sync") || "Last sync"}: {new Date(lastSync).toLocaleString()}
                </p>
              )}
            </div>
           
          </div>
        </section>

        {/* 🟦 Acción (Conectar/Desconectar) */}
        <section style={card} className="ev-fadeUp ev-delay-3">
          <h2 style={sectionTitle}>⚙️ {t("gmail_connection") || "Gmail Connection"}</h2>
          <p style={paragraph}>
            {t("gmail_connection_copy") ||
              "Connect your Gmail via Google OAuth. Evolvian accesses only what’s needed to automate messages."}
          </p>

          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            {!isConnected ? (
              <button
                onClick={handleConnect}
                disabled={!supportsEmail}
                style={{
                  ...btn,
                  backgroundColor: supportsEmail ? "#A3D9B1" : "#EDEDED",
                  color: supportsEmail ? "#1B2A41" : "#999",
                  cursor: supportsEmail ? "pointer" : "not-allowed",
                }}
              >
                🔗 {t("connect_gmail") || "Connect Gmail"}
              </button>
            ) : (
              <button
                onClick={handleDisconnect}
                style={{
                  ...btn,
                  backgroundColor: "#F5A623",
                  color: "#fff",
                }}
              >
                ❌ {t("disconnect") || "Disconnect"}
              </button>
            )}
          </div>

          <div style={helperNote}>
            {t("oauth_tip") ||
              "You’ll be redirected to Google to grant permissions and then back to Evolvian."}
          </div>

         
        </section>

        {/* 🟣 Cómo funciona */}
        <section style={card} className="ev-fadeUp ev-delay-4">
          <h2 style={sectionTitle}>🚀 {t("how_it_works") || "How It Works"}</h2>
          <ul style={list}>
            <li>1️⃣ {t("how_1") || "Connect your Gmail account."}</li>
            <li>2️⃣ {t("how_2") || "Evolvian listens for new incoming messages."}</li>
            
          </ul>
         
        </section>

        {/* 🔒 Upgrade */}
        {!supportsEmail && (
          <section style={card} className="ev-fadeUp ev-delay-5">
            <h2 style={sectionTitle}>🔒 {t("premium_feature") || "Premium Feature"}</h2>
            <p style={paragraph}>
              {t("email_premium_copy") ||
                "Gmail automation is available only for Premium or White Label plans. Upgrade to unlock automatic replies and scheduling."}
            </p>
            <button
              style={{ ...btn, backgroundColor: "#4A90E2", color: "#fff", marginTop: "0.6rem" }}
              onClick={() => (window.location.href = "/settings#plans")}
            >
              ⬆️ {t("upgrade_plan") || "Upgrade Plan"}
            </button>
            <div style={placeholderSmall}>🖼️ {t("placeholder_upgrade") || "[Upgrade Plan Graphic]"}</div>
          </section>
        )}
      </div>
    </div>
  );
}

/* 🎨 Evolvian Premium Light Styles */
const pageStyle = {
  backgroundColor: "#FFFFFF",
  minHeight: "100vh",
  padding: "2rem",
  display: "flex",
  justifyContent: "center",
  color: "#274472",
  fontFamily: "Inter, system-ui, sans-serif",
};

const wrap = {
  maxWidth: 900,
  width: "100%",
  display: "flex",
  flexDirection: "column",
  gap: "1.4rem",
};

const card = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  padding: "1.6rem",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
};

const headerRow = {
  display: "flex",
  alignItems: "center",
  gap: "1rem",
  marginBottom: "0.8rem",
};

const title = {
  fontSize: "1.6rem",
  fontWeight: 800,
  color: "#F5A623",
  margin: 0,
};

const subtitle = {
  color: "#4A90E2",
  margin: 0,
  marginTop: "0.25rem",
  fontSize: "1rem",
};

const sectionTitle = {
  fontSize: "1.2rem",
  fontWeight: 700,
  color: "#4A90E2",
  marginBottom: "0.6rem",
};

const statusGrid = {
  display: "grid",
  gridTemplateColumns: "1fr auto",
  alignItems: "center",
  gap: "1rem",
};

const paragraph = {
  color: "#274472",
  marginBottom: "0.8rem",
  lineHeight: 1.6,
};

const list = {
  color: "#274472",
  lineHeight: 1.8,
  marginLeft: "1rem",
};

const btn = {
  border: "none",
  padding: "0.75rem 1.4rem",
  borderRadius: "10px",
  fontWeight: 700,
  transition: "transform .15s ease, box-shadow .15s ease",
  boxShadow: "0 6px 16px rgba(0,0,0,0.10)",
};

const helperNote = {
  marginTop: "0.6rem",
  color: "#7A7A7A",
  fontSize: "0.95rem",
};

const placeholderBig = {
  background: "#FAFAFA",
  color: "#9CA3AF",
  textAlign: "center",
  padding: "2.2rem",
  marginTop: "1rem",
  borderRadius: "12px",
  fontSize: "0.9rem",
  border: "1px dashed #EDEDED",
};

const placeholderSmall = {
  ...placeholderBig,
  padding: "1.2rem",
  marginTop: 0,
};

const centerBox = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  minHeight: 160,
};

const spinner = {
  width: 36,
  height: 36,
  border: "4px solid #EDEDED",
  borderTop: "4px solid #4A90E2",
  borderRadius: "50%",
  animation: "ev-spin 1s linear infinite",
};
