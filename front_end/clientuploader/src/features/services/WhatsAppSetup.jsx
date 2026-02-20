import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabaseClient";
import axios from "axios";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { trackClientEvent } from "../../lib/tracking";
import { getAuthHeaders } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

const API = import.meta.env.VITE_API_URL;

const isValidPhone = (phone) => /^\+\d{11,15}$/.test(phone);
const isValidPhoneId = (id) => /^\d{10,20}$/.test(id);
const isValidToken = (token) => /^EA[A-Za-z0-9]{16,}$/.test(token);
const isValidWabaId = (id) => /^\d{8,24}$/.test(id);

export default function WhatsAppSetup() {
  const { t } = useLanguage();
  const clientId = useClientId();

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [provider, setProvider] = useState("meta");
  const [phone, setPhone] = useState("");
  const [waPhoneId, setWaPhoneId] = useState("");
  const [waToken, setWaToken] = useState("");
  const [waBusinessAccountId, setWaBusinessAccountId] = useState("");

  const [isLocked, setIsLocked] = useState(false);
  const [status, setStatus] = useState({ message: "", type: "" });

  const [touched, setTouched] = useState({
    phone: false,
    waPhoneId: false,
    waToken: false,
    waBusinessAccountId: false,
  });

  useEffect(() => {
    const init = async () => {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session) {
          setLoading(false);
          return;
        }

        setSession(session);

        if (!clientId) {
          setLoading(false);
          return;
        }

        const headers = await getAuthHeaders();
        const res = await axios.get(`${API}/whatsapp_status`, { headers });

        if (res.data.connected) {
          setPhone(res.data.phone || "");
          setWaPhoneId(res.data.wa_phone_id || "");
          setWaBusinessAccountId(res.data.wa_business_account_id || "");
          setProvider(res.data.provider || "meta");
          setIsLocked(true);
        }
      } catch {
        console.log("No WhatsApp config found");
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [clientId]);

  const handleSubmit = async () => {
    if (!session || submitting) return;

    if (!isValidPhone(phone)) {
      setStatus({ message: t("wa_error_phone"), type: "error" });
      return;
    }

    if (!isValidPhoneId(waPhoneId)) {
      setStatus({ message: t("wa_error_phone_id"), type: "error" });
      return;
    }

    if (!isValidToken(waToken)) {
      setStatus({ message: t("wa_error_token"), type: "error" });
      return;
    }

    if (!isValidWabaId(waBusinessAccountId)) {
      setStatus({ message: t("wa_error_waba_id"), type: "error" });
      return;
    }

    try {
      setSubmitting(true);
      setStatus({ message: "", type: "" });

      const headers = await getAuthHeaders();
      await axios.post(
        `${API}/link_whatsapp`,
        {
          email: session.user.email,
          phone,
          provider,
          wa_phone_id: waPhoneId,
          wa_token: waToken,
          wa_business_account_id: waBusinessAccountId || null,
        },
        { headers }
      );

      setIsLocked(true);
      setWaToken("");
      setStatus({ message: t("wa_success"), type: "success" });

      if (clientId) {
        void trackClientEvent({
          clientId,
          name: "Funnel_Channel_Connected",
          category: "funnel",
          label: "whatsapp",
          value: provider,
          eventKey: "funnel_channel_connected:whatsapp",
          metadata: { channel: "whatsapp", provider },
          dedupeLocal: true,
        });
      }
    } catch (err) {
      console.error(err);
      setStatus({ message: t("wa_error_linking"), type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleUnlink = async () => {
    if (!session || submitting) return;
    if (!window.confirm(t("wa_confirm_disconnect"))) return;

    try {
      setSubmitting(true);
      setStatus({ message: "", type: "" });

      const headers = await getAuthHeaders();
      await axios.post(
        `${API}/unlink_whatsapp`,
        {
          auth_user_id: session.user.id,
        },
        { headers }
      );

      setPhone("");
      setWaPhoneId("");
      setWaToken("");
      setWaBusinessAccountId("");
      setIsLocked(false);
      setStatus({ message: t("wa_disconnected"), type: "success" });
    } catch (err) {
      console.error(err);
      setStatus({ message: t("wa_error_unlinking"), type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  const showError = (field, value) => {
    if (!touched[field]) return null;

    if (field === "phone" && !isValidPhone(value)) {
      return <p className="ia-help-error">{t("wa_error_phone")}</p>;
    }

    if (field === "waPhoneId" && !isValidPhoneId(value)) {
      return <p className="ia-help-error">{t("wa_error_phone_id")}</p>;
    }

    if (field === "waToken" && !isValidToken(value)) {
      return <p className="ia-help-error">{t("wa_error_token")}</p>;
    }

    if (field === "waBusinessAccountId" && !isValidWabaId(value)) {
      return <p className="ia-help-error">{t("wa_error_waba_id")}</p>;
    }

    return null;
  };

  if (loading) {
    return (
      <div className="ia-page">
        <div className="ia-loader">
          <div className="ia-spinner" />
          <p style={{ color: "#274472", marginTop: "1rem" }}>{t("loading")}</p>
        </div>
      </div>
    );
  }

  const disableConnect =
    submitting ||
    !isValidPhone(phone) ||
    !isValidPhoneId(waPhoneId) ||
    !isValidToken(waToken) ||
    !isValidWabaId(waBusinessAccountId);

  return (
    <div className="ia-page">
      <div className="ia-shell ia-whatsapp-shell">
        <section className="ia-card" style={{ marginBottom: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: "0.75rem",
              flexWrap: "wrap",
              marginBottom: "1rem",
            }}
          >
            <h2 className="ia-header-title">💬 {t("whatsapp_integration_title")}</h2>
            {isLocked && <span className="ia-badge success">{t("connected")}</span>}
          </div>

          <div className="ia-form-grid">
            <div className="ia-form-field">
              <label className="ia-form-label">{t("wa_choose_provider")}</label>
              <select
                className="ia-form-input"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                disabled={isLocked}
              >
                <option value="meta">{t("meta_official_whatsapp_cloud_api")}</option>
              </select>
            </div>

            <div className="ia-form-field">
              <label className="ia-form-label">{t("wa_label_phone")}</label>
              <input
                className="ia-form-input"
                type="text"
                value={phone}
                placeholder="+5215512345678"
                disabled={isLocked}
                onChange={(e) => setPhone(e.target.value)}
                onBlur={() => setTouched((prev) => ({ ...prev, phone: true }))}
              />
              {showError("phone", phone)}
            </div>

            <div className="ia-form-field">
              <label className="ia-form-label">{t("whatsapp_phone_number_id")}</label>
              <input
                className="ia-form-input"
                type="text"
                value={waPhoneId}
                disabled={isLocked}
                onChange={(e) => setWaPhoneId(e.target.value)}
                onBlur={() => setTouched((prev) => ({ ...prev, waPhoneId: true }))}
              />
              {showError("waPhoneId", waPhoneId)}
            </div>

            <div className="ia-form-field">
              <label className="ia-form-label">{t("whatsapp_business_account_id")}</label>
              <input
                className="ia-form-input"
                type="text"
                value={waBusinessAccountId}
                placeholder={t("wa_placeholder_waba_id")}
                disabled={isLocked}
                onChange={(e) => setWaBusinessAccountId(e.target.value)}
                onBlur={() => setTouched((prev) => ({ ...prev, waBusinessAccountId: true }))}
              />
              {showError("waBusinessAccountId", waBusinessAccountId)}
            </div>

            {!isLocked && (
              <div className="ia-form-field">
                <label className="ia-form-label">{t("permanent_access_token")}</label>
                <input
                  className="ia-form-input"
                  type="password"
                  value={waToken}
                  onChange={(e) => setWaToken(e.target.value)}
                  onBlur={() => setTouched((prev) => ({ ...prev, waToken: true }))}
                />
                {showError("waToken", waToken)}
              </div>
            )}
          </div>

          <div className="ia-note" style={{ marginTop: "0.9rem" }}>
            <strong>{t("wa_data_usage_title")}</strong>
            <ul className="ia-list" style={{ marginTop: "0.35rem" }}>
              <li>{t("wa_data_usage_phone")}</li>
              <li>{t("wa_data_usage_phone_id")}</li>
              <li>{t("wa_data_usage_waba_id")}</li>
              <li>{t("wa_data_usage_token")}</li>
            </ul>
            <p style={{ margin: "0.45rem 0 0" }}>{t("wa_data_usage_security")}</p>
          </div>

          <div className="ia-inline-actions" style={{ marginTop: "1.2rem" }}>
            {!isLocked ? (
              <button
                type="button"
                className="ia-button"
                style={{ backgroundColor: "#2eb39a", color: "#fff", opacity: disableConnect ? 0.6 : 1 }}
                onClick={handleSubmit}
                disabled={disableConnect}
              >
                {submitting ? t("connecting") : t("connect_whatsapp")}
              </button>
            ) : (
              <button
                type="button"
                className="ia-button ia-button-ghost"
                onClick={handleUnlink}
                disabled={submitting}
              >
                {submitting ? t("processing") : t("disconnect_whatsapp")}
              </button>
            )}
          </div>

          {status.message && (
            <p
              className="ia-status-line"
              style={{ color: status.type === "error" ? "#f87171" : "#2eb39a", marginBottom: 0 }}
            >
              {status.message}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
