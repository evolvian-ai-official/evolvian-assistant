import { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";
import { useLanguage } from "../contexts/LanguageContext"; // ✅ Importar idioma

export default function VerifyMfa() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSendOtp = async (e) => {
    e.preventDefault();
    setLoading(true);

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        redirectTo: `${window.location.origin}/dashboard`,
      },
    });

    if (error) {
      toast.error(t("error_sending_login_link"));
    } else {
      toast.success(t("check_your_email_login_link"));
      setSuccess(true);
    }

    setLoading(false);
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <img src="/logo-evolvian.svg" alt="Logo Evolvian" style={{ width: "64px", margin: "0 auto 1rem" }} />
          <h1 style={titleStyle}>{t("access_verification")}</h1>
          <p style={subtitleStyle}>
            {t("confirm_email_to_continue")}
          </p>
        </div>

        {success ? (
          <p style={{ textAlign: "center", color: "#ededed" }}>
            {t("email_link_sent")}
          </p>
        ) : (
          <form onSubmit={handleSendOtp} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <input
              type="email"
              placeholder={t("email")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={inputStyle}
            />

            <button
              type="submit"
              disabled={loading}
              style={{
                ...buttonStyle,
                opacity: loading ? 0.7 : 1,
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              {loading ? t("sending") : t("send_login_link")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

// 🎨 Estilos
const containerStyle = {
  height: "100vh",
  width: "100vw",
  backgroundColor: "#0f1c2e",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "1rem",
  fontFamily: "system-ui, Avenir, Helvetica, Arial, sans-serif",
};

const cardStyle = {
  width: "100%",
  maxWidth: "400px",
  backgroundColor: "#1b2a41",
  borderRadius: "1.5rem",
  padding: "2rem",
  color: "white",
  boxShadow: "0 15px 40px rgba(0,0,0,0.3)",
  border: "1px solid #274472",
};

const titleStyle = {
  fontSize: "1.5rem",
  fontWeight: "bold",
};

const subtitleStyle = {
  fontSize: "0.9rem",
  color: "#ccc",
};

const inputStyle = {
  padding: "0.6rem 1rem",
  background: "transparent",
  border: "1px solid #274472",
  borderRadius: "8px",
  color: "white",
  fontSize: "1rem",
};

const buttonStyle = {
  backgroundColor: "#2eb39a",
  padding: "0.7rem",
  color: "white",
  borderRadius: "8px",
  fontWeight: "bold",
  border: "none",
  fontSize: "1rem",
};
