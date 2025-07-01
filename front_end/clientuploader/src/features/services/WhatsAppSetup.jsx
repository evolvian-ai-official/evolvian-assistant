import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabaseClient";
import axios from "axios";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";

const isValidPhone = (phone) => /^\+\d{11,15}$/.test(phone);
const isValidPhoneId = (id) => /^\d{10,20}$/.test(id);
const isValidToken = (token) => /^EA[A-Za-z0-9]{16,}$/.test(token);

export default function WhatsAppSetup() {
  const { t } = useLanguage();
  const [provider, setProvider] = useState("meta");
  const [phone, setPhone] = useState("");
  const [waPhoneId, setWaPhoneId] = useState("");
  const [waToken, setWaToken] = useState("");
  const [touched, setTouched] = useState({ phone: false, waPhoneId: false, waToken: false });
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState({ message: "", type: "" });
  const [isLocked, setIsLocked] = useState(false);
  const clientId = useClientId();

  useEffect(() => {
    const fetchSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setSession(session);
    };

    const fetchConfig = async () => {
      try {
        const res = await axios.get(`${import.meta.env.VITE_API_URL}/get_whatsapp_config`, {
          params: { client_id: clientId },
        });

        const { phone, wa_phone_id, wa_token, provider } = res.data || {};
        if (phone) setPhone(phone);
        if (wa_phone_id) setWaPhoneId(wa_phone_id);
        if (wa_token) setWaToken(wa_token);
        if (provider === "meta" || provider === "twilio") {
          setProvider(provider);
        } else {
          setProvider("meta");
        }
        if (phone && (provider === "twilio" || (wa_phone_id && wa_token))) {
          setIsLocked(true);
        }
      } catch (err) {
        console.log("ℹ️ No config found or failed to fetch:", err);
      }
    };

    fetchSession();
    fetchConfig();
  }, [clientId]);

  const handleSubmit = async () => {
    if (!session || !isValidPhone(phone)) return;
    if (provider === "meta" && (!isValidPhoneId(waPhoneId) || !isValidToken(waToken))) return;

    const payload = {
      auth_user_id: session.user.id,
      email: session.user.email,
      phone,
      provider,
      wa_phone_id: provider === "meta" ? waPhoneId : null,
      wa_token: provider === "meta" ? waToken : null,
    };

    try {
      await axios.post(`${import.meta.env.VITE_API_URL}/link_whatsapp`, payload);
      setStatus({ message: t("wa_success"), type: "success" });
      setIsLocked(true);
    } catch (err) {
      console.error(err);
      setStatus({ message: t("wa_error_linking"), type: "error" });
    }
  };

  const showError = (field, value) =>
    touched[field] && (
      <p style={errorStyle}>
        {field === "phone" && !isValidPhone(value) && t("wa_error_phone")}
        {field === "waPhoneId" && !isValidPhoneId(value) && t("wa_error_phone_id")}
        {field === "waToken" && !isValidToken(value) && t("wa_error_token")}
      </p>
    );

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div style={headerStyle}>
          <h2 style={titleStyle}>💬 {t("wa_setup_title")}</h2>
        </div>

        {/* Provider */}
        <div style={fieldGroup}>
          <label style={labelStyle}>{t("wa_choose_provider")}</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            disabled={isLocked}
            style={{
              ...inputStyle,
              backgroundColor: isLocked ? "#1b2a41" : "#0f1c2e",
              color: isLocked ? "#aaa" : "white",
              cursor: isLocked ? "not-allowed" : "pointer",
              fontWeight: "bold",
              border: "1px solid #4a90e2",
              appearance: "none",
              backgroundImage: `url("data:image/svg+xml;utf8,<svg fill='white' height='24' viewBox='0 0 24 24' width='24' xmlns='http://www.w3.org/2000/svg'><path d='M7 10l5 5 5-5z'/></svg>")`,
              backgroundRepeat: "no-repeat",
              backgroundPosition: "right 0.75rem center",
              paddingRight: "2rem",
              marginBottom: "1.5rem",
            }}
          >
            <option value="meta">{t("wa_provider_meta")}</option>
            <option value="twilio">{t("wa_provider_twilio")}</option>
          </select>
        </div>

        {/* Phone */}
        <div style={fieldGroup}>
          <label style={labelStyle}>{t("wa_label_phone")}</label>
          <input
            type="text"
            placeholder="+52XXXXXXXXXXXX"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            onBlur={() => setTouched((prev) => ({ ...prev, phone: true }))}
            disabled={isLocked}
            style={inputStyle}
          />
          {showError("phone", phone)}
        </div>

        {/* Meta Fields only */}
        {provider === "meta" && (
          <>
            <div style={fieldGroup}>
              <input
                type="text"
                placeholder={t("wa_placeholder_phone_id")}
                value={waPhoneId}
                onChange={(e) => setWaPhoneId(e.target.value)}
                onBlur={() => setTouched((prev) => ({ ...prev, waPhoneId: true }))}
                disabled={isLocked}
                style={inputStyle}
              />
              {showError("waPhoneId", waPhoneId)}
            </div>

            <div style={fieldGroup}>
              <input
                type="text"
                placeholder={t("wa_placeholder_token")}
                value={waToken}
                onChange={(e) => setWaToken(e.target.value)}
                onBlur={() => setTouched((prev) => ({ ...prev, waToken: true }))}
                disabled={isLocked}
                style={inputStyle}
              />
              {showError("waToken", waToken)}
            </div>
          </>
        )}

        {/* Submit */}
        {!isLocked && (
          <div style={{ display: "flex", gap: "1rem" }}>
            <button
              onClick={handleSubmit}
              disabled={
                !isValidPhone(phone) ||
                (provider === "meta" && (!isValidPhoneId(waPhoneId) || !isValidToken(waToken)))
              }
              style={{
                ...btnStyle,
                opacity:
                  isValidPhone(phone) &&
                  (provider === "twilio" || (isValidPhoneId(waPhoneId) && isValidToken(waToken)))
                    ? 1
                    : 0.5,
                cursor:
                  isValidPhone(phone) &&
                  (provider === "twilio" || (isValidPhoneId(waPhoneId) && isValidToken(waToken)))
                    ? "pointer"
                    : "not-allowed",
              }}
            >
              📲 {t("wa_button_link")}
            </button>
            <button
              onClick={() => window.history.back()}
              style={{
                ...btnStyle,
                backgroundColor: "#ededed",
                color: "#1b2a41",
              }}
            >
              ⬅️ {t("wa_button_back")}
            </button>
          </div>
        )}

        {/* Status */}
        {status.message && (
          <p style={{
            marginTop: "1rem",
            fontWeight: "bold",
            color: status.type === "error" ? "#f87171" : "#a3d9b1",
          }}>
            {status.message}
          </p>
        )}
      </div>
    </div>
  );
}

// 🎨 Estilos
const pageStyle = {
  padding: "2rem",
  fontFamily: "system-ui, sans-serif",
  backgroundColor: "#0f1c2e",
  color: "white",
  minHeight: "100vh",
  display: "flex",
  justifyContent: "center",
};

const cardStyle = {
  backgroundColor: "#1b2a41",
  padding: "2rem",
  borderRadius: "16px",
  maxWidth: "600px",
  width: "100%",
  boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
  border: "1px solid #274472",
};

const titleStyle = {
  fontSize: "1.8rem",
  fontWeight: "bold",
  color: "#f5a623",
  margin: 0,
};

const labelStyle = {
  fontWeight: 600,
  fontSize: "0.95rem",
  color: "#ededed",
  marginBottom: "0.25rem",
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem",
  borderRadius: "8px",
  border: "1px solid #4a90e2",
  marginBottom: "0.5rem",
  backgroundColor: "#0f1c2e",
  color: "white",
};

const helperStyle = {
  fontSize: "0.8rem",
  color: "#a3a3a3",
  marginBottom: "1.5rem",
};

const errorStyle = {
  fontSize: "0.8rem",
  color: "#f87171",
  marginTop: "-0.5rem",
  marginBottom: "1rem",
};

const fieldGroup = {
  marginBottom: "1.5rem",
};

const btnStyle = {
  backgroundColor: "#4a90e2",
  color: "white",
  padding: "0.7rem 1.2rem",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  cursor: "pointer",
};

const headerStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "2rem",
};
