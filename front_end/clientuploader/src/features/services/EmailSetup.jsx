import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { toast } from "@/components/ui/use-toast";
import { authFetch } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

const isChannelEnabled = (channel) => Boolean(channel?.active ?? channel?.is_active);
const gmailErrorMessageKeys = {
  missing_code: "email_setup_gmail_error_missing_code",
  missing_state: "email_setup_gmail_error_missing_state",
  state_expired: "email_setup_gmail_error_state_expired",
  oauth_failed: "email_setup_gmail_error_oauth_failed",
};

export default function EmailSetup() {
  const clientId = useClientId();
  const { t, lang } = useLanguage();

  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connectedEmail, setConnectedEmail] = useState(null);
  const [lastSync, setLastSync] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [senderEnabled, setSenderEnabled] = useState(false);
  const [updatingSender, setUpdatingSender] = useState(false);
  const [statusModal, setStatusModal] = useState(null);

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

  const fetchChannel = async () => {
    if (!clientId) return;
    try {
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/channels?client_id=${clientId}&type=email&provider=gmail`
      );
      if (res.status === 404) {
        setConnectedEmail(null);
        setIsConnected(false);
        setSenderEnabled(false);
        setLastSync(null);
        return;
      }

      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      if (list.length > 0) {
        const preferred = list.find((ch) => isChannelEnabled(ch)) || list[0];
        setConnectedEmail(preferred?.value || null);
        setIsConnected(true);
        setSenderEnabled(isChannelEnabled(preferred));
        setLastSync(preferred?.updated_at || null);
      } else {
        setConnectedEmail(null);
        setIsConnected(false);
        setSenderEnabled(false);
        setLastSync(null);
      }
    } catch (err) {
      console.error("❌ Error fetching Gmail channel:", err);
    }
  };

  useEffect(() => {
    fetchDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, t]);

  useEffect(() => {
    fetchChannel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    let hasChanges = false;

    if (params.get("gmail_connected") === "true") {
      setStatusModal({
        titleKey: "email_setup_modal_connected_title",
        messageKey: "email_setup_modal_connected_message",
        noteKey: "email_setup_modal_connected_note",
      });
      fetchChannel();
      params.delete("gmail_connected");
      hasChanges = true;
    }

    const gmailError = params.get("gmail_error");
    if (gmailError) {
      const gmailErrorKey = gmailErrorMessageKeys[gmailError];
      toast({
        variant: "destructive",
        title: t("email_setup_toast_connect_failed_title"),
        description:
          (gmailErrorKey ? t(gmailErrorKey) : null) ||
          t("email_setup_toast_connect_failed_description"),
      });
      params.delete("gmail_error");
      hasChanges = true;
    }

    if (hasChanges) {
      const qs = params.toString();
      const nextUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
      window.history.replaceState({}, "", nextUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, t]);

  const handleConnect = async () => {
    try {
      const res = await authFetch(
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
          title: t("email_setup_toast_start_connection_failed_title"),
          description: t("email_setup_toast_start_connection_failed_description"),
        });
      }
    } catch (err) {
      console.error("❌ Gmail connect error:", err);
      toast({
        title: t("email_setup_toast_connect_error_title"),
        description: t("email_setup_toast_connect_error_description"),
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
        setStatusModal({
          titleKey: "email_setup_modal_disconnected_title",
          messageKey: "email_setup_modal_disconnected_message",
          noteKey: "email_setup_modal_disconnected_note",
        });
        await fetchChannel();
      } else {
        toast({
          title: t("email_setup_toast_disconnect_failed_title"),
          description: t("email_setup_toast_disconnect_failed_description"),
        });
      }
    } catch (err) {
      console.error("❌ Disconnect error:", err);
      toast({
        title: t("email_setup_toast_disconnect_error_title"),
        description: t("email_setup_toast_disconnect_error_description"),
      });
    }
  };

  const handleToggleSender = async () => {
    if (!clientId || !isConnected) return;
    const nextEnabled = !senderEnabled;
    try {
      setUpdatingSender(true);
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/channels/email_sender_status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          provider: "gmail",
          enabled: nextEnabled,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed updating sender status");
      }

      setSenderEnabled(nextEnabled);
      toast({
        title: nextEnabled
          ? t("email_setup_sender_enabled_title")
          : t("email_setup_sender_paused_title"),
        description: nextEnabled
          ? t("email_setup_sender_enabled_description")
          : t("email_setup_sender_paused_description"),
      });
      await fetchChannel();
    } catch (err) {
      console.error("❌ Toggle sender error:", err);
      toast({
        title: t("email_setup_toast_save_failed_title"),
        description: t("email_setup_toast_save_failed_description"),
      });
    } finally {
      setUpdatingSender(false);
    }
  };

  const plan = dashboardData?.plan || {};
  const supportsEmail = plan?.supports_email === true;
  const normalizedPlanId = (plan?.id || "").toString().toLowerCase();
  const planName =
    (["free", "starter", "premium", "white_label"].includes(normalizedPlanId) && t(normalizedPlanId)) ||
    plan?.name ||
    t("free");

  const senderDisplay = isConnected && senderEnabled && connectedEmail
    ? `${connectedEmail} (Gmail)`
    : t("email_setup_sender_display_auto");

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
              <h1 className="ia-header-title">{t("email_setup_header_title")}</h1>
              <p className="ia-header-subtitle">
                {t("email_setup_header_subtitle")}
              </p>
            </div>
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">{t("email_setup_status_title")}</h2>
          <div className="ia-meta-grid">
            <p>
              <strong>{t("email_setup_status_plan_label")}:</strong> {planName}
            </p>
            <p>
              <strong>{t("email_setup_status_gmail_connected_label")}:</strong>{" "}
              {isConnected ? (
                <span style={{ color: "#2EB39A", fontWeight: 700 }}>
                  {t("yes")} ({connectedEmail || t("connected")})
                </span>
              ) : (
                <span style={{ color: "#F5A623", fontWeight: 700 }}>
                  {t("status_not_connected")}
                </span>
              )}
            </p>
            <p>
              <strong>{t("email_setup_status_sender_label")}:</strong> {senderDisplay}
            </p>
            {lastSync && (
              <p className="ia-note">
                {t("email_setup_status_last_update")}:{" "}
                {new Date(lastSync).toLocaleString(lang === "es" ? "es-ES" : "en-US")}
              </p>
            )}
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">{t("email_setup_connect_section_title")}</h2>
          <p style={{ color: "#274472", lineHeight: 1.55 }}>
            {t("email_setup_connect_section_description")}
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
                {t("connect_gmail")}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleDisconnect}
                className="ia-button"
                style={{ backgroundColor: "#F5A623", color: "#fff" }}
              >
                {t("email_setup_disconnect_gmail")}
              </button>
            )}
          </div>

          <div className="ia-note">
            {t("email_setup_connect_section_note")}
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">{t("email_setup_sender_section_title")}</h2>
          <p style={{ color: "#274472", lineHeight: 1.55 }}>
            {t("email_setup_sender_section_description")}
          </p>

          <div className="ia-inline-actions">
            <button
              type="button"
              onClick={handleToggleSender}
              disabled={!supportsEmail || !isConnected || updatingSender}
              className="ia-button"
              style={{
                backgroundColor: senderEnabled ? "#2EB39A" : "#EDEDED",
                color: senderEnabled ? "#fff" : "#1B2A41",
              }}
              >
              {updatingSender
                ? t("saving")
                : senderEnabled
                ? t("email_setup_sender_button_active_pause")
                : t("email_setup_sender_button_paused_activate")}
            </button>
          </div>

          <p className="ia-note">
            {t("email_setup_sender_recommendation")}
          </p>
        </section>

        {!supportsEmail && (
          <section className="ia-card" style={{ marginBottom: 0 }}>
            <h2 className="ia-card-title">{t("email_setup_premium_title")}</h2>
            <p style={{ color: "#274472", lineHeight: 1.55 }}>
              {t("email_setup_premium_description")}
            </p>
            <button
              type="button"
              className="ia-button ia-button-primary"
              onClick={() => (window.location.href = "/settings#plans")}
            >
              {t("see_plans")}
            </button>
          </section>
        )}
      </div>
      {statusModal && (
        <div
          className="ia-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={statusModal?.titleKey ? t(statusModal.titleKey) : ""}
          onClick={() => setStatusModal(null)}
        >
          <div className="ia-modal" onClick={(event) => event.stopPropagation()}>
            {statusModal.icon ? (
              <div className="ia-modal-side" aria-hidden="true">
                <div style={{ fontSize: "2rem" }}>{statusModal.icon}</div>
              </div>
            ) : null}
            <div className="ia-modal-main">
              <h3 className="ia-modal-title">
                {statusModal?.titleKey ? t(statusModal.titleKey) : ""}
              </h3>
              <p style={{ margin: 0, color: "#274472" }}>
                {statusModal?.messageKey ? t(statusModal.messageKey) : ""}
              </p>
              <p className="ia-modal-muted">
                {statusModal?.noteKey ? t(statusModal.noteKey) : ""}
              </p>
              <div className="ia-modal-actions">
                <button type="button" className="ia-button ia-button-warning" onClick={() => setStatusModal(null)}>
                  {t("email_setup_acknowledge")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
