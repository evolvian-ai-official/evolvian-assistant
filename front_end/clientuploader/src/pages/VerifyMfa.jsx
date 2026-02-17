import { useState, useEffect } from "react";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";
import { useLanguage } from "../contexts/LanguageContext";

export default function VerifyMfa() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [animateLogo, setAnimateLogo] = useState(false);

  useEffect(() => {
    setTimeout(() => setAnimateLogo(true), 100);

    if (!document.getElementById("pulseGlow")) {
      const style = document.createElement("style");
      style.id = "pulseGlow";
      style.textContent = `
        @keyframes pulseGlow {
          0%, 100% { box-shadow: 0 0 15px rgba(74,144,226,0.4); }
          50% { box-shadow: 0 0 25px rgba(163,217,177,0.7); }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

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
        {/* 🔹 Logo circular degradado con animación */}
        <div style={logoWrapper}>
          <div
            style={{
              ...logoCircle,
              transform: animateLogo ? "rotate(360deg)" : "rotate(0deg)",
              transition: "transform 1s ease-in-out",
              animation: "pulseGlow 4s ease-in-out infinite",
            }}
          >
            <img src="/logo-evolvian.svg" alt="Evolvian Logo" style={logoFull} />
          </div>
        </div>

        <h1 style={titleStyle}>{t("access_verification")}</h1>
        <p style={subtitleStyle}>{t("confirm_email_to_continue")}</p>

        {success ? (
          <p style={successTextStyle}>{t("email_link_sent")}</p>
        ) : (
          <form
            onSubmit={handleSendOtp}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "1rem",
              marginTop: "1.5rem",
            }}
          >
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

/* 🎨 Estilos Evolvian */
const containerStyle = {
  height: "100vh",
  width: "100vw",
  backgroundColor: "#f9fafb",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "Inter, system-ui, sans-serif",
};

const cardStyle = {
  width: "100%",
  maxWidth: "400px",
  backgroundColor: "#ffffff",
  borderRadius: "20px",
  padding: "2.5rem 2rem",
  boxShadow: "0 8px 40px rgba(39,68,114,0.1)",
  textAlign: "center",
  border: "1px solid #e5e7eb",
};

const logoWrapper = {
  display: "flex",
  justifyContent: "center",
  marginBottom: "1.2rem",
};

const logoCircle = {
  width: "80px",
  height: "80px",
  borderRadius: "50%",
  background: "radial-gradient(circle, #a3d9b1 0%, #4a90e2 100%)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  overflow: "hidden",
};

const logoFull = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
};

const titleStyle = {
  fontSize: "1.6rem",
  fontWeight: "700",
  color: "#274472",
  marginBottom: "0.5rem",
};

const subtitleStyle = {
  fontSize: "0.95rem",
  color: "#6b7280",
  marginBottom: "1rem",
};

const inputStyle = {
  width: "100%",
  padding: "0.6rem 1rem",
  backgroundColor: "#f9fafb",
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  color: "#1b2a41",
  fontSize: "1rem",
};

const buttonStyle = {
  backgroundColor: "#4a90e2",
  padding: "0.8rem",
  color: "white",
  borderRadius: "8px",
  fontWeight: "600",
  border: "none",
  cursor: "pointer",
  fontSize: "1rem",
  transition: "background 0.3s ease",
};

const successTextStyle = {
  color: "#4a90e2",
  fontSize: "0.95rem",
  fontWeight: "500",
  marginTop: "1rem",
};
