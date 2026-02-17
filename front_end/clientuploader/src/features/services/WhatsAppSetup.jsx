import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabaseClient";
import axios from "axios";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";

const API = import.meta.env.VITE_API_URL;

/* =========================
   VALIDATIONS
========================= */

const isValidPhone = (phone) => /^\+\d{11,15}$/.test(phone);
const isValidPhoneId = (id) => /^\d{10,20}$/.test(id);
const isValidToken = (token) => /^EA[A-Za-z0-9]{16,}$/.test(token);

/* =========================
   COMPONENT
========================= */

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

  const [isLocked, setIsLocked] = useState(false);
  const [status, setStatus] = useState({ message: "", type: "" });

  const [touched, setTouched] = useState({
    phone: false,
    waPhoneId: false,
    waToken: false,
  });

  /* ==========================
     INIT
  ========================== */

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

        const res = await axios.get(`${API}/whatsapp_status`, {
          params: { auth_user_id: session.user.id },
        });

        if (res.data.connected) {
          setPhone(res.data.phone || "");
          setWaPhoneId(res.data.wa_phone_id || "");
          setProvider(res.data.provider || "meta");
          setIsLocked(true);
        }

      } catch (err) {
        console.log("No WhatsApp config found");
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [clientId]);

  /* ==========================
     CONNECT
  ========================== */

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

    try {
      setSubmitting(true);
      setStatus({ message: "", type: "" });

      await axios.post(`${API}/link_whatsapp`, {
        auth_user_id: session.user.id,
        email: session.user.email,
        phone,
        provider,
        wa_phone_id: waPhoneId,
        wa_token: waToken,
      });

      setIsLocked(true);
      setWaToken("");

      setStatus({ message: t("wa_success"), type: "success" });

    } catch (err) {
      console.error(err);
      setStatus({ message: t("wa_error_linking"), type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  /* ==========================
     DISCONNECT
  ========================== */

  const handleUnlink = async () => {
    if (!session || submitting) return;

    if (!window.confirm(t("wa_confirm_disconnect"))) return;

    try {
      setSubmitting(true);
      setStatus({ message: "", type: "" });

      await axios.post(`${API}/unlink_whatsapp`, {
        auth_user_id: session.user.id,
      });

      setPhone("");
      setWaPhoneId("");
      setWaToken("");
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
      return <p style={errorStyle}>{t("wa_error_phone")}</p>;
    }

    if (field === "waPhoneId" && !isValidPhoneId(value)) {
      return <p style={errorStyle}>{t("wa_error_phone_id")}</p>;
    }

    if (field === "waToken" && !isValidToken(value)) {
      return <p style={errorStyle}>{t("wa_error_token")}</p>;
    }

    return null;
  };

  if (loading) {
    return <div style={pageStyle}>{t("loading")}</div>;
  }

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>

        <div style={headerStyle}>
          <h2 style={titleStyle}>{t("whatsapp_integration_title")}</h2>
          {isLocked && <span style={badgeStyle}>{t("connected")}</span>}
        </div>

        {/* Provider */}
        <div style={fieldGroup}>
          <label style={labelStyle}>{t("wa_choose_provider")}</label>
          <select
            style={inputStyle}
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            disabled={isLocked}
          >
            <option value="meta">
              {t("meta_official_whatsapp_cloud_api")}
            </option>
          </select>
        </div>

        {/* Phone */}
        <div style={fieldGroup}>
          <label style={labelStyle}>{t("wa_label_phone")}</label>
          <input
            style={inputStyle}
            type="text"
            value={phone}
            placeholder="+5215512345678"
            disabled={isLocked}
            onChange={(e) => setPhone(e.target.value)}
            onBlur={() =>
              setTouched((prev) => ({ ...prev, phone: true }))
            }
          />
          {showError("phone", phone)}
        </div>

        {/* Phone ID */}
        <div style={fieldGroup}>
          <label style={labelStyle}>{t("whatsapp_phone_number_id")}</label>
          <input
            style={inputStyle}
            type="text"
            value={waPhoneId}
            disabled={isLocked}
            onChange={(e) => setWaPhoneId(e.target.value)}
            onBlur={() =>
              setTouched((prev) => ({ ...prev, waPhoneId: true }))
            }
          />
          {showError("waPhoneId", waPhoneId)}
        </div>

        {/* Token */}
        {!isLocked && (
          <div style={fieldGroup}>
            <label style={labelStyle}>{t("permanent_access_token")}</label>
            <input
              style={inputStyle}
              type="password"
              value={waToken}
              onChange={(e) => setWaToken(e.target.value)}
              onBlur={() =>
                setTouched((prev) => ({ ...prev, waToken: true }))
              }
            />
            {showError("waToken", waToken)}
          </div>
        )}

        {/* Actions */}
        <div style={{ marginTop: "1.5rem" }}>
          {!isLocked ? (
            <button
              style={{
                ...primaryBtn,
                opacity:
                  submitting ||
                  !isValidPhone(phone) ||
                  !isValidPhoneId(waPhoneId) ||
                  !isValidToken(waToken)
                    ? 0.6
                    : 1,
              }}
              onClick={handleSubmit}
              disabled={
                submitting ||
                !isValidPhone(phone) ||
                !isValidPhoneId(waPhoneId) ||
                !isValidToken(waToken)
              }
            >
              {submitting ? t("connecting") : t("connect_whatsapp")}
            </button>
          ) : (
            <button
              style={secondaryBtn}
              onClick={handleUnlink}
              disabled={submitting}
            >
              {submitting ? t("processing") : t("disconnect_whatsapp")}
            </button>
          )}
        </div>

        {status.message && (
          <p
            style={{
              marginTop: "1.2rem",
              color:
                status.type === "error" ? "#f87171" : "#2eb39a",
              fontSize: "0.9rem",
            }}
          >
            {status.message}
          </p>
        )}
      </div>
    </div>
  );
}

/* =========================
   EVOLVIAN LIGHT STYLES
========================= */

const pageStyle = {
  backgroundColor: "#0f1c2e",
  minHeight: "100vh",
  display: "flex",
  justifyContent: "center",
  padding: "3rem 1rem",
  fontFamily: "system-ui, sans-serif",
  color: "white",
};

const cardStyle = {
  backgroundColor: "#1b2a41",
  padding: "2.5rem",
  borderRadius: "20px",
  width: "100%",
  maxWidth: "640px",
  border: "1px solid #274472",
  boxShadow: "0 20px 40px rgba(0,0,0,0.35)",
};

const headerStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "2rem",
};

const titleStyle = {
  fontSize: "1.6rem",
  fontWeight: "bold",
  color: "#f5a623",
};

const badgeStyle = {
  backgroundColor: "#274472",
  padding: "0.3rem 0.8rem",
  borderRadius: "999px",
  fontSize: "0.75rem",
  color: "#a3d9b1",
};

const labelStyle = {
  fontSize: "0.9rem",
  marginBottom: "0.3rem",
  color: "#ededed",
  fontWeight: 500,
};

const inputStyle = {
  width: "100%",
  padding: "0.7rem",
  borderRadius: "10px",
  border: "1px solid #4a90e2",
  backgroundColor: "#0f1c2e",
  color: "white",
};

const errorStyle = {
  fontSize: "0.8rem",
  color: "#f87171",
  marginTop: "0.4rem",
};

const fieldGroup = {
  marginBottom: "1.8rem",
};

const primaryBtn = {
  backgroundColor: "#2eb39a",
  color: "white",
  padding: "0.8rem 1.5rem",
  borderRadius: "10px",
  border: "none",
  fontWeight: "bold",
  cursor: "pointer",
};

const secondaryBtn = {
  backgroundColor: "#ededed",
  color: "#1b2a41",
  padding: "0.8rem 1.5rem",
  borderRadius: "10px",
  border: "none",
  fontWeight: "bold",
  cursor: "pointer",
};
