// 💾 Evolvian WidgetConsentScreen — versión final con validación estricta de email
import { useState, useEffect } from "react";
import ChatWidget from "./ChatWidget";

export default function WidgetConsentScreen({
  publicClientId,
  requireEmailConsent = false,
  requireTermsConsent = false,
  showLegalLinks = false,
  clientSettings = {},
}) {
  // ==========================
  // 🔧 Estado interno
  // ==========================
  const [email, setEmail] = useState("");
  const [emailValid, setEmailValid] = useState(false);
  const [phone, setPhone] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [acceptedEmailMarketing, setAcceptedEmailMarketing] = useState(false);
  const [consentGiven, setConsentGiven] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // ==========================
  // 🎨 Custom colors
  // ==========================
  const bg = clientSettings.consent_bg_color || "#FFF8E6";
  const color = clientSettings.consent_text_color || "#7A4F00";

  // ==========================
  // 🧼 Normalizar valores
  // ==========================
  const normalize = (v) => {
    if (v === undefined || v === null) return null;
    if (typeof v === "string" && v.trim() === "") return null;
    return v;
  };

  // ==========================
  // 🧭 Email validation rule
  // ==========================
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  useEffect(() => {
    if (!requireEmailConsent) return setEmailValid(true);
    setEmailValid(emailRegex.test(email.trim()));
  }, [email, requireEmailConsent]);

  // ==========================
  // 🚀 Auto-skip si no se requiere consentimiento
  // ==========================
  useEffect(() => {
    const requiresConsent =
      requireEmailConsent ||
      requireTermsConsent ||
      clientSettings.require_phone_consent;

    if (!requiresConsent) {
      setConsentGiven(true);
    }
  }, [
    requireEmailConsent,
    requireTermsConsent,
    clientSettings.require_phone_consent,
  ]);

  // ==========================
  // 💾 Registrar consentimiento
  // ==========================
  const handleSubmit = async () => {
    setErrorMsg("");

    if (requireEmailConsent && !emailValid) {
      return setErrorMsg("Please enter a valid email address.");
    }

    if (requireTermsConsent && !acceptedTerms) {
      return setErrorMsg("Please accept the terms to continue.");
    }

    setLoading(true);

    try {
      const apiUrl =
        window.location.hostname === "localhost"
          ? "http://localhost:8001"
          : "https://evolvian-assistant.onrender.com";

      const payload = {
        public_client_id: publicClientId,
        email: normalize(email),
        phone: normalize(phone),
        accepted_terms: !!acceptedTerms,
        accepted_email_marketing: acceptedEmailMarketing,
        user_agent: navigator.userAgent || "unknown",
      };

      const res = await fetch(`${apiUrl}/register_consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      await res.json();
      setConsentGiven(true);
    } catch (err) {
      setErrorMsg("Error saving your consent. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ==========================
  // 💬 Mostrar Chat después del consentimiento
  // ==========================
  if (consentGiven) {
    return <ChatWidget clientId={publicClientId} />;
  }

  // ==========================
  // 🧾 Pantalla de consentimiento
  // ==========================
  return (
    <div
      style={{
        backgroundColor: bg,
        color: color,
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "1.5rem",
        textAlign: "center",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <h3>Before we start...</h3>

      {requireEmailConsent && (
        <>
          <p
            style={{ marginBottom: "1rem", maxWidth: "320px", fontSize: "0.9rem" }}
          >
            Please provide your email before we continue.
          </p>

          {/* Email input */}
          <input
            type="email"
            placeholder="Your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{
              padding: "0.5rem",
              borderRadius: "8px",
              border: emailValid ? "1px solid #ccc" : "1px solid red",
              marginBottom: "0.3rem",
              width: "260px",
            }}
          />

          {!emailValid && email.trim() !== "" && (
            <p style={{ color: "red", fontSize: "0.75rem", marginBottom: "1rem" }}>
              Please enter a valid email address.
            </p>
          )}

          {/* Leyenda explicativa */}
          <p
            style={{
              fontSize: "0.75rem",
              color: "#666",
              marginBottom: "1rem",
              maxWidth: "260px",
              lineHeight: "1.2",
            }}
          >
            We collect your email to be used internally.
            It will <strong>not</strong> be shared with anyone.
          </p>

          {/* Checkbox de marketing */}
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              marginBottom: "1rem",
              fontSize: "0.85rem",
            }}
          >
            <input
              type="checkbox"
              checked={acceptedEmailMarketing}
              onChange={(e) => setAcceptedEmailMarketing(e.target.checked)}
            />
            <span>I agree to receive occasional emails with updates and news.</span>
          </label>
        </>
      )}

      {clientSettings.require_phone_consent && (
        <input
          type="tel"
          placeholder="Your phone (optional)"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          style={{
            padding: "0.5rem",
            borderRadius: "8px",
            border: "1px solid #ccc",
            marginBottom: "0.75rem",
            width: "260px",
          }}
        />
      )}

      {requireTermsConsent && (
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            marginBottom: "1rem",
          }}
        >
          <input
            type="checkbox"
            checked={acceptedTerms}
            onChange={(e) => setAcceptedTerms(e.target.checked)}
          />
          <span>
            I accept the{" "}
            <a
              href={clientSettings.terms_url}
              target="_blank"
              rel="noopener"
              style={{ color, textDecoration: "underline" }}
            >
              Terms & Conditions
            </a>
          </span>
        </label>
      )}

      {errorMsg && (
        <p style={{ color: "red", marginBottom: "0.5rem" }}>⚠️ {errorMsg}</p>
      )}

      {/* Continue button */}
      <button
        onClick={handleSubmit}
        disabled={
          loading ||
          (requireEmailConsent && !emailValid) ||
          (requireTermsConsent && !acceptedTerms)
        }
        style={{
          backgroundColor:
            loading ||
            (requireEmailConsent && !emailValid) ||
            (requireTermsConsent && !acceptedTerms)
              ? "#999"
              : color,
          color: bg,
          border: "none",
          borderRadius: "8px",
          padding: "0.6rem 1.2rem",
          fontWeight: "600",
          cursor:
            loading ||
            (requireEmailConsent && !emailValid) ||
            (requireTermsConsent && !acceptedTerms)
              ? "not-allowed"
              : "pointer",
        }}
      >
        {loading ? "Saving..." : "Continue"}
      </button>
    </div>
  );
}
