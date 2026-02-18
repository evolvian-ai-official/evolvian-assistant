import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { toast } from "@/components/ui/use-toast";
import { authFetch } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

export default function EmailSetup() {
  const clientId = useClientId();
  const { t } = useLanguage();

  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connectedEmail, setConnectedEmail] = useState(null);
  const [lastSync, setLastSync] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

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
        const validChannel = data.find((ch) => ch.active || ch.is_active) || data[0];
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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail_connected") === "true") {
      toast({
        title: t("gmail_connected_title"),
        description:
          t("gmail_connected_ok") || "Your Gmail account has been successfully linked.",
      });
      fetchChannel();
      params.delete("gmail_connected");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [t]);

  const handleConnect = async () => {
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/gmail_oauth/authorize?client_id=${clientId}`
      );
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

  const plan = dashboardData?.plan || {};
  const supportsEmail = plan?.supports_email === true;
  const planName = plan?.name || "Free";

  if (loading || !dashboardData) {
    return (
      <div className="ia-page">
        <div className="ia-loader">
          <div className="ia-spinner" />
          <p style={{ color: "#274472", marginTop: "1rem" }}>{t("loading") || "Loading..."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ia-page">
      <div className="ia-shell ia-email-shell">
        <section className="ia-card">
          <div className="ia-header-row">
            <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="ia-header-logo" />
            <div>
              <h1 className="ia-header-title">📧 {t("email_automation") || "Email Automation with Evolvian"}</h1>
              <p className="ia-header-subtitle">
                {t("email_intro") ||
                  "Let Evolvian automatically send replies, confirmations, and follow-ups using your Gmail account."}
              </p>
            </div>
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">🔍 {t("connection_status") || "Connection Status"}</h2>
          <div className="ia-meta-grid">
            <p>
              <strong>{t("plan") || "Plan"}:</strong> {planName}
            </p>
            <p>
              <strong>{t("status") || "Status"}:</strong>{" "}
              {isConnected ? (
                <span style={{ color: "#2EB39A", fontWeight: 700 }}>
                  🟢 {t("connected_as") || "Connected as"} {connectedEmail}
                </span>
              ) : (
                <span style={{ color: "#F5A623", fontWeight: 700 }}>
                  🟡 {t("not_connected") || "Not connected"}
                </span>
              )}
            </p>
            {lastSync && (
              <p className="ia-note">
                {t("last_sync") || "Last sync"}: {new Date(lastSync).toLocaleString()}
              </p>
            )}
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">⚙️ {t("gmail_connection") || "Gmail Connection"}</h2>
          <p style={{ color: "#274472", lineHeight: 1.55 }}>
            {t("gmail_connection_copy") ||
              "Connect your Gmail via Google OAuth. Evolvian accesses only what is needed to automate messages."}
          </p>

          <div className="ia-inline-actions">
            {!isConnected ? (
              <button
                type="button"
                onClick={handleConnect}
                disabled={!supportsEmail}
                className="ia-button"
                style={{
                  backgroundColor: supportsEmail ? "#A3D9B1" : "#EDEDED",
                  color: supportsEmail ? "#1B2A41" : "#999",
                }}
              >
                🔗 {t("connect_gmail") || "Connect Gmail"}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleDisconnect}
                className="ia-button"
                style={{ backgroundColor: "#F5A623", color: "#fff" }}
              >
                ❌ {t("disconnect") || "Disconnect"}
              </button>
            )}
          </div>

          <div className="ia-note">
            {t("oauth_tip") ||
              "You will be redirected to Google to grant permissions and then back to Evolvian."}
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">🚀 {t("how_it_works") || "How It Works"}</h2>
          <ul className="ia-list">
            <li>1️⃣ {t("how_1") || "Connect your Gmail account."}</li>
            <li>2️⃣ {t("how_2") || "Evolvian listens for new incoming messages."}</li>
          </ul>
        </section>

        {!supportsEmail && (
          <section className="ia-card" style={{ marginBottom: 0 }}>
            <h2 className="ia-card-title">🔒 {t("premium_feature") || "Premium Feature"}</h2>
            <p style={{ color: "#274472", lineHeight: 1.55 }}>
              {t("email_premium_copy") ||
                "Gmail automation is available only for Premium or White Label plans. Upgrade to unlock automatic replies and scheduling."}
            </p>
            <button
              type="button"
              className="ia-button ia-button-primary"
              onClick={() => (window.location.href = "/settings#plans")}
            >
              ⬆️ {t("upgrade_plan") || "Upgrade Plan"}
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
