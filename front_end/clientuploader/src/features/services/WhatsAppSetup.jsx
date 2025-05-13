import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabaseClient";
import axios from "axios";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext"; // ✅ Importar traducción

export default function WhatsAppSetup() {
  const [phone, setPhone] = useState("");
  const [provider, setProvider] = useState("meta");
  const [waPhoneId, setWaPhoneId] = useState("");
  const [waToken, setWaToken] = useState("");
  const [step, setStep] = useState(1);
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState({ message: "", type: "" });
  const clientId = useClientId();
  const { t } = useLanguage(); // ✅ Usar traducción

  const twilioSandbox = "+14155238886";

  useEffect(() => {
    const fetchSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setSession(session);
    };
    fetchSession();
  }, []);

  const handleSubmit = async () => {
    if (!phone || !session) return;

    const payload = {
      auth_user_id: session.user.id,
      email: session.user.email,
      phone,
      provider,
      wa_phone_id: provider === "meta" ? waPhoneId : null,
      wa_token: provider === "meta" ? waToken : null,
    };

    try {
      const res = await axios.post(`${import.meta.env.VITE_API_URL}/link_whatsapp`, payload);
      setStatus({ message: `✅ ${t("whatsapp_linked_success")}`, type: "success" });
      setStep(3);
    } catch (err) {
      console.error(err);
      setStatus({
        message: `❌ ${t("whatsapp_link_error")}`,
        type: "error",
      });
    }
  };

  const handleNext = () => setStep(step + 1);
  const handleBack = () => setStep(step - 1);

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <h2 style={titleStyle}>💬 {t("setup_whatsapp")}</h2>

        {step === 1 && (
          <>
            <p style={paragraphStyle}>
              <strong>{t("step1")}:</strong> {t("save_number_instruction")}
            </p>
            <h3 style={numberStyle}>{twilioSandbox}</h3>
            <p style={paragraphStyle}>
              <strong>{t("step2")}:</strong> {t("send_message_instruction")}
            </p>
            <code style={codeBoxStyle}>join come-science</code>
            <br />
            <button onClick={handleNext} style={btnStyle}>✅ {t("already_done")}</button>
          </>
        )}

        {step === 2 && (
          <>
            <p style={paragraphStyle}>
              <strong>{t("step3")}:</strong> {t("enter_whatsapp_number")}
            </p>

            <select value={provider} onChange={(e) => setProvider(e.target.value)} style={inputStyle}>
              <option value="meta">Meta Cloud API</option>
              <option value="twilio">Twilio</option>
            </select>

            <input
              type="text"
              placeholder="+52XXXXXXXXXX"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              style={inputStyle}
            />

            {provider === "meta" && (
              <>
                <input
                  type="text"
                  placeholder="Meta phone_number_id"
                  value={waPhoneId}
                  onChange={(e) => setWaPhoneId(e.target.value)}
                  style={inputStyle}
                />
                <input
                  type="text"
                  placeholder="Meta access_token"
                  value={waToken}
                  onChange={(e) => setWaToken(e.target.value)}
                  style={inputStyle}
                />
              </>
            )}

            <div style={{ display: "flex", gap: "1rem" }}>
              <button
                onClick={handleSubmit}
                disabled={!phone || (provider === "meta" && (!waPhoneId || !waToken))}
                style={{
                  ...btnStyle,
                  opacity: phone ? 1 : 0.5,
                  cursor: phone ? "pointer" : "not-allowed",
                }}
              >
                📲 {t("link_number")}
              </button>
              <button onClick={handleBack} style={backBtnStyle}>🔙 {t("back")}</button>
            </div>
            {status.message && (
              <p style={{
                marginTop: "1rem",
                fontWeight: "bold",
                color: status.type === "error" ? "#f87171" : "#a3d9b1",
              }}>
                {status.message}
              </p>
            )}
          </>
        )}

        {step === 3 && (
          <>
            <p style={paragraphStyle}>🎉 {t("number_linked_success")}</p>
            <p style={linkedNumberStyle}>{phone}</p>
            <p style={noteStyle}>{t("start_chatting_instruction")}</p>
            <a
              href={`https://wa.me/${phone.replace("+", "")}?text=Hola,%20quiero%20probar%20mi%20asistente%20Evolvian`}
              target="_blank"
              rel="noopener noreferrer"
              style={linkButtonStyle}
            >
              🔁 {t("test_assistant")}
            </a>
            <button
              onClick={() => setStep(2)}
              style={{ ...backBtnStyle, marginTop: "1.5rem" }}
            >
              ✏️ {t("change_number")}
            </button>
          </>
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
  marginBottom: "2rem",
};

const paragraphStyle = {
  marginBottom: "1rem",
};

const numberStyle = {
  fontSize: "1.25rem",
  fontWeight: "bold",
  color: "#a3d9b1",
  marginBottom: "1rem",
};

const codeBoxStyle = {
  backgroundColor: "#ededed",
  color: "#274472",
  padding: "0.5rem 1rem",
  borderRadius: "8px",
  display: "inline-block",
  marginBottom: "1.5rem",
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem",
  borderRadius: "8px",
  border: "1px solid #4a90e2",
  marginBottom: "1.5rem",
  backgroundColor: "#0f1c2e",
  color: "white",
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

const backBtnStyle = {
  backgroundColor: "#ededed",
  color: "#1b2a41",
  padding: "0.7rem 1.2rem",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  cursor: "pointer",
};

const linkedNumberStyle = {
  fontWeight: "bold",
  color: "#a3d9b1",
};

const noteStyle = {
  fontSize: "0.85rem",
  color: "#ededed",
  marginTop: "0.75rem",
};

const linkButtonStyle = {
  marginTop: "1.5rem",
  display: "inline-block",
  backgroundColor: "#2eb39a",
  color: "white",
  padding: "0.7rem 1.2rem",
  borderRadius: "8px",
  fontWeight: "bold",
  textDecoration: "none",
  marginRight: "1rem",
};
