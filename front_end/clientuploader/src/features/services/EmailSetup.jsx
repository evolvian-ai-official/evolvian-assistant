import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { toast } from "@/components/ui/use-toast";
import { authFetch } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

const isChannelEnabled = (channel) => Boolean(channel?.active ?? channel?.is_active);
const gmailErrorMessages = {
  missing_code: "No se recibió la autorización de Google. Intenta conectar tu Gmail otra vez.",
  missing_state: "La conexión se interrumpió. Vuelve a presionar Conectar Gmail.",
  state_expired: "La conexión venció por tiempo. Presiona Conectar Gmail nuevamente.",
  oauth_failed: "No se pudo terminar la conexión con Gmail. Intenta de nuevo.",
};

export default function EmailSetup() {
  const clientId = useClientId();
  const { t } = useLanguage();

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
        icon: "✅",
        title: "Felicitaciones, ya quedó conectado",
        message: "Ahora puedes enviar correos desde Evolvian a tus clientes usando tu Gmail.",
        note: "También puedes usar templates, confirmaciones y recordatorios automáticos.",
      });
      fetchChannel();
      params.delete("gmail_connected");
      hasChanges = true;
    }

    const gmailError = params.get("gmail_error");
    if (gmailError) {
      toast({
        variant: "destructive",
        title: "No se pudo conectar Gmail",
        description: gmailErrorMessages[gmailError] || "Ocurrió un problema al conectar Gmail. Intenta otra vez.",
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
          title: "No se pudo iniciar la conexión",
          description: "Intenta nuevamente en unos segundos.",
        });
      }
    } catch (err) {
      console.error("❌ Gmail connect error:", err);
      toast({
        title: "Error al conectar Gmail",
        description: "No pudimos iniciar la conexión. Intenta otra vez.",
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
          icon: "ℹ️",
          title: "Gmail desconectado",
          message: "Desde ahora, los correos saldrán desde el correo automático de Evolvian.",
          note: "Puedes volver a conectarlo cuando quieras para seguir usando esta funcionalidad.",
        });
        await fetchChannel();
      } else {
        toast({
          title: "No se pudo desconectar",
          description: "Intenta nuevamente.",
        });
      }
    } catch (err) {
      console.error("❌ Disconnect error:", err);
      toast({
        title: "Error al desconectar",
        description: "Ocurrió un problema inesperado. Intenta de nuevo.",
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
        title: nextEnabled ? "Envío activado" : "Envío pausado",
        description: nextEnabled
          ? "Desde ahora tus correos saldrán desde tu Gmail conectado."
          : "Desde ahora los correos saldrán desde el correo automático de Evolvian.",
      });
      await fetchChannel();
    } catch (err) {
      console.error("❌ Toggle sender error:", err);
      toast({
        title: "No se pudo guardar",
        description: "No se pudo cambiar el estado del envío. Intenta otra vez.",
      });
    } finally {
      setUpdatingSender(false);
    }
  };

  const plan = dashboardData?.plan || {};
  const supportsEmail = plan?.supports_email === true;
  const planName = plan?.name || "Free";

  const senderDisplay = isConnected && senderEnabled && connectedEmail
    ? `${connectedEmail} (Gmail)`
    : "noreply@notifications.evolvianai.com (correo automático)";

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
              <h1 className="ia-header-title">📧 Enviar correos con tu cuenta</h1>
              <p className="ia-header-subtitle">
                Aquí decides desde qué correo se envían confirmaciones, recordatorios y templates a tus clientes.
              </p>
            </div>
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">🔍 Estado actual</h2>
          <div className="ia-meta-grid">
            <p>
              <strong>Tu plan:</strong> {planName}
            </p>
            <p>
              <strong>Gmail conectado:</strong>{" "}
              {isConnected ? (
                <span style={{ color: "#2EB39A", fontWeight: 700 }}>🟢 Sí ({connectedEmail || "Conectado"})</span>
              ) : (
                <span style={{ color: "#F5A623", fontWeight: 700 }}>🟡 No conectado</span>
              )}
            </p>
            <p>
              <strong>Correo que se usa para enviar:</strong> {senderDisplay}
            </p>
            {lastSync && (
              <p className="ia-note">Última actualización: {new Date(lastSync).toLocaleString()}</p>
            )}
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">1) Conectar tu Gmail</h2>
          <p style={{ color: "#274472", lineHeight: 1.55 }}>
            Conecta el Gmail que quieres usar para mandar correos a tus clientes.
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
                🔗 Conectar Gmail
              </button>
            ) : (
              <button
                type="button"
                onClick={handleDisconnect}
                className="ia-button"
                style={{ backgroundColor: "#F5A623", color: "#fff" }}
              >
                ❌ Desconectar Gmail
              </button>
            )}
          </div>

          <div className="ia-note">
            Te llevaremos a Google para autorizar y regresarás aquí automáticamente.
          </div>
        </section>

        <section className="ia-card">
          <h2 className="ia-card-title">2) Activar envío con tu Gmail</h2>
          <p style={{ color: "#274472", lineHeight: 1.55 }}>
            Si lo activas, los correos salen desde tu Gmail. Si lo pausas, salen desde el correo automático de Evolvian.
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
                ? "Guardando..."
                : senderEnabled
                ? "Activado (clic para pausar)"
                : "Pausado (clic para activar)"}
            </button>
          </div>

          <p className="ia-note">
            Recomendación: haz primero una prueba de correo de confirmación y una de recordatorio.
          </p>
        </section>

        {!supportsEmail && (
          <section className="ia-card" style={{ marginBottom: 0 }}>
            <h2 className="ia-card-title">🔒 Función Premium</h2>
            <p style={{ color: "#274472", lineHeight: 1.55 }}>
              Esta opción está disponible en plan Premium o White Label.
            </p>
            <button
              type="button"
              className="ia-button ia-button-primary"
              onClick={() => (window.location.href = "/settings#plans")}
            >
              ⬆️ Ver planes
            </button>
          </section>
        )}
      </div>
      {statusModal && (
        <div
          className="ia-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={statusModal.title}
          onClick={() => setStatusModal(null)}
        >
          <div className="ia-modal" onClick={(event) => event.stopPropagation()}>
            <div className="ia-modal-side" aria-hidden="true">
              <div style={{ fontSize: "2rem" }}>{statusModal.icon || "✅"}</div>
            </div>
            <div className="ia-modal-main">
              <h3 className="ia-modal-title">{statusModal.title}</h3>
              <p style={{ margin: 0, color: "#274472" }}>{statusModal.message}</p>
              <p className="ia-modal-muted">{statusModal.note}</p>
              <div className="ia-modal-actions">
                <button type="button" className="ia-button ia-button-warning" onClick={() => setStatusModal(null)}>
                  Entendido
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
