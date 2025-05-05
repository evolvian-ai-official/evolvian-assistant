import { useState, useEffect } from "react";
import { supabase } from "../../lib/supabaseClient";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext"; // ✅ Importar traducción

export default function EmailSetup() {
  const [email, setEmail] = useState("");
  const [saved, setSaved] = useState(false);
  const clientId = useClientId();
  const { t } = useLanguage(); // ✅ Usar traducción

  useEffect(() => {
    const fetchEmail = async () => {
      if (!clientId) return;
      const { data } = await supabase
        .from("clients")
        .select("email_forward")
        .eq("id", clientId)
        .single();

      if (data?.email_forward) setEmail(data.email_forward);
    };

    fetchEmail();
  }, [clientId]);

  const handleSave = async () => {
    if (!clientId || !email) return;

    const { error } = await supabase
      .from("clients")
      .update({ email_forward: email })
      .eq("id", clientId);

    if (!error) setSaved(true);
  };

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <h2 style={titleStyle}>
          ✉️ {t("setup_email_assistant")}
        </h2>

        <p style={paragraphStyle}>
          {t("email_instructions_intro")}
        </p>

        <code style={codeBoxStyle}>
          contacto@tudominio.com → evolvian@correo.evolvian.app
        </code>

        <p style={paragraphStyle}>
          {t("save_email_instruction")}
        </p>

        <input
          type="email"
          placeholder={t("email_placeholder")}
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setSaved(false);
          }}
          style={inputStyle}
        />

        <button
          onClick={handleSave}
          style={buttonStyle}
        >
          {t("save_address")}
        </button>

        {saved && (
          <p style={{ color: "#a3d9b1", fontSize: "0.95rem" }}>
            ✅ {t("address_saved")}
          </p>
        )}

        <div style={{ marginTop: "2rem", fontSize: "0.9rem", color: "#ededed" }}>
          <p><strong>{t("how_it_works")}</strong></p>
          <ul style={ulStyle}>
            <li>1️⃣ {t("step1")}</li>
            <li>2️⃣ {t("step2")}</li>
            <li>3️⃣ {t("step3")}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

// 🎨 Estilos
const pageStyle = {
  backgroundColor: "#0f1c2e",
  minHeight: "100vh",
  padding: "2rem",
  fontFamily: "system-ui, sans-serif",
  color: "white",
  display: "flex",
  justifyContent: "center"
};

const cardStyle = {
  backgroundColor: "#1b2a41",
  padding: "2rem",
  borderRadius: "16px",
  maxWidth: "600px",
  width: "100%",
  boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
  border: "1px solid #274472"
};

const titleStyle = {
  fontSize: "1.8rem",
  fontWeight: "bold",
  color: "#f5a623",
  marginBottom: "1.5rem"
};

const paragraphStyle = {
  marginBottom: "1rem"
};

const codeBoxStyle = {
  backgroundColor: "#ededed",
  color: "#274472",
  padding: "0.6rem 1rem",
  borderRadius: "8px",
  display: "block",
  marginBottom: "1.5rem"
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem",
  borderRadius: "8px",
  border: "1px solid #4a90e2",
  marginBottom: "1rem",
  backgroundColor: "#0f1c2e",
  color: "white"
};

const buttonStyle = {
  backgroundColor: "#4a90e2",
  color: "white",
  padding: "0.7rem 1.2rem",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  cursor: "pointer",
  marginBottom: "1rem"
};

const ulStyle = {
  marginTop: "0.5rem",
  paddingLeft: "1.2rem",
  lineHeight: "1.7"
};
